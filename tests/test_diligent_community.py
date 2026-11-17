"""Community read acceptance from captured vendor responses; no vendor writes."""
import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.engine import source_identity_key
from quorumrelay.providers.contracts import Response
from quorumrelay.providers.diligent_community import DOCUMENTS, MEETINGS
from quorumrelay.storage import SQLiteStorage
from quorumrelay.interchange import read_bundle, write_bundle

FIXTURES = Path(__file__).parent / "fixtures" / "diligent_community"
BASE = "https://boonecountyil.community.diligentoneplatform.com"
SOURCE = Source("diligent-community", BASE, namespace="//boonecountyil.community.diligentoneplatform.com")
RANGE = {"date_from": "2026-11-01", "date_to": "2026-11-16"}
LIST = (FIXTURES / "meetings.json").read_bytes()
DOCS = (FIXTURES / "meeting-documents.json").read_bytes()
DETAIL = (FIXTURES / "meeting-data.json").read_bytes()


class Transport:
    def __init__(self, listing=LIST, docs=DOCS, status=200, redirect=False, cancel=None):
        self.listing, self.docs, self.status, self.redirect, self.cancel = listing, docs, status, redirect, cancel
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append(url)
        assert kwargs.get("method", "GET") == "GET" and kwargs.get("body") is None
        assert kwargs["allowed_origins"] == (BASE,) and kwargs["allow_redirects"] is False
        data, mime = (self.docs, "application/json") if url.endswith("meetingDocuments") else (
            (DETAIL, "application/json") if url.endswith("meetingData") else (
                (b"%PDF-1.7\nsynthetic document", "application/pdf") if "/document/" in url else (self.listing, "application/json")))
        if self.cancel:
            self.cancel.cancellation.set()
        return Response(url + "/wrong" if self.redirect else url, data, mime, self.status)


def discover(transport=None, source=SOURCE, **bounds):
    transport = transport or Transport()
    result = create_engine(provider_transport=transport).execute("discover", {
        "source": source.public_dict(), "bounds": {**RANGE, **bounds}})
    return result, transport


def test_registered_separately_and_writes_not_claimed():
    engine = create_engine()
    assert engine.execute("identify", {"url": BASE}).data["provider"] == SOURCE.provider
    row = engine.execute("capabilities", {"provider": SOURCE.provider}).data["providers"][0]
    assert len(row["additional_formats"]) == 3
    assert row["capabilities"]["operations"]["create"]["implementation_status"] == "not_implemented"
    assert engine.plan_write(SOURCE, {"changes": []}).status in {"failed", "unsupported"}
    assert len(engine.providers().data["formats"]) == 34


@pytest.mark.parametrize("encoded", [False, True])
def test_saved_fetch_uses_supplied_bytes_without_network(encoded):
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    request = {"source": SOURCE.public_dict(), "bounds": RANGE}
    if encoded:
        request["content_base64"] = base64.b64encode(LIST).decode()
    result = engine.execute("fetch", request, content=None if encoded else LIST)
    assert result.status == "partial", result.public_dict()
    assert len(result.data["records"]) == 3
    assert base64.b64decode(result.data["capture"]["content_base64"]) == LIST
    assert not transport.calls


@pytest.mark.parametrize("selector", [{"external_id": "1655"}, {"parent_id": "1655", "record_type": "document"}, {"attachment": {"record_key": "x"}}])
def test_saved_fetch_rejects_mixed_selection_without_network(selector):
    transport = Transport()
    result = create_engine(provider_transport=transport).execute("fetch", {
        "source": SOURCE.public_dict(), "content_base64": base64.b64encode(LIST).decode(), **selector})
    assert result.status == "failed"
    assert not transport.calls


def test_listing_filters_preserves_exact_capture_and_resumes_without_duplicates():
    first, transport = discover(max_records=1)
    assert first.status == "partial", first.public_dict()
    assert len(transport.calls) == 1 and "loadall=false" in transport.calls[0]
    assert first.data["records"][0]["identity"]["external_id"] == "1655"
    assert base64.b64decode(first.data["captures"][0]["content_base64"]) == LIST
    second, _ = discover(checkpoint=first.coverage["checkpoint"])
    assert {r["identity"]["external_id"] for r in second.data["records"]} == {"1654", "1659"}
    assert second.coverage["checkpoint"] is None and not second.coverage["catalog_complete"]
    filtered, _ = discover(source=replace(SOURCE, body="Committee of the Whole Meeting - Finance"))
    assert len(filtered.data["records"]) == 1


def test_resume_rejects_changed_response_or_scope():
    first, _ = discover(max_records=1)
    token = first.coverage["checkpoint"]
    changed, _ = discover(Transport(listing=LIST + b" "), checkpoint=token)
    assert changed.status == "failed"
    changed, _ = discover(checkpoint=token, date_from="2026-11-02")
    assert changed.status == "failed"


@pytest.mark.parametrize("listing", [b"<html>login</html>", b"{}", b"[null]", b'[{"Id":true}]'])
def test_malformed_listing_fails_instead_of_claiming_empty(listing):
    assert discover(Transport(listing=listing))[0].status == "failed"


@pytest.mark.parametrize("mutation", ["status", "redirect", "parser", "transfer", "cancel"])
def test_response_guards(mutation):
    context = OperationContext()
    transport = Transport(status=403 if mutation == "status" else 200,
                          redirect=mutation == "redirect", cancel=context if mutation == "cancel" else None)
    bounds = {**RANGE, **({"parser_bytes": 10} if mutation == "parser" else {}),
              **({"transfer_bytes": 10} if mutation == "transfer" else {})}
    result = create_engine(provider_transport=transport).execute("discover", {"source": SOURCE.public_dict(), "bounds": bounds}, context=context)
    assert result.status == ("cancelled" if mutation == "cancel" else "failed")


def test_empty_and_unpublished_are_partial_and_not_catalog_proof():
    result, _ = discover(Transport(listing=b"[]"))
    assert result.status == "partial" and not result.data["records"] and result.coverage["catalog_complete"] is False
    values = json.loads(LIST)
    values[0]["Published"] = False
    result, _ = discover(Transport(listing=json.dumps(values).encode()))
    assert len(result.data["records"]) == 2


def test_detail_and_documents_keep_identity_html_text_and_public_attachment_membership():
    engine = create_engine(provider_transport=Transport())
    detail = engine.fetch_record(SOURCE, "1655")
    assert detail.status == "partial" and detail.data["records"][0]["normalized"]["meeting_date"] is None
    docs = engine.fetch_related(SOURCE, "1655", "document")
    assert docs.status == "partial", docs.public_dict()
    assert len(docs.data["records"]) == 1  # nonpublic PDF42882 is not a downloadable record
    record = docs.data["records"][0]
    assert record["identity"]["parent"]["external_id"] == "1655"
    assert "Call to Order" in record["normalized"]["description"]
    assert record["normalized"]["source_html"] == json.loads(DOCS)["Documents"][0]["Html"]
    assert len(record["normalized"]["documents"]) > 1
    assert all("42882" not in d["url"] for d in record["normalized"]["documents"])
    assert base64.b64decode(docs.data["capture"]["content_base64"]) == DOCS


def test_wrong_parent_or_private_types_never_become_download_targets():
    values = json.loads(DOCS)
    values["Documents"][0]["MeetingId"] = 99
    result = create_engine(provider_transport=Transport(docs=json.dumps(values).encode())).fetch_related(SOURCE, "1655", "document")
    assert result.status == "failed"
    values["Documents"][0]["MeetingId"] = 1655
    values["Documents"][0]["DocumentType"] = 5  # closed agenda, even with IsPublic=true
    result = create_engine(provider_transport=Transport(docs=json.dumps(values).encode())).fetch_related(SOURCE, "1655", "document")
    assert not result.data["records"]


def test_saved_discovery_bounds_and_no_network():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    source = replace(SOURCE, input_format=MEETINGS)
    result = engine.execute("discover", {"source": source.public_dict(), "bounds": {"max_records": 1}}, content=LIST)
    assert result.status == "partial" and len(result.data["records"]) == 1, result.public_dict()
    assert not transport.calls
    assert engine.normalize(source, LIST, input_format=MEETINGS, bounds=Bounds(parser_bytes=10)).status == "failed"


@pytest.mark.parametrize("url", ["http://boonecountyil.community.diligentoneplatform.com", "https://example.org", "https://boonecountyil.community.diligentoneplatform.com.evil.example"])
def test_wrong_tenant_host_fails_before_network(url):
    result, transport = discover(source=Source(SOURCE.provider, url))
    assert result.status == "failed" and not transport.calls


def test_namespace_policy_before_network():
    transport = Transport()
    ctx = OperationContext(allowed_namespaces=frozenset({"//elsewhere.example"}))
    result = create_engine(provider_transport=transport).execute("discover", {"source": SOURCE.public_dict(), "bounds": RANGE}, context=ctx)
    assert result.status == "failed" and not transport.calls


@pytest.mark.parametrize("failure", ["html", "html_octet", "pdf", "empty", "large", "cross_scope"])
def test_file_failure_retains_record_without_returning_false_download(tmp_path, failure):
    class FileTransport(Transport):
        def request(self, url, **kwargs):
            self.calls.append(url)
            data, mime = {"html": (b"<html>Sign in</html>", "text/html"),
                          "html_octet": (b"<html>Login", "application/octet-stream"),
                          "pdf": (b"<html>Challenge</html>", "application/pdf"),
                          "empty": (b"", "application/pdf"),
                          "large": (b"%PDF-1.7" * 10, "application/pdf")}.get(failure, (b"%PDF-1.7", "application/pdf"))
            return Response(url, data, mime)
    transport = FileTransport()
    engine = create_engine(storage=SQLiteStorage(tmp_path / "files.sqlite"), provider_transport=transport)
    parsed = engine.normalize(SOURCE, DOCS, input_format=DOCUMENTS)
    engine.execute("import_bundle", {"bundle": parsed.data, "persist": True})
    record = parsed.data["records"][0]
    result = engine.fetch_attachment(SOURCE, record, index=1, bounds=Bounds(transfer_bytes=20),
                                    context=OperationContext(principal="other") if failure == "cross_scope" else None)
    assert result.status == "failed"
    if failure == "cross_scope":
        assert not transport.calls
    else:
        assert result.data["record"] == record and result.data["attachment"] is None


def test_download_revalidates_scoped_record_and_preserves_bytes_after_reopen(tmp_path):
    storage = SQLiteStorage(tmp_path / "community.sqlite")
    transport = Transport()
    engine = create_engine(storage=storage, provider_transport=transport)
    parsed = engine.normalize(SOURCE, DOCS, input_format=DOCUMENTS)
    record = parsed.data["records"][0]
    key = source_identity_key(record["identity"])
    imported = engine.execute("import_bundle", {"bundle": parsed.data, "persist": True})
    assert imported.status == "completed", imported.public_dict()
    storage = SQLiteStorage(tmp_path / "community.sqlite")
    engine = create_engine(storage=storage, provider_transport=transport)
    found = engine.execute("search", {"query": {"terms": ["Finance"]}})
    assert found.status == "partial" and found.data["hits"]  # captured subset, not complete upstream coverage
    for fmt in ("json", "jsonl", "zip"):
        output = io.BytesIO()
        write_bundle(parsed.data, output, format=fmt)
        assert read_bundle(output.getvalue(), format=fmt) == parsed.data
    result = engine.fetch_attachment(SOURCE, record, index=1)
    assert result.status == "completed", result.public_dict()
    raw = base64.b64decode(result.data["attachment"]["content_base64"])
    assert hashlib.sha256(raw).hexdigest() == result.data["attachment"]["sha256"]
    assert raw.startswith(b"%PDF-")
    tampered = deepcopy(record)
    tampered["normalized"]["documents"][1]["url"] = BASE + "/document/99999"
    storage.put("records", key, tampered, scope=OperationContext().scope)
    calls = len(transport.calls)
    assert engine.fetch_attachment(SOURCE, record, index=1).status == "failed"
    assert len(transport.calls) == calls
