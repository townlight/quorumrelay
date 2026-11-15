import base64
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.interchange import read_bundle
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers.peak_search import search_rows

ROOT = Path(__file__).resolve().parents[1] / "docs/capabilities/evidence/peak-public-search"
SOURCE = Source("peak", "https://douglascountynv.granicus.com/ViewPublisher.php?view_id=1")
PAGE = (ROOT / "page1.html").read_bytes()
EMPTY = (ROOT / "page2-empty.html").read_bytes()


def request(**bounds):
    return {"source": SOURCE.public_dict(), "native": True, "query": {"terms": ["budget"], "limit": 2},
        "bounds": {"max_records": 2, **bounds}}


def page(identity="1", current=1, total=2, excerpt="Budget action"):
    return (f'<table id="searchList"><tbody><tr class="listingRow"><td headers="Name">Council</td>'
        '<td headers="Date Council">November 5, 2026 - 10:00 AM</td><td>'
        f'<a href="//douglascountynv.granicus.com/AgendaViewer.php?view_id=1&amp;clip_id={identity}">Agenda</a>'
        '</td></tr><tr><td><table><tr><td class="searchSubItem">Item:</td>'
        f'<td class="searchSubItem">{excerpt}</td></tr></table></td></tr></tbody></table>'
        f'<script>pagination.load({current}, {total}, true);</script>').encode()


class Transport:
    def __init__(self, pages=None, *, callback=None):
        self.pages = pages or {1: PAGE, 2: EMPTY}
        self.calls = []
        self.callback = callback

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.callback:
            self.callback()
        number = int(parse_qs(urlsplit(url).query).get("pagenumber", [1])[0])
        return Response(url, self.pages[number], "text/html; charset=utf-8")


def test_actual_source_maps_150_native_groups_without_inventing_item_ids():
    rows, current, total, omitted = search_rows(SOURCE, PAGE)
    assert (len(rows), current, total, omitted) == (150, 1, 5, 0)
    assert len({r[0]["external_id"] for r in rows}) == 150
    assert rows[0][0]["external_id"] == "1968"
    assert all(r[2] == "meeting" and "agenda_items" not in r[0] for r in rows)
    assert "Cash Donation" in rows[0][0]["search_excerpt"]
    assert rows[0][0]["meeting_date"] == "2026-11-05"
    assert rows[0][0]["documents"][0]["url"].endswith("view_id=1&clip_id=1968")


def test_literal_form_request_and_exact_local_excerpt_matching():
    transport = Transport({1: page(excerpt="budget action"), 2: page("2", 2)})
    result = create_engine(provider_transport=transport).execute("search", request())
    assert result.status == "partial", result.public_dict()
    assert len(result.data["hits"]) == 1
    fields = parse_qs(urlsplit(transport.calls[0][0]).query)
    assert fields == {"view_id": ["1"], "keywords": ["budget"], "search_scope": ["past"],
        **{"types[" + k + "]": ["on"] for k in ["Clip", "AgendaItem", "AttachmentItem", "Note", "Vote,Motion"]}}
    assert not transport.calls[0][1]["allow_redirects"]
    assert base64.b64decode(result.data["bundle"]["capture"]["content_base64"]) == transport.pages[1]
    record = result.data["bundle"]["records"][0]
    assert transport.calls[0][0] in record["citation_urls"]
    assert record["text"][0]["citation_url"] == transport.calls[0][0]
    assert record["text"][0]["provenance"]["capture_sha256"] == result.data["bundle"]["capture"]["sha256"]
    assert not result.coverage["full_document_text_searched"]


def test_local_offset_resume_then_declared_next_page_and_scope_binding():
    transport = Transport({2: page("3", 2)})
    # Build two complete sibling groups, with only the outer page declaration.
    transport.pages[1] = (page("1").split(b'</tbody>')[0] + b'</tbody><tbody>'
        + page("2").split(b'<tbody>')[1].split(b'</tbody>')[0] + b'</tbody></table>'
        + b'<script>pagination.load(1, 2, true);</script>')
    engine = create_engine(provider_transport=transport)
    value = request(max_records=1)
    a = engine.execute("search", value)
    assert a.status == "partial", a.public_dict()
    b = engine.execute("search", {**value, "bounds": {**value["bounds"], "checkpoint": a.coverage["checkpoint"]}})
    assert b.status == "partial", b.public_dict()
    assert [r["identity"]["external_id"] for r in b.data["bundle"]["records"]] == ["2"]
    c = engine.execute("search", {**value, "bounds": {**value["bounds"], "checkpoint": b.coverage["checkpoint"]}})
    assert c.status == "partial" and c.coverage["checkpoint"] is None
    assert c.data["bundle"]["records"][0]["identity"]["external_id"] == "3"
    assert parse_qs(urlsplit(transport.calls[-1][0]).query)["pagenumber"] == ["2"]
    denied = engine.execute("search", {**value, "bounds": {**value["bounds"], "checkpoint": a.coverage["checkpoint"]}},
                            context=OperationContext(tenant="other"))
    assert denied.status == "failed" and len(transport.calls) == 3


def test_actual_empty_second_page_never_becomes_completed_empty():
    transport = Transport()
    value = request(max_records=1000)
    value["query"]["limit"] = 1000
    engine = create_engine(provider_transport=transport)
    first = engine.execute("search", value)
    assert first.status == "partial" and first.coverage["checkpoint"], first.public_dict()
    second = engine.execute("search", {**value, "bounds": {"checkpoint": first.coverage["checkpoint"]}})
    assert second.status == "failed" and not second.data
    assert not second.coverage["source_complete"] and len(transport.calls) == 2


@pytest.mark.parametrize("replacement", [b'clip_id=2', b'view_id=2&amp;clip_id=1',
    b'view_id=1&amp;clip_id=1&amp;token=x', b'view_id=1&amp;clip_id=1#other'])
def test_unsafe_native_viewer_bindings_fail(replacement):
    raw = page().replace(b'view_id=1&amp;clip_id=1', replacement)
    assert create_engine(provider_transport=Transport({1: raw})).execute("search", request()).status == "failed"


@pytest.mark.parametrize("change", ["body", "source", "empty_term", "long_term", "saved", "type"])
def test_unsupported_requests_fail_before_network(change):
    value = request()
    if change == "body":
        value["query"]["body"] = "Council"
    elif change == "source":
        value["source"]["url"] += "&view_id=2"
    elif change == "empty_term":
        value["query"]["terms"] = []
    elif change == "long_term":
        value["query"]["terms"] = ["x" * 256]
    elif change == "saved":
        value["records"] = []
    else:
        value["query"]["record_types"] = ["agenda_item"]
    vendor = Transport()
    assert create_engine(provider_transport=vendor).execute("search", value).status == "failed"
    assert not vendor.calls


@pytest.mark.parametrize("when", ["before", "transport", "mapping"])
def test_cancellation_is_honored_through_mapping(monkeypatch, when):
    from civic_data_connectors.providers import peak_search as module

    ctx = OperationContext()
    if when == "before":
        ctx.cancellation.set()
    vendor = Transport({1: page()}, callback=ctx.cancellation.set if when == "transport" else None)
    if when == "mapping":
        original = module.search_rows

        def cancel(*args):
            rows = original(*args)
            ctx.cancellation.set()
            return rows

        monkeypatch.setattr(module, "search_rows", cancel)
    result = create_engine(provider_transport=vendor).execute("search", request(), context=ctx)
    assert result.status == "cancelled" and not result.data


def test_byte_limit_and_same_page_revision_rejection():
    vendor = Transport({1: page()})
    result = create_engine(provider_transport=vendor).execute("search", request(transfer_bytes=100))
    assert result.status == "failed" and vendor.calls[0][1]["byte_limit"] == 100
    vendor = Transport()
    engine = create_engine(provider_transport=vendor)
    a = engine.execute("search", request(max_records=1))
    vendor.pages[1] += b'\n'
    b = engine.execute("search", request(max_records=1, checkpoint=a.coverage["checkpoint"]))
    assert b.status == "failed" and not b.data


def test_date_filter_stays_local_and_transport_deadline_cannot_complete(monkeypatch):
    from civic_data_connectors.providers import peak_search as module

    vendor = Transport({1: page()})
    value = request(date_from="2026-12-01", date_to="2026-12-31")
    result = create_engine(provider_transport=vendor).execute("search", value)
    assert result.status == "partial" and not result.data["hits"]
    assert "date_from" not in parse_qs(urlsplit(vendor.calls[0][0]).query)
    now = [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: now[0])
    vendor = Transport({1: page()}, callback=lambda: now.__setitem__(0, 2.0))
    result = create_engine(provider_transport=vendor).execute("search", request(deadline_seconds=1))
    assert result.status == "failed" and not result.data


def test_seen_native_ids_are_not_repeated_across_provider_pages():
    vendor = Transport({1: page(), 2: page(current=2)})
    engine = create_engine(provider_transport=vendor)
    first = engine.execute("search", request())
    second = engine.execute("search", request(checkpoint=first.coverage["checkpoint"]))
    assert second.status == "partial" and second.coverage["checkpoint"] is None
    assert second.data["bundle"]["records"] == [] and second.data["hits"] == []
    assert not second.coverage["source_complete"]


@pytest.mark.parametrize("format", ["json", "jsonl", "zip"])
def test_capture_native_identity_excerpt_and_links_survive_sqlite_neutral_export(tmp_path, format):
    raw = page(excerpt="budget &amp; taxes")
    vendor = Transport({1: raw})
    path = tmp_path / "state.sqlite"
    engine = create_engine(storage=SQLiteStorage(path), provider_transport=vendor)
    searched = engine.execute("search", request())
    bundle = searched.data["bundle"]
    imported = engine.execute("import_bundle", {"bundle": bundle, "persist": True})
    assert imported.status in {"completed", "partial"}, imported.public_dict()
    again = engine.execute("import_bundle", {"bundle": bundle, "persist": True})
    assert again.status in {"completed", "partial"}
    reopened = create_engine(storage=SQLiteStorage(path))
    local = reopened.execute("search", {"query": {"terms": ["taxes"]}})
    assert len(local.data["hits"]) == 1
    result = reopened.execute("export", {"bundle": bundle, "format": format})
    assert result.status == "completed", result.public_dict()
    restored = read_bundle(base64.b64decode(result.data["content_base64"]), format=format)
    assert restored["records"] == bundle["records"]
    assert base64.b64decode(restored["capture"]["content_base64"]) == raw
    assert restored["extensions"] == bundle["extensions"]
    replay = engine.execute("normalize", {"source": {**SOURCE.public_dict(), "input_format": "peak-public-search-html"}},
                            content=raw)
    assert replay.status == "completed"
    assert replay.data["records"][0]["normalized"] == bundle["records"][0]["normalized"]
