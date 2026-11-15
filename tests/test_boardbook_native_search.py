import base64
from pathlib import Path

import pytest

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.interchange import read_bundle
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers.boardbook_search import parse_bundle

SOURCE = Source("boardbook", "https://meetings.boardbook.org/Public/Organization/3307")
ROOT = Path(__file__).resolve().parents[1] / "docs/capabilities/evidence/boardbook-public-search"
PAGE = (ROOT / "results.html").read_bytes()


def request(**bounds):
    return {"source": SOURCE.public_dict(), "native": True, "query": {"terms": ["budget"], "limit": 100},
        "bounds": {"max_records": 2, **bounds}}


class Transport:
    def __init__(self, raw=PAGE, callback=None):
        self.raw, self.callback, self.calls = raw, callback, []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.callback:
            self.callback()
        return Response(url, self.raw, "text/html; charset=utf-8")


def test_actual_42_index_entries_keep_typed_native_ids_without_canonical_parent_inference():
    bundle = parse_bundle(SOURCE, "//meetings.boardbook.org/Public/Organization/3307", PAGE)
    assert len(bundle["records"]) == 42
    assert len({r["identity"]["external_id"] for r in bundle["records"]}) == 42
    first = bundle["records"][0]
    assert first["identity"]["external_id"] == "sparqmeetingsagendaitemtexts:3628623"
    assert first["identity"]["record_type"] == "search_result"
    assert first["identity"]["derivation"] == "vendor_search_index_locator"
    assert first["normalized"]["parent_identity_status"] == "not_supplied"
    assert "budget" in first["text"][0]["text"].lower()
    assert "returnUrl" not in first["text"][0]["citation_url"]


def test_literal_get_exact_local_filter_and_hash_bound_offset_continuation():
    vendor = Transport()
    engine = create_engine(provider_transport=vendor)
    a = engine.execute("search", request())
    assert a.status == "partial", a.public_dict()
    assert len(a.data["hits"]) == 2 and a.coverage["checkpoint"]
    assert not a.coverage["catalog_complete"] and not a.coverage["full_document_text_searched"]
    assert vendor.calls[0][0] == "https://meetings.boardbook.org/Search/Index/3307?q=budget"
    assert vendor.calls[0][1]["allowed_origins"] == ("https://meetings.boardbook.org",)
    assert vendor.calls[0][1]["allow_redirects"] is False
    b = engine.execute("search", request(checkpoint=a.coverage["checkpoint"]))
    assert b.status == "partial", b.public_dict()
    assert not ({r["identity"]["external_id"] for r in a.data["bundle"]["records"]}
                & {r["identity"]["external_id"] for r in b.data["bundle"]["records"]})
    vendor.raw += b'\n'
    revised = engine.execute("search", request(checkpoint=a.coverage["checkpoint"]))
    assert revised.status == "failed" and not revised.data
    changed = request(checkpoint=a.coverage["checkpoint"])
    changed["query"]["terms"] = ["other"]
    calls = len(vendor.calls)
    assert engine.execute("search", changed).status == "failed"
    assert len(vendor.calls) == calls


@pytest.mark.parametrize("replacement", [b'PublicOrgID=3308', b'PublicOrgID=3307&amp;PublicOrgID=3307',
    b'PublicOrgID=3307#other', b'Index=unknown&amp;PublicOrgID=3307'])
def test_cross_org_duplicate_and_unknown_locator_bindings_fail(replacement):
    raw = PAGE.replace(b'PublicOrgID=3307', replacement, 1)
    assert create_engine(provider_transport=Transport(raw)).execute("search", request()).status == "failed"


@pytest.mark.parametrize("change", ["date", "body", "type", "source", "saved", "term"])
def test_unsupported_filters_and_sources_fail_before_transport(change):
    value = request()
    if change == "date":
        value["query"]["date_from"] = "2026-01-01"
    elif change == "body":
        value["query"]["body"] = "Council"
    elif change == "type":
        value["query"]["record_types"] = ["meeting"]
    elif change == "source":
        value["source"]["url"] += "?other=1"
    elif change == "saved":
        value["bundle"] = {}
    else:
        value["query"]["terms"] = ["<other>"]
    vendor = Transport()
    assert create_engine(provider_transport=vendor).execute("search", value).status == "failed"
    assert not vendor.calls


@pytest.mark.parametrize("when", ["before", "transport", "mapping", "deadline"])
def test_interruption_cannot_publish_results(monkeypatch, when):
    from civic_data_connectors.providers import boardbook_search as module
    ctx, clock = OperationContext(), [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    if when == "before":
        ctx.cancellation.set()
    vendor = Transport(callback=ctx.cancellation.set if when == "transport" else
        (lambda: clock.__setitem__(0, 2.0)) if when == "deadline" else None)
    if when == "mapping":
        original = module.parse_bundle

        def cancel(*args):
            result = original(*args)
            ctx.cancellation.set()
            return result

        monkeypatch.setattr(module, "parse_bundle", cancel)
    result = create_engine(provider_transport=vendor).execute("search", request(deadline_seconds=1), context=ctx)
    assert result.status == ("failed" if when == "deadline" else "cancelled") and not result.data


def test_unverified_empty_and_oversized_results_fail_without_complete_empty_claim():
    for raw, limit in [(b'<div id="SearchResults"></div>', 100), (PAGE, 100)]:
        result = create_engine(provider_transport=Transport(raw)).execute("search", request(transfer_bytes=limit))
        assert result.status == "failed" and not result.data and not result.coverage["catalog_complete"]


@pytest.mark.parametrize("format", ["json", "jsonl", "zip"])
def test_saved_capture_ids_citations_excerpts_persist_reopen_and_roundtrip(tmp_path, format):
    path = tmp_path / "search.sqlite"
    engine = create_engine(storage=SQLiteStorage(path), provider_transport=Transport())
    result = engine.execute("search", request(max_records=100))
    assert result.status == "partial" and len(result.data["bundle"]["records"]) == 42
    bundle = result.data["bundle"]
    assert base64.b64decode(bundle["capture"]["content_base64"]) == PAGE
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": bundle, "persist": True}).status in {"completed", "partial"}
    reopened = create_engine(storage=SQLiteStorage(path))
    local = reopened.execute("search", {"query": {"terms": ["budget"], "limit": 100}})
    # Five provider document candidates omit the term from their supplied
    # metadata/excerpts. Never claim their unread document bytes were searched.
    assert len(local.data["hits"]) == 37
    assert {h["record"]["identity"]["external_id"] for h in local.data["hits"]} == {
        h["record"]["identity"]["external_id"] for h in result.data["hits"]}
    exported = reopened.execute("export", {"bundle": bundle, "format": format})
    assert exported.status == "completed", exported.public_dict()
    restored = read_bundle(base64.b64decode(exported.data["content_base64"]), format=format)
    assert restored["records"] == bundle["records"] and restored["extensions"] == bundle["extensions"]
    saved = reopened.execute("normalize", {"source": {**SOURCE.public_dict(), "input_format": "boardbook-public-search-html"}}, content=PAGE)
    assert saved.status == "completed" and len(saved.data["records"]) == 42
