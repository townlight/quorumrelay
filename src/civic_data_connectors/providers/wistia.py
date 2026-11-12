"""Documented Wistia search with exact local filtering and explicit excerpt caps."""

from __future__ import annotations

import json
from dataclasses import replace
from math import isfinite
from time import monotonic
from urllib.parse import urlencode, urlsplit

from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from .contracts import PublicTransport, RetrievalError, _origin
from .identification import configured_source, validate_source
from .native import make_bundle, wistia_row


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Source namespace is not authorized."),))
    parsed = urlsplit(source.url)
    if parsed.hostname != "api.wistia.com" or parsed.path.rstrip("/") != "/modern/medias":
        raise ValueError("Wistia native search requires the configured https://api.wistia.com/modern/medias source.")
    if content is not None or any(key in request for key in ("records", "bundle", "result")):
        raise ValueError("Native search retrieves provider matches; local captures use native=false.")
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from,
                    date_to=query.date_to or bounds.date_to)
    if bounds.checkpoint is not None:
        raise ValueError("The Wistia search endpoint does not provide continuation pagination.")
    expressions = [*query.terms, *query.phrases]
    if not expressions or any(not value.strip() for value in expressions):
        raise ValueError("Wistia native search requires at least one nonempty term or phrase.")
    provider_query = " ".join(expressions)
    if len(provider_query.encode("utf-8")) > min(4096, bounds.parser_bytes):
        raise ValueError("The native search query exceeds its bounded request size.")
    token = context.credentials.get("wistia_token")
    if not isinstance(token, str) or not token:
        return OperationResult("failed", errors=(Error("credentials_required",
            "Wistia native search requires a trusted server-side account read token."),),
            operation_id=context.operation_id)
    if context.check_cancelled():
        return OperationResult("cancelled", operation_id=context.operation_id)
    url = "https://api.wistia.com/modern/search?" + urlencode({"q": provider_query, "resource_type[]": "media"})
    deadline = monotonic() + bounds.deadline_seconds
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
                "provider_query_semantics": "provider-defined candidates; exact terms/phrases checked locally",
                "provider_query": provider_query, "catalog_complete": False,
                "provider_caps": {"primary_matches": 100, "additional_transcript_matches": 100,
                                  "pagination": False},
                "available_text": "metadata_and_provider_supplied_transcript_match_excerpts",
                "meeting_dates": "not inferred from media upload timestamps", "failures": []}
    try:
        response = (transport or PublicTransport()).request(
            url, headers={"Authorization": "Bearer " + token, "X-Wistia-API-Version": "2026-09",
                          "Accept": "application/json"},
            byte_limit=bounds.parser_bytes, deadline_seconds=max(0.001, deadline - monotonic()),
            allowed_origins=("https://api.wistia.com",))
        if context.check_cancelled():
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise RetrievalError("provider_deadline_exceeded")
        if response.status != 200:
            raise RetrievalError("provider_http_error", status=response.status)
        if _origin(response.url) != "https://api.wistia.com" or len(response.content) > bounds.parser_bytes:
            raise ValueError("The native response left its origin or exceeded parser bounds.")
        original = json.loads(response.content)
        data = original.get("data") if isinstance(original, dict) else None
        medias = data.get("medias") if isinstance(data, dict) else None
        if not isinstance(medias, list) or len(medias) > 200 or any(not isinstance(row, dict) for row in medias):
            raise ValueError("The native response does not contain a bounded media result array.")
        rows = []
        for raw in medias:
            normalized, kind = wistia_row(source, raw)
            rows.append((normalized, raw, kind))
        bundle = make_bundle(source, namespace, response.content, "wistia-search-json", rows)
        for record in bundle["records"]:
            matches = record["original"].get("transcript_matches", [])
            if not isinstance(matches, list):
                raise ValueError("Native transcript matches must be an array.")
            segments = []
            for index, match in enumerate(matches):
                if (not isinstance(match, dict) or not isinstance(match.get("text"), str)
                        or type(match.get("start_time_seconds")) not in {int, float}
                        or not isfinite(match["start_time_seconds"]) or match["start_time_seconds"] < 0):
                    raise ValueError("A native transcript match requires supplied text and timestamp.")
                segments.append({**match, "field": f"transcript_matches[{index}]",
                                 "citation_url": record["normalized"]["url"],
                                 "timestamp_seconds": match["start_time_seconds"],
                                 "completeness": "partial"})
            record["text"] = segments
        # The endpoint exposes no cursor; its documented caps and excerpt nature
        # remain partial even when fewer than the maximum candidates are returned.
        coverage.update({"status": "partial", "provider_returned_records": len(medias),
                         "candidate_limit_reached": len(medias) >= 100,
                         "supplied_transcript_excerpts_only": True})
        remaining = max(0.001, deadline - monotonic())
        result = search_records(bundle["records"], query, bounds=replace(bounds, deadline_seconds=remaining),
                                sources=coverage["sources"],
                                inherited_coverage=coverage, context=context, storage=engine.storage)
        return OperationResult(result.status, {**result.data, "bundle": bundle}, result.errors,
                               {**result.coverage, "scope": "native provider candidates and exact local excerpt matching"},
                               context.operation_id)
    except Exception as error:
        code = error.code if isinstance(error, RetrievalError) else "provider_search_failed"
        details = ({"http_status": error.status} if isinstance(error, RetrievalError)
                   and error.status is not None else {})
        return OperationResult("failed", errors=(Error(code,
            "The provider search could not be retrieved or verified.", retryable=True,
            source=source.url, details=details),),
            coverage={**coverage, "failures": [{"reason": code, **details}]}, operation_id=context.operation_id)


def fetch_record(source, namespace, external_id, bounds, context, transport, *, caption_language=None):
    """Retrieve the documented authenticated Media detail, with exact captured bytes."""
    import re
    from ..engine import _bounded_parser_result
    from .native import parse_native

    if not isinstance(external_id, str) or re.fullmatch(r"[A-Za-z0-9]{1,128}", external_id) is None:
        raise ValueError("Wistia external_id must be a provider-issued alphanumeric media hashed ID.")
    if (caption_language is not None and caption_language != "*"
            and (not isinstance(caption_language, str)
                 or re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", caption_language) is None)):
        raise ValueError("Caption language must be a provider language code or * for supplied tracks.")
    parsed = urlsplit(source.url)
    if parsed.hostname != "api.wistia.com" or parsed.path.rstrip("/") != "/modern/medias":
        raise ValueError("Wistia media detail requires the configured https://api.wistia.com/modern/medias source.")
    if bounds.checkpoint is not None:
        raise ValueError("Single-media retrieval does not accept a catalog checkpoint.")
    token = context.credentials.get("wistia_token")
    if not isinstance(token, str) or not token:
        return OperationResult("failed", errors=(Error("credentials_required",
            "Wistia media detail requires a trusted server-side account read token."),),
            operation_id=context.operation_id)
    if context.check_cancelled():
        return OperationResult("cancelled", operation_id=context.operation_id)
    url = "https://api.wistia.com/modern/medias/" + external_id
    if caption_language is not None:
        url += "/captions"
        if caption_language != "*":
            url += "/" + caption_language + "?include=segments"
    deadline = monotonic() + bounds.deadline_seconds
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "external_id": external_id,
                "scope": "one provider media detail", "catalog_complete": False,
                "available_text": "metadata_and_supplied_text_only", "failures": []}
    try:
        response = transport.request(url, headers={"Authorization": "Bearer " + token,
            "X-Wistia-API-Version": "2026-09", "Accept": "application/json"},
            byte_limit=bounds.parser_bytes, deadline_seconds=max(0.001, deadline - monotonic()),
            allowed_origins=("https://api.wistia.com",))
        if context.check_cancelled():
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise RetrievalError("provider_deadline_exceeded")
        if response.status != 200:
            raise RetrievalError("provider_http_error", status=response.status)
        if _origin(response.url) != "https://api.wistia.com" or len(response.content) > bounds.parser_bytes:
            raise ValueError("The provider detail left its origin or exceeded parser bounds.")
        original = json.loads(response.content)
        status = "completed"
        if caption_language is None:
            if not isinstance(original, dict) or original.get("hashed_id") != external_id:
                raise ValueError("The provider detail does not match the requested media hashed ID.")
            input_format = "wistia-media-detail-json"
        else:
            tracks = original if caption_language == "*" else [original]
            if not isinstance(tracks, list) or any(not isinstance(row, dict)
                    or row.get("media_id") != external_id
                    or (caption_language != "*" and row.get("language") != caption_language) for row in tracks):
                raise ValueError("The supplied captions do not match their requested media/language.")
            input_format = "wistia-caption-json"
            coverage.update({"scope": "supplied caption tracks for one media", "language": caption_language,
                             "generation_requested": False,
                             "permission_limits": "An empty caption list can reflect delegated-token visibility."})
            if not tracks or any(not row.get("text") and not row.get("segments") for row in tracks):
                status = "partial"
        bundle = parse_native(source, namespace, response.content, input_format)
        return _bounded_parser_result(OperationResult(status, bundle, coverage=coverage,
                                      operation_id=context.operation_id), bounds, context)
    except Exception as error:
        code = error.code if isinstance(error, RetrievalError) else "provider_detail_failed"
        details = ({"http_status": error.status} if isinstance(error, RetrievalError)
                   and error.status is not None else {})
        return OperationResult("failed", errors=(Error(code,
            "The requested media could not be retrieved or verified.", retryable=True,
            source=source.url, details=details),),
            coverage={**coverage, "failures": [{"external_id": external_id, "reason": code, **details}]},
            operation_id=context.operation_id)
