"""Observed public Select Search candidates; provider excerpts remain partial."""

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime
from hashlib import sha256
from http.cookiejar import CookieJar
import json
from time import monotonic
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from ..compat import _visible_text
from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, RetrievalError, _origin
from .discovery import _api_source
from .identification import configured_source, validate_source
from .native import make_bundle
from .novus import _Sessions, _SESSION_LOCK

FORMAT = "civicplus-search-json"
KINDS = {"agenda": "agenda", "agendaFiles": "agenda_file", "attachments": "attachment",
         "items": "agenda_item", "videoTimestamps": "video_timestamp", "closedCaptions": "caption_excerpt"}


def _sessions(engine):
    with _SESSION_LOCK:
        if not hasattr(engine, "_select_search_sessions"):
            engine._select_search_sessions = _Sessions()
        return engine._select_search_sessions


def search_rows(source, content):
    payload = json.loads(content)
    if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
        raise ValueError("The public Search response requires a value collection.")
    portal = "https://" + urlsplit(_api_source(source)).hostname.replace(".api.", ".portal.")
    rows = []
    for group in payload["value"]:
        event = group.get("event") if isinstance(group, dict) else None
        link = event.get("resourceLink") if isinstance(event, dict) else None
        parent = str(link.get("resourceId", "")) if isinstance(link, dict) else ""
        if not parent.isascii() or not parent.isdecimal() or link.get("path") != "event":
            raise ValueError("The public Search group has no supplied parent event identity.")
        if not isinstance(event.get("name"), str) or not event["name"].strip():
            raise ValueError("The public Search event has no title.")
        day = datetime.fromisoformat(event["meetingDate"].replace("Z", "+00:00")).date().isoformat()
        base = {"meeting_date": day, "url": portal + "/event/" + parent + "/files",
                "documents": [], "recordings": [], "date_basis": "supplied meetingDate calendar component",
                "source_meeting_date": event["meetingDate"]}
        location = event.get("eventLocation") or {}
        rows.append(({**base, "external_id": parent, "title": _visible_text(event["name"]),
                      "body": event.get("categoryName"),
                      "location": {k: _visible_text(v) for k, v in location.items() if isinstance(v, str)}},
                     deepcopy(group), "meeting"))
        for field, kind in KINDS.items():
            values = group.get(field) or []
            if isinstance(values, dict):
                values = [values]
            if not isinstance(values, list):
                raise ValueError("The public Search child collection changed shape.")
            for value in values:
                if not isinstance(value, dict):
                    raise ValueError("The public Search child is not an object.")
                identity, resource = str(value.get("id", "")), value.get("resourceLink")
                if (not identity.isascii() or not identity.isdecimal() or not isinstance(resource, dict)
                        or str(resource.get("resourceId")) != parent):
                    raise ValueError("The public Search child lacks its parent-bound supplied identity.")
                excerpts = value.get("fileContent") or []
                if not isinstance(excerpts, list) or any(not isinstance(text, str) for text in excerpts):
                    raise ValueError("The public Search excerpts changed shape.")
                rows.append(({**base, "external_id": identity, "title": _visible_text(str(value.get("name") or kind)),
                              "body": event.get("categoryName"), "search_excerpts": [_visible_text(x) for x in excerpts],
                              "excerpt_completeness": "provider_returned_excerpts_not_full_text"},
                             {"parent_event_id": parent, "search_role": field, "value": deepcopy(value)}, kind))
    return rows


def search_bundle(source, namespace, content):
    bundle = make_bundle(source, namespace, content, FORMAT, search_rows(source, content))
    for record in bundle["records"]:
        if record["identity"]["record_type"] != "meeting":
            parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
                      "external_id": record["original"]["parent_event_id"]}
            record["identity"]["parent"] = parent
            record["relationships"].append({"relation": "meeting", "identity": parent})
    return bundle


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Source namespace is not authorized."),))
    if (request.get("native") is not True or content is not None
            or any(k in request for k in ("content_base64", "records", "bundle", "result"))):
        raise ValueError("Select native Search retrieves public candidates; saved records use local search.")
    endpoint = _api_source(source).rsplit("/Events", 1)[0] + "/Search"
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    lower = max(filter(None, (query.date_from, bounds.date_from)), default=None)
    upper = min(filter(None, (query.date_to, bounds.date_to)), default=None)
    if not lower or not upper or lower > upper:
        raise ValueError("Select public Search requires a nonempty explicit date window.")
    query = replace(query, date_from=lower, date_to=upper, body=query.body or source.body)
    expressions = [*query.terms, *query.phrases]
    if not expressions or len(expressions[0]) > 512:
        raise ValueError("Select public Search requires a bounded term or phrase.")
    binding = canonical_hash({"source": source.public_dict(), "scope": context.scope, "query": asdict(query),
        "authorization": sorted(context.authorization),
        "operations": None if context.allowed_operations is None else sorted(context.allowed_operations),
        "namespaces": None if context.allowed_namespaces is None else sorted(context.allowed_namespaces),
        "contract": "select-public-search/v1"})
    task, seen, cached = {"skip": 0, "offset": 0}, set(), b""
    if bounds.checkpoint:
        try:
            state = _sessions(engine).get(bounds.checkpoint, binding)
        except ValueError:
            raise ValueError("Select Search continuation expired, belongs to another caller/source, or its engine restarted.") from None
        task, seen, cached = state["pending"], state["seen"], state["content"]
    if (set(task) - {"skip", "offset", "sha256", "previous_sha256"}
            or any(type(task.get(k)) is not int or not 0 <= task[k] <= 100000 for k in ("skip", "offset"))
            or (task["offset"] and not task.get("sha256"))):
        raise ValueError("Select Search continuation position is invalid.")
    deadline, origin = monotonic() + bounds.deadline_seconds, _origin(endpoint)
    active, session = transport or PublicTransport(), str(uuid4())
    records, bundles, errors, pages, finished = [], [], [], 0, False
    current_raw = cached

    def stopped():
        return operation_cancelled(engine.storage, context) or monotonic() >= deadline

    try:
        while pages < bounds.max_pages and len(records) < bounds.max_records and not stopped():
            fields = {"search": expressions[0], "startDate": lower + "T00:00:00.000Z",
                      "endDate": upper + "T23:59:59.999Z"}
            if task["skip"]:
                fields["$skip"] = str(task["skip"])
            url = endpoint + "?" + urlencode(fields)
            if cached:
                raw, cached = cached, b""
                if len(raw) > bounds.parser_bytes:
                    raise ValueError("The saved Search capture exceeds current parser bounds.")
            else:
                response = active.request(url, headers={"Accept": "application/json", "X-Stream-Session": session},
                    byte_limit=bounds.parser_bytes, deadline_seconds=max(.001, deadline-monotonic()),
                    allowed_origins=(origin,), allow_redirects=False)
                if (response.status != 200 or response.url != url or len(response.content) > bounds.parser_bytes
                        or response.content_type.split(";")[0].strip().lower() != "application/json" or stopped()):
                    raise RetrievalError("provider_search_response_invalid", status=response.status)
                raw = response.content
            current_raw = raw
            digest = sha256(raw).hexdigest()
            if task.get("sha256") and task["sha256"] != digest:
                raise ValueError("Select Search capture changed; restart its continuation.")
            payload = json.loads(raw)
            rows = search_rows(source, raw)
            if payload["value"] and digest == task.get("previous_sha256"):
                raise ValueError("Select Search repeated its preceding page.")
            bundle = search_bundle(source, namespace, raw)
            bundle["capture"]["retrieval_url"] = url
            selected = []
            if task["offset"] > len(rows):
                raise ValueError("Select Search continuation exceeds its captured page.")
            index = task["offset"]
            while index < len(rows) and len(records) < bounds.max_records and not stopped():
                record = bundle["records"][index]
                index += 1
                key = source_identity_key(record["identity"])
                if key not in seen:
                    selected.append(record)
                    records.append(record)
                    seen.add(key)
            bundle["records"] = selected
            bundles.append(bundle)
            pages += 1
            if index < len(rows):
                task = {"skip": task["skip"], "offset": index, "sha256": digest}
                break
            if not payload["value"]:
                finished = True
                break
            task = {"skip": task["skip"] + len(payload["value"]), "offset": 0, "previous_sha256": digest}
            current_raw = b""
            context.report(operation="search", pages=pages, returned_records=len(records))
    except Exception as exc:
        code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
        errors.append(Error(code, "The public Select Search response could not be retrieved or verified.",
                            retryable=True, source=source.url))
    checkpoint = None
    if not finished:
        try:
            checkpoint = _sessions(engine).put({"content": current_raw, "offset": task["offset"], "seen": seen,
                "grid_pages": {"skip": task["skip"]}, "pending": task, "exhausted": set(), "cookies": CookieJar()}, binding)
        except ValueError:
            errors.append(Error("continuation_capacity", "Search continuation capacity reached; use narrower bounds or wait for expiry."))
    coverage = {"native_search": True, "sources": [{**source.public_dict(), "namespace": namespace}],
        "scope": "public Search grouped candidates and supplied excerpts within a UTC request window",
        "provider_query_semantics": "provider-defined first expression; exact local metadata/excerpt matching",
        "full_document_text_searched": False, "transcript_text_complete": False,
        "catalog_complete": False, "source_complete": False, "query_window_exhausted": finished,
        "alternative_backend_search": "not_requested_or_verified", "pages": pages,
        "snapshot_consistency": "in-process exact captured page; 15-minute continuation TTL; unavailable after engine restart",
        "truncated": not finished, "checkpoint": checkpoint}
    if not records:
        status = "cancelled" if operation_cancelled(engine.storage, context) else "failed" if errors else "partial"
        return OperationResult(status, {"hits": [], "records": [], "query": asdict(query), "bundles": bundles},
                               tuple(errors), coverage, context.operation_id)
    originals = {source_identity_key(r["identity"]): r for r in records}
    local = [{**deepcopy(r), "normalized": {k: r["normalized"].get(k) for k in
             ("title", "body", "meeting_date", "location", "search_excerpts")}, "text": []} for r in records]
    matched = search_records(local, query, bounds=replace(bounds, checkpoint=None,
        deadline_seconds=max(.001, deadline-monotonic())), sources=coverage["sources"], inherited_coverage=coverage,
        context=context, storage=engine.storage)
    data = matched.data or {}
    for hit in data.get("hits", []):
        hit["record"] = originals[source_identity_key(hit["identity"])]
    data["records"] = [h["record"] for h in data.get("hits", [])]
    status = "cancelled" if operation_cancelled(engine.storage, context) else "failed" if errors and not bundles else "partial"
    return OperationResult(status, {**data, "bundles": bundles}, tuple(errors)+matched.errors,
                           {**matched.coverage, **coverage}, context.operation_id)
