"""Keyword requests through supplied public Agenda Center year controls."""

from copy import deepcopy
from dataclasses import asdict, replace
from time import monotonic
from urllib.parse import urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .agendacenter import controls, form_body
from .contracts import PublicTransport, RetrievalError, _origin
from .discovery import _checkpoint, _resume
from .identification import configured_source, validate_source
from .native import make_bundle


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Source namespace is not authorized."),))
    parts = urlsplit(source.url)
    if (request.get("native") is not True or content is not None or parts.scheme != "https"
            or parts.path.rstrip("/").lower() != "/agendacenter" or parts.query or parts.fragment
            or any(k in request for k in ("content_base64", "records", "bundle", "result"))):
        raise ValueError("Agenda Center native search requires its configured public HTTPS root and no saved input.")
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    lower = max(filter(None, (query.date_from, bounds.date_from)), default=None)
    upper = min(filter(None, (query.date_to, bounds.date_to)), default=None)
    expressions = [*query.terms, *query.phrases]
    if not lower or not upper or lower > upper or not expressions or len(expressions[0]) > 256:
        raise ValueError("A nonempty explicit date range and bounded native search expression are required.")
    if query.record_types and set(query.record_types) != {"meeting"}:
        raise ValueError("The observed Agenda Center results expose meeting agenda rows only.")
    query = replace(query, date_from=lower, date_to=upper, body=query.body or source.body)
    binding = canonical_hash({"source": source.public_dict(), "query": asdict(query), "scope": context.scope,
        "authorization": sorted(context.authorization),
        "operations": None if context.allowed_operations is None else sorted(context.allowed_operations),
        "namespaces": None if context.allowed_namespaces is None else sorted(context.allowed_namespaces),
        "contract": "agendacenter-year-keyword/v1"})
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else (None, set())
    origin, deadline = _origin(source.url), monotonic() + bounds.deadline_seconds
    records, bundles, errors, pages = [], [], [], 0
    current = None

    def stopped():
        return operation_cancelled(engine.storage, context) or monotonic() >= deadline

    def retrieve(url, **kwargs):
        if stopped():
            raise RetrievalError("provider_deadline_or_cancellation")
        response = (transport or PublicTransport()).request(url, byte_limit=bounds.parser_bytes,
            deadline_seconds=max(.001, deadline-monotonic()), allowed_origins=(origin,), allow_redirects=False, **kwargs)
        if (response.status != 200 or response.url != url or len(response.content) > bounds.parser_bytes
                or response.content_type.split(";")[0].strip().lower() != "text/html" or stopped()):
            raise RetrievalError("provider_search_response_invalid", status=response.status)
        return response.content

    try:
        public = controls(retrieve(source.url))
        available = [fields for fields in public if lower[:4] <= fields["year"] <= upper[:4]]
        if not available:
            raise ValueError("The requested years have no supplied public controls.")
        if queue is None:
            queue = [{"fields": fields, "offset": 0} for fields in available]
        while queue and pages < bounds.max_pages and len(records) < bounds.max_records and not stopped():
            current = queue.pop(0)
            if (set(current) - {"fields", "offset", "sha256"} or current.get("fields") not in available
                    or type(current.get("offset")) is not int or not 0 <= current["offset"] <= 10000
                    or (current["offset"] and not current.get("sha256"))):
                raise ValueError("The continuation changed its current public year control or position.")
            raw = retrieve(origin + "/AgendaCenter/UpdateCategoryList", method="POST",
                body=form_body({**current["fields"], "term": expressions[0]}),
                headers={"Content-Type": "application/x-www-form-urlencoded"})
            if b"An error has occurred in this application" in raw:
                bundles.append(make_bundle(source, namespace, raw, "agenda-center-html", []))
                raise ValueError("The provider returned an application-error page, not an empty result.")
            result = engine.normalize(replace(source, body=None), raw, input_format="agenda-center-html",
                bounds=replace(bounds, date_from=None, date_to=None, checkpoint=None, max_records=10000), context=context)
            if result.status in {"failed", "cancelled"} or not result.data or not result.data.get("records"):
                bundles.append(make_bundle(source, namespace, raw, "agenda-center-html", []))
                raise ValueError("No readable rows or verified empty-result marker were supplied.")
            bundle, index = result.data, current["offset"]
            candidates = sorted(bundle["records"], key=lambda record: record["identity"]["external_id"])
            # Published HTML generates fresh DOM row IDs on every response.
            # They are not record identities or search rank. Bind the mapped
            # provider values and preserve each exact response independently.
            digest = canonical_hash([{key: record[key] for key in ("identity", "normalized", "original")}
                                     for record in candidates])
            if current.get("sha256") and current["sha256"] != digest:
                raise ValueError("The mapped keyword result set changed; restart its continuation.")
            if index > len(candidates):
                raise ValueError("The continuation exceeds its captured page.")
            selected = []
            while index < len(candidates) and len(records) < bounds.max_records and not stopped():
                record = candidates[index]
                index += 1
                key = source_identity_key(record["identity"])
                if key not in seen:
                    selected.append(record)
                    records.append(record)
                    seen.add(key)
            bundle["records"] = selected
            bundle["capture"]["retrieval_url"] = origin + "/AgendaCenter/UpdateCategoryList"
            bundles.append(bundle)
            pages += 1
            if index < len(candidates):
                queue.insert(0, {**current, "offset": index, "sha256": digest})
            current = None
            context.report(operation="search", pages=pages, returned_records=len(records))
    except Exception as exc:
        code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
        errors.append(Error(code, "The public Agenda Center keyword page could not be retrieved or verified; application errors are not empty results.",
                            retryable=True, source=source.url))
        if current is not None:
            queue.insert(0, current)
    coverage = {"native_search": True, "sources": [{**source.public_dict(), "namespace": namespace}],
        "scope": "supplied public year/category keyword requests; title/date metadata only",
        "full_document_text_searched": False, "catalog_complete": False, "source_complete": False,
        "provider_query_semantics": "provider-defined term parameter; exact local title matching",
        "continuation_binding": "canonical mapped provider rowset; exact HTML retained; generated DOM IDs and rank are not identities",
        "body_filter": {"requested": query.body, "applied": False, "status": "unknown_retained" if query.body else "not_requested"},
        "pages": pages, "truncated": bool(queue),
        "checkpoint": _checkpoint(binding, queue, seen) if queue else None}
    if not records:
        status = "cancelled" if operation_cancelled(engine.storage, context) else "failed" if errors else "partial"
        return OperationResult(status, {"hits": [], "records": [], "bundles": bundles, "query": asdict(query)},
                               tuple(errors), coverage, context.operation_id)
    originals = {source_identity_key(r["identity"]): r for r in records}
    local = [{**deepcopy(r), "normalized": {k: r["normalized"].get(k) for k in ("title", "meeting_date")}, "text": []}
             for r in records]
    matched = search_records(local, replace(query, body=None), bounds=replace(bounds, checkpoint=None,
        deadline_seconds=max(.001, deadline-monotonic())), sources=coverage["sources"], inherited_coverage=coverage,
        context=context, storage=engine.storage)
    data = matched.data or {}
    for hit in data.get("hits", []):
        hit["record"] = originals[source_identity_key(hit["identity"])]
    data.update(records=[h["record"] for h in data.get("hits", [])], query=asdict(query))
    status = "cancelled" if operation_cancelled(engine.storage, context) else "partial"
    return OperationResult(status, {**data, "bundles": bundles}, tuple(errors)+matched.errors,
                           {**matched.coverage, **coverage}, context.operation_id)
