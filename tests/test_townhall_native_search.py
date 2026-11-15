import base64
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.interchange import read_bundle
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage

SOURCE = Source("town-hall-streams", "https://www.townhallstreams.com/town.php?id=31")
ROOT = Path(__file__).resolve().parents[1] / "docs/capabilities/evidence/townhall-public-search"
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


def test_actual_keyword_post_maps_39_existing_native_meeting_identities():
    vendor = Transport()
    engine = create_engine(provider_transport=vendor)
    result = engine.execute("search", request(max_records=100))
    assert result.status == "partial", result.public_dict()
    assert len(result.data["hits"]) == len(result.data["bundle"]["records"]) == 39
    record = result.data["bundle"]["records"][0]
    assert record["identity"]["external_id"] == "75394"
    assert record["normalized"]["meeting_date"] == "2026-06-25"
    assert record["normalized"]["time_zone_status"] == "unknown"
    assert record["normalized"]["recordings"][0]["url"].endswith("location_id=31&id=75394")
    assert record["normalized"]["url"] in record["citation_urls"]
    assert vendor.calls[0][0] == SOURCE.url
    kwargs = vendor.calls[0][1]
    assert kwargs["method"] == "POST"
    assert parse_qs(kwargs["body"].decode()) == {"search": ["budget"], "searchbtn": ["Search"]}
    assert not kwargs["allow_redirects"] and kwargs["allowed_origins"] == ("https://www.townhallstreams.com",)
    baseline = engine.normalize(SOURCE, PAGE, input_format="town-hall-streams-html")
    assert [r["identity"]["external_id"] for r in baseline.data["records"]] == [
        r["identity"]["external_id"] for r in result.data["bundle"]["records"]]
    assert not result.coverage["catalog_complete"] and not result.coverage["full_document_text_searched"]


def test_offset_revision_query_binding_and_local_date_filter():
    vendor = Transport()
    engine = create_engine(provider_transport=vendor)
    a = engine.execute("search", request())
    b = engine.execute("search", request(checkpoint=a.coverage["checkpoint"]))
    assert a.status == b.status == "partial" and a.coverage["checkpoint"]
    assert not ({r["identity"]["external_id"] for r in a.data["bundle"]["records"]}
                & {r["identity"]["external_id"] for r in b.data["bundle"]["records"]})
    changed = request(checkpoint=a.coverage["checkpoint"])
    changed["query"]["terms"] = ["other"]
    count = len(vendor.calls)
    assert engine.execute("search", changed).status == "failed" and len(vendor.calls) == count
    vendor.raw += b'\n'
    assert engine.execute("search", request(checkpoint=a.coverage["checkpoint"])).status == "failed"
    filtered = engine.execute("search", request(max_records=100, date_from="2026-06-25", date_to="2026-06-25"))
    assert len(filtered.data["hits"]) == 1
    assert set(parse_qs(vendor.calls[-1][1]["body"].decode())) == {"search", "searchbtn"}


@pytest.mark.parametrize("change", ["body", "type", "source", "term", "saved"])
def test_unsupported_requests_fail_before_transport(change):
    value = request()
    if change == "body":
        value["query"]["body"] = "Council"
    elif change == "type":
        value["query"]["record_types"] = ["document"]
    elif change == "source":
        value["source"]["url"] += "&id=32"
    elif change == "term":
        value["query"]["terms"] = ["<other>"]
    else:
        value["records"] = []
    vendor = Transport()
    assert create_engine(provider_transport=vendor).execute("search", value).status == "failed"
    assert not vendor.calls


@pytest.mark.parametrize("raw", [b'<html>No results</html>', PAGE.replace(b'location_id=31', b'location_id=32')])
def test_unverified_empty_or_cross_location_cannot_complete(raw):
    result = create_engine(provider_transport=Transport(raw)).execute("search", request())
    assert result.status == "failed" and not result.data and not result.coverage["catalog_complete"]


@pytest.mark.parametrize("when", ["before", "transport", "mapping", "deadline"])
def test_interruption_cannot_publish_results(monkeypatch, when):
    from civic_data_connectors.providers import townhall_search as module
    ctx, clock = OperationContext(), [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    if when == "before":
        ctx.cancellation.set()
    vendor = Transport(callback=ctx.cancellation.set if when == "transport" else
        (lambda: clock.__setitem__(0, 2.0)) if when == "deadline" else None)
    if when == "mapping":
        original = module.parse_bundle

        def cancel(*args):
            bundle = original(*args)
            ctx.cancellation.set()
            return bundle

        monkeypatch.setattr(module, "parse_bundle", cancel)
    result = create_engine(provider_transport=vendor).execute("search", request(deadline_seconds=1), context=ctx)
    assert result.status == ("failed" if when == "deadline" else "cancelled") and not result.data


def test_transfer_limit_is_enforced():
    vendor = Transport()
    result = create_engine(provider_transport=vendor).execute("search", request(transfer_bytes=100))
    assert result.status == "failed" and not result.data and vendor.calls[0][1]["byte_limit"] == 100


@pytest.mark.parametrize("format", ["json", "jsonl", "zip"])
def test_capture_identity_locator_and_context_survive_reopen_export(tmp_path, format):
    path = tmp_path / "search.sqlite"
    engine = create_engine(storage=SQLiteStorage(path), provider_transport=Transport())
    bundle = engine.execute("search", request(max_records=100)).data["bundle"]
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": bundle, "persist": True}).status in {"completed", "partial"}
    reopened = create_engine(storage=SQLiteStorage(path))
    local = reopened.execute("search", {"query": {"terms": ["budget"], "limit": 100}})
    assert len(local.data["hits"]) == 39
    exported = reopened.execute("export", {"bundle": bundle, "format": format})
    assert exported.status == "completed", exported.public_dict()
    restored = read_bundle(base64.b64decode(exported.data["content_base64"]), format=format)
    assert restored["records"] == bundle["records"] and restored["extensions"] == bundle["extensions"]
    assert base64.b64decode(restored["capture"]["content_base64"]) == PAGE


@pytest.mark.parametrize("replacement", [b"other", b"Budget", b""])
def test_response_echo_must_match_native_search_expression(replacement):
    old = b'name="search" value="budget"'
    raw = PAGE.replace(old, old.replace(b"budget", replacement))
    assert raw != PAGE
    result = create_engine(provider_transport=Transport(raw)).execute("search", request())
    assert result.status == "failed" and not result.data
    assert not result.coverage["catalog_complete"]


@pytest.mark.parametrize("hidden", [False, True])
def test_duplicate_or_hidden_only_query_controls_cannot_bind_response(hidden):
    field = 'search'
    import re
    pattern = rb"<input\b[^>]*name=[\"']" + field.encode() + rb"[\"'][^>]*>"
    match = re.search(pattern, PAGE)
    assert match
    control = match[0]
    replacement = b"<template>" + control + b"</template>" if hidden else control + control
    raw = PAGE[:match.start()] + replacement + PAGE[match.end():]
    result = create_engine(provider_transport=Transport(raw)).execute("search", request())
    assert result.status == "failed" and not result.data
