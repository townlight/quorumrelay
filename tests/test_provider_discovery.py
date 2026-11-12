"""Deterministic provider contracts. No sockets, accounts, or live vendor writes."""

import base64
import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from civic_data_connectors import Bounds, Engine, OperationContext, Source
from civic_data_connectors import providers
from civic_data_connectors.engine import source_identity_key
from civic_data_connectors.providers.contracts import Response

FIXTURES = Path(__file__).parent / "fixtures"
BRIEF = FIXTURES / "brief-discovery"
BASELINE = FIXTURES / "baseline"
CASES = json.loads((BASELINE / "cases.json").read_text())


class FakeTransport:
    def __init__(self, callback):
        self.callback = callback
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.callback(url, kwargs, len(self.calls))
        if isinstance(value, Exception):
            raise value
        if isinstance(value, Response):
            return value
        if isinstance(value, bytes):
            return Response(url, value)
        return Response(url, json.dumps(value).encode(), "application/json")


def make_engine(callback=None):
    engine = Engine()
    transport = FakeTransport(callback or (lambda *args: AssertionError("No network permitted")))
    providers.register(engine, transport=transport)
    return engine, transport


def request(provider, url, **kwargs):
    return {"source": {"provider": provider, "url": url, **kwargs},
            "bounds": {"date_from": "2026-11-01", "date_to": "2026-11-11"}}


def clerk(identity, day="2026-11-10", body="Council"):
    return {"id": identity, "eventName": f"{body} meeting", "categoryName": body,
            "startDateTime": f"{day}T19:00:00Z", "isPublished": "Published",
            "publishedFiles": []}


def event(identity, day="2026-11-10"):
    return {"EventId": identity, "EventBodyName": "Council", "EventDate": f"{day}T00:00:00",
            "EventTime": "7:00 PM", "EventRowVersion": f"r{identity}",
            "unknown": [None, False, 0, "", {"non_ascii": "café"}]}


@pytest.mark.parametrize("provider,fmt,url,content", [
    ("legistar", "legistar-events-json", "https://webapi.legistar.com/v1/city",
     json.dumps([event(1)]).encode()),
    ("wistia", "wistia-api-media-json", "https://api.wistia.com/modern/medias",
     b'[{"hashed_id":"media1","name":"Council","created":"2026-11-10T12:00:00Z"}]'),
    *[(provider, "granicus-listing-html", "https://city.granicus.com/ViewPublisher.php?view_id=1",
       b'<table><tr><td headers="Name">Council</td>'
       b'<td headers="Date"><span>1794355200</span>Nov. 11, 2026 - 7:00 PM</td></tr></table>')
      for provider in ("granicus", "peak")],
])
def test_native_saved_direct_normalize_execute_and_base64_parity(provider, fmt, url, content):
    engine, transport = make_engine()
    source = Source(provider, url, input_format=fmt)
    direct = engine.normalize(source, content, input_format=fmt)
    dispatched = engine.execute("normalize", {"source": source.public_dict()}, content=content)
    encoded = engine.execute("normalize", {"source": source.public_dict(),
                                          "content_base64": base64.b64encode(content).decode()})
    for result in (direct, dispatched, encoded):
        assert result.status == "completed", result.public_dict()
        assert result.data["capture"]["content_base64"] == base64.b64encode(content).decode()
        assert result.data["records"][0]["normalized"] == direct.data["records"][0]["normalized"]
        assert result.data["records"][0]["original"] == direct.data["records"][0]["original"]
        assert not result.coverage["catalog_complete"]
    assert transport.calls == []
    bounded = engine.normalize(source, content, input_format=fmt, bounds=Bounds(parser_bytes=1))
    assert bounded.status == "failed"
    denied = engine.normalize(source, content, input_format=fmt,
                              context=OperationContext(allowed_namespaces=frozenset({"other"})))
    assert denied.status == "failed"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["connector"] + "/" + case["input_format"])
def test_all_34_saved_format_discovery_paths(case):
    engine, transport = make_engine()
    req = {"source": {"provider": case["connector"], "url": case["source_url"],
                      "input_format": case["input_format"]}, "bounds": {"max_records": 10000}}
    result = engine.execute("discover", req, content=(BASELINE / case["file"]).read_bytes())
    assert result.status == "partial", result.public_dict()
    assert result.data["records"]
    assert "saved capture" in result.coverage["scope"]
    assert result.coverage["checkpoint"] is None
    assert len(result.data["captures"]) == 1
    assert transport.calls == []


def test_roster_identity_ambiguity_custom_domains_and_mismatch():
    engine, _ = make_engine()
    assert len(providers.FORMATS) == 31
    result = engine.execute("identify", {"url": "https://city.granicus.com/ViewPublisher.php?view_id=1"})
    assert result.data["ambiguous"]
    assert result.data["candidates"] == ["granicus", "peak"]
    unknown = engine.execute("identify", {"url": "https://city.example/meetings/detail/4"})
    assert not unknown.data["identified"]
    assert unknown.data["provider"] is None
    mismatch = engine.execute("validate_source", {"source": {
        "provider": "boardbook", "url": "https://city.primegov.com/public/portal"}})
    assert mismatch.status == "failed"
    explicit = engine.execute("validate_source", {"source": {
        "provider": "digital-towpath", "url": "https://city.example/meetings/detail/4"}})
    assert explicit.data["provider_recognition"] == "explicit_configuration_unverified"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://[::1]/", "https://localhost/a",
    "https://city.internal/a", "https://u:p@city.example/a",
    "https://city.example/?token=do-not-echo", "https://city.example/?api_key=do-not-echo",
    "https://city.example:8443/a", "https://city.example/a#fragment",
])
def test_identification_rejects_unsafe_or_credential_sources(url):
    result = make_engine()[0].execute("identify", {"url": url})
    assert result.status == "failed"
    assert "do-not-echo" not in json.dumps(result.public_dict())


def test_civicclerk_independent_captures_follow_all_four_pages():
    responses = [json.loads((BRIEF / f"civicclerk-erie-events-2026-11-11-page{i}.json").read_text())
                 for i in range(1, 5)]
    engine, transport = make_engine(lambda url, kw, count: responses[count - 1])
    req = request("civicplus-select", "https://erieco.api.civicclerk.com/v1/Events")
    req["bounds"]["date_from"] = "2026-01-01"
    result = engine.execute("discover", req)
    assert result.status == "completed", result.public_dict()
    assert len(transport.calls) == 4
    assert "$top" not in parse_qs(urlsplit(transport.calls[0][0]).query)
    assert result.coverage["pages"] == 4
    assert all(parse_qs(urlsplit(transport.calls[i + 1][0]).query) ==
               parse_qs(urlsplit(responses[i]["@odata.nextLink"]).query) for i in range(3))
    assert all(r["normalized"]["time_zone_status"] == "source_literal_unverified"
               for r in result.data["records"])
    raw = result.data["records"][0]["original"]
    assert "publishedFiles" in raw and "secondaryIanaTimeZone" in raw


def test_escribe_real_capture_uses_post_and_inclusive_end_translation():
    captured = (BRIEF / "escribe-bouldercounty-calendar.json").read_bytes()
    engine, transport = make_engine(lambda *args: captured)
    result = engine.execute("discover", request(
        "escribe", "https://pub-bouldercounty.escribemeetings.com/"))
    assert result.status == "completed", result.public_dict()
    url, options = transport.calls[0]
    assert url.endswith("/MeetingsCalendarView.aspx/GetCalendarMeetings")
    assert options["method"] == "POST"
    assert options["headers"] == {"Content-Type": "application/json"}
    assert json.loads(options["body"]) == {"calendarStartDate": "2026-11-01",
                                          "calendarEndDate": "2026-11-12"}
    assert {r["normalized"]["meeting_date"] for r in result.data["records"]} == {
        "2026-11-05", "2026-11-10"}


def test_legistar_api_separate_mapping_keyset_pages_and_credentials():
    pages = [[event(5), event(6)], [event(7)], []]
    engine, transport = make_engine(lambda url, kw, count: pages[count - 1])
    req = request("legistar", "https://city.legistar.com/Calendar.aspx", options={"page_size": 2})
    ctx = OperationContext(credentials={"legistar_token": "synthetic-secret-never-in-public"})
    result = engine.execute("discover", req, context=ctx)
    assert result.status == "completed", result.public_dict()
    assert [r["identity"]["external_id"] for r in result.data["records"]] == ["5", "6", "7"]
    first = result.data["records"][0]
    assert first["original"]["unknown"] == [None, False, 0, "", {"non_ascii": "café"}]
    assert first["source_revision"]["value"]["EventRowVersion"] == "r5"
    assert first["normalized"]["time_zone_status"] == "unknown"
    assert "scheduled_start" not in first["normalized"]
    params = parse_qs(urlsplit(transport.calls[0][0]).query)
    assert params["$top"] == ["2"]
    assert params["$orderby"] == ["EventId asc"]
    assert "EventDate ge datetime'2026-11-01'" in params["$filter"][0]
    assert "EventDate lt datetime'2026-11-12'" in params["$filter"][0]
    assert "EventId gt 6" in parse_qs(urlsplit(transport.calls[1][0]).query)["$filter"][0]
    assert ctx.credentials["legistar_token"] not in json.dumps(result.public_dict())


def test_primegov_independent_failure_keeps_successful_empty_sibling():
    engine, transport = make_engine(lambda url, kw, count: [] if count == 1 else RuntimeError(
        "https://secret.example/?token=synthetic-secret"))
    result = engine.execute("discover", request("primegov", "https://city.primegov.com/public/portal"))
    assert result.status == "partial", result.public_dict()
    assert result.data["records"] == []
    assert len(result.coverage["failures"]) == 1
    assert result.coverage["checkpoint"]
    assert "synthetic-secret" not in json.dumps(result.public_dict())
    assert "year=2026" in transport.calls[1][0]


def test_primegov_archive_years_exact_boundaries():
    engine, transport = make_engine(lambda *args: [])
    req = request("primegov", "https://city.primegov.com/public/portal")
    req["bounds"].update(date_from="2024-12-31", date_to="2026-01-01")
    result = engine.execute("discover", req)
    assert result.status == "completed"
    assert [parse_qs(urlsplit(call[0]).query).get("year") for call in transport.calls] == [
        None, ["2024"], ["2025"], ["2026"]]


def test_checkpoint_record_limit_resume_overlap_binding_and_changed_page():
    pages = {"first": {"value": [clerk(1), clerk(2)], "@odata.nextLink":
                      "https://city.api.civicclerk.com/v1/Events?$skip=2"},
             "second": {"value": [clerk(2), clerk(3)]}}
    engine, transport = make_engine(lambda url, kw, n: pages["second" if "$skip=2" in url else "first"])
    req = request("civicplus-select", "https://city.api.civicclerk.com/v1/Events")
    req["bounds"]["max_records"] = 1
    first = engine.execute("discover", req)
    assert first.status == "partial" and first.coverage["checkpoint"]
    req["bounds"]["checkpoint"] = first.coverage["checkpoint"]
    second = engine.execute("discover", req)
    assert [r["identity"]["external_id"] for r in second.data["records"]] == ["2"], second.public_dict()
    req["bounds"]["checkpoint"] = second.coverage["checkpoint"]
    third = engine.execute("discover", req)
    assert [r["identity"]["external_id"] for r in third.data["records"]] == ["3"], third.public_dict()
    changed = deepcopy(req)
    changed["bounds"]["date_to"] = "2026-11-12"
    assert engine.execute("discover", changed).status == "failed"
    assert engine.execute("discover", req, context=OperationContext(client_id="another")).status == "failed"
    changed = deepcopy(req)
    changed["record_types"] = ["document"]
    assert engine.execute("discover", changed).status == "failed"
    req["bounds"]["checkpoint"] = first.coverage["checkpoint"]
    pages["first"]["value"].append(clerk(4))
    changed_page = engine.execute("discover", req)
    assert changed_page.status == "failed"


def test_empty_middle_page_continues_to_next_and_cross_tenant_link_keeps_capture():
    pages = [{"value": [clerk(1)], "@odata.nextLink": "/v1/Events?$skip=1"},
             {"value": [], "@odata.nextLink": "/v1/Events?$skip=2"}, {"value": [clerk(2)]}]
    engine, transport = make_engine(lambda url, kw, n: pages[n - 1])
    result = engine.execute("discover", request(
        "civicplus-select", "https://city.api.civicclerk.com/v1/Events"))
    assert result.status == "completed"
    assert len(transport.calls) == 3
    assert len(result.data["records"]) == 2
    bad = {"value": [clerk(4)], "@odata.nextLink": "https://other.api.civicclerk.com/v1/Events"}
    engine, transport = make_engine(lambda *args: bad)
    result = engine.execute("discover", request(
        "civicplus-select", "https://city.api.civicclerk.com/v1/Events"))
    assert result.status == "partial"
    assert len(result.data["records"]) == 1
    assert len(transport.calls) == 1


def test_bounds_body_types_unknown_dates_and_cancel_after_page():
    pages = {"value": [clerk(1, "2026-11-01"), clerk(2, "2026-11-11"),
                       clerk(3, "2026-11-12"), clerk(4, body="Board")]}
    engine, _ = make_engine(lambda *args: pages)
    req = request("civicplus-select", "https://city.api.civicclerk.com/v1/Events", body="Council")
    result = engine.execute("discover", req)
    assert [r["identity"]["external_id"] for r in result.data["records"]] == ["1", "2"]
    req["record_types"] = ["document"]
    assert engine.execute("discover", req).data["records"] == []
    context = OperationContext()
    context.progress = lambda progress: (
        context.cancellation.set() if progress["operation"] == "discover" else None)
    engine, _ = make_engine(lambda *args: {"value": [clerk(1)], "@odata.nextLink": "/v1/Events?$skip=1"})
    result = engine.execute("discover", request(
        "civicplus-select", "https://city.api.civicclerk.com/v1/Events"), context=context)
    assert result.status == "cancelled"
    assert len(result.data["records"]) == 1 and result.coverage["checkpoint"]


def test_failed_page_resume_and_all_fail_never_completed_empty():
    engine, transport = make_engine(lambda url, kw, n: RuntimeError("fail"))
    req = request("primegov", "https://city.primegov.com/public/portal")
    result = engine.execute("discover", req)
    assert result.status == "failed" and len(result.coverage["failed_pages"]) == 2
    req["bounds"]["checkpoint"] = result.coverage["checkpoint"]
    transport.callback = lambda *args: []
    resumed = engine.execute("discover", req)
    assert resumed.status == "completed", resumed.public_dict()
    assert resumed.coverage["checkpoint"] is None


def test_saved_required_unknown_not_unsupported_vendor_and_missing_bounds():
    engine, transport = make_engine()
    result = engine.execute("discover", request(
        "tyler-meeting-manager", "https://city.meetingmanager.tylerapp.com/tenant/tylermm/calendar/"))
    assert result.status == "unsupported"
    assert "does not establish" in result.errors[0].message
    req = request("escribe", "https://pub-city.escribemeetings.com/")
    req["bounds"].pop("date_from")
    assert engine.execute("discover", req).status == "failed"
    assert not transport.calls


def test_attachment_failed_fetch_retains_meeting_and_no_arbitrary_proxy():
    raw = json.dumps([dict(event(1), EventAgendaFile="https://webapi.legistar.com/agenda.pdf")]).encode()
    engine, transport = make_engine(lambda *args: RuntimeError("403"))
    source = {"provider": "legistar", "url": "https://webapi.legistar.com/v1/city/Events",
              "input_format": "legistar-events-json"}
    parsed = engine.execute("fetch", {"source": source}, content=raw)
    record = parsed.data["records"][0]
    result = engine.execute("fetch", {"source": source, "attachment": {
        "record_key": source_identity_key(record["identity"]), "index": 0}}, content=raw)
    assert result.status == "partial"
    assert result.data["record"]["identity"] == record["identity"]
    assert result.data["record"]["normalized"] == record["normalized"]
    assert result.data["record"]["capture_sha256"] == record["capture_sha256"]
    assert result.coverage["unavailable_attachments"]
    arbitrary = engine.execute("fetch", {"source": source, "url": "https://unrelated.example/file",
                                         "attachment": {"record_key": "forged", "index": 0}})
    assert arbitrary.status == "failed"
    assert len(transport.calls) == 1


def test_transfer_limit_is_separate_from_parser_limit():
    raw = json.dumps([dict(event(1), EventAgendaFile="https://webapi.legistar.com/agenda.pdf")]).encode()
    packet = b"%PDF" + b"x" * 5000
    engine, transport = make_engine(lambda *args: packet)
    source = {"provider": "legistar", "url": "https://webapi.legistar.com/v1/city/Events",
              "input_format": "legistar-events-json"}
    record = engine.execute("fetch", {"source": source}, content=raw).data["records"][0]
    result = engine.execute("fetch", {"source": source, "bounds": {
        "parser_bytes": 1024, "transfer_bytes": 10000}, "attachment": {
            "record_key": source_identity_key(record["identity"])}}, content=raw)
    assert result.status == "completed"
    assert result.data["attachment"]["byte_length"] > 1024
    assert transport.calls[0][1]["byte_limit"] == 10000


def test_wistia_modern_version_bearer_page_and_unknown_meeting_date():
    media = {"hashed_id": "abc123", "name": "Council meeting",
             "created": "2026-11-10T10:00:00Z", "updated": "2026-11-11T10:00:00Z"}
    engine, transport = make_engine(lambda url, kw, n: [media] if n == 1 else [])
    req = request("wistia", "https://api.wistia.com/modern/medias",
                  input_format="wistia-api-media-json", options={"page_size": 1})
    result = engine.execute("discover", req, context=OperationContext(credentials={
        "wistia_token": "synthetic-bearer-secret"}))
    assert result.status == "partial"
    assert result.data["records"][0]["identity"]["record_type"] == "recording"
    assert "meeting_date" not in result.data["records"][0]["normalized"]
    assert result.coverage["unknown_date_records"] == ["abc123"]
    assert transport.calls[0][1]["headers"] == {
        "Authorization": "Bearer synthetic-bearer-secret", "X-Wistia-API-Version": "2026-09"}
    assert parse_qs(urlsplit(transport.calls[1][0]).query)["page"] == ["2"]
    assert "synthetic-bearer-secret" not in json.dumps(result.public_dict())


def test_discover_real_capture_import_search_preserves_partial_coverage(tmp_path):
    from civic_data_connectors import imports, search
    from civic_data_connectors.storage import SQLiteStorage
    engine = Engine(storage=SQLiteStorage(tmp_path / "early.sqlite"))
    transport = FakeTransport(lambda *args: (BRIEF / "escribe-bouldercounty-calendar.json").read_bytes())
    providers.register(engine, transport=transport)
    imports.register(engine)
    search.register(engine)
    found = engine.execute("discover", request("escribe", "https://pub-bouldercounty.escribemeetings.com/"))
    assert found.status == "completed", found.public_dict()
    for bundle in found.data["bundles"]:
        stored = engine.execute("import_bundle", {"bundle": bundle, "persist": True,
                                                  "coverage": found.coverage})
        assert stored.status in {"completed", "partial"}, stored.public_dict()
    result = engine.execute("search", {"query": {"terms": ["Commissioners"]}})
    assert len(result.data["hits"]) == 2, result.public_dict()


def test_aliases_unknown_source_fields_and_newsroom_tenant_namespace_scope():
    from civic_data_connectors.providers.identification import _aliases, canonical_provider
    for alias, canonical in _aliases().items():
        assert canonical_provider(alias) == canonical
    engine, transport = make_engine(lambda *args: [event(1)])
    source = {"provider": "legistar", "url": "https://city.legistar.com/Calendar.aspx",
              "future_configuration": {"nested": [None, False, 0, ""]}}
    validated = engine.execute("validate_source", {"source": source},
                               context=OperationContext(tenant="newsroom-not-upstream"))
    assert validated.status == "completed"
    assert validated.data["source"]["future_configuration"] == source["future_configuration"]
    namespace = validated.data["source"]["namespace"]
    allowed = OperationContext(tenant="newsroom-not-upstream",
                               allowed_namespaces=frozenset({namespace}))
    assert engine.execute("discover", {"source": source, "bounds": request("", "")["bounds"]},
                          context=allowed).status == "completed"
    before = len(transport.calls)
    assert engine.execute("discover", {"source": source}, context=OperationContext(
        allowed_namespaces=frozenset({"other"}))).status == "failed"
    assert len(transport.calls) == before


def test_granicus_upcoming_attachmentless_row_and_archived_clip_identity():
    content = (b'<table><tr><td headers="Name">Upcoming Council</td>'
               b'<td headers="Date"><span>1794355200</span>Nov. 11, 2026 - 7:00 PM</td></tr>'
               b'<tr><td headers="Name">Archived Council</td>'
               b'<td headers="Date">November 10, 2026 - 7:00 PM</td>'
               b'<td headers="VideoLink"><a href="MediaPlayer.php?clip_id=42">Video</a></td>'
               b'<td headers="Agenda"><a href="AgendaViewer.php?clip_id=42">Agenda</a></td>'
               b'</tr></table>')
    engine, _ = make_engine(lambda *args: content)
    result = engine.execute("discover", request(
        "granicus", "https://city.granicus.com/ViewPublisher.php?view_id=1"))
    assert result.status == "partial"
    upcoming, archived = result.data["records"]
    assert upcoming["identity"]["external_id"].startswith("derived:")
    assert upcoming["identity"]["derivation"] == "configured_url_date_title"
    assert upcoming["normalized"]["documents"] == []
    assert upcoming["normalized"]["recordings"] == []
    assert archived["identity"]["external_id"] == "42"
    assert archived["normalized"]["documents"][0]["kind"] == "agenda"


def test_http_failure_preserves_status_not_response_secrets():
    engine, _ = make_engine(lambda url, *args: Response(
        url, b"private error payload", status=429, headers={"Set-Cookie": "private-cookie"}))
    result = engine.execute("discover", request("legistar", "https://city.legistar.com/"))
    assert result.status == "failed"
    assert result.errors[0].code == "provider_http_error"
    assert result.errors[0].details["http_status"] == 429
    assert result.coverage["failures"][0]["http_status"] == 429
    assert "private" not in json.dumps(result.public_dict())


def test_gworks_scheduled_calendar_day_filters_before_record_cap():
    case = next(row for row in CASES if row["connector"] == "gworks")
    engine, _ = make_engine(lambda *args: (BASELINE / case["file"]).read_bytes())
    req = request("gworks", case["source_url"])
    req["bounds"]["max_records"] = 1
    result = engine.execute("discover", req)
    assert len(result.data["records"]) == 1
    assert result.data["records"][0]["identity"]["external_id"] == "5017"
    assert result.coverage["actual_dates"] == ["2026-11-10"]
    assert not result.coverage["unknown_date_records"]


def test_deadline_between_response_and_records_preserves_resumable_capture(monkeypatch):
    from civic_data_connectors.providers import discovery
    clock = [0.0]
    monkeypatch.setattr(discovery, "monotonic", lambda: clock[0])
    def reply(*args):
        clock[0] = 2.0
        return [event(1)]
    engine, _ = make_engine(reply)
    req = request("legistar", "https://city.legistar.com/")
    req["bounds"]["deadline_seconds"] = 1
    result = engine.execute("discover", req)
    assert result.status == "partial"
    assert result.data["records"] == []
    assert len(result.data["captures"]) == 1
    assert result.coverage["checkpoint"]

def test_tyler_explicit_observed_calendar_api_uses_fixed_bounded_post_and_reports_partial():
    case = next(row for row in CASES if row["connector"] == "tyler-meeting-manager")
    raw = (BASELINE / case["file"]).read_bytes()
    engine, transport = make_engine(lambda *args: raw)
    host = urlsplit(case["source_url"]).hostname
    req = request("tyler-meeting-manager", case["source_url"], input_format=case["input_format"],
                  options={"calendar_api_base": f"https://{host}/tylermmcalendar46612prod/"})
    req["bounds"] = {"date_from": "2020-01-01", "date_to": "2030-12-31"}
    result = engine.execute("discover", req)
    assert result.status == "partial", result.public_dict()
    assert result.data["records"]
    assert "completeness is unverified" in result.coverage["scope"]
    url, kwargs = transport.calls[0]
    assert url.endswith("/tylermmcalendar46612prod/meetingInformation/getMeetingInformationByDate")
    assert kwargs["method"] == "POST"
    assert json.loads(kwargs["body"]) == {"startDate": "01/01/2020", "endDate": "12/31/2030",
                                           "meetingTypeIds": [-1]}
    assert kwargs["allowed_origins"] == (f"https://{host}",)
    for base in ("http://ectortmmapp.meetingmanager.tylerapp.com/tylermmcalendar46612prod/",
                 "https://unrelated.example/tylermmcalendar46612prod/",
                 "https://ectortmmapp.meetingmanager.tylerapp.com/arbitrary/"):
        req["source"]["options"]["calendar_api_base"] = base
        assert engine.execute("discover", req).status == "failed"
    assert len(transport.calls) == 1
