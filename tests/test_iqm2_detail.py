import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.interchange import read_bundle

EVIDENCE = json.loads((Path(__file__).parent / "fixtures/iqm2-detail-1496.capture.json").read_bytes())
CAPTURE = base64.b64decode(EVIDENCE["content_base64"], validate=True)
SOURCE = Source("iqm2", EVIDENCE["source_url"], input_format="iqm2-meeting-detail-html")


def test_exact_public_detail_keeps_native_meeting_files_documents_and_other_meeting_references():
    assert len(CAPTURE) == EVIDENCE["byte_length"] == 89973
    assert hashlib.sha256(CAPTURE).hexdigest() == EVIDENCE["sha256"]
    engine = create_engine()
    result = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    records = result.data["records"]
    assert len(records) == 18
    meeting = records[0]
    normalized = meeting["normalized"]
    assert meeting["identity"]["external_id"] == "1496"
    assert normalized["body"] == "City Council" and normalized["meeting_date"] == "2026-11-17"
    assert normalized["source_start"] == "2026-11-17T17:30:00"
    assert normalized["source_status_literal"] == "" and normalized["source_minutes_id"] is None
    assert normalized["source_agenda_id"] == "1476" and normalized["time_zone_status"] == "unknown"
    assert len(normalized["documents"]) == 63
    assert [(d["source_type"], d["external_id"]) for d in normalized["documents"][:2]] == [("14", "1476"), ("1", "1476")]
    assert all(d["meeting_external_id"] == "1496" for d in normalized["documents"])
    assert len(normalized["agenda_items"]) == 17
    assert len(normalized["related_references"]) == 14
    assert all(ref["meeting_external_id"] != "1496" for ref in normalized["related_references"])
    assert all(r["identity"]["record_type"] == "legislative_file" and r["identity"]["parent"] == meeting["identity"] for r in records[1:])
    assert all(not r["normalized"]["documents"] for r in records[1:])  # FileOpen has meeting context, no explicit file-parent ID.
    assert len(normalized["rendered_agenda_rows"]) == 142
    assert "motion" not in normalized and "vote" not in normalized
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CAPTURE
    found = engine.execute("search", {"bundle": result.data, "query": {"record_types": ["legislative_file"], "terms": ["Landscape Structures"]}})
    assert len(found.data["hits"]) == 1, found.public_dict()
    exported = engine.execute("export", {"bundle": result.data, "format": "json"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="json") == result.data


def test_default_configured_detail_and_separate_supplied_fileopen_attachment_transfer():
    class Transport:
        def __init__(self): self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            return Response(url, CAPTURE, "text/html") if url == SOURCE.url else Response(url, b"%PDF-1.7\nsynthetic iQM2", "application/pdf")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.discover(replace(SOURCE, input_format=None))
    assert result.status == "partial" and len(result.data["records"]) == 18, result.public_dict()
    assert transport.calls == [SOURCE.url]
    record = result.data["records"][0]
    fetched = engine.fetch_attachment(SOURCE, record, index=0, capture=CAPTURE)
    assert fetched.status == "completed", fetched.public_dict()
    assert transport.calls[-1].endswith("FileOpen.aspx?Type=14&ID=1476&Inline=True")
    configured = engine.execute("fetch", {"source": replace(SOURCE, input_format=None).public_dict()})
    assert configured.status == "partial" and len(configured.data["records"]) == 18, configured.public_dict()


@pytest.mark.parametrize("content", [
    CAPTURE.replace(b'id="ContentPlaceholder1_txtMeetingID" value="1496"', b'id="ContentPlaceholder1_txtMeetingID" value="1497"'),
    CAPTURE.replace(b'action="./Detail_Meeting.aspx?ID=1496"', b'action="./Detail_Meeting.aspx?ID=1497"'),
    CAPTURE.replace(b'Type=14&amp;ID=1476', b'Type=14&amp;ID=1477'),
    CAPTURE.replace(b'Type=14&amp;ID=1476', b'Type=1&amp;ID=1476'),
    CAPTURE.replace(b'&ID=7743&', b'&ID=7478&'),
])
def test_public_detail_rejects_changed_meeting_download_binding_or_duplicate_native_file(content):
    assert content != CAPTURE
    result = create_engine().normalize(SOURCE, content, input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


def test_fileopen_other_meeting_context_is_retained_only_as_unassociated_reference():
    content = CAPTURE.replace(b'Type=4&ID=21288&MeetingID=1496', b'Type=4&ID=21288&MeetingID=1400')
    assert content != CAPTURE
    result = create_engine().normalize(SOURCE, content, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    normalized = result.data["records"][0]["normalized"]
    assert len(normalized["documents"]) == 62 and len(normalized["related_references"]) == 15
    assert any(ref.get("source_query", {}).get("ID") == "21288" for ref in normalized["related_references"])
