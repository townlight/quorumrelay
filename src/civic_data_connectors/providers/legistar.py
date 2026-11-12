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


def fetch_related(source, namespace, request, bounds, context, transport):
    """Read supplied Vote/RollCall rows under one explicitly selected EventItem.

    Collections use the API's OData integer-ID keyset. Checkpoints bind the parent,
    entity, tenant and caller scope; they are progress cursors, not snapshots.
    """
    from dataclasses import replace
    from ..engine import canonical_hash
    from .discovery import _checkpoint, _resume, _page_size
    kind = request.get("record_type")
    if kind not in {"vote", "roll_call"}:
        raise ValueError("Legistar related reads require record_type vote or roll_call.")
    parent, external_id = request.get("parent_id"), request.get("external_id")
    for value in [parent, *([external_id] if external_id is not None else [])]:
        if not isinstance(value, str) or re.fullmatch(r"[1-9][0-9]{0,18}", value) is None:
            raise ValueError("Related Legistar IDs must be positive decimal strings.")
    if external_id is not None and bounds.checkpoint:
        raise ValueError("One related detail does not accept a collection checkpoint.")
    if bounds.date_from or bounds.date_to or source.body:
        raise ValueError("Related rows have no meeting date/body; select the parent EventItem explicitly.")
    prefix, route, input_format = (("Vote", "Votes", "legistar-votes-json") if kind == "vote"
                                   else ("RollCall", "RollCalls", "legistar-rollcalls-json"))
    base = _api_source(source).removesuffix("/Events") + f"/EventItems/{parent}/{route}"
    origin = _origin(base)
    binding = canonical_hash({"source": source.public_dict(), "namespace": namespace,
                              "parent": parent, "kind": kind, "scope": context.scope})
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else ([{"after": 0}], set())
    if len(queue) > 1 or (queue and (set(queue[0]) != {"after"}
            or type(queue[0]["after"]) is not int or queue[0]["after"] < 0)):
        raise ValueError("Invalid related-read checkpoint task.")
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}],
                "scope": "one EventItem supplied " + route, "parent_id": parent,
                "catalog_complete": False, "collection_complete": False,
                "snapshot_consistency": "not_guaranteed", "failures": [], "pages": 0}
    deadline, records, bundles, errors = monotonic() + bounds.deadline_seconds, [], [], []
    try:
        while queue and coverage["pages"] < bounds.max_pages and len(records) < bounds.max_records:
            if context.check_cancelled():
                return OperationResult("cancelled", {"records": records, "bundles": bundles},
                                       coverage=coverage, operation_id=context.operation_id)
            after = queue[0]["after"]
            size = min(_page_size(source), bounds.max_records - len(records))
            parameters = {} if external_id is not None else {
                "$top": size, "$orderby": prefix + "Id", "$filter": prefix + "Id gt " + str(after)}
            token = context.credentials.get("legistar_token")
            if token is not None:
                if not isinstance(token, str) or not token:
                    raise ValueError("Invalid Legistar credential.")
                parameters["token"] = token
            url = base + ("/" + external_id if external_id is not None else "")
            if parameters:
                url += "?" + urlencode(parameters)
            response = transport.request(url, headers={"Accept": "application/json"},
                byte_limit=bounds.parser_bytes, deadline_seconds=max(0.001, deadline - monotonic()),
                allowed_origins=(origin,))
            if context.check_cancelled():
                return OperationResult("cancelled", {"records": records, "bundles": bundles},
                                       coverage=coverage, operation_id=context.operation_id)
            if monotonic() >= deadline:
                raise RetrievalError("provider_deadline_exceeded")
            if response.status != 200:
                raise RetrievalError("provider_http_error", status=response.status)
            from urllib.parse import urlsplit
            if (_origin(response.url) != origin or urlsplit(response.url).path != urlsplit(url).path
                    or len(response.content) > bounds.parser_bytes):
                raise ValueError("Related response exceeded its origin or parser bound.")
            original = json.loads(response.content)
            if external_id is not None:
                if not isinstance(original, dict) or original.get(prefix + "Id") != int(external_id):
                    raise ValueError("Related detail identity mismatch.")
                entries = [original]
            else:
                if not isinstance(original, list) or len(original) > size:
                    raise ValueError("Collection ignored the bounded query or returned an invalid shape.")
                entries = original
            ids = [row.get(prefix + "Id") if isinstance(row, dict) else None for row in entries]
            if (any(type(value) is not int or value <= after for value in ids)
                    or ids != sorted(set(ids)) or any(row.get(prefix + "EventItemId") != int(parent)
                                                    for row in entries)):
                raise ValueError("Related rows did not match their parent or advance their keyset.")
            bundle = parse_native(replace(source, url=base), namespace, response.content, input_format)
            parsed = _bounded_parser_result(OperationResult("completed", bundle), bounds, context)
            if parsed.status != "completed":
                raise ValueError("Related response exceeded normalized parser bounds.")
            records.extend(bundle["records"])
            bundles.append(bundle)
            coverage["pages"] += 1
            if external_id is not None or len(entries) < size:
                queue.clear()
            else:
                queue[0] = {"after": ids[-1]}
        coverage["returned_records"] = len(records)
        coverage["collection_complete"] = not queue
        coverage["source_complete"] = not queue
        coverage["checkpoint"] = _checkpoint(binding, queue, seen) if queue else None
        coverage["truncated"] = bool(queue)
        return OperationResult("partial" if queue else "completed",
            bundles[0] if external_id is not None and bundles else {"records": records, "bundles": bundles},
            coverage=coverage, operation_id=context.operation_id)
    except Exception as error:
        code = error.code if isinstance(error, RetrievalError) else "provider_related_read_failed"
        details = {"http_status": error.status} if isinstance(error, RetrievalError) and error.status else {}
        errors.append(Error(code, "The related provider rows could not be retrieved or verified.",
                            retryable=True, source=source.url, details=details))
        coverage["failures"].append({"reason": code, **details})
        coverage["checkpoint"] = _checkpoint(binding, queue, seen) if queue and external_id is None else None
        return OperationResult("partial" if records else "failed",
            {"records": records, "bundles": bundles} if records else None, tuple(errors), coverage,
            context.operation_id)


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
