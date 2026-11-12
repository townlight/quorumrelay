import base64
from dataclasses import replace
from pathlib import Path

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.compat import read_towncloud_agenda
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.providers.towncloud_detail import enrich_bundle


CAPTURE = (Path(__file__).parent / "fixtures/baseline/towncloud-agenda.response").read_bytes()
SOURCE = Source("towncloud", "https://towncloud.io/go/bennett-co/agendas/1033", input_format="towncloud-agenda-html")


def test_existing_saved_format_adds_hierarchy_native_attachments_and_search_export_without_changing_compatibility():
    engine = create_engine()
    result = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    assert result.data["compatibility"]["meetings"] == read_towncloud_agenda(SOURCE.url, CAPTURE)
    record = result.data["records"][0]
    normalized = record["normalized"]
    items = normalized["agenda_items"]
    assert len(items) == 11
    assert all(item["native_item_id"] is None and item["identity_derivation"] == "capture_local_display_position" for item in items)
    assert all(item["external_id"].startswith("capture:" + result.data["capture"]["sha256"]) for item in items)
    assert items[2]["parent_item_external_id"] == items[1]["external_id"]
    assert items[5]["parent_item_external_id"] == items[4]["external_id"]
    assert not items[4]["documents"] and len(items[5]["documents"]) == 1
    assert "October 19" not in items[4]["description"]
    docs = [doc for item in items for doc in item["documents"]]
    assert len(docs) == 8 and {doc["external_id"] for doc in docs} == {"8888", "8880", "8890", "8889", "8876", "8877", "8879", "8875"}
    assert len(normalized["documents"]) == 10
    assert record["normalized_sha256"] == canonical_hash(normalized)
    assert enrich_bundle(result.data) == result.data
    found = engine.execute("search", {"bundle": result.data, "query": {"terms": ["Development Project Status"]}})
    assert len(found.data["hits"]) == 1, found.public_dict()
    exported = engine.execute("export", {"bundle": result.data, "format": "json"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="json") == result.data


def test_default_configured_agenda_preserves_item_attachment_association_for_separate_transfer():
    class Transport:
        def __init__(self): self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            return Response(url, CAPTURE, "text/html") if url == SOURCE.url else Response(url, b"%PDF-1.7\nsynthetic TownCloud", "application/pdf")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.discover(Source(SOURCE.provider, SOURCE.url))
    assert result.status == "partial", result.public_dict()
    record = result.data["records"][0]
    assert transport.calls == [SOURCE.url]
    assert len(record["normalized"]["agenda_items"]) == 11
    denied = engine.fetch_attachment(SOURCE, record, index=2, capture=CAPTURE)
    assert denied.status == "partial" and transport.calls == [SOURCE.url]
    source = replace(SOURCE, options={"download_origins": ["https://towncloud-core-prod.s3.us-west-2.amazonaws.com"]})
    fetched = engine.fetch_attachment(source, record, index=2, capture=CAPTURE)
    assert fetched.status == "completed", fetched.public_dict()
    doc = record["normalized"]["documents"][2]
    assert doc["external_id"] == "8888" and doc["agenda_item_external_id"] == record["normalized"]["agenda_items"][5]["external_id"]
    assert transport.calls[-1] == doc["url"]


def test_foreign_tenant_attachment_is_not_associated():
    content = CAPTURE.replace(b"/uploads/bennett-co/", b"/uploads/other/")
    result = create_engine().normalize(SOURCE, content, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    assert all(not item["documents"] for item in result.data["records"][0]["normalized"]["agenda_items"])


def test_content_revision_preserves_meeting_identity_but_capture_positions_and_rich_hash_change():
    engine = create_engine()
    before = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format).data["records"][0]
    after = engine.normalize(SOURCE, CAPTURE.replace(b"Chair", b"Chairperson"), input_format=SOURCE.input_format).data["records"][0]
    assert before["identity"] == after["identity"]
    assert before["normalized_sha256"] != after["normalized_sha256"]
    assert before["normalized"]["agenda_items"][0]["external_id"] != after["normalized"]["agenda_items"][0]["external_id"]
