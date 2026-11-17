import base64
from pathlib import Path

import pytest

from quorumrelay import Source, create_engine
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.storage import SQLiteStorage


CONTENT = (Path(__file__).parent / "fixtures/gworks-published/5017-agenda.html").read_bytes()
SOURCE = Source("gworks", "https://files.frontdeskgworks.com/city/1311/cms/5017_agenda.html",
                input_format="gworks-published-meeting-html")


def test_real_published_capture_maps_sections_children_documents_and_search(tmp_path):
    engine = create_engine(storage=SQLiteStorage(tmp_path / "workflow.sqlite"))
    result = engine.normalize(SOURCE, CONTENT, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record = result.data["records"][0]
    normalized = record["normalized"]
    assert record["identity"]["external_id"] == "5017"
    listing_source = Source("gworks", "https://files.frontdeskgworks.com/city/1311/cms/data.json")
    listing = engine.normalize(listing_source, (Path(__file__).parent / "fixtures/baseline/gworks-1311.response").read_bytes(),
                               input_format="gworks-frontdesk-json")
    listed = next(row for row in listing.data["records"] if row["identity"]["external_id"] == "5017")
    assert all(record["identity"][key] == listed["identity"][key]
               for key in ("provider", "namespace", "record_type", "external_id", "parent"))
    assert normalized["scheduled_start"] == "2026-11-09T18:00:00"
    assert normalized["time_zone_status"] == "unknown"
    assert normalized["title"] == "November 9, 2026 Regular Council Meeting"
    items = normalized["agenda_items"]
    assert len(items) == 24
    assert sum(item["parent_item_external_id"] is None for item in items) == 11
    assert all(item["native_item_id"] is None for item in items)
    attachment = normalized["documents"][1]
    assert attachment["url"].endswith("/city/1311/media/11-09-26packet1.pdf")
    child = next(item for item in items if item["documents"])
    assert attachment["agenda_item_external_id"] == child["external_id"]
    assert child["parent_item_external_id"] == items[2]["external_id"]
    assert record["normalized_sha256"] == canonical_hash(normalized)
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": result.data, "persist": True}).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "workflow.sqlite"))
    found = reopened.execute("search", {"query": {"terms": ["Metronet"]}})
    assert len(found.data["hits"]) == 1, found.public_dict()
    exported = engine.execute("export", {"bundle": result.data, "format": "zip"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == result.data


@pytest.mark.parametrize("before,after", [
    (b"/city/1311/agenda/pdf/5017/", b"/city/9/agenda/pdf/5017/"),
    (b'contentTitle', b'unknownTitle'),
    (b'Nov 9, 2026 6:00 PM', b'unknown'),
])
def test_ambiguous_or_mismatched_metadata_is_rejected(before, after):
    result = create_engine().normalize(SOURCE, CONTENT.replace(before, after), input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


@pytest.mark.parametrize("url", [
    "https://files.frontdeskgworks.com/city/9/cms/5017_agenda.html",
    SOURCE.url + "?city=9",
    SOURCE.url.replace("_agenda.html", "_minutes.html"),
    SOURCE.url.replace("https:", "http:"),
])
def test_source_must_bind_exact_city_meeting_and_rendered_kind(url):
    result = create_engine().normalize(Source("gworks", url, input_format=SOURCE.input_format), CONTENT,
                                       input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


@pytest.mark.parametrize("replacement", [b"/city/9/media/", b"/city/1311/media/%2e%2e/",
                                          b"/city/1311/media/../", b"/city/1311/media/%2f"])
def test_foreign_or_unsafe_attachment_is_not_associated(replacement):
    result = create_engine().normalize(SOURCE, CONTENT.replace(b"/city/1311/media/", replacement),
                                       input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    assert len(result.data["records"][0]["normalized"]["documents"]) == 1


def test_headless_selected_discovery_and_supplied_attachment_transfer():
    class Transport:
        def __init__(self): self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            return Response(url, CONTENT, "text/html") if url == SOURCE.url else Response(url, b"%PDF-synthetic", "application/pdf")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.discover(SOURCE)
    assert result.status == "partial", result.public_dict()
    assert transport.calls == [SOURCE.url]
    record = result.data["records"][0]
    fetched = engine.fetch_attachment(SOURCE, record, index=1, capture=CONTENT)
    assert fetched.status == "completed", fetched.public_dict()
    assert transport.calls[-1] == record["normalized"]["documents"][1]["url"]
