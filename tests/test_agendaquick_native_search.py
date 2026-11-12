"""Focused tests for the observed anonymous AgendaQuick item-search form."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from quorumrelay import create_engine
from civic_data_connectors.models import OperationContext
from civic_data_connectors.providers.agendaquick_search import native_search
from civic_data_connectors.providers.contracts import Response

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = {
    "provider": "destiny-agendaquick",
    "url": "https://public.destinyhosted.com/agenda_publish.cfm?id=98622",
}
SEARCH_URL = "https://public.destinyhosted.com/adv_search_results.cfm?fp=ADVSRCH&id=98622"


class SearchTransport:
    def __init__(self, *, calendar=None, result=None):
        self.calendar = calendar if calendar is not None else (FIXTURES / "agendaquick-calendar.html").read_bytes()
        self.result = result
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if kwargs["method"] == "GET" and url == SOURCE["url"]:
            return Response(url, self.calendar, "text/html", set_cookie_headers=(
                "agendaquick-session=public; Path=/; Secure; HttpOnly; SameSite=Lax",
            ))
        if kwargs["method"] == "POST" and url == SEARCH_URL:
            fields = parse_qs(kwargs["body"].decode("ascii"), keep_blank_values=True)
            if fields.get("sstr") == ["quorumrelayempty987654321"]:
                result = (FIXTURES / "agendaquick-empty.html").read_bytes()
            else:
                result = self.result if self.result is not None else (
                    FIXTURES / "agendaquick-search.html").read_bytes()
            return Response(url, result, "text/html")
        return Response(url, b"unexpected request", "text/html", status=404)


def request(*, terms=("Council",), query_extra=None, bounds_extra=None):
    query = {"terms": list(terms), "date_from": "2025-01-01", "date_to": "2025-12-31", "limit": 100}
    query.update(query_extra or {})
    bounds = {"max_pages": 3, "max_records": 100, "parser_bytes": 256_000}
    bounds.update(bounds_extra or {})
    return {"native": True, "source": SOURCE, "query": query, "bounds": bounds}


def run(req=None, *, transport=None, context=None):
    active_transport = transport or SearchTransport()
    result = native_search(create_engine(), req or request(), None, context or OperationContext(),
                           transport=active_transport)
    return result, active_transport


def test_public_engine_registration_uses_actual_native_adapter():
    result = create_engine(provider_transport=SearchTransport()).execute("search", request())
    assert result.status == "partial" and not result.errors
    assert [hit["identity"]["external_id"] for hit in result.data["hits"]] == ["13632", "13638", "13971"]


def test_observed_form_posts_exact_fields_preserves_capture_and_matches_metadata_only():
    result, transport = run()

    assert result.status == "partial"
    assert [hit["identity"]["external_id"] for hit in result.data["hits"]] == ["13632", "13638", "13971"]
    assert result.coverage["native_search"] is True
    assert result.coverage["status"] == "partial"
    assert result.coverage["query_window_exhausted"] is True
    assert result.coverage["catalog_complete"] is False
    assert result.coverage["source_complete"] is False
    assert result.coverage["provider_query_semantics"].endswith("provider-defined")
    assert result.coverage["provider_description_scope"].startswith("displayed result excerpt")
    assert result.coverage["native_fields"] == [
        "title", "description", "meeting_date", "meeting_type", "department", "submitted_for",
    ]

    get_url, get_kwargs = transport.calls[0]
    post_url, post_kwargs = transport.calls[1]
    assert get_url == SOURCE["url"] and get_kwargs["method"] == "GET"
    assert get_kwargs["allow_redirects"] is False
    assert get_kwargs["allowed_origins"] == ("https://public.destinyhosted.com",)
    assert post_url == SEARCH_URL and post_kwargs["method"] == "POST"
    assert post_kwargs["allow_redirects"] is False
    assert post_kwargs["headers"]["Cookie"] == "agendaquick-session=public"
    fields = parse_qs(post_kwargs["body"].decode("ascii"), keep_blank_values=True)
    assert fields == {
        "beg_meetmth": ["1"], "beg_meetyr": ["2025"],
        "end_meetmth": ["12"], "end_meetyr": ["2025"],
        "sstr": ["Council"], "rtn_agline_rowid": [""], "formaction": [""],
        "form_type": ["AG_MEMO"], "mt": ["ALL"], "id": ["98622"],
    }

    capture = result.data["bundle"]["captures"][0]
    raw = (FIXTURES / "agendaquick-search.html").read_bytes()
    import base64
    import json

    assert base64.b64decode(capture["content_base64"]) == raw
    assert capture["sha256"] == sha256(raw).hexdigest()
    record = result.data["hits"][0]["record"]
    assert record["identity"]["derivation"] == "provider_identifier"
    assert record["normalized"]["external_id"] == "13632"
    assert record["normalized"]["description"]
    assert record["text"] == []
    assert result.data["hits"][0]["citation_urls"]
    assert json.loads(json.dumps(record["original"]))["heading_cells"]


def test_hit_limit_does_not_cut_off_later_candidate_on_same_page():
    result, _ = run(request(terms=("Council", "Western Arizona Council of Governments"),
                         query_extra={"limit": 1}))

    assert [hit["identity"]["external_id"] for hit in result.data["hits"]] == ["13971"]
    assert len(result.data["bundle"]["records"]) == 3


def test_public_page_url_is_not_searched_and_description_is_not_claimed_as_full_text():
    result, _ = run(request(terms=("agenda_publish.cfm",)))

    assert result.data["hits"] == []
    assert result.coverage["provider_description_scope"] == (
        "displayed result excerpt/description; not full document text"
    )


def test_body_filter_is_reported_unknown_and_candidates_are_retained():
    result, _ = run(request(query_extra={"body": "budget"}))

    assert len(result.data["hits"]) == 3
    assert result.coverage["body_filter"] == {
        "status": "unknown_retained", "requested": "budget", "applied": False,
    }
    assert result.coverage["limitations"]


def test_empty_marker_and_previous_link_are_not_mistaken_for_next_page():
    result, transport = run(request(terms=("quorumrelayempty987654321",)))

    assert result.status == "partial"
    assert result.data["hits"] == []
    assert result.coverage["query_window_exhausted"] is True
    assert result.coverage["source_complete"] is False
    assert len(transport.calls) == 2
    assert "startRow=-19" in (FIXTURES / "agendaquick-search.html").read_text(encoding="utf-8")


def test_one_record_limit_resumes_three_offsets_and_retry_replays_same_capture_row():
    req = request(bounds_extra={"max_records": 1})
    first, transport = run(req)
    first_checkpoint = first.coverage["checkpoint"]
    assert first.status == "partial" and first_checkpoint
    assert [hit["identity"]["external_id"] for hit in first.data["hits"]] == ["13632"]

    second_request = request(bounds_extra={"max_records": 1, "checkpoint": first_checkpoint})
    second = native_search(create_engine(), second_request, None, OperationContext(), transport=transport)
    assert [hit["identity"]["external_id"] for hit in second.data["hits"]] == ["13638"]
    second_checkpoint = second.coverage["checkpoint"]
    assert second_checkpoint
    assert second.data["hits"][0]["record"]["capture_sha256"] == first.data["hits"][0]["record"]["capture_sha256"]

    retried = native_search(create_engine(), second_request, None, OperationContext(), transport=transport)
    assert [hit["identity"]["external_id"] for hit in retried.data["hits"]] == ["13638"]
    assert retried.coverage["checkpoint"] == second_checkpoint

    third_request = request(bounds_extra={"max_records": 1, "checkpoint": second_checkpoint})
    third = native_search(create_engine(), third_request, None, OperationContext(), transport=transport)
    assert [hit["identity"]["external_id"] for hit in third.data["hits"]] == ["13971"]
    assert third.coverage["checkpoint"] is None
    assert third.coverage["query_window_exhausted"] is True


def test_changed_query_or_authorization_cannot_reuse_checkpoint():
    req = request(bounds_extra={"max_records": 1})
    first, transport = run(req)
    checkpoint = first.coverage["checkpoint"]
    changed = request(terms=("Council", "appointment"), bounds_extra={"max_records": 1,
                      "checkpoint": checkpoint})
    with pytest.raises(ValueError, match="checkpoint"):
        native_search(create_engine(), changed, None, OperationContext(), transport=transport)
    with pytest.raises(ValueError, match="checkpoint"):
        native_search(create_engine(), request(bounds_extra={"max_records": 1, "checkpoint": checkpoint}),
                      None, OperationContext(principal="different-caller"), transport=transport)
    assert len(transport.calls) == 2


def test_required_date_bounds_and_current_form_guard_fail_before_search_post():
    transport = SearchTransport()
    missing_bounds = request()
    missing_bounds["query"].pop("date_to")
    with pytest.raises(ValueError, match="explicit date range"):
        native_search(create_engine(), missing_bounds, None, OperationContext(), transport=transport)
    assert not transport.calls

    changed_calendar = SearchTransport(calendar=(FIXTURES / "agendaquick-calendar.html").read_bytes().replace(
        b"adv_search_results.cfm?fp=ADVSRCH&amp;id=98622",
        b"adv_search_results.cfm?fp=ADVSRCH&amp;id=99999"))
    result = native_search(create_engine(), request(), None, OperationContext(), transport=changed_calendar)
    assert result.status == "failed"
    assert len(changed_calendar.calls) == 1


def test_search_permission_and_cancellation_stop_before_public_request():
    denied = SearchTransport()
    result, _ = run(transport=denied, context=OperationContext(allowed_operations=frozenset({"identify"})))
    assert result.status == "failed"
    assert result.errors[0].code == "permission_denied"
    assert not denied.calls

    cancelled_context = OperationContext()
    cancelled_context.cancellation.set()
    cancelled = SearchTransport()
    result, _ = run(transport=cancelled, context=cancelled_context)
    assert result.status == "cancelled"
    assert not cancelled.calls

