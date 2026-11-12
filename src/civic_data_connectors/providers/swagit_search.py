"""Bounded native Swagit video search from an observed public GET form."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
from html.parser import HTMLParser
import re
from time import monotonic
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, RetrievalError, _origin
from .discovery import _checkpoint, _resume
from .identification import configured_source, validate_source, validate_url
from .native import make_bundle
from .swagit import FORMAT, listing_rows

_MAX_SEARCH_CHARS = 512
_MAX_NEXT_LINKS = 8


class _PageSignals(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.next_links = []
        self.visible = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"script", "style", "template"}:
            self.hidden += 1
        if tag in {"a", "link"} and "next" in (attributes.get("rel") or "").casefold().split():
            href = attributes.get("href")
            if href:
                self.next_links.append(href)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.visible.append(" ".join(data.split()))


def _validated_search_url(url, *, origin, expression, page):
    validate_url(url)
    parts = urlsplit(url)
    if (parts.scheme != "https" or _origin(url) != origin or parts.path != "/videos/search"
            or parts.fragment or parts.username or parts.password):
        raise ValueError("The Swagit search URL left the configured public search origin or route.")
    try:
        params = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as error:
        raise ValueError("The Swagit search query string is malformed.") from error
    expected_keys = {"q", "utf8"} if page == 1 else {"page", "q", "utf8"}
    if set(params) != expected_keys or any(len(values) != 1 for values in params.values()):
        raise ValueError("The Swagit search URL has unexpected query fields.")
    if params.get("q") != [expression] or params.get("utf8") != ["✓"]:
        raise ValueError("The Swagit search URL does not preserve the configured query.")
    if page > 1 and params.get("page") != [str(page)]:
        raise ValueError("The Swagit next link does not advance exactly one page.")
    return url


def _next_page_url(content, *, current_url, origin, expression, current_page):
    parser = _PageSignals()
    parser.feed(content.decode("utf-8-sig", errors="strict"))
    if len(parser.next_links) > _MAX_NEXT_LINKS:
        raise ValueError("The Swagit response contains too many rel=next links.")
    links = set(parser.next_links)
    if len(links) > 1:
        raise ValueError("The Swagit response contains conflicting rel=next links.")
    if not links:
        return None, " ".join(parser.visible).casefold()
    target = urljoin(current_url, next(iter(links)))
    expected_page = current_page + 1
    return _validated_search_url(target, origin=origin, expression=expression, page=expected_page), None


def _grant_binding(context):
    def selected(values):
        return None if values is None else sorted(values)
    return {
        "authorization": sorted(context.authorization),
        "allowed_operations": selected(context.allowed_operations),
        "allowed_namespaces": selected(context.allowed_namespaces),
    }


def native_search(engine, request, content, context, *, transport=None):
    """Search public Swagit candidates and locally match title/date metadata only."""
    if request.get("native") is not True:
        raise ValueError("Swagit search requires native=true; saved records use local search.")
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied",
            "Source namespace is not authorized."),), operation_id=context.operation_id)

    source_parts = urlsplit(source.url)
    if (source_parts.scheme != "https" or not re.fullmatch(r"[a-z0-9-]+\.new\.swagit\.com",
            source_parts.hostname or "", re.I) or not re.fullmatch(r"/views/[1-9][0-9]*/?", source_parts.path)
            or source_parts.query or source_parts.fragment):
        raise ValueError("Swagit search requires a configured HTTPS /views/{id}/ source on a new.swagit.com host.")
    if content is not None or any(key in request for key in (
            "content_base64", "records", "bundle", "result")):
        raise ValueError("Native Swagit search retrieves provider candidates; saved captures use native=false.")

    query = _query(request.get("query", {}))
    bounds = Bounds(**request.get("bounds", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from,
                    date_to=query.date_to or bounds.date_to)
    if source.body or query.body:
        raise ValueError("The observed Swagit search does not establish a body filter.")
    if query.record_types and set(query.record_types) != {"meeting"}:
        raise ValueError("The observed Swagit listing exposes meeting video records only.")
    expressions = [*query.terms, *query.phrases]
    if not expressions:
        raise ValueError("Swagit native search requires at least one nonempty term or phrase.")
    expression = expressions[0]
    if len(expression) > _MAX_SEARCH_CHARS or len(expression.encode("utf-8")) > min(bounds.parser_bytes, 4096):
        raise ValueError("The first Swagit search expression exceeds its request bound.")

    origin = _origin(source.url)
    initial_url = origin + "/videos/search?" + urlencode({"utf8": "✓", "q": expression})
    binding = canonical_hash({
        "source": source.public_dict(), "namespace": namespace, "query": asdict(query),
        "caller_scope": context.scope, "current_grant": _grant_binding(context),
        "contract": "swagit-public-video-search/v1",
    })
    if bounds.checkpoint:
        queue, seen = _resume(bounds.checkpoint, binding)
    else:
        queue, seen = ([{"page": 1, "offset": 0}], set())
    if len(queue) != 1:
        raise ValueError("Swagit search checkpoint must contain one bounded page task.")
    task = queue[0]
    if set(task) - {"page", "offset", "sha256", "url"}:
        raise ValueError("Swagit search checkpoint contains unsupported task fields.")
    page, offset = task.get("page"), task.get("offset", 0)
    if type(page) is not int or not 1 <= page <= 10000 or type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError("Swagit search checkpoint position is invalid.")
    if page == 1:
        if task.get("url") not in (None, initial_url):
            raise ValueError("The Swagit first-page checkpoint URL changed.")
        current_url = initial_url
    else:
        current_url = task.get("url")
        if not isinstance(current_url, str):
            raise ValueError("Swagit search checkpoint is missing its supplied next link.")
        _validated_search_url(current_url, origin=origin, expression=expression, page=page)
    expected_sha = task.get("sha256")
    if expected_sha is not None and (not isinstance(expected_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None):
        raise ValueError("Swagit search checkpoint page hash is invalid.")
    if offset and expected_sha is None:
        raise ValueError("A mid-page Swagit checkpoint must bind the captured page hash.")

    deadline = monotonic() + bounds.deadline_seconds
    pages, records, bundles, captures, errors = 0, [], [], [], []
    next_task = task
    unidentified_rows = timestamp_links = 0
    deadline_exceeded = False
    candidate_limit = bounds.max_records
    active_transport = transport or PublicTransport()
    while next_task and pages < bounds.max_pages and len(records) < candidate_limit:
        if operation_cancelled(engine.storage, context):
            break
        if monotonic() >= deadline:
            deadline_exceeded = True
            errors.append(Error("provider_deadline_exceeded", "The Swagit search deadline expired.",
                                retryable=True, source=source.url))
            break
        task, next_task = next_task, None
        page, offset = task["page"], task.get("offset", 0)
        current_url = (initial_url if page == 1 else task["url"])
        current_url = _validated_search_url(current_url, origin=origin, expression=expression, page=page)
        try:
            response = active_transport.request(
                current_url, headers={"Accept": "text/html"}, byte_limit=bounds.parser_bytes,
                deadline_seconds=max(0.001, deadline - monotonic()), allowed_origins=(origin,),
                allow_redirects=False)
            if operation_cancelled(engine.storage, context):
                next_task = task
                break
            if monotonic() >= deadline:
                raise RetrievalError("provider_deadline_exceeded")
            if response.status != 200:
                raise RetrievalError("provider_http_error", status=response.status)
            if (not isinstance(response.content, bytes) or len(response.content) > bounds.parser_bytes
                    or response.content_type.split(";")[0].strip().casefold() != "text/html"):
                raise ValueError("The Swagit response exceeded parser bounds or was not HTML.")
            response_url = _validated_search_url(response.url, origin=origin,
                                                 expression=expression, page=page)
            if response_url != current_url:
                raise ValueError("The Swagit response URL differs from its validated request.")
            digest = sha256(response.content).hexdigest()
            if task.get("sha256") and task["sha256"] != digest:
                raise ValueError("The resumed Swagit page changed; restart the search.")

            rows = listing_rows(source, response.content, allow_empty=True)
            if not rows:
                _, visible_text = _next_page_url(response.content, current_url=current_url,
                    origin=origin, expression=expression, current_page=page)
                if "no results containing all your search terms were found" not in (visible_text or ""):
                    raise ValueError("The Swagit response has neither video rows nor the observed empty-result marker.")
            else:
                next_url, _ = _next_page_url(response.content, current_url=current_url,
                    origin=origin, expression=expression, current_page=page)
                timestamp_links += sum(len(row[0].get("search_match_urls", [])) for row in rows)
                unidentified_rows += sum(row[0]["external_id"].startswith("derived:") for row in rows)

            bundle = make_bundle(source, namespace, response.content, FORMAT, rows)
            bundle["capture"]["retrieval_url"] = response.url
            if offset > len(bundle["records"]):
                raise ValueError("The Swagit checkpoint offset is outside the captured page.")
            selected = []
            for index in range(offset, len(bundle["records"])):
                if (operation_cancelled(engine.storage, context) or monotonic() >= deadline
                        or len(records) >= candidate_limit):
                    next_task = {"page": page, "offset": index, "sha256": digest,
                                 "url": current_url}
                    if monotonic() >= deadline:
                        deadline_exceeded = True
                        errors.append(Error("provider_deadline_exceeded", "The Swagit search deadline expired.",
                                            retryable=True, source=source.url))
                    break
                record = bundle["records"][index]
                if record["identity"]["external_id"].startswith("derived:"):
                    continue
                key = source_identity_key(record["identity"])
                if key not in seen:
                    seen.add(key)
                    selected.append(record)
                    records.append(record)
            else:
                if rows and next_url:
                    next_task = {"page": page + 1, "offset": 0, "url": next_url}
            bundle["records"] = selected
            bundles.append(bundle)
            captures.append(bundle["capture"])
            pages += 1
            context.report(operation="search", pages=pages, returned_records=len(records))
        except Exception as exc:
            code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
            deadline_exceeded = deadline_exceeded or code == "provider_deadline_exceeded"
            errors.append(Error(code, "The Swagit search page could not be retrieved or parsed.",
                                retryable=True, source=source.url))
            next_task = task
            break

    coverage = {
        "sources": [{**source.public_dict(), "namespace": namespace}],
        "native_search": True,
        "scope": "anonymous Swagit video candidates; exact local title/date metadata matching",
        "provider_query_semantics": "not independently established; first expression is used for candidates",
        "native_fields": ["title", "meeting_date"],
        "sound_search_timestamps_preserved": True,
        "timestamp_urls_seen": timestamp_links,
        "transcript_text_searched": False,
        "catalog_complete": False,
        "source_complete": False,
        "status": "partial",
        "pages": pages,
        "deadline_exceeded": deadline_exceeded,
        "unidentified_rows_omitted": unidentified_rows,
        "checkpoint": _checkpoint(binding, [next_task], seen) if next_task else None,
    }
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    if errors and not captures:
        return OperationResult("failed", errors=tuple(errors), coverage=coverage,
                              operation_id=context.operation_id)

    if not records:
        data = {"hits": [], "records": [], "query": asdict(query),
                "bundle": {"records": [], "captures": captures, "bundles": bundles}}
        return OperationResult("partial", data, tuple(errors), coverage, context.operation_id)

    originals = {source_identity_key(row["identity"]): row for row in records}
    local = [{**deepcopy(row),
              "normalized": {key: row["normalized"].get(key) for key in ("title", "meeting_date")},
              "text": []} for row in records]
    searched = search_records(
        local, query,
        bounds=replace(bounds, checkpoint=None, deadline_seconds=max(0.001, deadline - monotonic())),
        sources=coverage["sources"], inherited_coverage=coverage, context=context, storage=engine.storage)
    if searched.data is None or searched.status == "cancelled":
        return searched
    for hit in searched.data["hits"]:
        hit["record"] = originals[source_identity_key(hit["identity"])]
    searched.data["records"] = [hit["record"] for hit in searched.data["hits"]]
    fetched_bundle = {"records": records, "captures": captures, "bundles": bundles}
    return OperationResult("partial", {**searched.data, "bundle": fetched_bundle},
                           tuple(errors) + searched.errors, {**searched.coverage, **coverage},
                           context.operation_id)
