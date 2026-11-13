import base64
from dataclasses import replace
import hashlib
from pathlib import Path

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors import compat
from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.clerkbase_detail import enrich_bundle

CAPTURE = (Path(__file__).parent / "fixtures/baseline/clerkbase.response").read_bytes()
SOURCE = Source("clerkbase", "https://clerkshq.com/Content/Richmond-ri/council/2022/apr19_22tc.htm",
                input_format="clerkbase-document-html")


def test_exact_saved_document_text_search_export_and_legacy_parity():
    engine = create_engine()
    result = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    record, = result.data["records"]
    value = record["normalized"]
    assert "American Rescue Plan Funding" in value["document_text"]
    assert any("Ukrainian people" in p["text"] for p in value["document_paragraphs"])
    assert "body" not in value and "votes" not in value and "agenda_items" not in value
    assert record["identity"]["external_id"] == "/content/richmond-ri/council/2022/apr19_22tc.htm"
    assert record["identity"]["derivation"] == "url_path"
    assert record["normalized_sha256"] == canonical_hash(value)
    assert record["text"][0]["provenance"]["capture_sha256"] == hashlib.sha256(CAPTURE).hexdigest()
    assert base64.b64decode(result.data["capture"]["content_base64"]) == CAPTURE
    assert result.data["compatibility"]["meetings"] == compat.read_clerkbase(SOURCE.url, CAPTURE)
    searched = engine.execute("search", {"bundle": result.data, "query": {"terms": ["American Rescue Plan Funding"]}})
    assert len(searched.data["hits"]) == 1, searched.public_dict()
    exported = engine.execute("export", {"bundle": result.data, "format": "json"})
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format="json") == result.data
    assert enrich_bundle(result.data) == result.data


def test_configured_default_document_get_retains_same_rich_text():
    class Transport:
        def __init__(self): self.calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            return Response(url, CAPTURE, "text/html")

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.discover(replace(SOURCE, input_format=None))
    assert result.status == "partial", result.public_dict()
    assert len(result.data["records"]) == 1
    assert "American Rescue Plan Funding" in result.data["records"][0]["normalized"]["document_text"]
    assert transport.calls == [SOURCE.url]


def test_text_revision_changes_rich_digest_without_changing_legacy_identity_or_projection():
    engine = create_engine()
    before = engine.normalize(SOURCE, CAPTURE, input_format=SOURCE.input_format).data
    changed = CAPTURE.replace(b"American Rescue Plan Funding", b"Updated Rescue Plan Funding")
    assert changed != CAPTURE
    after = engine.normalize(SOURCE, changed, input_format=SOURCE.input_format).data
    assert before["records"][0]["identity"] == after["records"][0]["identity"]
    assert before["compatibility"]["meetings"] == after["compatibility"]["meetings"]
    assert before["records"][0]["normalized_sha256"] != after["records"][0]["normalized_sha256"]
    assert before["capture"]["sha256"] != after["capture"]["sha256"]


def test_static_document_text_excludes_navigation_forms_scripts_and_hidden_nodes():
    raw = CAPTURE.replace(b"</body>", b'<nav>navonlytoken</nav><form>formonlytoken</form><script>scriptinjectedtoken</script><p hidden>hiddenonlytoken</p></body>')
    assert raw != CAPTURE
    result = create_engine().normalize(SOURCE, raw, input_format=SOURCE.input_format)
    assert result.status == "completed", result.public_dict()
    value = result.data["records"][0]["normalized"]
    assert all(t not in value["document_text"] for t in ("navonlytoken", "formonlytoken", "scriptinjectedtoken", "hiddenonlytoken"))
    assert all("hiddenonlytoken" not in p["text"] for p in value["document_paragraphs"])
