import base64
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.interchange import read_bundle
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers.telvue_search import parse_bundle

PLAYER = "4jeRlBTetCoFJdyT5ssIvBrB9VUvRN0M"
SOURCE = Source("telvue", f"https://videoplayer.telvue.com/player/{PLAYER}/videos")
ROOT = Path(__file__).resolve().parents[1] / "docs/capabilities/evidence/telvue-public-search"
PAGE = (ROOT / "results.html").read_bytes()


def request(**bounds):
    return {"source": SOURCE.public_dict(), "native": True, "query": {"terms": ["council"], "limit": 100},
        "bounds": {"max_records": 2, **bounds}}


class Transport:
    def __init__(self, raw=PAGE, callback=None):
        self.raw, self.callback, self.calls = raw, callback, []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.callback:
            self.callback()
        return Response(url, self.raw, "text/html; charset=utf-8")


def test_actual_43_native_media_ids_and_query_echo_does_not_prove_local_match():
    vendor = Transport()
    result = create_engine(provider_transport=vendor).execute("search", request(max_records=100))
    assert result.status == "partial", result.public_dict()
    assert len(result.data["bundle"]["records"]) == 43 and len(result.data["hits"]) == 22
    assert result.coverage["provider_declared_total"] == 43
    assert result.coverage["provider_remaining_unretrieved"] == 0
    first = result.data["bundle"]["records"][0]
    assert first["identity"]["external_id"] == "1066963" and first["identity"]["record_type"] == "recording"
    assert first["normalized"]["meeting_date"] == "2026-11-03"
    assert first["normalized"]["date_derivation"] == "calendar_date_in_supplied_title"
    assert first["normalized"]["time_zone_status"] == "unknown"
    assert first["relationships"][0]["value"]["url"] in first["citation_urls"]
    assert "terms=council" in first["relationships"][0]["value"]["url"]
    # Planning Board is a provider candidate, with query-bearing locators,
    # but cannot match locally without supplied matching text.
    assert "Planning Board" in result.data["bundle"]["records"][1]["normalized"]["title"]
    assert "1066784" not in {h["identity"]["external_id"] for h in result.data["hits"]}
    fields = parse_qs(urlsplit(vendor.calls[0][0]).query)
    assert fields == {"showtabssearch": ["true"], "fullscreen": ["false"], "search": ["council"]}
    assert not vendor.calls[0][1]["allow_redirects"]
    assert not result.coverage["full_document_text_searched"] and not result.coverage["catalog_complete"]


def test_offset_revision_query_binding_and_local_dates():
    vendor = Transport()
    engine = create_engine(provider_transport=vendor)
    a = engine.execute("search", request())
    b = engine.execute("search", request(checkpoint=a.coverage["checkpoint"]))
    assert a.status == b.status == "partial" and a.coverage["checkpoint"]
    assert not ({r["identity"]["external_id"] for r in a.data["bundle"]["records"]}
                & {r["identity"]["external_id"] for r in b.data["bundle"]["records"]})
    value = request(checkpoint=a.coverage["checkpoint"])
    value["query"]["terms"] = ["other"]
    calls = len(vendor.calls)
    assert engine.execute("search", value).status == "failed" and len(vendor.calls) == calls
    vendor.raw += b'\n'
    assert engine.execute("search", request(checkpoint=a.coverage["checkpoint"])).status == "failed"
    filtered = engine.execute("search", request(max_records=100, date_from="2026-11-03", date_to="2026-11-03"))
    assert len(filtered.data["hits"]) == 1
    assert "date_from" not in parse_qs(urlsplit(vendor.calls[-1][0]).query)


@pytest.mark.parametrize("change", ["body", "type", "playlist", "source", "term", "saved"])
def test_unsupported_requests_never_broaden_playlist_scope_or_retrieve(change):
    value = request()
    if change == "body":
        value["query"]["body"] = "Council"
    elif change == "type":
        value["query"]["record_types"] = ["meeting"]
    elif change == "playlist":
        value["source"]["url"] = SOURCE.url.replace("/videos", "/playlists/1757")
    elif change == "source":
        value["source"]["url"] += "?other=1"
    elif change == "term":
        value["query"]["terms"] = ["<other>"]
    else:
        value["records"] = []
    vendor = Transport()
    assert create_engine(provider_transport=vendor).execute("search", value).status == "failed"
    assert not vendor.calls


@pytest.mark.parametrize("raw", [b'<html>No results</html>',
    PAGE.replace(f'/player/{PLAYER}/videos/search/1066963'.encode(), b'/player/other-player/videos/search/1066963'),
    PAGE.replace(b'data-video-id="1066963"', b'data-video-id="999"', 1),
    PAGE.replace(b'vid_type=medium', b'vid_type=playlist', 1),
    PAGE.replace(b'vid_type=medium&amp;showtabssearch=true&amp;fullscreen=false',
        b'vid_type=medium&amp;showtabssearch=true&amp;fullscreen=false&amp;fullscreen=false', 1)])
def test_unverified_empty_and_mismatched_native_locators_fail(raw):
    result = create_engine(provider_transport=Transport(raw)).execute("search", request())
    assert result.status == "failed" and not result.data and not result.coverage["catalog_complete"]


@pytest.mark.parametrize("when", ["before", "transport", "mapping", "deadline"])
def test_interruption_cannot_publish_results(monkeypatch, when):
    from civic_data_connectors.providers import telvue_search as module
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


def test_transfer_limit_and_declared_unretrieved_count_are_explicit():
    result = create_engine(provider_transport=Transport()).execute("search", request(transfer_bytes=100))
    assert result.status == "failed" and not result.data
    raw = PAGE.replace(b'data-total-available-count="43"', b'data-total-available-count="50"')
    result = create_engine(provider_transport=Transport(raw)).execute("search", request(max_records=100))
    assert result.status == "partial" and result.coverage["provider_remaining_unretrieved"] == 7
    assert result.coverage["checkpoint"] is None and not result.coverage["catalog_complete"]


@pytest.mark.parametrize("format", ["json", "jsonl", "zip"])
def test_capture_native_links_and_exact_hits_survive_reopen_export(tmp_path, format):
    path = tmp_path / "search.sqlite"
    engine = create_engine(storage=SQLiteStorage(path), provider_transport=Transport())
    searched = engine.execute("search", request(max_records=100))
    bundle = searched.data["bundle"]
    for _ in range(2):
        assert engine.execute("import_bundle", {"bundle": bundle, "persist": True}).status in {"completed", "partial"}
    reopened = create_engine(storage=SQLiteStorage(path))
    local = reopened.execute("search", {"query": {"terms": ["council"], "limit": 100}})
    assert len(local.data["hits"]) == 22
    assert {h["identity"]["external_id"] for h in local.data["hits"]} == {
        h["identity"]["external_id"] for h in searched.data["hits"]}
    exported = reopened.execute("export", {"bundle": bundle, "format": format})
    assert exported.status == "completed", exported.public_dict()
    restored = read_bundle(base64.b64decode(exported.data["content_base64"]), format=format)
    assert restored["records"] == bundle["records"] and restored["extensions"] == bundle["extensions"]
    assert base64.b64decode(restored["capture"]["content_base64"]) == PAGE
    saved = reopened.execute("normalize", {"source": {**SOURCE.public_dict(), "input_format": "telvue-public-search-html"}}, content=PAGE)
    assert saved.status == "completed" and len(saved.data["records"]) == 43


def test_hidden_summary_script_does_not_become_searchable_text():
    raw = PAGE.replace(b'<div class="summary" style="display: block;">',
        b'<div class="summary" style="display: block;"><script>hidden-only-expression</script>', 1)
    bundle = parse_bundle(SOURCE, "//telvue.com/player/" + PLAYER, raw)
    assert "hidden-only-expression" not in bundle["records"][0]["normalized"]["description"]


@pytest.mark.parametrize("replacement", [b"budget", b"Council", b"council+meeting"])
def test_native_response_search_terms_must_match_exact_request(replacement):
    raw = PAGE.replace(b"terms=council", b"terms=" + replacement)
    assert raw != PAGE
    result = create_engine(provider_transport=Transport(raw)).execute("search", request())
    assert result.status == "failed" and not result.data
    assert not result.coverage["catalog_complete"]
