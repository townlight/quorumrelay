from pathlib import Path
from urllib.parse import parse_qs

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = {"provider": "suiteone-media", "url": "https://vermilionoh.suiteonemedia.com/"}
ROOT = b'<form id="searchEventsForm" action="/Home/SearchEvents"><input id="ev-search"><option value="-1"></form>'


class Transport:
    def __init__(self):
        self.calls = []
        self.changed = False

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["allow_redirects"] is False
        if url == SOURCE["url"]:
            return Response(url, ROOT, "text/html")
        assert url == SOURCE["url"] + "Home/GetRecentEvents"
        values = parse_qs(kwargs["body"].decode())
        assert values["category"] == ["-1"] and values["page"] == ["1"]
        name = "suiteone-search-empty.html" if values["search"] == ["quorumrelayneverpresentqzxjvk"] else "suiteone-search-council.html"
        raw = (FIXTURES / name).read_bytes()
        return Response(url, raw + (b"<!--changed-->" if self.changed else b""), "text/html")


def request(term="Council", **bounds):
    return {"source": SOURCE, "native": True, "query": {"terms": [term]}, "bounds": {
        "date_from": "2025-01-01", "date_to": "2026-12-31", "parser_bytes": 2 * 1024**2,
        "max_records": 3, **bounds}}


def test_actual_keyword_capture_and_distinct_resumed_ids():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute("search", request())
    assert first.status == "partial" and not first.errors
    assert first.coverage["checkpoint"] and first.coverage["provider_candidates"] == 3
    second = engine.execute("search", request(checkpoint=first.coverage["checkpoint"]))
    assert second.status == "partial" and not second.errors
    first_ids = {r["identity"]["external_id"] for b in first.data["bundles"] for r in b["records"]}
    second_ids = {r["identity"]["external_id"] for b in second.data["bundles"] for r in b["records"]}
    assert len(first_ids) == len(second_ids) == 3 and first_ids.isdisjoint(second_ids)
    assert first.coverage["catalog_complete"] is False
    assert first.coverage["full_document_text_searched"] is False


def test_observed_empty_result_is_partial_without_invented_rows():
    result = create_engine(provider_transport=Transport()).execute("search", request("quorumrelayneverpresentqzxjvk"))
    assert result.status == "partial" and not result.errors
    assert result.data["records"] == [] and result.coverage["checkpoint"] is None


def test_changed_capture_and_other_caller_continuations_fail_closed():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute("search", request())
    transport.changed = True
    changed = engine.execute("search", request(checkpoint=first.coverage["checkpoint"]))
    assert changed.status == "failed" and changed.errors
    count = len(transport.calls)
    foreign = engine.execute("search", request(checkpoint=first.coverage["checkpoint"]),
                             context=OperationContext(principal="other"))
    assert foreign.status == "failed" and len(transport.calls) == count


def test_native_search_namespace_revocation_prevents_transport():
    transport = Transport()
    result = create_engine(provider_transport=transport).execute("search", request(),
        context=OperationContext(allowed_namespaces=frozenset({"unrelated"})))
    assert result.status == "failed" and not transport.calls
