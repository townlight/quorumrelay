"""Exact public fixture traversal proves paging, not complete archive/search coverage."""

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.engine import source_identity_key
from quorumrelay.providers.contracts import Response
from civic_data_connectors.providers.novus import FORMAT, Listing, _sessions

ROOT = Path(__file__).parent / "fixtures" / "brief-discovery" / "novus-eastbrunswick"
SOURCE = Source("novusagenda", "https://ebps.novusagenda.com/agendapublic/")
PAGES = [(ROOT / f"page-{index:02}.html").read_bytes() for index in range(1, 13)]


class FixtureTransport:
    def __init__(self):
        self.calls, self.fail_page = [], None
        self.pages = list(PAGES)

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert url == SOURCE.url
        assert kwargs["allowed_origins"] == ("https://ebps.novusagenda.com",)
        if kwargs["method"] == "GET":
            assert kwargs["body"] is None
            assert "Cookie" not in kwargs["headers"]
            page = 0
        else:
            parameters = {key: values[0] for key, values in parse_qs(kwargs["body"].decode(), keep_blank_values=True).items()}
            previous = next(index for index, raw in enumerate(self.pages[:-1])
                            if Listing(raw).controls["__VIEWSTATE"] == parameters["__VIEWSTATE"])
            parsed = Listing(self.pages[previous])
            assert parameters == {**parsed.controls, "__EVENTTARGET": parsed.next_targets["agenda_item"], "__EVENTARGUMENT": ""}
            assert "ASP.NET_SessionId=synthetic-cookie-" + str(previous) in kwargs["headers"]["Cookie"]
            assert "other=synthetic-other-cookie" in kwargs["headers"]["Cookie"]
            page = previous + 1
        return Response(url, self.pages[page], "text/html", 503 if page == self.fail_page else 200,
                        set_cookie_headers=(f"ASP.NET_SessionId=synthetic-cookie-{page}; Path=/; Secure; HttpOnly",
                                            "other=synthetic-other-cookie; Path=/; Secure"))


def test_exact_twelve_page_listing_preserves_all_rows_raw_links_and_separate_grid_pages():
    transport = FixtureTransport()
    result = create_engine(provider_transport=transport).discover(SOURCE)
    assert result.status == "partial", result.public_dict()
    rows = result.data["records"]
    assert len(rows) == len({source_identity_key(row["identity"]) for row in rows}) == 191
    items = [row for row in rows if row["identity"]["record_type"] == "agenda_item"]
    meetings = [row for row in rows if row["identity"]["record_type"] == "meeting"]
    assert len(items) == 180 and len(meetings) == 11
    assert sum(not row["identity"]["external_id"].startswith("derived:") for row in items) == 75
    assert sum(row["identity"]["external_id"].startswith("derived:") for row in items) == 105
    assert all(row["normalized"]["source_position"]["page"] == 1 for row in meetings)
    assert all(row["identity"]["parent"]["record_type"] == "meeting" for row in items if row["identity"]["parent"])
    assert result.coverage["listing_exhausted"] is True
    assert result.coverage["catalog_complete"] is False
    assert result.coverage["observed_window"] == ["2026-08-11", "2027-02-11"]
    assert len(transport.calls) == 12
    for index, bundle in enumerate(result.data["bundles"]):
        assert base64.b64decode(bundle["capture"]["content_base64"]) == PAGES[index]
        assert bundle["capture"]["sha256"] == hashlib.sha256(PAGES[index]).hexdigest()
    assert "synthetic-cookie" not in json.dumps(result.public_dict())
    assert "synthetic-other-cookie" not in json.dumps(result.public_dict())


def test_one_record_continuations_do_not_hit_arbitrary_session_count_and_retries_are_stable():
    transport, keys = FixtureTransport(), []
    engine, checkpoint = create_engine(provider_transport=transport), None
    for _ in range(200):
        result = engine.discover(SOURCE, bounds=Bounds(max_records=1, checkpoint=checkpoint))
        assert not result.errors, result.public_dict()
        keys.extend(source_identity_key(row["identity"]) for row in result.data["records"])
        checkpoint = result.coverage["checkpoint"]
        if not checkpoint:
            break
        assert checkpoint.startswith("novus:") and len(checkpoint) == 54
        if len(keys) in {10, 40, 100}:
            retry1 = engine.discover(SOURCE, bounds=Bounds(max_records=1, checkpoint=checkpoint))
            retry2 = engine.discover(SOURCE, bounds=Bounds(max_records=1, checkpoint=checkpoint))
            assert [row["identity"] for row in retry1.data["records"]] == [row["identity"] for row in retry2.data["records"]]
            assert retry1.coverage["checkpoint"] == retry2.coverage["checkpoint"]
    assert len(keys) == len(set(keys)) == 191
    assert len(_sessions(engine).values) > 32
    assert len(_sessions(engine).payloads) == 12


def test_scope_filters_expiry_restart_and_saved_default_compatibility():
    transport, engine = FixtureTransport(), create_engine(provider_transport=FixtureTransport())
    result = engine.discover(SOURCE, bounds=Bounds(max_records=1))
    checkpoint = result.coverage["checkpoint"]
    assert engine.discover(SOURCE, bounds=Bounds(checkpoint=checkpoint), context=OperationContext(principal="other")).status == "failed"
    assert engine.discover(SOURCE, bounds=Bounds(checkpoint=checkpoint, date_from="2026-09-01")).status == "failed"
    assert engine.discover(Source("novusagenda", SOURCE.url.replace("ebps", "other")), bounds=Bounds(checkpoint=checkpoint)).status == "failed"
    assert create_engine(provider_transport=transport).discover(SOURCE, bounds=Bounds(checkpoint=checkpoint)).status == "failed"
    assert not transport.calls
    _sessions(engine).values[checkpoint]["expires"] = 0
    assert engine.discover(SOURCE, bounds=Bounds(checkpoint=checkpoint)).status == "failed"
    filtered = engine.execute("discover", {"source": {**SOURCE.public_dict(), "body": "Explicit unmapped board"},
        "record_types": ["agenda_item"], "bounds": {"date_from": "2026-10-01", "date_to": "2026-10-31"}})
    assert filtered.status == "partial", filtered.public_dict()
    assert filtered.data["records"]
    assert all(row["identity"]["record_type"] == "agenda_item" and
               "2026-10-01" <= row["normalized"]["meeting_date"] <= "2026-10-31" for row in filtered.data["records"])
    assert len(filtered.coverage["unknown_body_records"]) == len(filtered.data["records"])
    raw = (Path(__file__).parent / "fixtures" / "baseline" / "novusagenda.json").read_bytes()
    saved = create_engine().normalize(SOURCE, raw)
    assert saved.status == "completed", saved.public_dict()
    assert saved.data["records"][0]["identity"]["external_id"] == "sandbox-novusagenda"


def test_failed_page_retry_byte_limits_cancellation_and_forged_pager():
    transport = FixtureTransport()
    transport.fail_page = 1
    engine = create_engine(provider_transport=transport)
    result = engine.discover(SOURCE)
    assert result.status == "partial" and result.coverage["failed_pages"]
    assert result.coverage["failed_pages"][0]["http_status"] == 503
    transport.fail_page = None
    resumed = engine.discover(SOURCE, bounds=Bounds(checkpoint=result.coverage["checkpoint"]))
    assert resumed.coverage["listing_exhausted"] is True
    assert len(result.data["records"]) + len(resumed.data["records"]) == 191
    assert engine.discover(SOURCE, bounds=Bounds(parser_bytes=1024)).status == "failed"
    limited = engine.discover(SOURCE, bounds=Bounds(max_pages=1))
    assert limited.coverage["checkpoint"] and len(limited.data["records"]) == 26
    context = OperationContext()
    context.cancellation.set()
    assert engine.discover(SOURCE, context=context).status == "cancelled"
    forged = FixtureTransport()
    target = Listing(forged.pages[0]).next_targets["agenda_item"].encode()
    forged.pages[0] = forged.pages[0].replace(target, b"ctl00$Staff$Delete")
    bad = create_engine(provider_transport=forged).discover(SOURCE)
    assert bad.status == "failed" and len(forged.calls) == 1


def test_additive_saved_page_replay_retains_original_html_and_never_runs_pager():
    result = create_engine().normalize(Source("novusagenda", SOURCE.url), PAGES[0], input_format=FORMAT)
    assert result.status == "completed", result.public_dict()
    assert len(result.data["records"]) == 26
    assert base64.b64decode(result.data["capture"]["content_base64"]) == PAGES[0]


def test_capacity_failure_is_explicit_and_does_not_evict_active_other_callers():
    engine = create_engine(provider_transport=FixtureTransport())
    first = engine.discover(SOURCE, bounds=Bounds(max_records=1))
    other = engine.discover(SOURCE, bounds=Bounds(max_records=1), context=OperationContext(principal="other"))
    cache = _sessions(engine)
    active = set(cache.values)
    assert len(active) == 2
    cache.max_bytes = 1
    limited = engine.discover(SOURCE, bounds=Bounds(max_records=1, checkpoint=first.coverage["checkpoint"]))
    assert limited.status == "partial" and len(limited.data["records"]) == 1
    assert limited.errors[0].code == "novus_continuation_capacity"
    assert limited.coverage["checkpoint"] is None
    assert set(cache.values) == active
    assert other.coverage["checkpoint"] in cache.values
