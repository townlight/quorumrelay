import base64
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.interchange import read_bundle


EVIDENCE = json.loads((Path(__file__).parent / "fixtures/agendaquick-detail-1737.capture.json").read_bytes())
CAPTURE = base64.b64decode(EVIDENCE["content_base64"], validate=True)
SOURCE = Source("destiny-agendaquick", EVIDENCE["source_url"], input_format="agendaquick-public-agenda-html")


def test_exact_captured_agenda_preserves_native_memo_meeting_and_packet_associations():
    assert len(CAPTURE) == EVIDENCE["byte_length"] == 59886
    assert hashlib.sha256(CAPTURE).hexdigest() == EVIDENCE["sha256"]
    engine = create_engine()
    result = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    normalized = record["normalized"]
    assert record["identity"]["external_id"] == "1737"
    assert normalized["body"] == "YUMA COUNTY BOARD OF SUPERVISORS"
    assert normalized["meeting_date"] == "2026-11-02"
    assert normalized["source_time"] == "9:00 A.M."
    assert normalized["time_zone_status"] == "unknown"
    items = normalized["agenda_items"]
    assert len(items) == 25 and len({item["external_id"] for item in items}) == 25
    assert all(item["meeting_external_id"] == "1737" for item in items)
    assert items[0]["external_id"] == "14719" and items[0]["source_line_id"] == "70543"
    assert items[0]["agenda_number"] == "1." and items[0]["source_revision_literal"] == "0"
    assert items[0]["source_cells"][-1]["text"].strip() == "No Action"
    assert "motion" not in items[0] and "vote" not in items[0]
    assert len(normalized["documents"]) == 2
    assert normalized["documents"][1]["kind"] == "packet"
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CAPTURE
    found = engine.execute("search", {"bundle": result.data,
        "query": {"body": normalized["body"], "terms": ["Adoption Day"]}})
    assert found.status == "partial" and len(found.data["hits"]) == 1
    assert found.coverage["incomplete_text"]
    exported = engine.execute("export", {"bundle": result.data, "format": "json"})
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="json") == result.data


def test_default_configured_detail_and_existing_packet_retrieval_are_separate_guarded_reads():
    class Transport:
        def __init__(self): self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            if url == SOURCE.url:
                return Response(url, CAPTURE, "text/html")
            assert url.endswith("1737_11-02-26%20R%20PACKET.pdf")
            return Response(url, b"%PDF-1.7\nsynthetic packet bytes", "application/pdf")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    source = replace(SOURCE, input_format=None)
    result = engine.discover(source)
    assert result.status == "partial", result.public_dict()
    assert result.data["captures"][0]["input_format"] == SOURCE.input_format
    record = result.data["records"][0]
    assert len(record["normalized"]["agenda_items"]) == 25
    assert transport.calls == [SOURCE.url]
    fetched = engine.fetch_attachment(SOURCE, record, index=1, capture=CAPTURE)
    assert fetched.status == "completed", fetched.public_dict()
    assert len(transport.calls) == 2
    assert fetched.data["attachment"]["citation_url"] == record["normalized"]["documents"][1]["url"]


@pytest.mark.parametrize("source,content", [
    (replace(SOURCE, url=SOURCE.url.replace("id=98622", "id=98623")), CAPTURE),
    (replace(SOURCE, url=SOURCE.url.replace("seq=1737", "seq=1738")), CAPTURE),
    (SOURCE, CAPTURE.replace(b"ag&#x3d;1737", b"ag&#x3d;1738", 1)),
    (SOURCE, CAPTURE.replace(b"&amp;seq&#x3d;14740", b"&amp;seq&#x3d;14719", 1)),
], ids=["foreign_tenant", "foreign_meeting", "foreign_parent", "duplicate_item"])
def test_agenda_rejects_cross_tenant_meeting_or_duplicate_item_binding(source, content):
    result = create_engine().normalize(source, content, input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


def test_memo_title_only_revision_preserves_native_identity_and_changes_rich_digest():
    engine = create_engine()
    first = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    changed = CAPTURE.replace(b"Adoption Day", b"Updated Adoption Day", 1)
    second = engine.normalize(SOURCE, changed, input_format=SOURCE.input_format)
    assert second.status == "completed", second.public_dict()
    a, b = first.data["records"][0], second.data["records"][0]
    assert a["identity"] == b["identity"]
    assert a["normalized_sha256"] != b["normalized_sha256"]
