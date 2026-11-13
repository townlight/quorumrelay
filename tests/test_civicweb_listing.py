"""CivicWeb meeting and document listing from saved public Loveland, CO captures; no live network."""
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response

FIXTURES = Path(__file__).parent / "fixtures" / "civicweb-listing"
ORIGIN = "https://cilovelandco.civicweb.net"
SOURCE = Source("civicweb", ORIGIN + "/")
MEETINGS = (FIXTURES / "loveland-meetings.json").read_bytes()
TYPES = (FIXTURES / "loveland-meeting-types.html").read_bytes()
DOCS = {i: (FIXTURES / f"loveland-docs-{i}.json").read_bytes() for i in (18421, 18353, 18077)}
RANGE = {"date_from": "2026-10-01", "date_to": "2026-11-30"}


class Transport:
    """Serves saved captures by URL and records every request, so a test can see what was asked."""

    def __init__(self, meetings=MEETINGS, types=TYPES, docs=None, fail=()):
        self.meetings, self.types, self.docs, self.fail = meetings, types, docs or DOCS, set(fail)
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        parts = urlsplit(url)
        assert kwargs["allow_redirects"] is False and kwargs["allowed_origins"] == (ORIGIN,)
        assert parts.scheme + "://" + parts.hostname == ORIGIN and parts.path != "" and not url.endswith((".pdf", ".html"))
        if any(token in url for token in self.fail):
            return Response(url, b"", "text/plain", 503)
        if parts.path == "/Services/MeetingsService.svc/meetings":
            return Response(url, self.meetings, "application/json")
        if parts.path == "/Portal/MeetingTypeList.aspx":
            return Response(url, self.types, "text/html")
        meeting = parts.path.split("/")[-2]
        assert parts.path.endswith("/meetingDocuments")
        return Response(url, self.docs.get(int(meeting), b"[]"), "application/json")


def discover(transport=None, source=SOURCE, request=None, **bounds):
    transport = transport or Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.execute("discover", {"source": source.public_dict(),
                                         "bounds": {**RANGE, **bounds}, **(request or {})})
    return result, transport


def ids(result, record_type="meeting"):
    return [r["identity"]["external_id"] for r in result.data["records"] if r["identity"]["record_type"] == record_type]


def test_lists_meetings_in_range_with_bodies_and_omits_unpublished():
    result, transport = discover()
    assert result.status == "partial", result.public_dict()
    # Published meetings only: 18433, 18220 and 18395 are Published=false on the portal.
    assert sorted(ids(result)) == sorted(map(str, (
        18183, 18425, 18424, 18054, 18078, 18196, 18423, 18182, 18421, 18420, 18181, 18411, 18077, 18195)))
    # Newest first, in a stable order a continuation can rely on.
    assert ids(result)[:4] == ["18183", "18425", "18424", "18054"]
    by_id = {r["identity"]["external_id"]: r["normalized"] for r in result.data["records"]}
    council = by_id["18421"]
    assert council["title"] == "LOVELAND CITY COUNCIL MEETING - 04 Nov 2026"
    assert council["meeting_date"] == "2026-11-04" and council["source_start"] == "2026-11-04T18:00:00"
    assert council["body"] == "LOVELAND CITY COUNCIL MEETING" and council["body_source"] == "meeting_type_list"
    assert council["meeting_type_id"] == "10" and council["time_zone_status"] == "unknown"
    assert council["url"] == ORIGIN + "/Portal/MeetingInformation.aspx?Id=18421"
    assert council["documents"] == [] and council["documents_availability"] == "not_supplied_by_meeting_listing"
    assert by_id["18078"]["source_status"]["title_marks_cancelled"] is True
    coverage = result.coverage
    assert coverage["unpublished_omitted"] == 3 and coverage["meeting_types"] == "applied"
    assert coverage["catalog_complete"] is False and coverage["source_complete"] is False
    assert coverage["listing_exhausted"] is True and coverage["checkpoint"] is None
    # One meeting-type page and one date-range request, both plain GETs on the tenant origin.
    urls = [url for url, _ in transport.calls]
    meetings_url = next(u for u in urls if "/meetings?" in u)
    assert parse_qs(urlsplit(meetings_url).query) == {"from": ["2026-10-01"], "to": ["2026-11-30"]}
    assert len(urls) == 2


def test_capture_and_identity_provenance():
    result, _ = discover()
    bundle = result.data["bundles"][0]
    assert bundle["capture"]["sha256"] == hashlib.sha256(MEETINGS).hexdigest()
    assert bundle["capture"]["input_format"] == "civicweb-meetings-json"
    record = result.data["records"][0]
    assert record["identity"]["provider"] == "civicweb" and record["identity"]["namespace"] == "//cilovelandco.civicweb.net"
    assert record["capture_sha256"] == hashlib.sha256(MEETINGS).hexdigest()
    assert record["original"]["Id"] == int(record["identity"]["external_id"])


def test_dates_are_inclusive_and_filtered_even_when_the_service_returns_more():
    result, _ = discover(date_from="2026-11-10", date_to="2026-11-12")
    assert sorted(ids(result)) == ["18054", "18078", "18196", "18423"]
    assert result.coverage["filtered_records"] > 0
    assert result.coverage["actual_dates"] == ["2026-11-10", "2026-11-11", "2026-11-12"]


def test_body_filter_uses_the_portal_meeting_type_name():
    result, _ = discover(source=Source("civicweb", ORIGIN + "/", body="planning commission"))
    assert sorted(ids(result)) == ["18181", "18182", "18183"]
    assert {r["normalized"]["body"] for r in result.data["records"]} == {"Planning Commission"}


def _with_calendar_row():
    rows = json.loads(MEETINGS)
    rows.append({"ExternalCalendar": False, "Id": 222, "MeetingDate": "2026-11-06", "MeetingDateTime": "2026-11-06 00:00",
                 "MeetingLocation": "", "MeetingTime": "", "Name": "Rolling Calendar - Updated 11-6-26",
                 "Published": True, "TypeId": 36, "VideoIcon": ""})
    return Transport(meetings=json.dumps(rows).encode())


def test_calendar_and_notice_meeting_types_are_flagged_not_dropped_by_default():
    result, _ = discover(_with_calendar_row())
    assert "222" in ids(result) and "18421" in ids(result)
    values = {r["identity"]["external_id"]: r["normalized"] for r in result.data["records"]}
    assert values["222"]["likely_not_a_meeting"] is True
    assert values["222"]["likely_not_a_meeting_type"] == "Rolling Calendar"
    assert values["18421"]["likely_not_a_meeting"] is False and values["18421"]["likely_not_a_meeting_type"] is None
    assert result.coverage["flagged_meeting_types"] == [{"id": "36", "name": "Rolling Calendar"}]
    assert result.coverage["likely_non_meeting_omitted"] == 0 and result.coverage["exclude_likely_non_meetings"] is False


def test_exclude_likely_non_meetings_is_an_explicit_option_and_is_counted():
    result, _ = discover(_with_calendar_row(), request={"exclude_likely_non_meetings": True})
    assert "222" not in ids(result) and "18421" in ids(result)
    assert result.coverage["likely_non_meeting_omitted"] == 1
    assert result.coverage["flagged_meeting_types"] == [{"id": "36", "name": "Rolling Calendar"}]
    bad, _ = discover(request={"exclude_likely_non_meetings": "yes"})
    assert bad.status == "failed"


def test_a_real_body_with_a_flagged_word_in_its_type_name_is_still_returned():
    types = TYPES.replace(b">Planning Commission<", b">Budget Committee<")
    result, _ = discover(Transport(types=types))
    assert {"18182", "18181", "18183"} <= set(ids(result))
    flagged = {r["normalized"]["body"]: r["normalized"]["likely_not_a_meeting"] for r in result.data["records"]}
    assert flagged["Budget Committee"] is True


def test_meeting_type_page_failure_is_reported_and_does_not_hide_meetings():
    result, _ = discover(Transport(fail=("MeetingTypeList",)))
    assert result.status == "partial" and "18421" in ids(result)
    assert result.coverage["meeting_types"] == "unavailable_request_failed"
    assert result.coverage["non_meeting_flagging"] == "not_applied_meeting_types_unavailable"
    assert result.errors and result.errors[0].code == "provider_http_error"
    council = next(r for r in result.data["records"] if r["identity"]["external_id"] == "18421")
    assert council["normalized"]["body"] == "LOVELAND CITY COUNCIL MEETING"
    assert council["normalized"]["body_source"].startswith("title_with_date")


def test_meeting_service_failure_fails_with_a_retry_checkpoint_free_error():
    result, _ = discover(Transport(fail=("/meetings?",)))
    assert result.status == "failed" and result.errors[0].code == "provider_http_error"
    assert result.coverage["failures"][0]["kind"] == "meetings"


def test_documents_are_listed_per_meeting_with_links_only():
    result, transport = discover(request={"record_types": ["meeting", "document"]}, date_from="2026-11-04",
                                 date_to="2026-11-04")
    assert ids(result) == ["18421"]
    documents = [r for r in result.data["records"] if r["identity"]["record_type"] == "document"]
    assert [d["identity"]["external_id"] for d in documents] == ["522441", "522399"]
    agenda, packet = documents
    assert agenda["normalized"]["kind"] == "agenda" and agenda["normalized"]["format"] == "html"
    assert agenda["normalized"]["url"] == (
        ORIGIN + "/document/522441/LOVELAND%20CITY%20COUNCIL%20MEETING%20-%2004%20Nov%202026.html")
    # IsPublic=false: the document is listed but no link is offered.
    assert packet["normalized"]["is_public"] is False and packet["normalized"]["url"] is None
    assert packet["normalized"]["url_availability"] == "not_public"
    assert agenda["identity"]["parent"]["record_type"] == "meeting" and agenda["identity"]["parent"]["external_id"] == "18421"
    assert agenda["relationships"][0]["relation"] == "meeting"
    assert agenda["original"]["Html"]["omitted_from_record"] is True and agenda["normalized"]["has_html_body"] is True
    assert result.coverage["documents"].startswith("read for each returned meeting")
    assert [u for u, _ in transport.calls][-1] == ORIGIN + "/Services/MeetingsService.svc/meetings/18421/meetingDocuments"
    assert not any(u.endswith((".html", ".pdf")) for u, _ in transport.calls)


def test_pdf_minutes_and_unmapped_document_types_get_evidenced_link_shapes():
    rows = json.loads(DOCS[18353])
    rows[2]["IsPublic"] = True
    rows.append({**rows[0], "Id": 9, "DocumentType": 77, "Html": ""})
    engine = create_engine(provider_transport=Transport(docs={18353: json.dumps(rows).encode()}))
    result = engine.fetch_related(SOURCE, "18353", "document")
    assert result.status == "partial", result.public_dict()
    urls = {r["identity"]["external_id"]: r["normalized"] for r in result.data["records"]}
    assert urls["520275"]["kind"] == "minutes_adopted" and urls["520275"]["url"].endswith(".pdf")
    assert urls["9"]["kind"] == "document" and urls["9"]["url"] == ORIGIN + "/document/9/"
    assert result.coverage["catalog_complete"] is False


def test_checkpoint_resumes_documents_without_repeating_records():
    request = {"record_types": ["meeting", "document"]}
    first, _ = discover(request=request, date_from="2026-10-14", date_to="2026-11-04", max_pages=4)
    assert first.status == "partial" and first.coverage["truncated"] is True
    token = first.coverage["checkpoint"]
    assert token and first.coverage["pages"] == 4
    seen = {(r["identity"]["record_type"], r["identity"]["external_id"]) for r in first.data["records"]}
    second, transport = discover(request=request, date_from="2026-10-14", date_to="2026-11-04", checkpoint=token)
    assert second.coverage["checkpoint"] is None and second.coverage["listing_exhausted"] is True
    again = {(r["identity"]["record_type"], r["identity"]["external_id"]) for r in second.data["records"]}
    assert not seen & again
    # A resumed call reads only the remaining document lists, not the meeting list again.
    assert all("meetingDocuments" in url for url, _ in transport.calls)
    meetings = {k for k in seen | again if k[0] == "meeting"}
    assert {k[1] for k in meetings} == {"18077", "18181", "18195", "18411", "18420", "18421"}


def test_checkpoint_from_other_dates_is_rejected():
    first, _ = discover(request={"record_types": ["document"]}, max_pages=3)
    assert first.coverage["checkpoint"]
    other, _ = discover(request={"record_types": ["document"]}, date_from="2026-10-02",
                        date_to="2026-11-30", checkpoint=first.coverage["checkpoint"])
    assert other.status == "failed" and other.errors[0].code == "invalid_input"
    assert "different source, filters, dates" in other.errors[0].message


def test_max_records_truncates_with_a_continuation_over_the_same_listing():
    first, _ = discover(max_records=3)
    assert len(first.data["records"]) == 3 and first.coverage["truncated"] is True
    second, _ = discover(max_records=100, checkpoint=first.coverage["checkpoint"])
    assert not set(ids(first)) & set(ids(second)) and len(set(ids(first)) | set(ids(second))) == 14


def test_explicit_dates_are_required_and_a_foreign_host_is_rejected():
    engine = create_engine(provider_transport=Transport())
    undated = engine.execute("discover", {"source": SOURCE.public_dict(), "bounds": {}})
    assert undated.status == "failed" and "date_from" in undated.errors[0].message
    # i.civicweb.net is iCompass's own image host, not a city tenant.
    image_host = Source("civicweb", "https://i.civicweb.net/", input_format="civicweb-meetings-json")
    result = engine.execute("discover", {"source": image_host.public_dict(), "bounds": RANGE})
    assert result.status == "failed" and "tenant" in result.errors[0].message


def test_response_from_another_url_is_not_trusted():
    class Redirecting(Transport):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            return Response(url + "&x=1", response.content, response.content_type)
    result, _ = discover(Redirecting())
    assert result.status == "failed" and result.errors[0].code == "provider_response_outside_contract"


def test_identification_skips_icompass_image_host():
    engine = create_engine()
    tenant = engine.execute("identify", {"url": ORIGIN + "/Portal/MeetingTypeList.aspx"})
    image = engine.execute("identify", {"url": "https://i.civicweb.net/FileStorage/x.png"})
    assert tenant.data["provider"] == "civicweb"
    assert image.data["provider"] is None and image.data["candidates"] == []


def test_meeting_type_list_url_keeps_the_original_listing_route():
    transport = Transport(types=TYPES)
    engine = create_engine(provider_transport=transport)
    source = Source("civicweb", ORIGIN + "/Portal/MeetingTypeList.aspx")
    engine.execute("discover", {"source": source.public_dict(), "bounds": RANGE})
    assert [urlsplit(u).path for u, _ in transport.calls] == ["/Portal/MeetingTypeList.aspx"]


def test_saved_meetings_and_documents_parse_without_network():
    engine = create_engine()
    meetings = engine.normalize(Source("civicweb", ORIGIN + "/"), MEETINGS, input_format="civicweb-meetings-json")
    assert meetings.status == "completed" and len(meetings.data["records"]) == 18
    documents = engine.normalize(Source("civicweb", ORIGIN + "/"), DOCS[18421], input_format="civicweb-meeting-documents-json")
    assert [r["identity"]["record_type"] for r in documents.data["records"]] == ["document"] * 2
    baseline = {(p["connector"], p["input_format"]) for p in create_engine().providers().data["formats"]}
    assert len(baseline) == 34 and ("civicweb", "civicweb-html") in baseline


def test_related_documents_reject_a_row_for_another_meeting_and_bad_ids():
    engine = create_engine(provider_transport=Transport(docs={18077: DOCS[18421]}))
    mismatch = engine.fetch_related(SOURCE, "18077", "document")
    assert mismatch.status == "failed" and mismatch.errors[0].code == "civicweb_documents_unavailable"
    assert engine.fetch_related(SOURCE, "../18077", "document").status == "failed"
    assert engine.fetch_related(SOURCE, "18077", "vote").status == "failed"
    context = OperationContext()
    context.cancellation.set()
    assert engine.fetch_related(SOURCE, "18077", "document", context=context).status == "cancelled"


def test_discover_honors_caller_namespace_policy():
    engine = create_engine(provider_transport=Transport())
    request = {"source": SOURCE.public_dict(), "bounds": RANGE}
    allowed = OperationContext(allowed_operations=frozenset({"discover"}),
                               allowed_namespaces=frozenset({"//cilovelandco.civicweb.net"}))
    assert "18421" in ids(engine.execute("discover", request, context=allowed))
    denied = OperationContext(allowed_operations=frozenset({"discover"}),
                              allowed_namespaces=frozenset({"//elsewhere.civicweb.net"}))
    result = engine.execute("discover", request, context=denied)
    assert result.status == "failed" and result.errors[0].code in {"permission_denied", "invalid_input"}
    assert result.data is None
