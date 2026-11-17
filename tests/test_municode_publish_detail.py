import base64
from pathlib import Path
import pytest
from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response
from test_municode_publish import RAW, URL, FORMAT

ID = "4a737d59a401417fbd7fd597e964fdba"
ROOT = Path(__file__).parent / "fixtures/municode-publish"

class Network:
    def __init__(self, kind="agenda", fail=False):
        self.calls, self.kind, self.fail = [], kind, fail
    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["allowed_origins"] == ("https://meetings.municode.com",)
        assert not kwargs["allow_redirects"]
        data = RAW if url == URL else (ROOT / f"effingham-{self.kind}.html").read_bytes()
        return Response(url, data, "text/html", 403 if self.fail and url != URL else 200)

@pytest.mark.parametrize("kind,count", [("agenda", 0), ("packet", 293)])
def test_selected_document_preserves_sections_and_links(kind, count):
    network = Network(kind)
    source = Source("municode-meetings", URL, input_format=FORMAT, options={"detail_kind": kind})
    result = create_engine(provider_transport=network).fetch_record(source, ID)
    assert result.status == "partial" and not result.errors, result.public_dict()
    record = result.data["records"][0]
    assert record["identity"]["external_id"] == ID
    sections = record["normalized"]["agenda_sections"]
    assert len(sections) == 19 and sum(len(s["items"]) for s in sections) == 28
    assert sum(len(i["links"]) for s in sections for i in s["items"]) == count
    assert len(result.data["captures"]) == 1
    assert len(network.calls) == 2
    assert network.calls[1][0].endswith("ip=" + ("false" if kind == "agenda" else "true"))
    assert record["text"] and all(t["provenance"]["capture_sha256"] == result.data["capture"]["sha256"] for t in record["text"])


def test_absent_identity_and_failed_detail_remain_bounded():
    n = Network()
    source = Source("municode-meetings", URL, input_format=FORMAT)
    result = create_engine(provider_transport=n).fetch_record(source, "f" * 32)
    assert result.errors and len(n.calls) == 1
    n = Network(fail=True)
    result = create_engine(provider_transport=n).fetch_record(source, ID)
    assert result.status == "partial" and result.errors and result.data["records"][0]["identity"]["external_id"] == ID
    n = Network()
    result = create_engine(provider_transport=n).execute("fetch", {"source": source.public_dict(), "external_id": ID, "bounds": {"max_pages": 1}})
    assert result.errors and len(n.calls) == 1


def test_saved_format_and_malformed_html():
    source = Source("municode-meetings", URL, input_format="municode-publishpage-detail-html", options={"meeting_id": ID, "detail_kind": "agenda"})
    raw = (ROOT / "effingham-agenda.html").read_bytes()
    result = create_engine().normalize(source, raw, input_format=source.input_format)
    assert result.status == "completed" and len(result.data["records"]) == 1
    invalid = create_engine().normalize(source, b"<html>missing</html>", input_format=source.input_format)
    assert invalid.status == "failed"

def test_header_mismatch_and_cancellation_keep_listing():
    class Changed(Network):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            if url != URL:
                return Response(url, response.content.replace(b"November 17, 2026", b"November 18, 2026", 1), "text/html", 200)
            return response
    source = Source("municode-meetings", URL, input_format=FORMAT)
    result = create_engine(provider_transport=Changed()).fetch_record(source, ID)
    assert result.errors and result.data["records"][0]["identity"]["external_id"] == ID
    assert result.data["captures"][0]["retrieval_url"].endswith("ip=false")
    context = OperationContext()
    class Cancel(Network):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            if url != URL:
                context.cancellation.set()
            return response
    result = create_engine(provider_transport=Cancel()).fetch_record(source, ID, context=context)
    assert result.status == "cancelled" and result.data["records"][0]["identity"]["external_id"] == ID


def test_transfer_budget_and_saved_bundle_roundtrip(tmp_path):
    from civic_data_connectors.storage import SQLiteStorage
    from civic_data_connectors.interchange import read_bundle
    source = Source("municode-meetings", URL, input_format=FORMAT)
    network = Network()
    result = create_engine(provider_transport=network).execute("fetch", {"source": source.public_dict(), "external_id": ID, "bounds": {"transfer_bytes": len(RAW) + 2}})
    assert result.errors and result.data["records"][0]["identity"]["external_id"] == ID
    assert network.calls[1][1]["byte_limit"] == 2
    database = tmp_path / "detail.sqlite"
    engine = create_engine(provider_transport=Network(), storage=SQLiteStorage(database))
    result = engine.fetch_record(source, ID)
    imported = engine.execute("import_bundle", {"bundle": result.data, "persist": True})
    reopened = create_engine(storage=SQLiteStorage(database))
    exported = reopened.execute("export", {"bundle_key": imported.data["bundle_key"], "format": "zip"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="zip") == result.data

def test_packet_attachment_capture_verified_transfer():
    raw = (ROOT / "effingham-packet.html").read_bytes()
    origin = "https://mccmeetingspublic.blob.core.usgovcloudapi.net"
    source = Source("municode-meetings", URL, input_format="municode-publishpage-detail-html", options={"meeting_id": ID, "detail_kind": "packet", "download_origins": [origin]})
    class Attachment:
        def request(self, url, **kwargs):
            assert url.startswith(origin + "/") and origin in kwargs["allowed_origins"]
            return Response(url, b"%PDF-1.7 synthetic", "application/pdf", 200)
    engine = create_engine(provider_transport=Attachment())
    normalized = engine.normalize(source, raw, input_format=source.input_format)
    record = normalized.data["records"][0]
    assert record["normalized"]["documents"][0]["kind"] == "supporting_material"
    assert record["normalized"]["agenda_sections"][0]["links"][0]["url"].startswith("https://www.youtube.com/")
    fetched = engine.fetch_attachment(source, record, capture=raw)
    assert fetched.status == "completed", fetched.public_dict()

def test_listing_rejects_cross_origin_selected_ada_link():
    changed = RAW.replace(b"https://meetings.municode.com/adaHtmlDocument/index", b"https://elsewhere.invalid/adaHtmlDocument/index", 1)
    network = Network()
    class BadListing(Network):
        def request(self, url, **kwargs):
            response = super().request(url, **kwargs)
            return Response(url, changed if url == URL else response.content, "text/html", 200)
    network = BadListing()
    result = create_engine(provider_transport=network).fetch_record(Source("municode-meetings", URL, input_format=FORMAT), ID)
    assert result.errors and len(network.calls) == 1

def test_fetched_detail_source_replays_capture():
    source = Source("municode-meetings", URL, input_format=FORMAT)
    engine = create_engine(provider_transport=Network())
    result = engine.fetch_record(source, ID)
    replay = engine.normalize(Source(**result.data["source"]), base64.b64decode(result.data["capture"]["content_base64"]), input_format="municode-publishpage-detail-html")
    assert replay.status == "completed", replay.public_dict()
    assert replay.data["records"][0]["identity"] == result.data["records"][0]["identity"]

def test_fetched_packet_attachment_index_matches_raw_replay():
    origin = "https://mccmeetingspublic.blob.core.usgovcloudapi.net"
    source = Source("municode-meetings", URL, input_format=FORMAT, options={"detail_kind": "packet", "download_origins": [origin]})
    result = create_engine(provider_transport=Network("packet")).fetch_record(source, ID)
    record = result.data["records"][0]
    index = next(i for i, d in enumerate(record["normalized"]["documents"]) if d["kind"] == "supporting_material")
    expected = record["normalized"]["documents"][index]["url"]
    class Attachment:
        def request(self, url, **kwargs):
            assert url == expected
            return Response(url, b"%PDF-1.7 synthetic", "application/pdf", 200)
    fetched = create_engine(provider_transport=Attachment()).fetch_attachment(Source(**result.data["source"]), record, index=index, capture=base64.b64decode(result.data["capture"]["content_base64"]))
    assert fetched.status == "completed", fetched.public_dict()
