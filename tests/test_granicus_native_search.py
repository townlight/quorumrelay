"""Observed Granicus Clip form pages; provider ranking remains partial metadata."""
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response

FIXTURES = Path(__file__).parent / "fixtures" / "granicus-native-search"
SOURCE = {"provider": "granicus", "url": "https://townofsuperior.granicus.com/ViewPublisher.php?view_id=2"}


class Transport:
    def __init__(self):
        self.calls = []
    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        q = parse_qs(urlsplit(url).query)
        name = "empty-search" if q["allwords"] == ["quorumrelaynonsensical987654321"] else (
            "planning-page2" if q.get("pagenumber") == ["2"] else "planning-search")
        return Response(url, (FIXTURES / (name + ".html")).read_bytes(), "text/html")


def request(**bounds):
    return {"native": True, "source": SOURCE, "query": {"terms": ["Planning"], "limit": 100}, "bounds": bounds}


def test_clip_search_bounded_pages_resume_and_scope_binding():
    transport, ctx = Transport(), OperationContext(principal="alice")
    owner = create_engine(provider_transport=transport)
    first = owner.execute("search", request(max_pages=1, max_records=7), context=ctx)
    assert first.status == "partial", first.public_dict()
    assert len(first.data["bundle"]["records"]) == 7
    assert first.coverage["checkpoint"] and not first.coverage["catalog_complete"]
    assert first.coverage["agenda_document_text_searched"] is False
    second = owner.execute("search", request(max_pages=1, max_records=50, checkpoint=first.coverage["checkpoint"]), context=ctx)
    assert second.status == "partial", second.public_dict()
    assert len(second.data["bundle"]["records"]) == 13
    assert second.coverage["checkpoint"]
    third = owner.execute("search", request(max_pages=1, max_records=50, checkpoint=second.coverage["checkpoint"]), context=ctx)
    assert third.status == "partial", third.public_dict()
    assert len(third.data["bundle"]["records"]) == 20
    assert parse_qs(urlsplit(transport.calls[-1][0]).query)["pagenumber"] == ["2"]
    assert all(call[1]["allowed_origins"] == ("https://townofsuperior.granicus.com",) for call in transport.calls)
    assert owner.execute("search", request(checkpoint=first.coverage["checkpoint"]), context=replace(ctx, principal="bob")).status == "failed"
    changed = request(checkpoint=first.coverage["checkpoint"])
    changed["query"] = {"terms": ["Council"]}
    assert owner.execute("search", changed, context=ctx).status == "failed"


def test_empty_date_filter_and_namespace_denial():
    transport = Transport()
    owner = create_engine(provider_transport=transport)
    empty = request(max_pages=1)
    empty["query"] = {"terms": ["quorumrelaynonsensical987654321"]}
    result = owner.execute("search", empty)
    assert result.status == "partial" and result.data["hits"] == []
    dated = request(max_pages=1)
    dated["query"] = {"terms": ["Planning"], "date_from": "2025-12-01", "date_to": "2025-12-31"}
    result = owner.execute("search", dated)
    assert result.status == "partial" and result.data["hits"]
    assert all(hit["record"]["normalized"]["meeting_date"].startswith("2025-12") for hit in result.data["hits"])
    denied = owner.execute("search", request(), context=OperationContext(allowed_namespaces=frozenset()))
    assert denied.status == "failed"


def test_unrecognized_or_changed_page_and_cancellation_fail_closed():
    transport = Transport()
    owner = create_engine(provider_transport=transport)
    first = owner.execute("search", request(max_records=1, max_pages=1))
    transport.request = lambda url, **kw: Response(url, b"bad html", "text/html")
    result = owner.execute("search", request(checkpoint=first.coverage["checkpoint"]))
    assert result.status == "failed" and result.errors
    cancelled = OperationContext()
    cancelled.cancellation.set()
    assert owner.execute("search", request(), context=cancelled).status == "cancelled"


def test_query_limit_preserves_unvisited_candidates_for_resume():
    owner = create_engine(provider_transport=Transport())
    req = request(max_pages=1, max_records=50)
    req["query"]["limit"] = 2
    first = owner.execute("search", req)
    assert len(first.data["hits"]) == 2 and first.coverage["checkpoint"]
    req["bounds"]["checkpoint"] = first.coverage["checkpoint"]
    second = owner.execute("search", req)
    assert len(second.data["hits"]) == 2
    assert {x["identity"]["external_id"] for x in first.data["hits"]}.isdisjoint(
        {x["identity"]["external_id"] for x in second.data["hits"]})


def test_durable_cancellation_stops_following_pages(tmp_path):
    from quorumrelay.storage import SQLiteStorage, update_operation
    storage = SQLiteStorage(tmp_path / "operations.sqlite")
    ctx = OperationContext(operation_id="search-cancel")
    transport = Transport()
    def on_progress(progress):
        if progress.get("pages") == 1:
            update_operation(storage, "search-cancel", {"cancel_requested": True}, scope=ctx.scope)
    ctx.progress = on_progress
    owner = create_engine(storage=storage, provider_transport=transport)
    result = owner.execute("search", request(max_pages=4), context=ctx)
    assert result.status == "cancelled"
    assert len(transport.calls) == 1
