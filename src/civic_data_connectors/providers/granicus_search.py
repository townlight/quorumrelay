"""Bounded native Granicus Clip search from the observed public form."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import re
from time import monotonic
from urllib.parse import parse_qs, urlencode, urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, RetrievalError, _origin
from .discovery import _checkpoint, _resume
from .granicus import listing_rows
from .identification import configured_source, validate_source
from .native import make_bundle


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Source namespace is not authorized."),))
    parts = urlsplit(source.url)
    query_parts = parse_qs(parts.query, keep_blank_values=True)
    if (parts.scheme != "https" or not re.fullmatch(r"[^.]+\.granicus\.com", parts.hostname or "")
            or parts.path.lower() != "/viewpublisher.php" or set(query_parts) != {"view_id"}
            or len(query_parts["view_id"]) != 1 or not re.fullmatch(r"[0-9]{1,12}", query_parts["view_id"][0])):
        raise ValueError("Granicus search requires an HTTPS ViewPublisher source with one numeric view_id.")
    if content is not None or any(key in request for key in ("records", "bundle", "result")):
        raise ValueError("Native search retrieves provider candidates; saved captures use native=false.")
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from, date_to=query.date_to or bounds.date_to)
    if source.body or query.body:
        raise ValueError("The observed Clip search does not establish a body filter.")
    expressions = [*query.terms, *query.phrases]
    if not expressions or any(not value.strip() for value in expressions):
        raise ValueError("Clip search requires at least one nonempty term or phrase.")
    candidate = expressions[0]
    if len(candidate) > 255 or len(candidate.encode("utf-8")) > min(1024, bounds.parser_bytes):
        raise ValueError("The provider search expression exceeds its bound.")
    binding = canonical_hash({"source": source.public_dict(), "query": asdict(query), "scope": context.scope,
                              "contract": "granicus-clip-search/v1"})
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else ([{"page": 1}], set())
    if len(queue) != 1 or set(queue[0]) - {"page", "offset", "sha256"}:
        raise ValueError("Invalid Granicus Clip search checkpoint.")
    task = queue[0]
    page, offset = task.get("page"), task.get("offset", 0)
    if type(page) is not int or not 1 <= page <= 10000 or type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError("Invalid Granicus Clip search checkpoint position.")
    origin = _origin(source.url)
    deadline, pages, records, bundles, captures, errors = monotonic() + bounds.deadline_seconds, 0, [], [], [], []
    next_task = task
    unidentified = 0
    # Do not consume candidates past the output hit limit without a continuation.
    candidate_limit = min(bounds.max_records, query.limit)
    while next_task and pages < bounds.max_pages and len(records) < candidate_limit:
        if operation_cancelled(engine.storage, context) or monotonic() >= deadline:
            break
        task, next_task = next_task, None
        page, offset = task["page"], task.get("offset", 0)
        params = {"view_id": query_parts["view_id"][0], "types[Clip]": "on", "allwords": candidate}
        if page > 1:
            params["pagenumber"] = page
        url = origin + "/ViewSearchResults.php?" + urlencode(params)
        try:
            response = (transport or PublicTransport()).request(url, byte_limit=bounds.parser_bytes,
                deadline_seconds=max(.001, deadline - monotonic()), allowed_origins=(origin,))
            if operation_cancelled(engine.storage, context):
                next_task = task
                break
            if monotonic() >= deadline:
                raise RetrievalError("provider_deadline_exceeded")
            if response.status != 200:
                raise RetrievalError("provider_http_error", status=response.status)
            if _origin(response.url) != origin or len(response.content) > bounds.parser_bytes:
                raise ValueError("The search response left its origin or exceeded its byte bound.")
            digest = hashlib.sha256(response.content).hexdigest()
            if task.get("sha256") and task["sha256"] != digest:
                raise ValueError("The resumed search page changed; restart the search.")
            html = response.content.decode("utf-8", errors="replace")
            if not re.search(r'<table\b[^>]*\bid\s*=\s*["\']searchList["\']', html, re.I):
                raise ValueError("The search result table is unavailable.")
            empty = bool(re.search(r'No results matched your search\.', html, re.I))
            rows = [] if empty else listing_rows(source, response.content)
            unidentified += sum(row[0]["external_id"].startswith("derived:") for row in rows)
            rows = [row for row in rows if not row[0]["external_id"].startswith("derived:")]
            if offset > len(rows) or (empty and offset):
                raise ValueError("The checkpoint offset is outside the search page.")
            markers = re.findall(r'pagination\.load\(\s*(\d+)\s*,\s*(\d+)\s*,', html)
            if len(markers) > 1 or (markers and (int(markers[0][0]) != page or not page <= int(markers[0][1]) <= 10000)):
                raise ValueError("Search pagination does not match the requested page.")
            if page > 1 and not markers:
                raise ValueError("Search pagination metadata is missing.")
            total_pages = int(markers[0][1]) if markers else page
            bundle = make_bundle(source, namespace, response.content, "granicus-listing-html", rows)
            bundle["capture"]["retrieval_url"] = response.url
            selected = []
            for index in range(offset, len(bundle["records"])):
                if operation_cancelled(engine.storage, context) or monotonic() >= deadline or len(records) >= candidate_limit:
                    next_task = {"page": page, "offset": index, "sha256": digest}
                    break
                record = bundle["records"][index]
                key = source_identity_key(record["identity"])
                if key not in seen:
                    seen.add(key)
                    selected.append(record)
                    records.append(record)
            else:
                if page < total_pages:
                    next_task = {"page": page + 1}
            bundle["records"] = selected
            bundles.append(bundle)
            captures.append(bundle["capture"])
            pages += 1
            context.report(operation="search", pages=pages, returned_records=len(records))
        except Exception as exc:
            code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
            errors.append(Error(code, "The provider search page could not be retrieved or parsed.",
                                retryable=True, source=source.url))
            next_task = task
            break
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
                "scope": "native Clip candidates; exact local title and date metadata matching",
                "provider_query_semantics": "provider-defined candidates; first supplied expression; exact local AND",
                "native_fields": ["title", "meeting_date"], "agenda_document_text_searched": False,
                "catalog_complete": False, "source_complete": False, "pages": pages,
                "unidentified_rows_omitted": unidentified,
                "status": "partial", "checkpoint": _checkpoint(binding, [next_task], seen) if next_task else None}
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    if errors and not captures:
        return OperationResult("failed", errors=tuple(errors), coverage=coverage, operation_id=context.operation_id)
    originals = {source_identity_key(row["identity"]): row for row in records}
    local = [{**deepcopy(row), "normalized": {key: row["normalized"].get(key) for key in ("title", "meeting_date")},
              "text": [], "relationships": []} for row in records]
    searched = search_records(local, query, bounds=replace(bounds, checkpoint=None,
        deadline_seconds=max(.001, deadline - monotonic())), sources=coverage["sources"],
        inherited_coverage=coverage, context=context, storage=engine.storage)
    if searched.data is None or searched.status == "cancelled":
        return searched
    for hit in searched.data["hits"]:
        hit["record"] = originals[source_identity_key(hit["identity"])]
    bundle = {"records": records, "captures": captures, "bundles": bundles}
    return OperationResult("partial", {**searched.data, "bundle": bundle}, tuple(errors) + searched.errors,
                           {**searched.coverage, **coverage}, context.operation_id)
