"""Bounded AgendaQuick public agenda-item search from the observed form."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import re
from time import monotonic
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import Request

from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .agendaquick import SEARCH_FORMAT, search_rows
from .contracts import PublicTransport, RetrievalError, _origin
from .discovery import _checkpoint, _resume
from .identification import configured_source, validate_source, validate_url
from .native import make_bundle
from .novus import _cookies

_HOST = "public.destinyhosted.com"
_TENANT_ID = "98622"
_FORM_INPUTS = {
    "rtn_agline_rowid": "",
    "formaction": "",
    "form_type": "AG_MEMO",
    "mt": "ALL",
    "id": _TENANT_ID,
}
_DATE_FIELDS = ("beg_meetmth", "beg_meetyr", "end_meetmth", "end_meetyr")
_LOCAL_FIELDS = ("title", "description", "meeting_date", "meeting_type", "department", "submitted_for")
_MAX_NEXT_LINKS = 16


class _SearchForm(HTMLParser):
    """Read only the current public AgendaQuick item-search form."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.current = None
        self.select = None
        self.option_values = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {
                "name": attrs.get("name", ""),
                "method": attrs.get("method", "").lower(),
                "action": attrs.get("action", ""),
                "inputs": {},
                "selects": {},
            }
            if self.current["name"] == "form2":
                self.forms.append(self.current)
        if self.current is None or self.current["name"] != "form2":
            return
        if tag == "input" and attrs.get("name"):
            name = attrs["name"]
            if name in self.current["inputs"]:
                self.current["inputs"][name].append(attrs.get("value", ""))
            else:
                self.current["inputs"][name] = [attrs.get("value", "")]
            if name == "sstr":
                self.current["inputs"][name + "_type"] = [attrs.get("type", "")]
                self.current["inputs"][name + "_maxlength"] = [attrs.get("maxlength", "")]
        elif tag == "select" and attrs.get("name"):
            self.select = attrs["name"]
            self.current["selects"].setdefault(self.select, [])
        elif tag == "option" and self.select:
            self.current["selects"].setdefault(self.select, []).append(attrs.get("value", ""))

    def handle_endtag(self, tag):
        if tag == "select":
            self.select = None
        elif tag == "form":
            self.current = None
            self.select = None


class _ResultSignals(HTMLParser):
    """Extract the displayed result counter and explicit next controls only."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.links = []
        self.active = None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "template"}:
            self.hidden += 1
        if tag == "a":
            self.active = {"href": attrs.get("href"), "rel": attrs.get("rel", ""),
                           "title": attrs.get("title", ""), "aria": attrs.get("aria-label", ""),
                           "text": []}
            self.links.append(self.active)

    def handle_endtag(self, tag):
        if tag == "a":
            self.active = None
        elif tag in {"script", "style", "template"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.hidden:
            return
        if data.strip():
            self.text.append(" ".join(data.split()))
        if self.active is not None:
            self.active["text"].append(" ".join(data.split()))


def _tenant_source(source):
    parts = urlsplit(source.url)
    query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    if (parts.scheme != "https" or parts.hostname != _HOST or parts.port is not None
            or parts.path.lower() != "/agenda_publish.cfm" or parts.fragment
            or set(query) != {"id"} or query.get("id") != [_TENANT_ID]):
        raise ValueError("AgendaQuick public search requires the configured Yuma tenant calendar source.")
    validate_url(source.url)
    return query["id"][0]


def _action_url(source, action, tenant):
    target = urljoin(source.url, action)
    validate_url(target)
    parts = urlsplit(target)
    query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    if (parts.scheme != "https" or _origin(target) != _origin(source.url)
            or parts.path.lower() != "/adv_search_results.cfm" or parts.fragment
            or set(query) != {"fp", "id"} or query.get("fp") != ["ADVSRCH"]
            or query.get("id") != [tenant]):
        raise ValueError("The current public AgendaQuick form action does not match the observed search route.")
    return target


def _read_form(source, content, tenant):
    parser = _SearchForm()
    parser.feed(content.decode("utf-8-sig", errors="strict"))
    if len(parser.forms) != 1:
        raise ValueError("The current public AgendaQuick item-search form is unavailable or ambiguous.")
    form = parser.forms[0]
    if form["method"] != "post":
        raise ValueError("The AgendaQuick item-search form is not the observed POST form.")
    action = _action_url(source, form["action"], tenant)
    inputs = form["inputs"]
    expected_inputs = {"sstr", *_FORM_INPUTS}
    if set(inputs) != expected_inputs | {"sstr_type", "sstr_maxlength"}:
        raise ValueError("The current AgendaQuick item-search form has unexpected input fields.")
    for name, value in _FORM_INPUTS.items():
        if inputs.get(name) != [value]:
            raise ValueError("The current AgendaQuick hidden search fields changed.")
    if inputs.get("sstr_type") != ["text"] or inputs.get("sstr_maxlength") != ["100"]:
        raise ValueError("The current AgendaQuick search text control changed.")
    selects = form["selects"]
    if set(selects) != set(_DATE_FIELDS):
        raise ValueError("The current AgendaQuick form date controls changed.")
    months = set(str(value) for value in range(1, 13))
    years = set(str(value) for value in range(2007, 2051))
    for field in ("beg_meetmth", "end_meetmth"):
        if not months <= set(selects[field]):
            raise ValueError("The current AgendaQuick month options are incomplete.")
    for field in ("beg_meetyr", "end_meetyr"):
        if not years <= set(selects[field]):
            raise ValueError("The current AgendaQuick year options are incomplete.")
    return action, selects


def _fields(source, form_controls, expression, first_day, last_day):
    _tenant_source(source)
    values = {
        "beg_meetmth": str(first_day.month),
        "beg_meetyr": str(first_day.year),
        "end_meetmth": str(last_day.month),
        "end_meetyr": str(last_day.year),
        "sstr": expression,
        **_FORM_INPUTS,
    }
    for name in _DATE_FIELDS:
        if values[name] not in form_controls.get(name, []):
            raise ValueError("The requested date range is outside the current public form options.")
    return values


def _counter_and_next(content):
    parser = _ResultSignals()
    parser.feed(content.decode("utf-8-sig", errors="strict"))
    visible = " ".join(parser.text)
    if "no records were found matching the search criteria" in visible.casefold():
        return None, None, True
    matches = re.findall(r"\bDisplaying\s+([0-9,]+)\s+to\s+([0-9,]+)\s+of\s+([0-9,]+)\s+Records\b",
                         visible, re.I)
    if len(matches) != 1:
        raise ValueError("The AgendaQuick result page has no unique published record counter.")
    start, end, total = (int(value.replace(",", "")) for value in matches[0])
    if not 1 <= start <= end <= total:
        raise ValueError("The AgendaQuick published result counter is inconsistent.")
    next_links = []
    for link in parser.links:
        label = " ".join([link["aria"], link["title"], *link["text"]]).casefold()
        rel = link["rel"].casefold().split()
        if link["href"] and ("next" in rel or re.search(r"\bnext\b", label)):
            next_links.append(link["href"])
    if len(next_links) > _MAX_NEXT_LINKS or len(set(next_links)) > 1:
        raise ValueError("The AgendaQuick result page has conflicting next-page controls.")
    return {"first": start, "last": end, "total": total}, (next_links[0] if next_links else None), False


def _validated_next(source, href, filters):
    target = urljoin(source.url, href)
    validate_url(target)
    parts = urlsplit(target)
    try:
        values = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as error:
        raise ValueError("The AgendaQuick next-page URL is malformed.") from error
    allowed = {"startRow", "id", "form_type", "beg_meetmth", "beg_meetyr", "end_meetmth",
               "end_meetyr", "mt", "sstr", "fp", "dept", "hartkeywords", "sortby"}
    required = {"startRow", "id", "form_type", *_DATE_FIELDS, "mt", "sstr", "fp"}
    if (parts.scheme != "https" or _origin(target) != _origin(source.url)
            or parts.path.lower() != "/adv_search_results.cfm" or parts.fragment
            or set(values) - allowed or any(len(items) != 1 for items in values.values())
            or not required <= set(values)):
        raise ValueError("The AgendaQuick next-page link left the observed public search route or filter scope.")
    if not re.fullmatch(r"-?[0-9]{1,8}", values["startRow"][0]):
        raise ValueError("The AgendaQuick supplied next-page marker is invalid.")
    expected = {key: filters[key] for key in ("id", "form_type", *_DATE_FIELDS, "mt", "sstr")}
    expected["fp"] = "ADVSRCH"
    if any(values.get(key) != [value] for key, value in expected.items()):
        raise ValueError("The AgendaQuick next-page link changed the submitted search filters.")
    if values.get("dept", ["ALL"]) != ["ALL"] or values.get("hartkeywords", [""]) != [""]:
        raise ValueError("The AgendaQuick next-page link contains unsupported search filters.")
    if values.get("sortby", ["f.form_num, f.rev_num"]) != ["f.form_num, f.rev_num"]:
        raise ValueError("The AgendaQuick next-page link changed the unverified sort order.")
    return target


def _grant_binding(context):
    def selected(values):
        return None if values is None else sorted(values)
    return {"authorization": sorted(context.authorization),
            "allowed_operations": selected(context.allowed_operations),
            "allowed_namespaces": selected(context.allowed_namespaces)}


def _calendar_response(response, requested_url, *, byte_limit):
    if response.status != 200:
        raise RetrievalError("provider_http_error", status=response.status)
    if response.url != requested_url or _origin(response.url) != _origin(requested_url):
        raise ValueError("The AgendaQuick public form response left the exact configured URL.")
    if (not isinstance(response.content, bytes) or len(response.content) > byte_limit
            or response.content_type.split(";")[0].strip().casefold() != "text/html"):
        raise ValueError("The AgendaQuick public form response exceeded bounds or was not HTML.")


def native_search(engine, request, content, context, *, transport=None):
    """Search AgendaQuick item candidates and exact-match only observed metadata."""
    if request.get("native") is not True:
        raise ValueError("AgendaQuick search requires native=true; saved records use local search.")
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied",
            "Source namespace is not authorized."),), operation_id=context.operation_id)
    tenant = _tenant_source(source)
    if source.provider not in {"agendaquick", "destiny-agendaquick"}:
        raise ValueError("AgendaQuick search requires the configured AgendaQuick provider.")
    if content is not None or any(key in request for key in ("content_base64", "records", "bundle", "result")):
        raise ValueError("Native AgendaQuick search retrieves public candidates; saved captures use native=false.")

    query = _query(request.get("query", {}))
    bounds = Bounds(**request.get("bounds", {}))
    lower = max(filter(None, (query.date_from, bounds.date_from)), default=None)
    upper = min(filter(None, (query.date_to, bounds.date_to)), default=None)
    if not lower or not upper or lower > upper:
        raise ValueError("AgendaQuick native item search requires a nonempty explicit date range.")
    query = replace(query, date_from=lower, date_to=upper)
    if query.record_types and set(query.record_types) != {"agenda_item"}:
        raise ValueError("The observed AgendaQuick search exposes agenda items only.")
    expressions = (*query.terms, *query.phrases)
    if not expressions:
        raise ValueError("AgendaQuick native search requires at least one term or phrase.")
    expression = expressions[0]
    if len(expression) > 100 or len(expression.encode("utf-8")) > min(bounds.parser_bytes, 400):
        raise ValueError("The AgendaQuick search expression exceeds the observed 100-character field bound.")
    first_day, last_day = date.fromisoformat(lower), date.fromisoformat(upper)
    candidate_fields = {
        "beg_meetmth": str(first_day.month), "beg_meetyr": str(first_day.year),
        "end_meetmth": str(last_day.month), "end_meetyr": str(last_day.year),
        "sstr": expression, **_FORM_INPUTS,
    }
    origin = _origin(source.url)
    binding = canonical_hash({"source": source.public_dict(), "namespace": namespace,
        "query": asdict(query), "caller_scope": context.scope, "current_grant": _grant_binding(context),
        "form_fields": candidate_fields, "contract": "agendaquick-public-item-search/v1"})
    if bounds.checkpoint:
        queue, seen = _resume(bounds.checkpoint, binding)
        if len(queue) != 1:
            raise ValueError("AgendaQuick search checkpoint must contain one page task.")
        task = queue[0]
        if set(task) - {"kind", "url", "offset", "sha256"} or task.get("kind") not in {"post", "get"}:
            raise ValueError("AgendaQuick search checkpoint contains unsupported task fields.")
    else:
        queue, seen = ([{"kind": "post", "offset": 0}], set())
        task = queue[0]
    offset = task.get("offset", 0)
    # A per-call max_records limit can be smaller than an absolute offset in
    # the captured provider page. The actual row count is checked after the
    # hash-bound page is fetched and parsed.
    if type(offset) is not int or not 0 <= offset <= bounds.parser_bytes:
        raise ValueError("AgendaQuick search checkpoint offset is invalid.")
    if task["kind"] == "get":
        page_url = task.get("url")
        if not isinstance(page_url, str):
            raise ValueError("AgendaQuick search checkpoint is missing its supplied next-page URL.")
        page_url = _validated_next(source, page_url, candidate_fields)
    else:
        page_url = None
        if task.get("url") is not None:
            raise ValueError("AgendaQuick search POST checkpoint cannot override the observed form action.")
    expected_digest = task.get("sha256")
    if expected_digest is not None and not re.fullmatch(r"[0-9a-f]{64}", str(expected_digest)):
        raise ValueError("AgendaQuick checkpoint page digest is invalid.")
    if offset and expected_digest is None:
        raise ValueError("AgendaQuick mid-page checkpoint must bind the captured response hash.")

    active_transport = transport or PublicTransport()
    deadline = monotonic() + bounds.deadline_seconds
    pages, records, bundles, captures, errors = 0, [], [], [], []
    counters, unidentified = [], 0
    counter, next_href, explicit_empty = None, None, False
    query_window_exhausted = False
    next_task = None
    cookie_jar = CookieJar()
    try:
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", operation_id=context.operation_id)
        form_response = active_transport.request(source.url, method="GET", headers={"Accept": "text/html"},
            byte_limit=bounds.parser_bytes, deadline_seconds=max(0.001, deadline - monotonic()),
            allowed_origins=(origin,), allow_redirects=False)
        _calendar_response(form_response, source.url, byte_limit=bounds.parser_bytes)
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", operation_id=context.operation_id)
        _cookies(cookie_jar, form_response, source.url)
        form_action, options = _read_form(source, form_response.content, tenant)
        fields = _fields(source, options, expression, first_day, last_day)
        # max_records bounds upstream candidates. Query.limit applies to exact
        # local hits and must not prevent a later candidate on the same page
        # from matching the remaining terms.
        candidate_limit = bounds.max_records
        while task and pages < bounds.max_pages and len(records) < candidate_limit:
            if operation_cancelled(engine.storage, context):
                next_task = task
                break
            if monotonic() >= deadline:
                next_task = task
                errors.append(Error("provider_deadline_exceeded", "The AgendaQuick search deadline expired.",
                                    retryable=True, source=source.url))
                break
            if task["kind"] == "post":
                url, method = form_action, "POST"
                body = urlencode(fields).encode("ascii")
                if len(body) > bounds.parser_bytes:
                    raise ValueError("AgendaQuick search form body exceeds parser bounds.")
            else:
                url, method, body = task["url"], "GET", None
            headers = {"Accept": "text/html", "Referer": source.url}
            if method == "POST":
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            cookie_request = Request(url)
            cookie_jar.add_cookie_header(cookie_request)
            if cookie_request.has_header("Cookie"):
                headers["Cookie"] = cookie_request.get_header("Cookie")
            response = active_transport.request(url, method=method, body=body, headers=headers,
                byte_limit=bounds.parser_bytes, deadline_seconds=max(0.001, deadline - monotonic()),
                allowed_origins=(origin,), allow_redirects=False)
            if operation_cancelled(engine.storage, context):
                next_task = task
                break
            _calendar_response(response, url, byte_limit=bounds.parser_bytes)
            if monotonic() >= deadline:
                raise RetrievalError("provider_deadline_exceeded")
            _cookies(cookie_jar, response, url)
            digest = sha256(response.content).hexdigest()
            if task.get("sha256") and task["sha256"] != digest:
                raise ValueError("The resumed AgendaQuick search page changed; restart the search.")
            counter, next_href, explicit_empty = _counter_and_next(response.content)
            rows = [] if explicit_empty else search_rows(source, response.content)
            if counter and counter["last"] - counter["first"] + 1 < len(rows):
                raise ValueError("The AgendaQuick result counter is smaller than the mapped row set.")
            page_offset = task.get("offset", 0)
            if page_offset > len(rows):
                raise ValueError("AgendaQuick checkpoint offset is outside the captured result page.")
            next_url = _validated_next(source, next_href, candidate_fields) if next_href else None
            bundle = make_bundle(source, namespace, response.content, SEARCH_FORMAT, rows)
            bundle["capture"]["retrieval_url"] = response.url
            selected = []
            for index in range(page_offset, len(bundle["records"])):
                if (operation_cancelled(engine.storage, context) or monotonic() >= deadline
                        or len(records) >= candidate_limit):
                    next_task = {"kind": task["kind"], "offset": index, "sha256": digest}
                    if task["kind"] == "get":
                        next_task["url"] = url
                    if monotonic() >= deadline:
                        errors.append(Error("provider_deadline_exceeded", "The AgendaQuick search deadline expired.",
                                            retryable=True, source=source.url))
                    break
                record = bundle["records"][index]
                external_id = record["identity"]["external_id"]
                if not re.fullmatch(r"[0-9]{1,18}", str(external_id)):
                    unidentified += 1
                    continue
                key = source_identity_key(record["identity"])
                if key not in seen:
                    seen.add(key)
                    selected.append(record)
                    records.append(record)
            else:
                if next_url:
                    next_task = {"kind": "get", "url": next_url, "offset": 0}
                elif explicit_empty or (counter and counter["last"] >= counter["total"]):
                    query_window_exhausted = True
            bundle["records"] = selected
            bundles.append(bundle)
            captures.append(bundle["capture"])
            pages += 1
            if counter:
                counters.append(counter)
            context.report(operation="search", pages=pages, returned_records=len(records))
            task = next_task
            if task and pages < bounds.max_pages and len(records) < candidate_limit:
                next_task = None
    except Exception as exc:
        code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
        errors.append(Error(code, "The AgendaQuick public item-search page could not be retrieved or parsed.",
                            retryable=True, source=source.url))

    body_requested = query.body if query.body is not None else source.body
    coverage = {
        "sources": [{**source.public_dict(), "namespace": namespace}],
        "native_search": True,
        "scope": "public AgendaQuick agenda-item candidates; exact local matching on selected metadata",
        "provider_query_semantics": "public sstr form; exact-term and phrase semantics remain provider-defined",
        "native_fields": list(_LOCAL_FIELDS),
        "searched_fields": list(_LOCAL_FIELDS),
        "full_source_searched": False,
        "provider_description_scope": "displayed result excerpt/description; not full document text",
        "query_window_exhausted": bool(query_window_exhausted and not errors and not next_task),
        "provider_result_counters": counters,
        "catalog_complete": False,
        "source_complete": False,
        "status": "partial",
        "pages": pages,
        "unidentified_rows_omitted": unidentified,
        "body_filter": {"status": "unknown_retained" if body_requested else "not_requested",
                        "requested": body_requested, "applied": False},
        "checkpoint": _checkpoint(binding, [next_task], seen) if next_task else None,
    }
    if body_requested:
        coverage["limitations"] = ["The public item-search form has no verified body filter; candidates are retained with body unknown."]
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    if errors and not captures:
        return OperationResult("failed", errors=tuple(errors), coverage=coverage,
                              operation_id=context.operation_id)

    originals = {source_identity_key(row["identity"]): row for row in records}
    local = [{**deepcopy(row),
              "normalized": {key: row.get("normalized", {}).get(key) for key in _LOCAL_FIELDS
                             if row.get("normalized", {}).get(key) is not None},
              "text": [], "relationships": []} for row in records]
    local_query = replace(query, body=None)
    searched = search_records(local, local_query,
        bounds=replace(bounds, date_from=None, date_to=None, checkpoint=None,
                       deadline_seconds=max(0.001, deadline - monotonic())),
        sources=coverage["sources"], inherited_coverage=coverage,
        context=context, storage=engine.storage)
    if searched.data is None or searched.status == "cancelled":
        return searched
    for hit in searched.data["hits"]:
        hit["record"] = originals[source_identity_key(hit["identity"])]
    bundle = {"records": records, "captures": captures, "bundles": bundles}
    return OperationResult("partial", {**searched.data, "bundle": bundle},
                           tuple(errors) + searched.errors, {**searched.coverage, **coverage},
                           context.operation_id)
