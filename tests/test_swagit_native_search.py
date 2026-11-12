"""Bounded Swagit public search; timestamp links remain citations, not transcripts."""

from dataclasses import replace
from pathlib import Path
from time import sleep
from urllib.parse import parse_qs, urlsplit

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response


FIXTURES = Path(__file__).parent / "fixtures" / "swagit-native-search"
SOURCE = {"provider": "swagit", "url": "https://princetontx.new.swagit.com/views/261/"}


class FixtureTransport:
    def __init__(self, *, mode=None):
        self.calls = []
        self.mode = mode

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        params = parse_qs(urlsplit(url).query, keep_blank_values=True)
        page = params.get("page", ["1"])[0]
        if self.mode == "delay":
            sleep(0.02)
        if self.mode == "oversize":
            body = (FIXTURES / "page-1.html").read_bytes()
            return Response(url, body + (b" " * 1000), "text/html")
        if self.mode == "changed-page" and page == "1":
            body = (FIXTURES / "page-1.html").read_bytes() + b" "
            return Response(url, body, "text/html")
        if self.mode == "cross-origin-next" and page == "1":
            body = (FIXTURES / "page-1.html").read_bytes().replace(
                b"/videos/search?page=2&amp;q=Council&amp;utf8=%E2%9C%93",
                b"https://attacker.example/videos/search?page=2&amp;q=Council&amp;utf8=%E2%9C%93",
            )
            return Response(url, body, "text/html")
        if self.mode == "wrong-next-page" and page == "1":
            body = (FIXTURES / "page-1.html").read_bytes().replace(
                b"/videos/search?page=2&amp;q=Council&amp;utf8=%E2%9C%93",
                b"/videos/search?page=3&amp;q=Council&amp;utf8=%E2%9C%93",
            )
            return Response(url, body, "text/html")
        name = "empty.html" if params.get("q") == ["quorumrelaynonsensical987654321"] else (
            "page-2.html" if page == "2" else "page-1.html")
        return Response(url, (FIXTURES / name).read_bytes(), "text/html")


def request(**bounds):
    return {"native": True, "source": SOURCE,
            "query": {"terms": ["Council", "2026"], "limit": 100}, "bounds": bounds}


def make_engine(transport):
    return create_engine(provider_transport=transport)


def test_native_search_exact_local_metadata_and_rel_next_resume():
    transport = FixtureTransport()
    engine = make_engine(transport)
    ctx = OperationContext(principal="alice", client_id="swagit-test",
                           allowed_operations=frozenset({"search"}),
                           allowed_namespaces=frozenset({"//princetontx.new.swagit.com"}))
    first = engine.execute("search", request(max_pages=1), context=ctx)
    assert first.status == "partial", first.public_dict()
    assert first.coverage["native_search"] is True
    assert first.coverage["catalog_complete"] is False
    assert first.coverage["native_fields"] == ["title", "meeting_date"]
    assert first.coverage["provider_query_semantics"].startswith("not independently established")
    assert first.coverage["transcript_text_searched"] is False
    assert first.coverage["timestamp_urls_seen"] > 0
    assert first.coverage["checkpoint"]
    assert len(first.data["bundle"]["records"]) == 10
    assert first.data["hits"]
    for hit in first.data["hits"]:
        assert {match["field"] for match in hit["matches"]} <= {
            "normalized.title", "normalized.meeting_date"}
        assert "Council" in hit["record"]["normalized"]["title"] or "Council" in hit["record"]["normalized"]["meeting_date"]
        assert "2026" in hit["record"]["normalized"]["title"] or "2026" in hit["record"]["normalized"]["meeting_date"]
        assert hit["record"]["text"] == []
    first_record = first.data["bundle"]["records"][0]
    assert first_record["normalized"]["search_match_urls"]
    assert all("ts=" in url for url in first_record["normalized"]["search_match_urls"])
    assert not any("transcript" in text for text in first_record["normalized"].values()
                   if isinstance(text, str))

    second = engine.execute("search", request(max_pages=1, checkpoint=first.coverage["checkpoint"]), context=ctx)
    assert second.status == "partial", second.public_dict()
    first_ids = {row["identity"]["external_id"] for row in first.data["bundle"]["records"]}
    second_ids = {row["identity"]["external_id"] for row in second.data["bundle"]["records"]}
    assert len(second_ids) == 10
    assert first_ids.isdisjoint(second_ids)
    assert parse_qs(urlsplit(transport.calls[0][0]).query, keep_blank_values=True) == {
        "utf8": ["✓"], "q": ["Council"]}
    assert parse_qs(urlsplit(transport.calls[1][0]).query, keep_blank_values=True) == {
        "page": ["2"], "q": ["Council"], "utf8": ["✓"]}
    assert all(call[1]["allowed_origins"] == ("https://princetontx.new.swagit.com",)
               and call[1]["allow_redirects"] is False for call in transport.calls)


def test_empty_result_is_explicit_partial_not_local_fallback():
    transport = FixtureTransport()
    engine = make_engine(transport)
    req = request(max_pages=1)
    req["query"] = {"terms": ["quorumrelaynonsensical987654321"], "limit": 20}
    result = engine.execute("search", req)
    assert result.status == "partial"
    assert result.data["hits"] == []
    assert result.coverage["pages"] == 1
    assert result.coverage["native_search"] is True
    assert result.coverage["catalog_complete"] is False
    assert len(transport.calls) == 1


def test_mid_page_resume_preserves_candidates_and_rejects_changed_response():
    transport = FixtureTransport()
    engine = make_engine(transport)
    req = request(max_pages=1, max_records=2)
    first = engine.execute("search", req)
    assert len(first.data["bundle"]["records"]) == 2
    assert first.coverage["checkpoint"]

    second = engine.execute("search", request(max_pages=1, max_records=2,
        checkpoint=first.coverage["checkpoint"]))
    assert len(second.data["bundle"]["records"]) == 2
    assert {r["identity"]["external_id"] for r in first.data["bundle"]["records"]}.isdisjoint(
        {r["identity"]["external_id"] for r in second.data["bundle"]["records"]})
    assert parse_qs(urlsplit(transport.calls[1][0]).query, keep_blank_values=True) == {
        "utf8": ["✓"], "q": ["Council"]}

    changed_transport = FixtureTransport()
    changed_engine = make_engine(changed_transport)
    initial = changed_engine.execute("search", req)
    changed_transport.mode = "changed-page"
    changed = changed_engine.execute("search", request(max_pages=1, max_records=2,
        checkpoint=initial.coverage["checkpoint"]))
    assert changed.status == "failed"
    assert changed.errors
    assert len(changed_transport.calls) == 2


def test_checkpoint_binds_caller_query_and_current_grant():
    transport = FixtureTransport()
    engine = make_engine(transport)
    ctx = OperationContext(principal="alice", client_id="swagit-test",
                           authorization=frozenset({"public-search"}),
                           allowed_namespaces=frozenset({"//princetontx.new.swagit.com"}))
    first = engine.execute("search", request(max_pages=1, max_records=2), context=ctx)
    token = first.coverage["checkpoint"]

    changed_caller = engine.execute("search", request(checkpoint=token), context=replace(ctx, principal="bob"))
    assert changed_caller.status == "failed"
    changed_grant = engine.execute("search", request(checkpoint=token),
        context=replace(ctx, authorization=frozenset({"public-search", "other-grant"})))
    assert changed_grant.status == "failed"
    changed_namespace_grant = engine.execute("search", request(checkpoint=token),
        context=replace(ctx, allowed_namespaces=frozenset()))
    assert changed_namespace_grant.status == "failed"
    changed_query = request(checkpoint=token)
    changed_query["query"] = {"terms": ["Parks"], "limit": 100}
    assert engine.execute("search", changed_query, context=ctx).status == "failed"
    assert len(transport.calls) == 1


def test_next_link_origin_page_query_and_native_input_are_validated():
    for mode in ("cross-origin-next", "wrong-next-page"):
        transport = FixtureTransport(mode=mode)
        result = make_engine(transport).execute("search", request(max_pages=2))
        assert result.status == "failed"
        assert result.errors
        assert len(transport.calls) == 1

    transport = FixtureTransport()
    not_native = request()
    not_native["native"] = False
    result = make_engine(transport).execute("search", not_native)
    assert result.status == "failed"
    assert transport.calls == []

    saved = request()
    saved["content_base64"] = "e30="
    result = make_engine(transport).execute("search", saved, content=b"{}")
    assert result.status == "failed"
    assert transport.calls == []


def test_permission_cancel_deadline_and_response_byte_guards():
    transport = FixtureTransport()
    engine = make_engine(transport)
    denied = engine.execute("search", request(), context=OperationContext(allowed_namespaces=frozenset()))
    assert denied.status == "failed"
    assert not transport.calls

    cancelled_context = OperationContext()
    cancelled_context.cancellation.set()
    cancelled = engine.execute("search", request(), context=cancelled_context)
    assert cancelled.status == "cancelled"
    assert not transport.calls

    delay_transport = FixtureTransport(mode="delay")
    deadline = make_engine(delay_transport).execute("search", request(deadline_seconds=0.005))
    assert deadline.status == "failed"
    assert deadline.errors[0].code == "provider_deadline_exceeded"

    oversized = make_engine(FixtureTransport(mode="oversize")).execute(
        "search", request(parser_bytes=100000))
    assert oversized.status == "failed"
    assert oversized.errors
