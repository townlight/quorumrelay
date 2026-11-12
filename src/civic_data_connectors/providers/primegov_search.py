"""Observed public PrimeGov search; returned excerpts do not establish full text."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime
from html.parser import HTMLParser
import json
from time import monotonic
from urllib.parse import urlencode, urlsplit

from ..engine import canonical_hash
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, RetrievalError, _origin
from .discovery import _checkpoint, _resume
from .identification import configured_source, validate_source
from .native import make_bundle


class _Excerpt(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _rows(original, source):
    if not isinstance(original, list) or len(original) > 10000:
        raise ValueError("Expected a locally bounded public search array; use narrower dates.")
    rows, omitted = [], 0
    for raw in original:
        if not isinstance(raw, dict):
            raise ValueError("Public search rows must be objects.")
        kind = {"Meeting": "meeting", "Item": "agenda_item", "Attachment": "document"}.get(raw.get("info"))
        if kind is None or type(raw.get("id")) is not int or type(raw.get("meetingId")) is not int:
            omitted += 1
            continue
        if kind == "meeting" and raw["id"] != raw["meetingId"]:
            raise ValueError("The supplied meeting identity is inconsistent.")
        day = datetime.fromisoformat(raw["meetingDate"]).date().isoformat()
        excerpt = raw.get("highlights")
        normalized = {"external_id": str(raw["id"]), "title": raw.get("title"),
                      "meeting_date": day, "meeting_title": raw.get("meetingTitle"),
                      "source_date": raw["meetingDate"], "time_zone_status": "unknown",
                      "url": _origin(source.url) + "/Portal/Meeting?" + urlencode({"meetingId": raw["meetingId"]})}
        if isinstance(excerpt, str):
            normalized["search_excerpt"] = "".join(_Excerpt(excerpt).parts)
        rows.append((normalized, raw, kind))
    # The observed endpoint reorders tied candidates between identical requests.
    # Use native identities for traversal; do not claim to retain provider rank.
    rows.sort(key=lambda row: (row[2], row[0]["external_id"], row[1]["meetingId"], canonical_hash(row[1])))
    return rows, omitted


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Source namespace is not authorized."),))
    parts = urlsplit(source.url)
    if parts.scheme != "https" or parts.path.rstrip("/").lower() != "/public/portal" or parts.query:
        raise ValueError("PrimeGov native search requires an HTTPS public/portal source without a query.")
    if content is not None or any(key in request for key in ("records", "bundle", "result")):
        raise ValueError("Native search retrieves public candidates; use native=false for saved captures.")
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from, date_to=query.date_to or bounds.date_to)
    expressions = [*query.terms, *query.phrases]
    if not expressions or any(not value.strip() for value in expressions) or not query.date_from or not query.date_to:
        raise ValueError("Public search requires a nonempty term/phrase and explicit date bounds.")
    if source.body or query.body:
        raise ValueError("The observed public search result does not establish a body filter.")
    candidate = expressions[0]
    if len(candidate.encode("utf-8")) > min(1024, bounds.parser_bytes):
        raise ValueError("The provider search expression exceeds its local bound.")
    binding = canonical_hash({"source": source.public_dict(), "query": asdict(query), "scope": context.scope,
                              "contract": "primegov-public-search/v1"})
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else ([{"offset": 0}], set())
    if (len(queue) != 1 or set(queue[0]) - {"offset", "sha256"} or seen
            or type(queue[0].get("offset")) is not int or not 0 <= queue[0]["offset"] <= 10000):
        raise ValueError("Invalid public search checkpoint.")
    task = queue[0]
    origin = _origin(source.url)
    url = origin + "/api/v2/PublicPortal/search"
    fields = {"CommitteeId": "", "MeetingDateFrom": date.fromisoformat(query.date_from).strftime("%m/%d/%Y"),
              "MeetingDateTo": date.fromisoformat(query.date_to).strftime("%m/%d/%Y"),
              "MeetingType": "", "ItemTypeId": "", "ItemTitle": "", "Sponsor": "", "TrackingNo": "",
              "Text": candidate, "IsFromAdvanceSearch": "true"}
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
                "scope": "public provider candidates; exact local metadata and supplied excerpt matching",
                "provider_query_semantics": "provider-defined first expression; exact local AND",
                "full_document_text_searched": False, "catalog_complete": False, "source_complete": False,
                "candidate_order": "stable native kind/id; provider ranking is not retained",
                "provider_pagination": "no continuation in observed public request/array; completeness unknown"}
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    deadline = monotonic() + bounds.deadline_seconds
    try:
        response = (transport or PublicTransport()).request(url, method="POST", body=urlencode(fields).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            byte_limit=bounds.parser_bytes, deadline_seconds=max(.001, deadline - monotonic()),
            allowed_origins=(origin,), allow_redirects=False)
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if response.status != 200:
            raise RetrievalError("provider_http_error", status=response.status)
        if response.url != url or len(response.content) > bounds.parser_bytes or monotonic() >= deadline:
            raise ValueError("Public search response changed route or exceeded its bounds.")
        original = json.loads(response.content)
        rows, omitted = _rows(original, source)
        digest = canonical_hash(sorted(original, key=canonical_hash))
        if task.get("sha256") and task["sha256"] != digest:
            raise ValueError("The resumed response changed; restart the public search.")
        offset = task["offset"]
        if offset > len(rows):
            raise ValueError("The checkpoint lies outside the response.")
        end = min(len(rows), offset + min(query.limit, bounds.max_records))
        bundle = make_bundle(source, namespace, response.content, "primegov-search-json", rows[offset:end])
        bundle["capture"]["retrieval_url"] = url
        for record in bundle["records"]:
            if record["identity"]["record_type"] != "meeting":
                record["identity"]["parent"] = {"provider": source.provider, "namespace": namespace,
                    "record_type": "meeting", "external_id": str(record["original"]["meetingId"])}
        coverage.update({"pages": 1, "status": "partial", "provider_returned_rows": len(rows) + omitted,
            "unmapped_rows_omitted": omitted, "checkpoint": _checkpoint(binding,
                [{"offset": end, "sha256": digest}], set()) if end < len(rows) else None})
        result = search_records(deepcopy(bundle["records"]), query,
            bounds=replace(bounds, checkpoint=None, deadline_seconds=max(.001, deadline - monotonic())),
            sources=coverage["sources"], inherited_coverage=coverage, context=context, storage=engine.storage)
        if result.data is None:
            return result
        return OperationResult(result.status, {**result.data, "bundle": bundle}, result.errors,
                               {**result.coverage, **coverage}, context.operation_id)
    except Exception as exc:
        code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
        return OperationResult("failed", errors=(Error(code, "The public search could not be retrieved or verified.",
            retryable=True, source=source.url),), coverage=coverage, operation_id=context.operation_id)
