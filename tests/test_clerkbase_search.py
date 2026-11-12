"""Focused tests for captured South Kingstown ClerkBase public search/tree rows."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs
import base64

import pytest

from quorumrelay import create_engine
from civic_data_connectors.models import OperationContext
from civic_data_connectors.providers.clerkbase_search import (
    FORMAT, listing_rows, mark_supplied_url_identities, native_search,
)
from civic_data_connectors.providers.contracts import Response

FIXTURES = Path(__file__).parent / "fixtures" / "clerkbase"
SOURCE = {"provider": "clerkbase", "url": "https://clerkshq.com/southkingstown-ri"}
SEARCH_URL = "https://clerkshq.com/search"


class ClerkBaseTransport:
    def __init__(self, *, home=None, page1=None, page2=None, empty=None):
        self.home = home if home is not None else (FIXTURES / "home.html").read_bytes()
        self.page1 = page1 if page1 is not None else (FIXTURES / "search-council-page1.html").read_bytes()
        self.page2 = page2 if page2 is not None else (FIXTURES / "search-council-page2.html").read_bytes()
        self.empty = empty if empty is not None else (FIXTURES / "search-empty.html").read_bytes()
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if kwargs["method"] == "GET" and url == SOURCE["url"]:
            return Response(url, self.home, "text/html", set_cookie_headers=(
                "clerkbase-public=sk; Path=/; Secure; HttpOnly; SameSite=Lax",
            ))
        if kwargs["method"] != "POST" or url != SEARCH_URL:
            return Response(url, b"unexpected request", "text/html", status=404)
        fields = parse_qs(kwargs["body"].decode("ascii"), keep_blank_values=True)
        if fields.get("sm.SearchRequest") == ["quorumrelayneverpresentqzxjvk"]:
            return Response(url, self.empty, "text/html")
        if fields.get("sm.pageNum") == ["1"]:
            return Response(url, self.page2, "text/html")
        return Response(url, self.page1, "text/html")


def search_request(*, terms=("Council",), query_extra=None, bounds_extra=None, body=None):
    query = {"terms": list(terms), "limit": 100}
    query.update(query_extra or {})
    bounds = {"max_pages": 1, "max_records": 100, "parser_bytes": 256_000}
    bounds.update(bounds_extra or {})
    return {"native": True, "source": SOURCE, "query": query, "bounds": bounds}, body


def execute(req=None, *, transport=None, context=None):
    request, body = req if req is not None else search_request()
    active = transport or ClerkBaseTransport()
    result = native_search(create_engine(), request, body, context or OperationContext(), transport=active)
    return result, active


def test_copied_fixtures_retain_the_captured_response_bytes():
    expected = {
        "agenda-tree.html": "f6bbafc6b2c93997344cb74227bd28290ea4326fe0ad7704059154c133404ae4",
        "home.html": "b1e705ee64876e7d1434e31ad6e95b0697508e6b65e9353075050507e2e2b734",
        "search-council-page1.html": "35e87031d5015ac8aae6f6159bbe333374278fe65b43b84f504e5c0a792b2648",
        "search-council-page2.html": "0b7f080bd5ef31a9c670d9df1b53739c83a6d2f662c09bc9eff284dd21284b9b",
        "search-empty.html": "044cca27dc9ee925a37137d7465d581f64cff7341d57bda22701c2507b2af471",
    }
    assert {name: sha256((FIXTURES / name).read_bytes()).hexdigest() for name in expected} == expected


def test_tree_rows_use_exact_supplied_document_url_and_keep_unknown_source_attributes():
    content = (FIXTURES / "agenda-tree.html").read_bytes()
    rows = listing_rows(type("Source", (), SOURCE)(), content)

    assert len(rows) == 5
    normalized, raw, record_type = rows[0]
    assert record_type == "document"
    assert normalized["url"] == "https://clerkshq.com/Content/SouthKingstown-ri/council/2026/jan12_26ag.htm"
    assert normalized["external_id"] == normalized["url"]
    assert normalized["title"] == "Jan. 12, 2026 - Regular Session"
    assert normalized["meeting_date"] == "2026-01-12"
    assert normalized["location"] is None and normalized["search_excerpts"] == []
    assert "data-node-id" in raw["link_attributes"]
    assert raw["link_attributes"]["data-path"] == "SouthKingstown_Docket,AGENDA,"
    assert "parent" not in normalized

    bundle = mark_supplied_url_identities({"records": [{
        "identity": {"external_id": normalized["external_id"]}, "normalized": normalized,
    }]})
    assert bundle["records"][0]["identity"]["derivation"] == "supplied_url"


def test_tree_mapper_rejects_cross_origin_content_url():
    content = (FIXTURES / "agenda-tree.html").read_bytes().replace(
        b'href="/Content/SouthKingstown-ri/council/2026/jan12_26ag.htm"',
        b'href="https://example.invalid/Content/SouthKingstown-ri/council/2026/jan12_26ag.htm"', 1)
    with pytest.raises(ValueError, match="disagree|content tree"):
        listing_rows(type("Source", (), SOURCE)(), content)


def test_native_search_replays_observed_form_and_preserves_page_capture():
    result, transport = execute()

    assert result.status == "partial"
    assert result.coverage["native_search"] is True
    assert result.coverage["status"] == "partial"
    assert result.coverage["catalog_complete"] is False
    assert result.coverage["source_complete"] is False
    assert result.coverage["document_content_retrieved"] is False
    assert result.coverage["search_snippets_only"] is True
    assert result.coverage["provider_result_total"] == 2140
    assert result.coverage["checkpoint"]
    assert result.data["bundle"]["captures"][0]["input_format"] == FORMAT
    assert len(result.data["bundle"]["records"]) == 20
    assert result.data["hits"]

    get_url, get_kwargs = transport.calls[0]
    post_url, post_kwargs = transport.calls[1]
    assert get_url == SOURCE["url"] and get_kwargs["method"] == "GET"
    assert get_kwargs["allowed_origins"] == ("https://clerkshq.com",)
    assert get_kwargs["allow_redirects"] is False
    assert post_url == SEARCH_URL and post_kwargs["method"] == "POST"
    assert post_kwargs["allowed_origins"] == ("https://clerkshq.com",)
    assert post_kwargs["allow_redirects"] is False
    assert post_kwargs["headers"]["Cookie"] == "clerkbase-public=sk"
    fields = parse_qs(post_kwargs["body"].decode("ascii"), keep_blank_values=True)
    assert fields["sm.IxId"] == ["SouthKingstown-ri"]
    assert fields["sm.SearchRequest"] == ["Council"]
    assert fields["sm.SearchType"] == ["AllWords"]
    assert fields["sm.Near"] == ["14"]
    assert fields["sm.ExcludeEnabled"] == ["false"]
    assert fields["sm.IncludeSynopsis"] == ["true", "false"]
    assert fields["sm.Stemming"] == ["true", "false"]
    assert fields["sm.WordNetSynonyms"] == ["false"]
    assert fields["sm.Fuzzy"] == ["false"]
    assert fields["sm.Fuzziness"] == ["4"]
    assert "sm.TreePath" not in fields and "sm.pageNum" not in fields

    capture = result.data["bundle"]["captures"][0]
    original = (FIXTURES / "search-council-page1.html").read_bytes()
    assert base64.b64decode(capture["content_base64"]) == original
    assert capture["sha256"] == sha256(original).hexdigest()
    record = result.data["hits"][0]["record"]
    assert record["identity"]["external_id"] == record["normalized"]["url"]
    assert record["identity"]["derivation"] == "supplied_url"
    assert record["identity"].get("parent") is None
    assert record["normalized"]["search_excerpts"]
    assert record["text"] == []
    assert "data-result-id" in record["original"]["row_attributes"]
    assert record["identity"]["external_id"] != record["original"]["row_attributes"]["data-result-id"]


def test_native_pager_uses_published_data_page_num_minus_one():
    req, body = search_request(bounds_extra={"max_pages": 1})
    first, transport = execute((req, body))
    checkpoint = first.coverage["checkpoint"]
    assert checkpoint

    resumed, _ = execute(search_request(bounds_extra={"max_pages": 1, "checkpoint": checkpoint}),
                         transport=transport)
    assert resumed.status == "partial"
    assert resumed.coverage["pages"] == 1
    assert resumed.coverage["provider_page_counts"][0]["first"] == 20
    assert len(resumed.data["bundle"]["records"]) == 20
    page2_fields = parse_qs(transport.calls[-1][1]["body"].decode("ascii"), keep_blank_values=True)
    assert page2_fields["sm.pageNum"] == ["1"]
    assert set(hit["identity"]["external_id"] for hit in first.data["hits"]).isdisjoint(
        hit["identity"]["external_id"] for hit in resumed.data["hits"])


def test_phrase_mode_empty_result_body_unknown_and_no_local_url_matching():
    phrase, phrase_body = search_request(terms=(), query_extra={"phrases": ["Regular Session"]})
    phrase_result, phrase_transport = execute((phrase, phrase_body))
    phrase_fields = parse_qs(phrase_transport.calls[1][1]["body"].decode("ascii"), keep_blank_values=True)
    assert phrase_fields["sm.SearchRequest"] == ["Regular Session"]
    assert phrase_fields["sm.SearchType"] == ["Phrase"]

    empty_request, empty_body = search_request(terms=("quorumrelayneverpresentqzxjvk",))
    empty_result, _ = execute((empty_request, empty_body))
    assert empty_result.status == "partial"
    assert empty_result.data["hits"] == []
    assert empty_result.coverage["query_window_exhausted"] is True
    assert empty_result.coverage["source_complete"] is False

    body_request, body_payload = search_request(query_extra={"body": "ordinance"})
    body_result, _ = execute((body_request, body_payload))
    assert body_result.data["hits"]
    assert body_result.coverage["body_filter"]["status"] == "unknown_retained"
    assert body_result.coverage["body_filter"]["applied"] is False

    url_request, url_body = search_request(terms=("Council", "jan12_26ag.htm"))
    url_result, _ = execute((url_request, url_body))
    assert url_result.data["hits"] == []


def test_mid_page_checkpoint_hash_scope_and_caller_binding():
    req, body = search_request(bounds_extra={"max_records": 1})
    first, transport = execute((req, body))
    checkpoint = first.coverage["checkpoint"]
    assert checkpoint
    assert len(first.data["bundle"]["records"]) == 1

    changed_page = transport.page1 + b"\n<!-- changed after checkpoint -->"
    transport.page1 = changed_page
    resumed_req, resumed_body = search_request(bounds_extra={"max_records": 1, "checkpoint": checkpoint})
    failed, _ = execute((resumed_req, resumed_body), transport=transport)
    assert failed.status == "failed"
    assert failed.errors

    unchanged = ClerkBaseTransport()
    first, _ = execute((req, body), transport=unchanged)
    checkpoint = first.coverage["checkpoint"]
    changed_query, changed_body = search_request(terms=("Council", "zoning"), bounds_extra={
        "max_records": 1, "checkpoint": checkpoint,
    })
    with pytest.raises(ValueError, match="checkpoint"):
        native_search(create_engine(), changed_query, changed_body, OperationContext(), transport=unchanged)
    with pytest.raises(ValueError, match="checkpoint"):
        native_search(create_engine(), search_request(bounds_extra={"max_records": 1,
                      "checkpoint": checkpoint})[0], None, OperationContext(principal="other"),
                      transport=unchanged)


def test_changed_site_permission_and_cancellation_are_stopped_before_search():
    wrong = {"native": True, "source": {"provider": "clerkbase", "url": "https://clerkshq.com/OtherSite"},
             "query": {"terms": ["Council"]}}
    with pytest.raises(ValueError, match="South Kingstown"):
        native_search(create_engine(), wrong, None, OperationContext(), transport=ClerkBaseTransport())

    denied_transport = ClerkBaseTransport()
    denied, _ = execute(context=OperationContext(allowed_operations=frozenset({"identify"})),
                        transport=denied_transport)
    assert denied.status == "failed" and denied.errors[0].code == "permission_denied"
    assert not denied_transport.calls

    context = OperationContext()
    context.cancellation.set()
    cancelled_transport = ClerkBaseTransport()
    cancelled, _ = execute(context=context, transport=cancelled_transport)
    assert cancelled.status == "cancelled"
    assert not cancelled_transport.calls

