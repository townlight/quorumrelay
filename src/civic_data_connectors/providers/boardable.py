"""Bounded Boardable public meeting-list discovery from observed public routes."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urlsplit
from html.parser import HTMLParser

from ..engine import canonical_hash, source_identity_key
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .contracts import RetrievalError, _origin
from .discovery import _checkpoint, _resume
from .identification import validate_source
from .native import make_bundle

FORMAT = "boardable-public-meetings-json"
SITE_ORIGIN = "https://site.boardable.com"
API_ORIGIN = "https://app.boardable.com"
API_PATH = "/api/public-sites/meetings"
PAGE_SIZE = 10
_RECORD_TYPES = {"meeting", "recording", "document", "agenda_item", "transcript"}
_SLUG = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")


class _NuxtData(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._capture = False
        self.parts = []
        self.matches = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script" and dict(attrs).get("id") == "__NUXT_DATA__":
            self._capture = True
            self.parts = []

    def handle_data(self, data):
        if self._capture:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._capture:
            self.matches.append("".join(self.parts))
            self.parts = []
            self._capture = False


def _source_slug(source):
    parts = urlsplit(source.url)
    if (parts.scheme != "https" or parts.hostname != "site.boardable.com" or
            parts.port not in {None, 443} or parts.username is not None or parts.password is not None or
            parts.query or parts.fragment):
        raise ValueError("Boardable public discovery requires an HTTPS site.boardable.com meeting-list source.")
    path = parts.path.strip("/").split("/")
    if len(path) not in {1, 2} or (len(path) == 2 and path[1] != "meetings"):
        raise ValueError("Boardable public discovery accepts only an organization landing or /meetings route.")
    slug = path[0]
    if not _SLUG.fullmatch(slug):
        raise ValueError("The Boardable organization slug is not a safe public route segment.")
    return slug


def _deref(table, value):
    if type(value) is int:
        if 0 <= value < len(table):
            return table[value]
        return None
    return value


def _site_id(content, slug):
    parser = _NuxtData()
    parser.feed(content.decode("utf-8-sig"))
    parser.close()
    if len(parser.matches) != 1:
        raise ValueError("The public Boardable page did not expose one __NUXT_DATA__ state table.")
    try:
        table = json.loads(parser.matches[0])
    except (ValueError, UnicodeError):
        raise ValueError("The public Boardable page state table was not valid JSON.") from None
    if not isinstance(table, list):
        raise ValueError("The public Boardable page state table had an unexpected shape.")
    matches = []
    for item in table:
        if not isinstance(item, dict) or not {"id", "slug", "organization_slug"} <= set(item):
            continue
        identifier = _deref(table, item["id"])
        item_slug = _deref(table, item["slug"])
        organization_slug = _deref(table, item["organization_slug"])
        if (type(identifier) is int and identifier > 0 and item_slug == slug and
                organization_slug == slug):
            matches.append(identifier)
    if len(matches) != 1:
        raise ValueError("The public page did not uniquely identify its configured organization site.")
    return matches[0]


def _page_url(mode, page):
    query = urlencode([
        ("count", str(PAGE_SIZE)), ("search", ""), ("group", ""), ("status", ""),
        ("sort", "asc"), ("upcoming", "true" if mode else "false"), ("page", str(page)),
    ])
    return f"{API_ORIGIN}{API_PATH}?{query}"


def _validate_next(value, mode, page, last_page):
    if value is None:
        if page != last_page:
            raise ValueError("Boardable omitted its observed next-page link before the reported final page.")
        return None
    if not isinstance(value, str):
        raise ValueError("Boardable returned an invalid next-page link.")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.hostname != "app.boardable.com" or
            parsed.port not in {None, 443} or parsed.username is not None or parsed.password is not None or
            parsed.path != API_PATH or parsed.fragment):
        raise ValueError("Boardable next-page link left the observed public API route.")
    pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    query = dict(pairs)
    if (len(pairs) != len(query) or set(query) != {"count", "search", "group", "status", "sort", "upcoming", "page"} or
            query.get("count") != str(PAGE_SIZE) or query.get("search") != "" or
            query.get("group") != "" or query.get("status") != "" or query.get("sort") != "asc" or
            query.get("upcoming") != ("true" if mode else "false") or
            query.get("page") != str(page + 1) or page >= last_page):
        raise ValueError("Boardable next-page link changed the site scope, listing filters, or page sequence.")
    return value


def _parse_listing(content, mode, page):
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeError):
        raise ValueError("The Boardable public meeting-list response was not valid JSON.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("The Boardable public meeting-list response had an unexpected shape.")
    meta, links = payload.get("meta"), payload.get("links")
    if not isinstance(meta, dict) or not isinstance(links, dict) or "next" not in links:
        raise ValueError("The Boardable public meeting-list response omitted pagination metadata.")
    current, size, total, last = (meta.get("current_page"), meta.get("per_page"),
                                  meta.get("total"), meta.get("last_page"))
    if (type(current) is not int or current != page or type(size) is not int or size != PAGE_SIZE or
            type(total) is not int or total < 0 or type(last) is not int or last < 1 or page > last or
            last != max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) or len(payload["data"]) > PAGE_SIZE or
            any(not isinstance(row, dict) for row in payload["data"])):
        raise ValueError("The Boardable pagination fields did not match the observed page contract.")
    following = _validate_next(links["next"], mode, page, last)
    return payload, following


def _meeting_row(source, raw):
    identifier, slug, title = raw.get("id"), raw.get("slug"), raw.get("title")
    if type(identifier) is not int or identifier <= 0 or not isinstance(slug, str) or not _SLUG.fullmatch(slug):
        raise ValueError("A Boardable listing row omitted its observed numeric ID or safe meeting slug.")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("A Boardable listing row omitted its meeting title.")
    start, end = raw.get("start"), raw.get("end")
    start = start if isinstance(start, dict) else {}
    end = end if isinstance(end, dict) else {}
    raw_start = start.get("date") if isinstance(start.get("date"), str) else None
    raw_end = end.get("date") if isinstance(end.get("date"), str) else None
    day = None
    if raw_start:
        try:
            day = datetime.fromisoformat(raw_start.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    description = raw.get("description") if isinstance(raw.get("description"), str) else None
    org_slug = _source_slug(source)
    detail_url = f"{SITE_ORIGIN}/{org_slug}/meetings/{slug}"
    normalized = {
        "external_id": str(identifier), "title": title, "description": description,
        "meeting_date": day, "source_start": raw_start, "source_end": raw_end,
        "source_timezone": start.get("timezone"), "time_zone_status": "source_literal_unverified",
        "url": detail_url, "documents": [], "recordings": [], "agenda_items": [],
        "documents_availability": "not_supplied_by_meeting_listing",
        "recordings_availability": "not_supplied_by_meeting_listing",
        "agenda_items_availability": "not_supplied_by_meeting_listing",
        "source_status": {key: raw[key] for key in ("materials_published", "published_materials_status")
                          if key in raw},
    }
    return normalized, deepcopy(raw), "meeting"


def _task(value):
    if not isinstance(value, dict) or set(value) - {"mode", "page", "offset", "sha256"}:
        raise ValueError("The Boardable continuation task is invalid.")
    mode, page, offset, digest = value.get("mode"), value.get("page"), value.get("offset", 0), value.get("sha256")
    if (type(mode) is not bool or type(page) is not int or not 1 <= page <= 10000 or
            type(offset) is not int or not 0 <= offset < PAGE_SIZE or
            (offset > 0 and digest is None) or
            (digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)))):
        raise ValueError("The Boardable continuation position is invalid.")
    return {"mode": mode, "page": page, "offset": offset, "sha256": digest}


def _configured_tasks(bounds, binding):
    if not bounds.checkpoint:
        return ([{"mode": True, "page": 1, "offset": 0, "sha256": None},
                 {"mode": False, "page": 1, "offset": 0, "sha256": None}], set())
    queue, seen = _resume(bounds.checkpoint, binding)
    return [_task(item) for item in queue], seen


def discover_public(engine, source, namespace, bounds, context, transport, *, saved=None, record_types=None):
    """List observed public meeting pages only; no detail/document catalog claim is made."""
    if saved is not None:
        return OperationResult.unsupported("discover", reason="Boardable saved captures continue through the configured parser.")
    slug = _source_slug(source)
    resolved_namespace = validate_source(source, context)
    if namespace is not None and namespace != resolved_namespace:
        raise ValueError("The Boardable source namespace did not match the configured public organization.")
    namespace = resolved_namespace
    if not context.allows("discover", namespace):
        return OperationResult("failed", errors=(Error(
            "permission_denied", "The source namespace is outside the caller's discovery grant."),))
    if record_types is None:
        record_types = []
    if (not isinstance(record_types, list) or
            any(not isinstance(value, str) or value not in _RECORD_TYPES for value in record_types)):
        raise ValueError("record_types must be a list of supported civic record types.")
    binding = canonical_hash({
        "source": source.public_dict(), "namespace": namespace,
        "dates": [bounds.date_from, bounds.date_to], "body": source.body,
        "record_types": record_types, "scope": context.scope,
        "format": FORMAT, "semantics": "boardable-public-listing/v1",
    })
    queue, seen = _configured_tasks(bounds, binding)
    deadline = monotonic() + bounds.deadline_seconds
    records, bundles, captures, errors = [], [], [], []
    pages, filtered = 0, 0
    unknown_dates, unknown_bodies = [], []
    failures = []
    site_id = None
    landing_digest = None
    landing_length = None
    api_origin = API_ORIGIN

    def fail(error, task=None):
        code = error.code if isinstance(error, RetrievalError) else "provider_page_failed"
        details = ({"http_status": error.status} if isinstance(error, RetrievalError) and
                   error.status is not None else {})
        errors.append(Error(code, "A Boardable public page could not be retrieved or parsed.",
                            retryable=True, source=source.url, details=details))
        failures.append({"page": pages, "mode": task["mode"] if task else "landing", "reason": code})

    if queue and not operation_cancelled(engine.storage, context) and monotonic() < deadline:
        try:
            response = transport.request(source.url, byte_limit=bounds.parser_bytes,
                deadline_seconds=max(.001, deadline - monotonic()), allowed_origins=(SITE_ORIGIN,),
                allow_redirects=False, headers={"Accept": "text/html"})
            if operation_cancelled(engine.storage, context):
                pass
            elif monotonic() >= deadline:
                raise RetrievalError("provider_deadline_exceeded")
            elif (response.status != 200 or response.url != source.url or _origin(response.url) != SITE_ORIGIN or
                  len(response.content) > bounds.parser_bytes or
                  response.content_type.split(";", 1)[0].strip().casefold() != "text/html"):
                raise RetrievalError("provider_landing_unavailable", status=response.status)
            else:
                site_id = _site_id(response.content, slug)
                landing_digest, landing_length = hashlib.sha256(response.content).hexdigest(), len(response.content)
        except Exception as exc:
            fail(exc)

    while queue and site_id is not None and pages < bounds.max_pages and len(records) < bounds.max_records:
        if operation_cancelled(engine.storage, context) or monotonic() >= deadline:
            break
        task = queue.pop(0)
        url = _page_url(task["mode"], task["page"])
        try:
            response = transport.request(url, byte_limit=bounds.parser_bytes,
                deadline_seconds=max(.001, deadline - monotonic()), allowed_origins=(api_origin,),
                allow_redirects=False, headers={"Accept": "application/json", "SiteId": str(site_id)})
            if operation_cancelled(engine.storage, context):
                queue.insert(0, task)
                break
            if monotonic() >= deadline:
                raise RetrievalError("provider_deadline_exceeded")
            if response.status != 200:
                raise RetrievalError("provider_http_error", status=response.status)
            if (_origin(response.url) != api_origin or response.url != url or
                    len(response.content) > bounds.parser_bytes or
                    response.content_type.split(";", 1)[0].strip().casefold() != "application/json"):
                raise RetrievalError("provider_response_outside_contract", status=response.status)
            digest = hashlib.sha256(response.content).hexdigest()
            if task["sha256"] and task["sha256"] != digest:
                raise ValueError("The resumed Boardable page changed; restart discovery without its checkpoint.")
            payload, following = _parse_listing(response.content, task["mode"], task["page"])
            bundle = make_bundle(source, namespace, response.content, FORMAT,
                                 [_meeting_row(source, row) for row in payload["data"]])
            bundle["capture"]["retrieval_url"] = response.url
            selected = []
            rows = bundle["records"]
            offset = task["offset"]
            if offset > len(rows):
                raise ValueError("The Boardable continuation offset exceeds this page.")
            interrupted = False
            for index in range(offset, len(rows)):
                if (operation_cancelled(engine.storage, context) or monotonic() >= deadline or
                        len(records) >= bounds.max_records):
                    queue.insert(0, {"mode": task["mode"], "page": task["page"],
                                    "offset": index, "sha256": digest})
                    interrupted = True
                    break
                record = rows[index]
                key = source_identity_key(record["identity"])
                if key in seen:
                    continue
                normalized = record["normalized"]
                day = normalized.get("meeting_date")
                if day and ((bounds.date_from and day < bounds.date_from) or
                            (bounds.date_to and day > bounds.date_to)):
                    filtered += 1
                    continue
                if not day and (bounds.date_from or bounds.date_to):
                    unknown_dates.append(record["identity"]["external_id"])
                if record_types and "meeting" not in record_types:
                    filtered += 1
                    continue
                if source.body:
                    unknown_bodies.append(record["identity"]["external_id"])
                seen.add(key)
                selected.append(record)
                records.append(record)
            pages += 1
            bundle["records"] = selected
            bundles.append(bundle)
            captures.append(bundle["capture"])
            if not interrupted and following:
                queue.insert(0, {"mode": task["mode"], "page": task["page"] + 1,
                                 "offset": 0, "sha256": None})
            context.report(operation="discover", pages=pages, returned_records=len(records))
        except Exception as exc:
            fail(exc, task)
            queue.insert(0, task)
            break

    # Keep the two independent listing modes and their positions across bounded calls.
    queue = [_task(item) for item in queue]
    checkpoint = _checkpoint(binding, queue, seen) if queue else None
    cancelled = operation_cancelled(engine.storage, context)
    timed_out = monotonic() >= deadline
    unobserved_types = sorted(set(record_types) - {"meeting"})
    coverage = {
        "sources": [{**source.public_dict(), "namespace": namespace, "input_format": FORMAT}],
        "tenant_resolution": {"method": "matched public __NUXT_DATA__ organization slug",
                              "public_site_id": site_id, "landing_sha256": landing_digest,
                              "landing_byte_length": landing_length},
        "date_from": bounds.date_from, "date_to": bounds.date_to, "date_inclusivity": "both",
        "record_types": record_types, "unobserved_record_types": unobserved_types,
        "body": source.body, "returned_records": len(records), "filtered_records": filtered,
        "body_filter_status": "unknown_listing_description_is_not_mapped_as_body" if source.body else "not_requested",
        "actual_dates": sorted({row["normalized"].get("meeting_date") for row in records
                                 if row["normalized"].get("meeting_date")}),
        "unknown_date_records": unknown_dates, "unknown_body_records": unknown_bodies,
        "pages": pages, "failed_pages": failures, "failures": failures,
        "listing_exhausted": not queue and not failures,
        "catalog_complete": False, "source_complete": False,
        "available_text": "meeting_title_and_supplied_description_only",
        "documents_and_agenda_items": "not_supplied_by_public_meeting_listing",
        "truncated": bool(queue), "deadline_exceeded": timed_out,
        "checkpoint": checkpoint,
        "scope": "bounded public meeting-list pages; document/detail catalog completeness is unverified",
    }
    if cancelled:
        status = "cancelled"
    elif failures and not captures:
        status = "failed"
    else:
        status = "partial"
    data = {"source": source.public_dict(), "records": records, "captures": captures, "bundles": bundles}
    return OperationResult(status, data, tuple(errors), coverage, context.operation_id)
