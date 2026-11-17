"""Actual declared Peak feed shapes; no publication/meeting-date identity conflation."""
import base64
from dataclasses import replace
from pathlib import Path

import pytest
from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response

SOURCE = Source("peak", "https://lowermerion.granicus.com/ViewPublisherRSS.php?view_id=1&mode=agendas",
                input_format="peak-publication-rss-xml")
CONTENT = (Path(__file__).parent / "fixtures/peak-rss/agendas.xml").read_bytes()
MINUTES = (Path(__file__).parent / "fixtures/peak-rss/minutes.xml").read_bytes()


class Network:
    def __init__(self, content=CONTENT, *, mime="text/xml", url=SOURCE.url):
        self.calls, self.content, self.mime, self.url = [], content, mime, url

    def request(self, url, **options):
        self.calls.append((url, options))
        assert url == SOURCE.url and options["allow_redirects"] is False
        assert options["allowed_origins"] == ("https://lowermerion.granicus.com",)
        return Response(self.url, self.content, self.mime)


def test_actual_agenda_feed_retains_publication_guid_raw_fields_and_document_locator():
    result = create_engine().normalize(SOURCE, CONTENT, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    assert len(result.data["records"]) == 4
    row = result.data["records"][0]
    assert row["identity"]["record_type"] == "document_publication" and row["identity"]["parent"] is None
    assert row["identity"]["external_id"] == "ddb284ee-ceed-11f1-89ef-005056a84798"
    value = row["normalized"]
    assert value["source_event_id"] == "179" and value["source_view_id"] == "1"
    assert value["source_published"] == "Fri, 13 Nov 2026 08:27:21 -0800"
    assert "meeting_date" not in value and "source_time" not in value
    assert value["meeting_identity"] == "not_established"
    assert value["documents"][0]["url"].endswith("AgendaViewer.php?view_id=1&event_id=179")
    assert value["source_publication_parts"]["tz"] == "8"
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CONTENT


def test_empty_minutes_feed_is_observed_empty_not_an_invented_nonempty_schema():
    source = replace(SOURCE, url=SOURCE.url.replace("agendas", "minutes"))
    result = create_engine().normalize(source, MINUTES, input_format=source.input_format)
    assert result.status == "completed" and result.data["records"] == [], result.public_dict()
    assert base64.b64decode(result.data["capture"]["content_base64"]) == MINUTES


def test_configured_default_feed_discovery_reopen_search_and_zip_preserve_source(tmp_path):
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"), provider_transport=network)
    context = OperationContext(principal="reader", client_id="app", tenant="town")
    result = engine.discover(replace(SOURCE, input_format=None), context=context)
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert len(network.calls) == 1 and len(result.data["records"]) == 4
    assert result.coverage["source_complete"] is False
    assert result.coverage["publication_time_is_meeting_time"] is False
    bundle = result.data
    assert engine.execute("import_bundle", {"bundle": bundle, "persist": True}, context=context).status == "completed"
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "data.sqlite"))
    found = reopened.execute("search", {"query": {"phrases": ["Board of Commissioners"]}}, context=context)
    assert found.data["hits"], found.public_dict()
    exported = reopened.execute("export", {"format": "zip", "bundle": bundle}, context=context)
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == bundle


def test_local_feed_resume_uses_capture_hash_and_date_filter_does_not_use_publication_time():
    network = Network()
    engine = create_engine(provider_transport=network)
    bounds = Bounds(max_records=2, date_from="2030-01-01", date_to="2030-01-02")
    first = engine.discover(SOURCE, bounds=bounds)
    assert len(first.data["records"]) == 2 and first.coverage["checkpoint"], first.public_dict()
    assert len(first.coverage["unknown_date_records"]) == 2
    second = engine.discover(SOURCE, bounds=replace(bounds, checkpoint=first.coverage["checkpoint"]))
    assert len(second.data["records"]) == 2 and not second.coverage["checkpoint"]
    assert {r["identity"]["external_id"] for r in first.data["records"]}.isdisjoint(
        r["identity"]["external_id"] for r in second.data["records"])
    network.content = CONTENT.replace(b"Board of Commissioners", b"Changed publication")
    changed = engine.discover(SOURCE, bounds=replace(bounds, checkpoint=first.coverage["checkpoint"]))
    assert changed.errors and not changed.data["records"]


@pytest.mark.parametrize("data", [
    CONTENT.replace(b"mode=agendas", b"mode=podcast"),
    CONTENT.replace(b"event_id=179", b"event_id=180&amp;other=1"),
    CONTENT.replace(b"event_id=179", b"event_id=180&other=1"),
    CONTENT.replace(b"AgendaViewer.php", b"MinutesViewer.php"),
    CONTENT.replace(b"isPermaLink=\"false\"", b"isPermaLink=\"true\""),
    CONTENT.replace(b"ddb284ee-ceed-11f1-89ef-005056a84798", b"not-a-native-guid"),
    CONTENT.replace(b"<channel>", b"<channel><guid>unrelated</guid><link>https://example.com</link>"),
    CONTENT.replace(b"<rss ", b"<!DOCTYPE rss [<!ENTITY x 'bad'>]><rss "),
])
def test_unbound_malformed_or_entity_feed_rejects_without_invented_records(data):
    assert data != CONTENT
    result = create_engine().normalize(SOURCE, data, input_format=SOURCE.input_format)
    assert result.status == "failed", result.public_dict()


@pytest.mark.parametrize("url", [SOURCE.url+"&view_id=2", SOURCE.url.replace("view_id=1", "view_id=0"),
    SOURCE.url.replace("mode=agendas", "mode=podcast"), SOURCE.url+"#fragment"])
def test_unmapped_feed_selection_rejects_before_network(url):
    network = Network()
    result = create_engine(provider_transport=network).discover(replace(SOURCE, url=url))
    assert result.status == "failed" and not network.calls, result.public_dict()


@pytest.mark.parametrize("mime,url", [("text/html", SOURCE.url), ("text/xml", SOURCE.url+"&other=1")])
def test_exact_response_and_mime_are_required(mime, url):
    result = create_engine(provider_transport=Network(mime=mime, url=url)).discover(SOURCE)
    assert result.status == "failed" and result.errors, result.public_dict()


def test_current_transfer_limit_and_pre_cancel_are_respected():
    network = Network()
    engine = create_engine(provider_transport=network)
    result = engine.discover(SOURCE, bounds=Bounds(transfer_bytes=len(CONTENT)-1))
    assert result.errors and network.calls[0][1]["byte_limit"] == len(CONTENT)-1
    context = OperationContext()
    context.cancellation.set()
    assert engine.discover(SOURCE, context=context).status == "cancelled"
    assert len(network.calls) == 1
