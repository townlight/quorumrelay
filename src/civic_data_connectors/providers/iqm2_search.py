"""Observed iQM2 public search result and scoped anonymous form session."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import re
from threading import Lock
from time import monotonic, time
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import Request

from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, RetrievalError
from .identification import configured_source, validate_source
from .native import make_bundle
from .novus import _Sessions, _cookies

FORMAT = "iqm2-public-search-html"
_ORIGIN = "https://kentwa.iqm2.com"
_URL = _ORIGIN + "/Citizens/Search.aspx"
_LOCK = Lock()


class _Form(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.active, self.action, self.method = False, None, None
        self.controls, self.select, self.option = {}, None, None
        self.feed(content.decode("utf-8-sig"))

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "form" and d.get("id") == "aspnetForm":
            if self.action is not None:
                raise ValueError("Ambiguous public search form.")
            self.active, self.action, self.method = True, d.get("action"), d.get("method", "").lower()
        if not self.active:
            return
        if tag == "input" and d.get("name") and "disabled" not in d:
            kind = d.get("type", "text").lower()
            if kind in {"hidden", "text", "search"} or (kind in {"checkbox", "radio"} and "checked" in d):
                self.controls[d["name"]] = d.get("value", "on" if kind in {"checkbox", "radio"} else "")
        if tag == "select" and d.get("name") and "disabled" not in d:
            self.select = {"name": d["name"], "options": []}
        if tag == "option" and self.select is not None:
            self.option = {"value": d.get("value"), "selected": "selected" in d, "text": []}

    def handle_data(self, value):
        if self.option is not None:
            self.option["text"].append(value)

    def handle_endtag(self, tag):
        if tag == "option" and self.option is not None and self.select is not None:
            self.select["options"].append(self.option)
            self.option = None
        if tag == "select" and self.select is not None:
            options = self.select["options"]
            if options:
                choice = next((v for v in options if v["selected"]), options[0])
                self.controls[self.select["name"]] = choice["value"] if choice["value"] is not None else "".join(choice["text"])
            self.select = None
        if tag == "form":
            self.active = False


class _Results(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.in_list, self.item, self.title, self.mode = False, None, None, None
        self.rows, self.next, self.anchor, self.all_text = [], None, None, []
        self.found = False
        self.feed(content.decode("utf-8-sig"))

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if d.get("id") == "divSearchResults":
            self.found = True
        if tag == "ol" and "Search" in d.get("class", "").split():
            self.in_list = True
        if tag == "li" and self.in_list:
            self.item = {"href": None, "title": [], "description": [], "meta": []}
        if tag == "a":
            if self.item is not None and "T" in d.get("class", "").split():
                self.item["href"], self.mode = d.get("href"), "title"
            elif self.item is None and d.get("href", "").startswith("Search.aspx#"):
                self.anchor = {"href": d["href"], "text": []}
        if self.item is not None and tag == "div":
            cls = d.get("class", "").split()
            if "D" in cls:
                self.mode = "description"
            elif "G" in cls:
                self.mode = "meta"

    def handle_data(self, data):
        self.all_text.append(data)
        if self.item is not None and self.mode:
            self.item[self.mode].append(data)
        if self.anchor is not None:
            self.anchor["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a":
            if self.anchor is not None:
                if " ".join("".join(self.anchor["text"]).split()).casefold() == "next":
                    if self.next is not None and self.next != self.anchor["href"]:
                        raise ValueError("Ambiguous search pager.")
                    self.next = self.anchor["href"]
                self.anchor = None
            if self.mode == "title":
                self.mode = None
        if tag == "li" and self.in_list and self.item is not None:
            self.rows.append(self.item)
            self.item, self.mode = None, None
        if tag == "ol" and self.in_list:
            self.in_list = False


def _rows(source, content):
    page = _Results(content)
    if not page.found:
        raise ValueError("The public iQM2 result container is missing.")
    empty = "did not match any documents" in " ".join(page.all_text).casefold()
    if not page.rows and not empty:
        raise ValueError("The iQM2 page did not contain recognized results or an explicit empty result.")
    rows = []
    for raw in page.rows:
        link = urljoin(_URL, raw["href"] or "")
        p = urlsplit(link)
        values = parse_qs(p.query, keep_blank_values=True)
        routes = {"/Citizens/FileOpen.aspx": ("attachment", {"ID", "Type"}),
                  "/Citizens/Detail_Communication.aspx": ("communication", {"ID"}),
                  "/Citizens/Detail_LegiFile.aspx": ("legislative_file", {"ID"})}
        route = routes.get(p.path)
        if (p.scheme != "https" or p.netloc != "kentwa.iqm2.com" or p.fragment or not route
                or set(values) != route[1] or len(values["ID"]) != 1 or not values["ID"][0].isascii()
                or not values["ID"][0].isdecimal() or ("Type" in values and values["Type"] != ["4"])):
            continue
        title = " ".join("".join(raw["title"]).split())
        excerpt = " ".join("".join(raw["description"]).split())
        meta = " ".join("".join(raw["meta"]).split())
        if not title:
            continue
        day = None
        match = re.search(r"\b([A-Z][a-z]{2} \d{1,2}, \d{4} \d{1,2}:\d{2} [AP]M)", meta)
        if match:
            try:
                day = datetime.strptime(match.group(1), "%b %d, %Y %I:%M %p").date().isoformat()
            except ValueError:
                pass
        normalized = {"external_id": values["ID"][0], "title": title, "description": excerpt,
            "meeting_date": day, "time_zone_status": "unknown", "url": link, "source_kind": route[0],
            "documents": [], "recordings": [], "agenda_items_availability": "unverified"}
        rows.append((normalized, deepcopy(raw), route[0]))
    if page.rows and not rows:
        raise ValueError("No iQM2 rows had an observed route-specific identity.")
    return rows, page.next


def _next_hash(href, expression, previous):
    if not href:
        return None
    p = urlsplit(urljoin(_URL, href))
    q = parse_qs(p.fragment, keep_blank_values=True, strict_parsing=True)
    if (p.scheme != "https" or p.netloc != "kentwa.iqm2.com" or p.path != "/Citizens/Search.aspx" or p.query
            or set(q) != {"SearchText", "Type", "MediaOnly", "Start", "SortBy"}
            or any(len(v) != 1 for v in q.values()) or q["SearchText"] != [expression]
            or q["Type"] != ["All"] or q["MediaOnly"] != ["False"] or q["SortBy"] != ["Relevance"]
            or not q["Start"][0].isascii() or not q["Start"][0].isdecimal()
            or not previous < int(q["Start"][0]) <= 1000000):
        raise ValueError("The supplied iQM2 pager changed search scope.")
    return "#" + p.fragment, int(q["Start"][0])


def _form_fields(content, expression):
    form = _Form(content)
    if form.method != "post" or urljoin(_URL, form.action or "") != _URL:
        raise ValueError("The observed iQM2 public form changed.")
    controls = form.controls
    for suffix in ("SearchText", "hfInputHashQuery", "hfRealSearchTerms", "hfAdvancedSearchOption", "txtExclude"):
        keys = [name for name in controls if name.endswith("$" + suffix)]
        if len(keys) != 1:
            raise ValueError("The observed iQM2 search controls changed.")
        controls[keys[0]] = expression if suffix == "SearchText" else ""
    if "__VIEWSTATE" not in controls or len(urlencode(controls).encode()) > 65536:
        raise ValueError("The iQM2 public form state is missing or too large.")
    return controls



class _BoundedSessions(_Sessions):
    def put(self, state, binding):
        # The generic session cache accounts for captures and cookies; reserve a
        # strict upper bound for private ASP.NET controls as well.
        with self.lock:
            self._prune()
            if len(self.values) >= 64:
                raise ValueError("Private search continuation capacity reached.")
        return super().put(state, binding)


def _cache(engine):
    with _LOCK:
        if not hasattr(engine, "_iqm2_search_sessions"):
            engine._iqm2_search_sessions = _BoundedSessions()
        return engine._iqm2_search_sessions


def _checked_response(transport, url, method, body, headers, bounds, deadline):
    if monotonic() >= deadline:
        raise RetrievalError("provider_deadline_exceeded")
    response = transport.request(url, method=method, body=body, headers=headers,
        byte_limit=bounds.parser_bytes, deadline_seconds=max(.001, deadline - monotonic()),
        allowed_origins=(_ORIGIN,), allow_redirects=False)
    if response.status != 200:
        raise RetrievalError("provider_http_error", status=response.status)
    if (response.url != url or not isinstance(response.content, bytes) or len(response.content) > bounds.parser_bytes
            or response.content_type.split(";")[0].strip().lower() != "text/html" or monotonic() >= deadline):
        raise ValueError("The bounded public search response was not the requested HTML.")
    return response


def _headers(cookies, url, *, post=False):
    result = {"Accept": "text/html", "Referer": _URL}
    req = Request(url)
    cookies.add_cookie_header(req)
    if req.has_header("Cookie"):
        result["Cookie"] = req.get_header("Cookie")
    if post:
        result["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    return result


def _grant(context):
    def ordered(value):
        return None if value is None else sorted(value)
    return {"authorization": sorted(context.authorization), "operations": ordered(context.allowed_operations),
            "namespaces": ordered(context.allowed_namespaces)}


def native_search(engine, request, content, context, *, transport=None):
    if request.get("native") is not True or content is not None or any(
            key in request for key in ("content_base64", "records", "bundle", "result")):
        raise ValueError("iQM2 native search requires a fresh public search.")
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Source namespace is not authorized."),))
    p = urlsplit(source.url)
    if (source.provider != "iqm2" or p.scheme != "https" or p.netloc != "kentwa.iqm2.com"
            or p.path.casefold() not in {"/citizens/calendar.aspx", "/citizens/search.aspx"} or p.query or p.fragment):
        raise ValueError("Public search requires the observed Kent iQM2 source.")
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    lower = max(filter(None, (query.date_from, bounds.date_from)), default=None)
    upper = min(filter(None, (query.date_to, bounds.date_to)), default=None)
    if lower and upper and lower > upper:
        raise ValueError("The requested iQM2 date ranges do not overlap.")
    query = replace(query, date_from=lower, date_to=upper)
    if source.body or query.body:
        raise ValueError("The observed public iQM2 search does not establish a body filter.")
    expressions = (*query.terms, *query.phrases)
    if not expressions or not expressions[0].strip() or len(expressions[0].encode()) > 1024:
        raise ValueError("A bounded search expression is required.")
    expression = expressions[0]
    binding = canonical_hash({"source": source.public_dict(), "namespace": namespace, "query": asdict(query),
        "scope": context.scope, "grant": _grant(context), "contract": "iqm2-public-search/v1"})
    cache = _cache(engine)
    state = cache.get(bounds.checkpoint, binding) if bounds.checkpoint else {
        "content": None, "cookies": CookieJar(), "offset": 0, "grid_pages": {"meeting": 0},
        "seen": set(), "exhausted": set(), "pending": None, "controls": None}
    active, deadline = transport or PublicTransport(), monotonic() + bounds.deadline_seconds
    records, bundles, errors = [], [], []
    pages, finished = 0, False
    transferred = 0

    def fetch(url, method, body, headers):
        nonlocal transferred
        remaining = bounds.transfer_bytes - transferred
        if remaining <= 0:
            raise RetrievalError("provider_transfer_limit")
        response = _checked_response(active, url, method, body, headers,
                                     replace(bounds, parser_bytes=min(bounds.parser_bytes, remaining)), deadline)
        transferred += len(response.content)
        return response

    try:
        if state["content"] is None:
            if operation_cancelled(engine.storage, context):
                return OperationResult("cancelled", operation_id=context.operation_id)
            form = fetch(_URL, "GET", None, _headers(state["cookies"], _URL))
            _cookies(state["cookies"], form, _URL)
            state["controls"] = _form_fields(form.content, expression)
            state["pending"] = "initial"
        while pages < bounds.max_pages and len(records) < bounds.max_records:
            if operation_cancelled(engine.storage, context) or monotonic() >= deadline:
                break
            if state["pending"] is not None:
                controls = deepcopy(state["controls"])
                pending = state["pending"]
                action = "DoSearch" if pending == "initial" else "DoSearchFull"
                if pending != "initial":
                    current = _next_hash(_Results(state["content"]).next, expression, state["grid_pages"]["meeting"])
                    if current is None or current[0] != pending:
                        raise ValueError("The current public result no longer supplies the continuation.")
                    key = next(k for k in controls if k.endswith("$hfInputHashQuery"))
                    controls[key] = pending
                body = urlencode(controls).encode()
                if len(body) > bounds.parser_bytes:
                    raise ValueError("Public form state exceeds the parser limit.")
                url = _URL + "?" + urlencode({"Action": action, "RequestTime": str(int(time() * 1000))})
                response = fetch(url, "POST", body, _headers(state["cookies"], url, post=True))
                _cookies(state["cookies"], response, url)
                if pending != "initial" and response.content == state["content"]:
                    raise ValueError("The supplied pager did not advance.")
                if pending != "initial":
                    state["grid_pages"]["meeting"] = current[1]
                state["content"], state["offset"], state["pending"] = response.content, 0, None
            if len(state["content"]) > bounds.parser_bytes:
                raise ValueError("Continued response exceeds parser bounds.")
            rows, next_href = _rows(source, state["content"])
            bundle = make_bundle(source, namespace, state["content"], FORMAT, rows)
            selected = []
            for index in range(state["offset"], len(bundle["records"])):
                if (len(records) >= bounds.max_records or operation_cancelled(engine.storage, context)
                        or monotonic() >= deadline):
                    break
                state["offset"] = index + 1
                record = bundle["records"][index]
                key = source_identity_key(record["identity"])
                if key not in state["seen"]:
                    state["seen"].add(key)
                    selected.append(record)
                    records.append(record)
            bundle["records"] = selected
            bundles.append(bundle)
            pages += 1
            if state["offset"] >= len(rows):
                next_page = _next_hash(next_href, expression, state["grid_pages"]["meeting"])
                if next_page:
                    state["pending"] = next_page[0]
                else:
                    finished = True
                    break
            context.report(operation="search", pages=pages, returned_records=len(records))
    except Exception as exc:
        code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
        errors.append(Error(code, "The public iQM2 search could not be retrieved or verified.",
                            retryable=True, source=source.url))
    if monotonic() >= deadline and not operation_cancelled(engine.storage, context):
        errors.append(Error("provider_deadline_exceeded", "The public search deadline expired.",
                            retryable=True, source=source.url))
    checkpoint = None
    if not finished and state["content"] is not None:
        try:
            checkpoint = cache.put(state, binding)
        except ValueError:
            errors.append(Error("continuation_capacity", "Private continuation capacity is exhausted."))
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
        "scope": "mixed public search results; exact local metadata and displayed excerpt matching",
        "native_fields": ["title", "description", "meeting_date"], "full_source_searched": False,
        "catalog_complete": False, "source_complete": False, "query_window_exhausted": False,
        "observed_page_exhausted": finished and not errors, "status": "partial", "pages": pages,
        "checkpoint": checkpoint, "checkpoint_lifetime": "15 minutes; current engine process only"}
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    if errors and not bundles:
        return OperationResult("failed", errors=tuple(errors), coverage=coverage, operation_id=context.operation_id)
    originals = {source_identity_key(r["identity"]): r for r in records}
    local = [{**deepcopy(r), "normalized": {k: r["normalized"].get(k) for k in ("title", "description", "meeting_date")},
              "text": [], "relationships": []} for r in records]
    searched = search_records(local, query, bounds=replace(bounds, checkpoint=None,
        deadline_seconds=max(.001, deadline - monotonic())),
        sources=coverage["sources"], inherited_coverage=coverage, context=context, storage=engine.storage)
    if searched.data is None or searched.status == "cancelled":
        return searched
    for hit in searched.data["hits"]:
        hit["record"] = originals[source_identity_key(hit["identity"])]
    return OperationResult("partial", {**searched.data, "bundle": {"records": records, "bundles": bundles,
        "captures": [b["capture"] for b in bundles]}}, tuple(errors) + searched.errors,
        {**searched.coverage, **coverage}, context.operation_id)
