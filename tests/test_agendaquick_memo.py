import base64
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.interchange import read_bundle


EVIDENCE = json.loads((Path(__file__).parent / "fixtures/agendaquick-memo-14719.capture.json").read_bytes())
CAPTURE = base64.b64decode(EVIDENCE["content_base64"], validate=True)
SOURCE = Source("destiny-agendaquick", EVIDENCE["source_url"], input_format="agendaquick-public-memo-html")


def test_exact_memo_maps_native_parent_sections_and_supplied_attachment_search_export():
    assert len(CAPTURE) == EVIDENCE["byte_length"] == 13777
    assert hashlib.sha256(CAPTURE).hexdigest() == EVIDENCE["sha256"]
    engine = create_engine()
    result = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == "14719"
    assert record["identity"]["parent"]["external_id"] == "1737"
    normalized = record["normalized"]
    assert normalized["title"] == "Proclamation: Adoption Day"
    assert normalized["meeting_date"] == "2026-11-02"
    assert len(normalized["sections"]) == 6
    assert normalized["sections"][1]["text"] == normalized["sections"][2]["text"] == ""
    assert "motion" not in normalized and "vote" not in normalized and "body" not in normalized
    assert normalized["documents"][0]["url"].endswith("14719_Adoption_Day_2026.pdf")
    assert len(record["text"]) == 3
    found = engine.execute("search", {"bundle": result.data, "query": {"terms": ["Approved as to form"]}})
    assert len(found.data["hits"]) == 1, found.public_dict()
    exported = engine.execute("export", {"bundle": result.data, "format": "json"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="json") == result.data
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CAPTURE


def test_configured_memo_discovery_and_separate_capture_bound_attachment():
    class Transport:
        def __init__(self): self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            return Response(url, CAPTURE, "text/html") if url == SOURCE.url else Response(url, b"%PDF-1.7\nsynthetic", "application/pdf")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.discover(replace(SOURCE, input_format=None))
    assert result.status == "partial", result.public_dict()
    assert transport.calls == [SOURCE.url]
    record = result.data["records"][0]
    fetched = engine.fetch_attachment(SOURCE, record, index=0, capture=CAPTURE)
    assert fetched.status == "completed", fetched.public_dict()
    assert transport.calls[-1] == record["normalized"]["documents"][0]["url"]


@pytest.mark.parametrize("source,content", [
    (replace(SOURCE, url=SOURCE.url.replace("id=98622", "id=98623")), CAPTURE),
    (replace(SOURCE, url=SOURCE.url.replace("ag=1737", "ag=1738")), CAPTURE),
    (replace(SOURCE, url=SOURCE.url.replace("seq=14719&", "seq=14720&")), CAPTURE),
    (SOURCE, CAPTURE.replace(b"rev_num=0", b"rev_num=1")),
    (SOURCE, CAPTURE.replace(b"popupAttachments('/yumacdocs/", b"popupAttachments('https://evil.example/")),
    (SOURCE, CAPTURE.replace(b"1. REQUESTED BOARD ACTION:", b"1. UNKNOWN STRUCTURE:")),
])
def test_memo_rejects_foreign_identity_or_unsafe_unrecognized_structure(source, content):
    result = create_engine().normalize(source, content, input_format=source.input_format)
    assert result.status == "failed", result.public_dict()
