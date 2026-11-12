"""Legistar's documented single-event read, without an unrestricted URL input."""

from __future__ import annotations

import json
import re
from time import monotonic
from urllib.parse import urlencode

from ..engine import _bounded_parser_result
from ..models import Bounds, Error, OperationResult
from .contracts import RetrievalError, _origin
from .discovery import _api_source
from .native import parse_native

DETAIL_DOCUMENTATION = (
    "https://webapi.legistar.com/Help/Api/"
    "GET-v1-Client-Events-EventId_EventItems_AgendaNote_MinutesNote_EventItemAttachments"
)


def fetch_record(source, namespace, external_id, bounds, context, transport):
    """Fetch one event with supplied items, notes and attachment metadata.

    Every optional field is requested explicitly. Missing fields remain absent;
    one event detail does not establish complete discovery or document download.
    """
    if not isinstance(external_id, str) or re.fullmatch(r"[1-9][0-9]{0,18}", external_id) is None:
        raise ValueError("Legistar external_id must be a positive decimal EventId string.")
    if bounds.checkpoint is not None:
        raise ValueError("Single-event retrieval does not accept a catalog checkpoint.")
    if context.check_cancelled():
        return OperationResult("cancelled", operation_id=context.operation_id)
    query = {"EventItems": 1, "AgendaNote": 1, "MinutesNote": 1, "EventItemAttachments": 1}
    token = context.credentials.get("legistar_token")
    if token is not None:
        if not isinstance(token, str) or not token:
            raise ValueError("The configured Legistar credential is invalid.")
        query["token"] = token
    url = _api_source(source) + "/" + external_id + "?" + urlencode(query)
    origin = _origin(url)
    deadline = monotonic() + bounds.deadline_seconds
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}],
                "external_id": external_id, "scope": "one provider event detail",
                "catalog_complete": False, "requested_fields": [key for key in query if key != "token"],
                "available_text": "metadata_and_supplied_text_only", "failures": []}
    try:
        response = transport.request(url, headers={"Accept": "application/json"},
                                     byte_limit=bounds.parser_bytes,
                                     deadline_seconds=max(0.001, deadline - monotonic()),
                                     allowed_origins=(origin,))
        if context.check_cancelled():
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise RetrievalError("provider_deadline_exceeded")
        if response.status != 200:
            raise RetrievalError("provider_http_error", status=response.status)
        if _origin(response.url) != origin or len(response.content) > bounds.parser_bytes:
            raise ValueError("The provider detail left its origin or exceeded parser bounds.")
        original = json.loads(response.content)
        if not isinstance(original, dict) or original.get("EventId") != int(external_id):
            raise ValueError("The provider detail does not match the requested EventId.")
        bundle = parse_native(source, namespace, response.content, "legistar-event-json")
        coverage["source_complete"] = True
        coverage["returned_records"] = 1
        coverage["agenda_items_availability"] = bundle["records"][0]["normalized"]["agenda_items_availability"]
        return _bounded_parser_result(OperationResult("completed", bundle, coverage=coverage,
                                      operation_id=context.operation_id), bounds, context)
    except Exception as error:
        code = error.code if isinstance(error, RetrievalError) else "provider_detail_failed"
        details = ({"http_status": error.status} if isinstance(error, RetrievalError)
                   and error.status is not None else {})
        return OperationResult("failed", errors=(Error(code,
            "The requested provider event could not be retrieved or verified.",
            retryable=True, source=source.url, details=details),),
            coverage={**coverage, "failures": [{"external_id": external_id, "reason": code, **details}]},
            operation_id=context.operation_id)


def native_search(engine, request, content, context, *, transport=None):
    """Native EventBodyName search; never advertise agenda or document text coverage."""
    from copy import deepcopy
    from dataclasses import asdict, replace
    from urllib.parse import parse_qsl, urlsplit, urlunsplit
    from ..engine import source_identity_key
    from ..search import _query, search_records
    from .contracts import PublicTransport
    from .discovery import discover
    from .identification import configured_source, validate_source

    source = configured_source(request["source"])
    validate_source(source, context)
    if content is not None or any(key in request for key in ("records", "bundle", "result")):
        raise ValueError("Native body search retrieves provider records; supplied captures use native=false.")
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from,
                    date_to=query.date_to or bounds.date_to)
    bounds = replace(bounds, date_from=query.date_from, date_to=query.date_to)
    expressions = [*query.terms, *query.phrases]
    if not expressions and not query.body and not source.body:
        raise ValueError("Legistar native body search requires terms, phrases or an exact body filter.")
    if any(not expression.strip() or len(expression.encode("utf-8")) > 1024 for expression in expressions):
        raise ValueError("Native body search expressions must be nonempty bounded strings.")
    if source.body and query.body and source.body != query.body:
        raise ValueError("The query body conflicts with the configured source body.")
    body = query.body or source.body
    source = replace(source, body=body, input_format="legistar-events-json")
    underlying = transport or PublicTransport()
    clauses = []
    for expression in expressions:
        literal = expression.lower().replace("'", "''")
        clauses.append("substringof('" + literal + "',tolower(EventBodyName))")
    if body:
        clauses.append("EventBodyName eq '" + body.replace("'", "''") + "'")
    class BodyQueryTransport:
        def request(self, url, **kwargs):
            parts = urlsplit(url)
            parameters = dict(parse_qsl(parts.query, keep_blank_values=True))
            parameters["$filter"] = " and ".join([parameters["$filter"], *clauses])
            target = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(parameters), ""))
            return underlying.request(target, **kwargs)
    # Bind common-query semantics to the checkpoint: otherwise a caller could
    # replay a prior body query's seen IDs against different expressions.
    binding = {"query": asdict(query), "fields": ["EventBodyName"]}
    from ..engine import canonical_hash
    # Discovery's existing source binding includes options. This key is internal
    # to the native adapter; it is not accepted as arbitrary source configuration.
    checkpoint = bounds.checkpoint
    if checkpoint is not None:
        import base64
        if not isinstance(checkpoint, str) or len(checkpoint) > 400 * 1024:
            raise ValueError("Native body search checkpoint is invalid or too large.")
        try:
            state = json.loads(base64.b64decode(checkpoint, altchars=b"-_", validate=True))
        except (ValueError, UnicodeError):
            raise ValueError("Invalid native body search checkpoint.") from None
        if not isinstance(state, dict) or state.get("query_binding") != canonical_hash(binding):
            raise ValueError("The native checkpoint belongs to a different body search.")
        bounds = replace(bounds, checkpoint=state["checkpoint"])
    deadline = monotonic() + bounds.deadline_seconds
    result = discover(engine, {"source": source.public_dict(), "bounds": asdict(bounds)}, None,
                      context, transport=BodyQueryTransport())
    if not isinstance(result.data, dict) or result.status in {"failed", "cancelled"}:
        return result
    original = {source_identity_key(row["identity"]): row for row in result.data["records"]}
    records = []
    for row in result.data["records"]:
        records.append({**deepcopy(row), "normalized": {"body": row["normalized"].get("body")},
                        "text": [], "relationships": []})
    searched = search_records(records, query,
        bounds=replace(bounds, deadline_seconds=max(0.001, deadline - monotonic())), sources=result.coverage["sources"],
        inherited_coverage={**result.coverage, "status": result.status,
                            "native_search": True, "native_fields": ["EventBodyName"]}, context=context)
    for hit in searched.data["hits"]:
        hit["record"] = deepcopy(original[source_identity_key(hit["identity"])])
    coverage = {**searched.coverage, "scope": "native EventBodyName metadata only; exact local term/phrase filtering",
                "catalog_complete": False, "agenda_document_text_searched": False}
    if result.coverage.get("checkpoint"):
        import base64
        coverage["checkpoint"] = base64.urlsafe_b64encode(json.dumps({
            "query_binding": canonical_hash(binding), "checkpoint": result.coverage["checkpoint"],
        }, separators=(",", ":")).encode()).decode()
    return OperationResult(searched.status, {**searched.data, "bundle": result.data},
                           result.errors + searched.errors, coverage, context.operation_id)
