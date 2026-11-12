"""Observed public SuiteOne keyword results, with bounded capture continuations."""

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
from hashlib import sha256
from time import monotonic
from urllib.parse import urlencode, urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
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
    if (request.get("native") is not True or content is not None
            or any(key in request for key in ("content_base64", "records", "bundle", "result"))
            or parts.scheme != "https" or not (parts.hostname or "").endswith(".suiteonemedia.com")
            or parts.path not in ("", "/") or parts.query or parts.fragment):
        raise ValueError("SuiteOne native search requires a configured public HTTPS tenant root and no saved input.")
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from, date_to=query.date_to or bounds.date_to)
    expressions = [*query.terms, *query.phrases]
    if not expressions or len(expressions[0]) > 512:
        raise ValueError("A bounded nonempty native search expression is required.")
    if source.body or query.body or (query.record_types and set(query.record_types) != {"meeting"}):
        raise ValueError("The observed SuiteOne public keyword route establishes meeting results, without a body filter.")
    if not query.date_from or not query.date_to:
        raise ValueError("SuiteOne native search requires explicit inclusive date bounds.")
    binding = canonical_hash({"source": source.public_dict(), "query": asdict(query), "scope": context.scope,
        "authorization": sorted(context.authorization),
        "operations": None if context.allowed_operations is None else sorted(context.allowed_operations),
        "namespaces": None if context.allowed_namespaces is None else sorted(context.allowed_namespaces),
        "contract": "suiteone-keyword-current-results/v1"})
    task, seen = {"offset": 0}, set()
    if bounds.checkpoint:
        queue, seen = _resume(bounds.checkpoint, binding)
        if len(queue) != 1:
            raise ValueError("Invalid SuiteOne search continuation.")
        task = queue[0]
    if (set(task) - {"offset", "sha256"} or type(task.get("offset")) is not int
            or not 0 <= task["offset"] <= 10000 or (task["offset"] and not task.get("sha256"))):
        raise ValueError("Invalid SuiteOne search capture position.")
    origin, deadline = _origin(source.url), monotonic() + bounds.deadline_seconds
    active = transport or PublicTransport()
    coverage = {"native_search": True, "sources": [{**source.public_dict(), "namespace": namespace}],
        "scope": "public keyword result capture; title/date matching over returned meetings only",
        "catalog_complete": False, "source_complete": False, "full_document_text_searched": False,
        "provider_query_semantics": "provider-defined first expression; exact local metadata matching",
        "server_date_semantics": "unverified; returned dates also checked locally",
        "older_group_search_semantics": "unverified; unfiltered Older Meetings controls are not followed"}
    records, bundles, errors, next_task = [], [], [], task

    def stopped():
        return operation_cancelled(engine.storage, context) or monotonic() >= deadline

    def retrieve(url, **kwargs):
        if stopped():
            raise RetrievalError("provider_deadline_or_cancellation")
        response = active.request(url, byte_limit=bounds.parser_bytes,
            deadline_seconds=max(.001, deadline - monotonic()), allowed_origins=(origin,),
            allow_redirects=False, **kwargs)
        if (response.status != 200 or response.url != url or len(response.content) > bounds.parser_bytes
                or response.content_type.split(";")[0].strip().lower() != "text/html" or stopped()):
            raise RetrievalError("provider_search_response_invalid", status=response.status)
        return response.content

    try:
        root = retrieve(source.url)
        if (b'id="searchEventsForm"' not in root or b'action="/Home/SearchEvents"' not in root
                or b'id="ev-search"' not in root or b'value="-1"' not in root):
            raise ValueError("The current public keyword controls are unavailable.")
        fields = {"search": expressions[0], "category": "-1", "psize": "10", "page": "1",
            "dateFrom": date.fromisoformat(query.date_from).strftime("%m/%d/%Y"),
            "dateTo": date.fromisoformat(query.date_to).strftime("%m/%d/%Y")}
        raw = retrieve(origin + "/Home/GetRecentEvents", method="POST", body=urlencode(fields).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        digest = sha256(raw).hexdigest()
        if task.get("sha256") and task["sha256"] != digest:
            raise ValueError("The resumed keyword capture changed; restart the search.")
        if b"There are no events found for the selected options" in raw:
            if task["offset"]:
                raise ValueError("The resumed result set became empty.")
            next_task = None
            bundles.append(make_bundle(source, namespace, raw, "suiteone-archive-html", []))
        else:
            result = engine.normalize(replace(source, body=None), raw, input_format="suiteone-archive-html",
                bounds=replace(bounds, checkpoint=None, date_from=None, date_to=None, max_records=10000), context=context)
            if result.status in {"failed", "cancelled"} or not result.data or not result.data.get("records"):
                raise ValueError("The public search did not provide readable meeting rows.")
            bundle = result.data
            candidates = bundle["records"]
            if task["offset"] > len(candidates):
                raise ValueError("The continuation exceeds the captured result set.")
            index = task["offset"]
            while index < len(candidates) and len(records) < bounds.max_records and not stopped():
                record = candidates[index]
                index += 1
                key = source_identity_key(record["identity"])
                if key not in seen:
                    seen.add(key)
                    records.append(record)
            next_task = {"offset": index, "sha256": digest} if index < len(candidates) else None
            bundle["records"] = records
            bundles.append(bundle)
    except Exception as exc:
        code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
        errors.append(Error(code, "The public SuiteOne keyword capture could not be retrieved or verified; restart if it changed.",
                            retryable=True, source=source.url))
    coverage.update(pages=len(bundles), provider_candidates=len(records), truncated=bool(next_task),
        checkpoint=_checkpoint(binding, [next_task], seen) if next_task else None)
    if not records:
        status = "cancelled" if operation_cancelled(engine.storage, context) else "failed" if errors else "partial"
        return OperationResult(status, {"hits": [], "records": [], "query": asdict(query), "bundles": bundles},
                               tuple(errors), coverage, context.operation_id)
    originals = {source_identity_key(r["identity"]): r for r in records}
    local = [{**deepcopy(r), "normalized": {k: r["normalized"].get(k) for k in ("title", "meeting_date")},
              "text": []} for r in records]
    matched = search_records(local, query, bounds=replace(bounds, checkpoint=None,
        deadline_seconds=max(.001, deadline - monotonic())), sources=coverage["sources"],
        inherited_coverage=coverage, context=context, storage=engine.storage)
    data = matched.data or {}
    for hit in data.get("hits", []):
        hit["record"] = originals[source_identity_key(hit["identity"])]
    data["records"] = [h["record"] for h in data.get("hits", [])]
    status = "cancelled" if operation_cancelled(engine.storage, context) else "failed" if errors and not bundles else "partial"
    return OperationResult(status, {**data, "bundles": bundles}, tuple(errors) + matched.errors,
                           {**matched.coverage, **coverage}, context.operation_id)
