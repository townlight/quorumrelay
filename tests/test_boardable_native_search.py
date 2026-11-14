"""Vendor-client synthetic public search; listing capture alone binds numeric IDs."""

import base64
from copy import deepcopy
from pathlib import Path
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import Engine, OperationContext, Source
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers import register
from civic_data_connectors.providers.boardable_search import native_search
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.native import parse_native

ROOT = "https://site.boardable.com/ventura-county-community-college-district/meetings"
SOURCE = {"provider": "boardable", "url": ROOT}
FIXTURES = Path(__file__).parent / "fixtures/boardable-discovery"
LANDING = (FIXTURES / "tenant-landing.html").read_bytes()
PAGE = (FIXTURES / "page-1.json").read_bytes()
NAMESPACE = "//site.boardable.com/ventura-county-community-college-district"
SLUG = "938b9e-atac-november-12-2026"


class Vendor:
    def __init__(self):
        self.payload = {"meetings": [{"title": "ATAC Board budget", "slug": SLUG,
            "search_highlight": {"agenda": "<em>Budget</em> review<script>Hidden secret</script>"},
            "attachment_matches": [{"id": 1, "title": "Budget", "url": "https://untrusted.invalid/file"}],
            "unknown": [False, None]}], "metadata": {"unknown": True}}
        self.calls = []
        self.fault = None
        self.context = None

    def request(self, url, **options):
        self.calls.append((url, options))
        assert options["allow_redirects"] is False and options["deadline_seconds"] > 0
        if url == ROOT:
            return Response(url, LANDING, "text/html")
        assert urlsplit(url).path == "/api/public-sites/search"
        assert options["headers"]["SiteId"] == "3"
        if self.fault == "timeout":
            raise TimeoutError()
        if self.fault == "cancel":
            self.context.cancellation.set()
        raw = json.dumps(self.payload).encode()
        if self.fault == "oversize":
            raw = b" " * (options["byte_limit"] + 1)
        return Response(url + ("/other" if self.fault == "redirect" else ""), raw,
                        "text/html" if self.fault == "mime" else "application/json",
                        403 if self.fault == "denied" else 200)


def setup(tmp_path, *, capture=True):
    engine = Engine(storage=SQLiteStorage(tmp_path / "search.sqlite"))
    context, vendor = OperationContext(), Vendor()
    vendor.context = context
    register(engine, transport=vendor)
    bundle = parse_native(Source(**SOURCE), NAMESPACE, PAGE, "boardable-public-meetings-json")
    if capture:
        engine.storage.put("captures", bundle["capture"]["sha256"], bundle["capture"], scope=context.scope)
    request = {"source": SOURCE, "native": True, "query": {"terms": ["budget"]}}
    return engine, context, vendor, request, bundle


def test_native_search_uses_exact_client_query_preserves_identity_raw_unknowns_and_excerpt(tmp_path):
    engine, context, vendor, request, listing = setup(tmp_path)
    result = engine.execute("search", request, context=context)
    assert result.status == "partial", result.public_dict()
    assert len(result.data["hits"]) == 1
    record = result.data["records"][0]
    assert record["identity"] == listing["records"][0]["identity"]
    assert record["original"]["unknown"] == [False, None]
    assert record["text"][0]["text"] == "Budget review"
    assert record["text"][0]["completeness"] == "partial"
    assert result.coverage["catalog_complete"] is False
    assert result.coverage["incomplete_text"] is True
    assert len(vendor.calls) == 2  # Never fetch attachments or guessed detail URLs.
    query = parse_qs(urlsplit(vendor.calls[1][0]).query, keep_blank_values=True)
    assert query == {"query": ["budget"], "year": [""], "month": [""], "type": ["meetings"]}
    captures = result.data["bundle"]["captures"]
    assert listing["capture"] in captures
    assert json.loads(base64.b64decode(captures[0]["content_base64"])) == vendor.payload


@pytest.mark.parametrize("fault", ["absent", "hash", "source", "caller", "ambiguous"])
def test_unknown_or_untrusted_listing_binding_never_invents_native_or_slug_id(tmp_path, fault):
    engine, context, vendor, request, listing = setup(tmp_path, capture=False)
    c = deepcopy(listing["capture"])
    if fault == "hash":
        c["content_base64"] = base64.b64encode(PAGE + b" ").decode()
    elif fault == "source":
        c["source_url"] += "/other"
    if fault != "absent":
        engine.storage.put("captures", c["sha256"], c,
            scope="other" if fault == "caller" else context.scope)
    if fault == "ambiguous":
        payload = json.loads(PAGE)
        payload["data"][0]["id"] = 999999
        other = parse_native(Source(**SOURCE), NAMESPACE, json.dumps(payload).encode(), "boardable-public-meetings-json")
        engine.storage.put("captures", other["capture"]["sha256"], other["capture"], scope=context.scope)
    result = engine.execute("search", request, context=context)
    assert result.status == "partial", result.public_dict()
    assert not result.data["hits"] and not result.data["records"]
    assert len(result.data["candidates"]) == 1
    assert result.coverage["failures"][0]["reason"] == "numeric_identity_not_bound_to_listing_capture"


@pytest.mark.parametrize("fault", ["timeout", "redirect", "mime", "denied", "oversize", "cancel", "shape", "duplicate", "unsafe"])
def test_failed_or_cancelled_search_is_not_successful_empty_result(tmp_path, fault):
    engine, context, vendor, request, _ = setup(tmp_path)
    if fault == "shape":
        vendor.payload = {"unknown": []}
    elif fault == "duplicate":
        vendor.payload["meetings"].append(deepcopy(vendor.payload["meetings"][0]))
    elif fault == "unsafe":
        vendor.payload["meetings"][0]["slug"] = "../other"
    else:
        vendor.fault = fault
    result = engine.execute("search", request, context=context)
    assert result.status == ("cancelled" if fault == "cancel" else "failed"), result.public_dict()
    if fault in {"shape", "duplicate", "unsafe"}:
        assert result.data["bundle"]["captures"]  # Preserve received bytes even when mapping fails.
    assert len(vendor.calls) == 2


@pytest.mark.parametrize("fault", ["body", "type", "checkpoint", "empty", "native", "content", "permission"])
def test_unmapped_request_or_scope_fails_before_network(tmp_path, fault):
    engine, context, vendor, request, _ = setup(tmp_path)
    if fault == "body":
        request["query"]["body"] = "Council"
    elif fault == "type":
        request["query"]["record_types"] = ["document"]
    elif fault == "checkpoint":
        request["bounds"] = {"checkpoint": "invented"}
    elif fault == "empty":
        request["query"] = {}
    elif fault == "native":
        request["native"] = False
    elif fault == "content":
        request["content_base64"] = "e30="
    else:
        context.allowed_namespaces = frozenset({"other"})
    if fault in {"native", "content"}:
        with pytest.raises(ValueError):
            native_search(engine, request, None, context, transport=vendor)
    else:
        result = engine.execute("search", request, context=context)
        assert result.status == "failed", result.public_dict()
    assert not vendor.calls


def test_exact_terms_phrases_date_filter_and_truncation_are_qualified(tmp_path):
    engine, context, vendor, request, _ = setup(tmp_path)
    request["query"] = {"terms": ["budget"], "phrases": ["budget review"],
                        "date_from": "2026-11-01", "date_to": "2026-11-30"}
    vendor.payload["meetings"].append({"title": "Unresolved", "slug": "other"})
    request["bounds"] = {"max_records": 1}
    result = engine.execute("search", request, context=context)
    assert result.status == "partial" and len(result.data["hits"]) == 1, result.public_dict()
    assert result.coverage["truncated"] is True and result.coverage["checkpoint"] is None
    query = parse_qs(urlsplit(vendor.calls[1][0]).query, keep_blank_values=True)
    assert query["year"] == ["2026"] and query["month"] == ["11"]


def test_search_capture_import_reopen_zip_retains_native_identity_and_supplied_excerpt(tmp_path):
    from quorumrelay import create_engine
    _, context, vendor, request, listing = setup(tmp_path)
    engine = create_engine(storage=SQLiteStorage(tmp_path / "workflow.sqlite"), provider_transport=vendor)
    assert engine.execute("import_bundle", {"bundle": listing, "persist": True}, context=context).status == "completed"
    vendor.payload["meetings"][0]["attachment_matches"][0]["context"] = "<em>Appropriation</em> note"
    result = engine.execute("search", request, context=context)
    assert result.status == "partial", result.public_dict()
    bundle = result.data["bundle"]
    assert bundle["records"][0]["identity"] == listing["records"][0]["identity"]
    for _ in range(2):
        imported = engine.execute("import_bundle", {"bundle": bundle, "persist": True}, context=context)
        assert imported.status == "completed", imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / "workflow.sqlite"))
    assert len(list(reopened.storage.list("records", scope=context.scope))) == len(listing["records"])
    assert reopened.execute("search", {"query": {"terms": ["Appropriation"]}}, context=context).data["hits"]
    exported = reopened.execute("export", {"bundle": bundle, "format": "zip"}, context=context)
    assert exported.status == "completed", exported.public_dict()
    destination = create_engine(storage=SQLiteStorage(tmp_path / "restored.sqlite"))
    restored = destination.execute("import_bundle", {"format": "zip", "persist": True}, context=context,
        content=base64.b64decode(exported.data["content_base64"]))
    assert restored.status == "completed", restored.public_dict()
    record = restored.data["bundle"]["records"][0]
    assert record["identity"] == listing["records"][0]["identity"]
    assert record["original"] == vendor.payload["meetings"][0]
    assert record["text"] == bundle["records"][0]["text"]
    assert record["extensions"] == bundle["records"][0]["extensions"]
