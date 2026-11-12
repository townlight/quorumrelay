"""Exact observed public form and array, without full-text/catalog claims."""
from dataclasses import replace
import json
from pathlib import Path
from urllib.parse import parse_qs

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response

FIXTURE = Path(__file__).parent / "fixtures" / "primegov-native-search"
SOURCE = {"provider": "primegov", "url": "https://reno.primegov.com/public/portal"}


class Transport:
    def __init__(self):
        self.calls = []
        self.content = (FIXTURE / "council.json").read_bytes()

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(url, self.content, "application/json")


def request(**bounds):
    return {"native": True, "source": SOURCE, "query": {"terms": ["Council"], "limit": 200,
            "date_from": "2026-11-01", "date_to": "2026-11-30"}, "bounds": bounds}


def test_observed_form_raw_rows_parents_and_partial_excerpts():
    transport = Transport()
    result = create_engine(provider_transport=transport).execute("search", request(max_records=200))
    assert result.status == "partial", result.public_dict()
    bundle = result.data["bundle"]
    assert len(bundle["records"]) == 140
    assert {r["identity"]["record_type"] for r in bundle["records"]} == {"meeting", "agenda_item", "document"}
    first = bundle["records"][0]
    assert first["original"] in json.loads(transport.content)
    assert first["identity"]["parent"]["external_id"] == str(first["original"]["meetingId"])
    assert "<em>" not in bundle["records"][-1]["normalized"].get("search_excerpt", "")
    assert result.data["hits"] and result.coverage["checkpoint"] is None
    assert result.coverage["full_document_text_searched"] is False
    assert not result.coverage["catalog_complete"] and not result.coverage["source_complete"]
    url, args = transport.calls[0]
    assert url == "https://reno.primegov.com/api/v2/PublicPortal/search"
    assert args["method"] == "POST" and args["allow_redirects"] is False
    assert parse_qs(args["body"].decode())["MeetingDateFrom"] == ["11/01/2026"]
    assert parse_qs(args["body"].decode())["Text"] == ["Council"]
    assert args["allowed_origins"] == ("https://reno.primegov.com",)


def test_checkpoint_preserves_all_candidates_and_binds_scope_query_and_page():
    transport, ctx = Transport(), OperationContext(principal="alice")
    engine = create_engine(provider_transport=transport)
    first = engine.execute("search", request(max_records=1), context=ctx)
    token = first.coverage["checkpoint"]
    second = engine.execute("search", request(max_records=2, checkpoint=token), context=ctx)
    assert len(first.data["bundle"]["records"]) == 1 and len(second.data["bundle"]["records"]) == 2
    assert first.data["bundle"]["records"][0]["identity"] != second.data["bundle"]["records"][0]["identity"]
    transport.content = json.dumps(list(reversed(json.loads(transport.content)))).encode()
    reordered = engine.execute("search", request(max_records=2, checkpoint=token), context=ctx)
    assert reordered.status == "partial"
    assert [r["identity"] for r in reordered.data["bundle"]["records"]] == [r["identity"] for r in second.data["bundle"]["records"]]
    assert engine.execute("search", request(checkpoint=token), context=replace(ctx, principal="bob")).status == "failed"
    changed = request(checkpoint=token)
    changed["query"]["terms"] = ["Budget"]
    assert engine.execute("search", changed, context=ctx).status == "failed"
    transport.content = b"[]"
    assert engine.execute("search", request(checkpoint=token), context=ctx).status == "failed"


def test_empty_limits_denial_cancellation_and_changed_route_fail_closed():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    transport.content = (FIXTURE / "empty.json").read_bytes()
    result = engine.execute("search", request())
    assert result.status == "partial" and result.data["hits"] == []
    transport.calls.clear()
    assert engine.execute("search", request(), context=OperationContext(allowed_namespaces=frozenset())).status == "failed"
    assert not transport.calls
    ctx = OperationContext()
    ctx.cancellation.set()
    assert engine.execute("search", request(), context=ctx).status == "cancelled" and not transport.calls
    assert engine.execute("search", request(parser_bytes=1)).status == "failed"
    no_dates = request()
    no_dates["query"] = {"terms": ["Council"]}
    assert engine.execute("search", no_dates).status == "failed"
    transport.request = lambda url, **kw: Response(url + "/other", b"[]", "application/json")
    assert engine.execute("search", request()).status == "failed"


def test_unknown_rows_are_explicit_and_hidden_markup_is_not_search_text():
    transport = Transport()
    transport.content = json.dumps([{"info": "FutureKind", "id": 4, "meetingId": 8}]).encode()
    result = create_engine(provider_transport=transport).execute("search", request())
    assert result.status == "partial" and result.coverage["unmapped_rows_omitted"] == 1
    assert result.data["hits"] == []
    transport.content = json.dumps([{"info": "Meeting", "id": 8, "meetingId": 8,
        "meetingDate": "2026-11-01T00:00:00", "title": "Budget", "highlights": "<script>Council</script>Budget"}]).encode()
    result = create_engine(provider_transport=transport).execute("search", request())
    assert result.data["hits"] == []
    assert result.data["bundle"]["records"][0]["original"]["highlights"].startswith("<script>")
