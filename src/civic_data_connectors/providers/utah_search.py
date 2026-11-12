"""Bounded anonymous Utah public-notice form search; session state stays private."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from threading import Lock
from time import monotonic
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request

from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, RetrievalError
from .identification import configured_source, validate_source
from .native import make_bundle
from .novus import _Sessions, _cookies
from .utah_public import FORMAT, search_rows

_URL = "https://www.utah.gov/pmn/search.html"
_NEXT = "https://www.utah.gov/pmn/searchresult.html"
_LOCK = Lock()


def _cache(engine):
    with _LOCK:
        if not hasattr(engine, "_utah_search_sessions"):
            engine._utah_search_sessions = _Sessions()
        return engine._utah_search_sessions


class _Controls(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.token, self.action, self.method, self.next_rows = None, None, None, []
        self.anchor = None
        self.feed(content.decode("utf-8-sig"))

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "form" and d.get("id") == "searchform":
            if self.action is not None:
                raise ValueError("Ambiguous public search form.")
            self.action, self.method = d.get("action"), d.get("method", "").lower()
        if tag == "meta" and d.get("name") == "_csrf":
            self.token = d.get("content")
        if tag == "a" and "jump_to" in d.get("class", "").split():
            value = d.get("data-rel", "")
            if not value.isascii() or not value.isdecimal() or len(value) > 8:
                raise ValueError("Invalid supplied Utah pager control.")
            self.anchor = {"value": int(value), "label": [d.get("aria-label", ""), d.get("title", "")]}

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor["label"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            label = " ".join(self.anchor["label"]).strip().casefold()
            if label in {"next", "next page", ">", "»"}:
                self.next_rows.append(self.anchor["value"])
            self.anchor = None



def _response(transport, url, method, body, headers, bounds, deadline):
    if monotonic() >= deadline:
        raise RetrievalError("provider_deadline_exceeded")
    response = transport.request(url, method=method, body=body, headers=headers,
        byte_limit=bounds.parser_bytes, deadline_seconds=max(.001, deadline-monotonic()),
        allowed_origins=("https://www.utah.gov",), allow_redirects=False)
    if response.status != 200:
        raise RetrievalError("provider_http_error", status=response.status)
    if response.url != url or not isinstance(response.content, bytes) or len(response.content) > bounds.parser_bytes:
        raise ValueError("Public search response did not match the bounded endpoint.")
    if response.content_type.split(";")[0].strip().lower() != "text/html" or monotonic() >= deadline:
        raise ValueError("Public search response is not bounded HTML.")
    return response


def _headers(jar, url, token=None):
    headers = {"Accept": "text/html", "Referer": _URL}
    req = Request(url)
    jar.add_cookie_header(req)
    if req.has_header("Cookie"):
        headers["Cookie"] = req.get_header("Cookie")
    if token:
        headers.update({"X-CSRF-TOKEN": token, "Content-Type": "application/x-www-form-urlencoded"})
    return headers


def _run(engine, source, namespace, bounds, context, transport, *, body, expression, binding):
    if not bounds.date_from or not bounds.date_to or bounds.date_from > bounds.date_to or not body:
        raise ValueError("Utah public search requires an explicit body and inclusive date range.")
    cache = _cache(engine)
    state = cache.get(bounds.checkpoint, binding) if bounds.checkpoint else {
        "content": None, "cookies": CookieJar(), "offset": 0, "grid_pages": {"meeting": -1},
        "seen": set(), "exhausted": set(), "pending": None, "token": None}
    deadline = monotonic() + bounds.deadline_seconds
    fields = {"searchType": "on", "entityName": "", "publicBodyName": body, "title": expression,
              "agenda": "", "tags": "", "startDate": bounds.date_from, "endDate": bounds.date_to,
              "deadlineDate": "", "createdDate": "", "sortColumn": "", "sortOrder": ""}
    records, bundles, errors = [], [], []
    pages = 0
    finished = False
    try:
        if state["content"] is None:
            if operation_cancelled(engine.storage, context):
                return OperationResult("cancelled", operation_id=context.operation_id)
            form = _response(transport, _URL, "GET", None, _headers(state["cookies"], _URL), bounds, deadline)
            _cookies(state["cookies"], form, _URL)
            controls = _Controls(form.content)
            if (controls.method != "post" or urljoin(_URL, controls.action or "") != _URL
                    or not controls.token or len(controls.token) > 8192):
                raise ValueError("The observed public search form changed.")
            if operation_cancelled(engine.storage, context):
                return OperationResult("cancelled", operation_id=context.operation_id)
            state["token"] = controls.token
            post_fields = {**fields, "_csrf": controls.token}
            payload = urlencode(post_fields).encode()
            if len(payload) > bounds.parser_bytes:
                raise ValueError("Public search form exceeds parser bounds.")
            response = _response(transport, _URL, "POST", payload,
                                 _headers(state["cookies"], _URL, controls.token), bounds, deadline)
            _cookies(state["cookies"], response, _URL)
            state["content"] = response.content
        while pages < bounds.max_pages and len(records) < bounds.max_records:
            if operation_cancelled(engine.storage, context) or monotonic() >= deadline:
                break
            if state["pending"] is not None:
                controls = _Controls(state["content"])
                marker = state["pending"]
                if marker not in controls.next_rows or not state["token"]:
                    raise ValueError("The current public page lacks its supplied pager control.")
                form = urlencode({**fields, "startingRow": str(marker)}).encode()
                if len(form) > bounds.parser_bytes:
                    raise ValueError("Public pager form exceeds parser bounds.")
                response = _response(transport, _NEXT, "POST", form,
                                     _headers(state["cookies"], _NEXT, state["token"]), bounds, deadline)
                _cookies(state["cookies"], response, _NEXT)
                if response.content == state["content"]:
                    raise ValueError("The public pager did not advance.")
                state["content"], state["offset"], state["pending"] = response.content, 0, None
            if len(state["content"]) > bounds.parser_bytes:
                raise ValueError("Continued page exceeds current parser bounds.")
            controls = _Controls(state["content"])
            rows = search_rows(source, state["content"])
            bundle = make_bundle(source, namespace, state["content"], FORMAT, rows)
            selected = []
            for index in range(state["offset"], len(bundle["records"])):
                if (len(records) >= bounds.max_records or operation_cancelled(engine.storage, context)
                        or monotonic() >= deadline):
                    break
                state["offset"] = index + 1
                record = bundle["records"][index]
                key = source_identity_key(record["identity"])
                if key in state["seen"]:
                    continue
                state["seen"].add(key)
                value = record["normalized"]
                if value.get("body", "").casefold() != body.casefold():
                    continue
                if not bounds.date_from <= value["meeting_date"] <= bounds.date_to:
                    continue
                selected.append(record)
                records.append(record)
            bundle["records"] = selected
            bundles.append(bundle)
            pages += 1
            if state["offset"] >= len(rows):
                current_page = state["grid_pages"]["meeting"]
                next_values = sorted(set(x for x in controls.next_rows if x > current_page))
                if next_values:
                    state["pending"] = next_values[0]
                    state["grid_pages"]["meeting"] = next_values[0]
                else:
                    finished = True
                    break
            context.report(operation="search", pages=pages, returned_records=len(records))
    except Exception as exc:
        code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
        errors.append(Error(code, "The public Utah search could not be retrieved or verified.",
                            retryable=True, source=source.url))
    checkpoint = None
    if not finished and state["content"] is not None:
        try:
            checkpoint = cache.put(state, binding)
        except ValueError:
            errors.append(Error("continuation_capacity", "Private continuation capacity is exhausted."))
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
        "scope": "public notice metadata; exact body/date and local title matching",
        "catalog_complete": False, "source_complete": False, "full_source_searched": False,
        "status": "partial", "pages": pages, "checkpoint": checkpoint,
        "checkpoint_lifetime": "15 minutes; current engine process only",
        "query_window_exhausted": False, "observed_page_exhausted": finished and not errors, "body": body}
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    status = "failed" if errors and not bundles else "partial"
    return OperationResult(status, {"records": records, "bundles": bundles,
        "captures": [bundle["capture"] for bundle in bundles]}, tuple(errors), coverage, context.operation_id)


def _validate(source, bounds, context):
    p = urlsplit(source.url)
    if (source.provider != "utah-public-notice" or p.scheme != "https" or p.hostname != "www.utah.gov"
            or p.path not in ("/pmn/", "/pmn/search.html") or p.query or p.fragment):
        raise ValueError("Utah public search requires its configured public search or home URL.")
    if not bounds.date_from or not bounds.date_to:
        raise ValueError("Utah public search requires explicit date bounds.")


def _grant(context):
    def ordered(value):
        return None if value is None else sorted(value)
    return {"authorization": sorted(context.authorization), "operations": ordered(context.allowed_operations),
            "namespaces": ordered(context.allowed_namespaces)}


def discover_public(engine, source, namespace, bounds, context, transport):
    _validate(source, bounds, context)
    if not context.allows("discover", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Source namespace is not authorized."),))
    body = source.body
    binding = canonical_hash({"source": source.public_dict(), "namespace": namespace, "body": body,
        "dates": [bounds.date_from, bounds.date_to], "scope": context.scope, "grant": _grant(context),
        "contract": "utah-public-notice-search/v1"})
    return _run(engine, source, namespace, bounds, context, transport, body=body, expression="", binding=binding)


def native_search(engine, request, content, context, *, transport=None):
    if request.get("native") is not True or content is not None or any(
            k in request for k in ("content_base64", "records", "bundle", "result")):
        raise ValueError("Native Utah search requires a fresh public search.")
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Source namespace is not authorized."),))
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    lower = max(filter(None, (query.date_from, bounds.date_from)), default=None)
    upper = min(filter(None, (query.date_to, bounds.date_to)), default=None)
    bounds = replace(bounds, date_from=lower, date_to=upper)
    _validate(source, bounds, context)
    if source.body and query.body and source.body.casefold() != query.body.casefold():
        raise ValueError("Source and query body filters differ.")
    body = query.body or source.body
    expressions = (*query.terms, *query.phrases)
    if not expressions or not expressions[0].strip() or len(expressions[0].encode()) > 1024:
        raise ValueError("Utah native search requires a bounded expression.")
    query = replace(query, date_from=lower, date_to=upper, body=body)
    binding = canonical_hash({"source": source.public_dict(), "namespace": namespace, "query": asdict(query),
        "scope": context.scope, "grant": _grant(context), "contract": "utah-native-search/v1"})
    result = _run(engine, source, namespace, bounds, context, transport or PublicTransport(),
                  body=body, expression=expressions[0], binding=binding)
    if result.status in {"failed", "cancelled"}:
        return result
    records = result.data["records"]
    originals = {source_identity_key(r["identity"]): r for r in records}
    local = [{**deepcopy(r), "normalized": {k: r["normalized"].get(k) for k in ("title", "meeting_date", "body")},
              "text": [], "relationships": []} for r in records]
    searched = search_records(local, query, bounds=replace(bounds, checkpoint=None),
        sources=result.coverage["sources"], inherited_coverage=result.coverage, context=context, storage=engine.storage)
    if searched.data is None or searched.status == "cancelled":
        return searched
    for hit in searched.data["hits"]:
        hit["record"] = originals[source_identity_key(hit["identity"])]
    return OperationResult("partial", {**searched.data, "bundle": result.data}, result.errors + searched.errors,
                           {**searched.coverage, **result.coverage}, context.operation_id)

