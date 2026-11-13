import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.interchange import read_bundle

EVIDENCE = json.loads((Path(__file__).parent / "fixtures/novus-coversheet-12406.capture.json").read_bytes())
CAPTURE = base64.b64decode(EVIDENCE["content_base64"], validate=True)
SOURCE = Source("novusagenda", EVIDENCE["source_url"], input_format="novus-public-coversheet-html")


def test_saved_cover_sheet_native_item_parent_text_search_and_export():
    assert len(CAPTURE) == EVIDENCE["byte_length"] == 30741
    assert hashlib.sha256(CAPTURE).hexdigest() == EVIDENCE["sha256"]
    engine = create_engine()
    result = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record, = result.data["records"]
    assert record["identity"]["record_type"] == "agenda_item"
    assert record["identity"]["external_id"] == "12406"
    assert record["identity"]["parent"]["external_id"] == "996"
    value = record["normalized"]
    assert value["meeting_date"] == "2026-10-29"
    assert value["title"] == "Personnel Actions (Roll Call - Majority of Full Board Required)"
    assert "collective bargaining agreements" in value["text"]
    assert len(value["documents"]) == 1
    assert value["documents"][0]["external_id"] == "11729"
    assert value["documents"][0]["agenda_item_external_id"] == "12406"
    assert "votes" not in value and "motions" not in value  # Rendered blank vote form is not cast votes.
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CAPTURE
    searched = engine.execute("search", {"bundle": result.data, "query": {"terms": ["collective bargaining"]}})
    assert len(searched.data["hits"]) == 1, searched.public_dict()
    exported = engine.execute("export", {"bundle": result.data, "format": "json"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="json") == result.data


def test_default_configured_discover_fetch_and_separate_attachment_transfer():
    class Transport:
        def __init__(self): self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            return Response(url, CAPTURE, "text/html") if url == SOURCE.url else Response(url, b"%PDF-1.7\nsynthetic Novus", "application/pdf")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.discover(replace(SOURCE, input_format=None))
    assert result.status == "partial" and len(result.data["records"]) == 1, result.public_dict()
    record = result.data["records"][0]
    fetched = engine.fetch_attachment(SOURCE, record, index=0, capture=CAPTURE)
    assert fetched.status == "completed", fetched.public_dict()
    assert transport.calls[-1].endswith("AttachmentViewer.ashx?AttachmentID=11729&ItemID=12406")
    configured = engine.execute("fetch", {"source": replace(SOURCE, input_format=None).public_dict()})
    assert configured.status == "partial" and len(configured.data["records"]) == 1, configured.public_dict()


@pytest.mark.parametrize("old,new", [
    (b'action="./Coversheet.aspx?ItemID=12406&amp;MeetingID=996"', b'action="./Coversheet.aspx?ItemID=12406&amp;MeetingID=997"'),
    (b'AttachmentID=11729&amp;ItemID=12406', b'AttachmentID=11729&amp;ItemID=12407'),
    (b'href="AttachmentViewer.ashx?', b'href="https://other.novusagenda.com/agendapublic/AttachmentViewer.ashx?'),
    (b'SUBJECT:', b'SUBJECT MISSING:'),
])
def test_changed_form_attachment_context_origin_or_missing_subject_is_rejected(old, new):
    assert old in CAPTURE
    result = create_engine().normalize(SOURCE, CAPTURE.replace(old, new), input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


MEETING_EVIDENCE = json.loads((Path(__file__).parent / "fixtures/novus-meetingview-996.capture.json").read_bytes())
MEETING_CAPTURE = base64.b64decode(MEETING_EVIDENCE["content_base64"], validate=True)
MEETING_SOURCE = Source("novusagenda", MEETING_EVIDENCE["url"], input_format="novus-public-listing-html")


def test_saved_meeting_view_exact_context_native_children_text_search_export():
    assert len(MEETING_CAPTURE) == MEETING_EVIDENCE["bytes"] == 784159
    assert hashlib.sha256(MEETING_CAPTURE).hexdigest() == MEETING_EVIDENCE["sha256"]
    engine = create_engine()
    result = engine.normalize(MEETING_SOURCE, MEETING_CAPTURE, input_format=MEETING_SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    meeting, *items = result.data["records"]
    value = meeting["normalized"]
    assert meeting["identity"]["external_id"] == "996" and len(items) == 20
    assert value["body"] == "East Brunswick Board of Education"
    assert value["title"] == "Board Meeting Agenda" and value["source_start"] == "2026-10-29T18:30:00"
    assert value["time_zone_status"] == "unknown" and value["source_minutes_meeting_id"] == "-1"
    assert len({r["identity"]["external_id"] for r in items}) == 20
    assert all(r["identity"]["parent"] == meeting["identity"] for r in items)
    assert all(r["normalized"]["meeting_external_id"] == "996" for r in items)
    assert all(r["normalized"]["documents"][0]["kind"] == "linked_source" for r in items)
    assert "votes" not in value and "motions" not in value
    assert base64.b64decode(result.data["capture"]["content_base64"]) == MEETING_CAPTURE
    found = engine.execute("search", {"bundle": result.data, "query": {"record_types": ["meeting"], "terms": ["Snow Plowing"]}})
    assert len(found.data["hits"]) == 1, found.public_dict()
    exported = engine.execute("export", {"bundle": result.data, "format": "json"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="json") == result.data


def test_default_meeting_view_configured_discovery_and_fetch():
    class Transport:
        def __init__(self): self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            return Response(url, MEETING_CAPTURE, "text/html")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.discover(replace(MEETING_SOURCE, input_format=None))
    assert result.status == "partial" and len(result.data["records"]) == 21, result.public_dict()
    fetched = engine.execute("fetch", {"source": replace(MEETING_SOURCE, input_format=None).public_dict()})
    assert fetched.status == "partial" and len(fetched.data["records"]) == 21, fetched.public_dict()
    assert transport.calls == [MEETING_SOURCE.url, MEETING_SOURCE.url]


def test_observed_cover_sheet_case_variant_preserves_native_identity():
    alternate = replace(SOURCE, url=SOURCE.url.replace("Coversheet.aspx", "CoverSheet.aspx"))
    raw = CAPTURE.replace(b'action="./Coversheet.aspx?', b'action="./CoverSheet.aspx?')
    engine = create_engine()
    before = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    after = engine.normalize(alternate, raw, input_format=alternate.input_format)
    assert after.status == "completed", after.public_dict()
    assert before.data["records"][0]["identity"] == after.data["records"][0]["identity"]


@pytest.mark.parametrize("old,new", [
    (b'action="./MeetingView.aspx?MeetingID=996&amp;MinutesMeetingID=-1&amp;doctype=Agenda"', b'action="./MeetingView.aspx?MeetingID=996&amp;MinutesMeetingID=670&amp;doctype=Agenda"'),
    (b'CoverSheet.aspx?ItemID=12435&amp;MeetingID=996', b'CoverSheet.aspx?ItemID=12435&amp;MeetingID=995'),
    (b'CoverSheet.aspx?ItemID=12512&amp;MeetingID=996', b'CoverSheet.aspx?ItemID=12435&amp;MeetingID=996'),
    (b'href="CoverSheet.aspx?', b'href="https://other.novusagenda.com/agendapublic/CoverSheet.aspx?'),
])
def test_changed_meeting_context_item_parent_duplicate_and_foreign_origin_rejected(old, new):
    assert old in MEETING_CAPTURE
    result = create_engine().normalize(MEETING_SOURCE, MEETING_CAPTURE.replace(old, new), input_format=MEETING_SOURCE.input_format)
    assert result.status == "failed", result.public_dict()
