"""Bounded ClerkBase South Kingstown search and supplied agenda-tree rows."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import re
from time import monotonic
from urllib.parse import urlencode, urljoin, urlsplit, unquote
from urllib.request import Request

from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, RetrievalError, _origin
from .discovery import _checkpoint, _resume
from .identification import configured_source, validate_source, validate_url
from .native import make_bundle
from .novus import _cookies

FORMAT = "clerkbase-search-html"
_HOST = "clerkshq.com"
_SITE = "SouthKingstown-ri"
_TREE_PATHS = {
    "SouthKingstown_Docket", "SouthKingstown_Council", "SouthKingstown_TM_Reports",
    "SK_Planning", "TRC", "SK_Zoning", "BOARDS", "Town_Council_Agenda Archive",
}
_SEARCH_TYPES = {"AllWords", "AnyWords", "Phrase", "Boolean", "NearTerm"}
_LOCAL_FIELDS = ("title", "location", "search_excerpts", "meeting_date")
_MAX_PAGE_NUMBER = 10000


class _SidebarForm(HTMLParser):
    """Read the currently published sidebar controls without executing script."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.current = None
        self.select = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form" and "sidebar-form" in values.get("class", "").split():
            self.current = {"attrs": values, "controls": []}
            self.forms.append(self.current)
        if self.current is None:
            return
        if tag == "input":
            self.current["controls"].append({"kind": "input", "attrs": values})
        elif tag == "select":
            self.select = {"kind": "select", "attrs": values, "options": []}
            self.current["controls"].append(self.select)
        elif tag == "option" and self.select is not None:
            self.select["options"].append(values)

    def handle_endtag(self, tag):
        if tag == "select":
            self.select = None
        elif tag == "form":
            self.current = None
            self.select = None


class _SearchPage(HTMLParser):
    """Read provider-supplied document rows, counters and next controls."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.link = None
        self.search_word = []
        self.search_word_count = 0
        self._in_search_word = False
        self.paragraphs = []
        self.paragraph = None
        self.next_page_numbers = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        classes = set(values.get("class", "").split())
        if tag == "tr" and "data-result-url" in values:
            self.row = {"attrs": values, "cells": []}
            self.rows.append(self.row)
            self.cell = None
        elif tag == "td" and self.row is not None:
            self.cell = {"text": [], "links": []}
            self.row["cells"].append(self.cell)
        elif tag == "a" and self.cell is not None:
            self.link = {"attrs": values, "text": []}
            self.cell["links"].append(self.link)
        if tag == "strong" and "search-word" in classes:
            self.search_word_count += 1
            self._in_search_word = True
        if tag == "p":
            self.paragraph = []
        if tag == "a" and "js-page-link" in classes and "next" in classes:
            self.next_page_numbers.append(values.get("data-page-num", ""))

    def handle_endtag(self, tag):
        if tag == "a":
            self.link = None
        elif tag == "td":
            self.cell = None
        elif tag == "tr":
            self.row = None
            self.cell = None
            self.link = None
        elif tag == "strong":
            self._in_search_word = False
        elif tag == "p" and self.paragraph is not None:
            self.paragraphs.append(" ".join(" ".join(self.paragraph).split()))
            self.paragraph = None

    def handle_data(self, data):
        if self.row is not None and self.cell is not None:
            self.cell["text"].append(data)
            if self.link is not None:
                self.link["text"].append(data)
        if self._in_search_word:
            self.search_word.append(data)
        if self.paragraph is not None:
            self.paragraph.append(data)


class _AgendaTree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and "js-doc-view" in values.get("class", "").split():
            self.active = {"attrs": values, "text": []}
            self.links.append(self.active)

    def handle_endtag(self, tag):
        if tag == "a":
            self.active = None

    def handle_data(self, data):
        if self.active is not None:
            self.active["text"].append(data)


def _site_source(source):
    parts = urlsplit(source.url)
    if (parts.scheme != "https" or parts.hostname != _HOST or parts.port is not None
            or parts.path.rstrip("/").casefold() != "/southkingstown-ri".casefold()
            or parts.query or parts.fragment):
        raise ValueError("ClerkBase search is limited to the configured South Kingstown public site.")
    validate_url(source.url)
    return _SITE


def _document_url(source, supplied):
    origin = _origin(source.url)
    target = urljoin(origin + "/", supplied)
    validate_url(target)
    parts = urlsplit(target)
    decoded = unquote(parts.path)
    if (parts.scheme != "https" or _origin(target) != origin or parts.query or parts.fragment
            or not decoded.casefold().startswith(f"/Content/{_SITE}/".casefold())
            or any(segment in {".", ".."} for segment in decoded.split("/"))):
        raise ValueError("ClerkBase supplied document URL left the configured public content tree.")
    return target


def _explicit_title_date(title):
    match = re.match(
        r"^(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+"
        r"([0-3]?[0-9]),\s+([0-9]{4})(?=\s*[-–]|$)", title, re.I)
    if not match:
        return None
    month_name = match.group(1)[:3].casefold()
    try:
        month = {name.casefold(): index for index, name in enumerate(
            ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))
            if name}[month_name]
        return date(int(match.group(3)), month, int(match.group(2))).isoformat()
    except (KeyError, ValueError):
        return None


def _row_mapping(source, row):
    attrs = row["attrs"]
    supplied_url = attrs.get("data-result-url")
    title = " ".join((attrs.get("data-title") or "").split())
    cells = row["cells"]
    if not supplied_url or not title or len(cells) < 4:
        return None
    url = _document_url(source, supplied_url)
    row_links = [link["attrs"].get("href") for cell in cells for link in cell["links"]
                 if link["attrs"].get("href")]
    if not row_links or any(_document_url(source, link) != url for link in row_links):
        raise ValueError("ClerkBase result row links disagree with its supplied document URL.")
    excerpts = []
    for cell in cells:
        for link in cell["links"]:
            if "search-word-line" in link["attrs"].get("class", "").split():
                excerpt = " ".join(" ".join(link["text"]).split())
                if excerpt and excerpt not in excerpts:
                    excerpts.append(excerpt)
    location = " ".join(" ".join(cells[3]["text"]).split())
    normalized = {
        "external_id": url,
        "title": title,
        "url": url,
        "location": location,
        "search_excerpts": excerpts,
        "documents": [],
        "recordings": [],
        "time_zone_status": "unknown",
        "agenda_items_availability": "unverified",
    }
    day = _explicit_title_date(title)
    if day:
        normalized["meeting_date"] = day
    raw = {
        "row_attributes": deepcopy(attrs),
        "cell_text": [" ".join(" ".join(cell["text"]).split()) for cell in cells],
        "links": [{"attributes": deepcopy(link["attrs"]),
                   "text": " ".join(" ".join(link["text"]).split())}
                  for cell in cells for link in cell["links"]],
    }
    return normalized, raw, "document"


def _search_rows(source, content):
    parser = _SearchPage()
    parser.feed(content.decode("utf-8-sig", errors="strict"))
    search_word = " ".join(" ".join(parser.search_word).split())
    paragraphs = parser.paragraphs
    empty = (len(paragraphs) == 1 and re.fullmatch(
        r"There are no results for\s+.+", paragraphs[0], re.I) is not None)
    if empty:
        empty_term = re.sub(r"^There are no results for\s+", "", paragraphs[0], flags=re.I).strip()
        if search_word or parser.rows or parser.next_page_numbers:
            raise ValueError("ClerkBase empty-result response contains conflicting result content.")
        return [], {"empty": True, "empty_term": empty_term, "total": 0, "first": 0,
                    "last": -1, "page_size": 0, "next_page_num": None, "row_count": 0,
                    "omitted": 0}
    if parser.search_word_count != 1 or not search_word:
        raise ValueError("ClerkBase search response does not display one unique search expression.")
    status_match = re.search(
        r"window\.searchStatus\s*=\s*\{\s*totalFileCount:\s*([0-9]+),\s*"
        r"firstItem:\s*([0-9]+),\s*lastItem:\s*([0-9]+),\s*pageSize:\s*([0-9]+)\s*\}",
        content.decode("utf-8-sig", errors="strict"), re.S)
    if not status_match:
        raise ValueError("ClerkBase search response lacks its published page counters.")
    total, first, last, page_size = (int(value) for value in status_match.groups())
    if total <= 0 or page_size <= 0 or first < 0 or last < first or last >= total:
        raise ValueError("ClerkBase published search counters are inconsistent.")
    if last - first + 1 != len(parser.rows):
        raise ValueError("ClerkBase page counters do not match the supplied result rows.")
    if len(parser.next_page_numbers) > 1:
        raise ValueError("ClerkBase response contains conflicting next-page controls.")
    next_page_num = None
    if parser.next_page_numbers:
        value = parser.next_page_numbers[0]
        if not re.fullmatch(r"[2-9][0-9]{0,4}", value):
            raise ValueError("ClerkBase next-page control has an invalid page number.")
        next_page_num = int(value) - 1
        if next_page_num > _MAX_PAGE_NUMBER:
            raise ValueError("ClerkBase next-page control exceeds its page bound.")
    rows, seen_urls, omitted = [], set(), 0
    for row in parser.rows:
        mapped = _row_mapping(source, row)
        if mapped is None:
            omitted += 1
            continue
        url = mapped[0]["url"]
        if url in seen_urls:
            omitted += 1
            continue
        seen_urls.add(url)
        rows.append(mapped)
    return rows, {"empty": False, "empty_term": None, "total": total, "first": first,
                  "last": last, "page_size": page_size, "next_page_num": next_page_num,
                  "row_count": len(parser.rows), "omitted": omitted,
                  "search_word": search_word}


def listing_rows(source, content):
    """Map the captured South Kingstown agenda tree without inferring parents."""
    _site_source(source)
    parser = _AgendaTree()
    parser.feed(content.decode("utf-8-sig", errors="strict"))
    rows, seen = [], set()
    for link in parser.links:
        attrs = link["attrs"]
        title = " ".join(" ".join(link["text"]).split()) or " ".join((attrs.get("title") or "").split())
        if not title or not attrs.get("href"):
            continue
        url = _document_url(source, attrs["href"])
        if url in seen:
            continue
        seen.add(url)
        normalized = {
            "external_id": url,
            "title": title,
            "url": url,
            "location": None,
            "search_excerpts": [],
            "documents": [],
            "recordings": [],
            "time_zone_status": "unknown",
            "agenda_items_availability": "unverified",
        }
        day = _explicit_title_date(title)
        if day:
            normalized["meeting_date"] = day
        rows.append((normalized, {"link_attributes": deepcopy(attrs),
                                  "link_text": " ".join(" ".join(link["text"]).split())}, "document"))
    if not rows:
        raise ValueError("The current ClerkBase response has no supplied South Kingstown document links.")
    return rows


def mark_supplied_url_identities(bundle):
    """Label document URL keys as supplied URLs, never as provider IDs."""
    for record in bundle.get("records", []):
        url = record.get("normalized", {}).get("url")
        if record.get("identity", {}).get("external_id") == url:
            record["identity"]["derivation"] = "supplied_url"
            record["identity"]["stability"] = "Uses the exact supplied public document URL; changes when that URL changes."
    return bundle


def _search_url(source):
    target = urljoin(source.url, "search")
    validate_url(target)
    if target != _origin(source.url) + "/search":
        raise ValueError("The ClerkBase public search path no longer matches the observed relative route.")
    return target


def _form_pairs(source, content, expression, search_type):
    parser = _SidebarForm()
    parser.feed(content.decode("utf-8-sig", errors="strict"))
    if len(parser.forms) != 1:
        raise ValueError("The current ClerkBase sidebar search form is unavailable or ambiguous.")
    form = parser.forms[0]
    attrs = form["attrs"]
    if attrs.get("action") not in (None, "") or attrs.get("method") not in (None, ""):
        raise ValueError("The ClerkBase sidebar form no longer follows the observed JavaScript POST route.")
    controls = form["controls"]
    named = [item for item in controls if item["kind"] == "input" and item["attrs"].get("name")]
    counts = {}
    for item in named:
        name = item["attrs"]["name"]
        counts[name] = counts.get(name, 0) + 1
    expected_counts = {
        "sm.IxId": 1, "sm.SearchRequest": 1, "sm.TreePath": len(_TREE_PATHS),
        "sm.SearchType": len(_SEARCH_TYPES), "sm.Near": 1, "sm.ExcludeEnabled": 2,
        "sm.ExcludeTerm": 1, "sm.IncludeSynopsis": 2, "sm.Stemming": 2,
        "sm.WordNetSynonyms": 2, "sm.Fuzzy": 2,
    }
    if counts != expected_counts:
        raise ValueError("The ClerkBase sidebar search fields changed from the observed public form.")
    values = {}
    for item in named:
        field = item["attrs"]
        values.setdefault(field["name"], []).append(field)
    if values["sm.IxId"][0].get("value") != _SITE or values["sm.SearchRequest"][0].get("value") != "":
        raise ValueError("The ClerkBase form belongs to a different site or has a prefilled query.")
    tree = values["sm.TreePath"]
    if {field.get("value") for field in tree} != _TREE_PATHS or any("checked" in field for field in tree):
        raise ValueError("The ClerkBase default document scope is no longer all public documents.")
    radio_values = {field.get("value") for field in values["sm.SearchType"]}
    selected_radio = [field.get("value") for field in values["sm.SearchType"] if "checked" in field]
    if radio_values != _SEARCH_TYPES or selected_radio != ["AllWords"]:
        raise ValueError("The ClerkBase public search type controls changed.")
    if values["sm.Near"][0].get("value") != "14" or values["sm.ExcludeTerm"][0].get("value") != "":
        raise ValueError("The ClerkBase public search default proximity or exclusion field changed.")
    for name, expected_checked in (("sm.ExcludeEnabled", False), ("sm.IncludeSynopsis", True),
                                   ("sm.Stemming", True), ("sm.WordNetSynonyms", False),
                                   ("sm.Fuzzy", False)):
        pair = values[name]
        if (pair[0].get("type") != "checkbox" or pair[0].get("value") != "true"
                or pair[1].get("type") != "hidden" or pair[1].get("value") != "false"
                or ("checked" in pair[0]) != expected_checked):
            raise ValueError("The ClerkBase public search option defaults changed.")
    selects = [item for item in controls if item["kind"] == "select"]
    if len(selects) != 1 or selects[0]["attrs"].get("name") != "sm.Fuzziness":
        raise ValueError("The ClerkBase fuzziness control changed.")
    options = selects[0]["options"]
    if ([option.get("value") for option in options] != list(map(str, range(7)))
            or [option.get("value") for option in options if "selected" in option] != ["4"]):
        raise ValueError("The ClerkBase fuzziness options or default changed.")
    pairs = []
    radio_added = False
    for item in controls:
        if item["kind"] == "select":
            pairs.append(("sm.Fuzziness", "4"))
            continue
        field = item["attrs"]
        name, kind = field.get("name"), field.get("type", "text").casefold()
        if not name or name == "sm.TreePath" or "disabled" in field:
            continue
        if name == "sm.SearchRequest":
            pairs.append((name, expression))
        elif name == "sm.SearchType":
            if not radio_added:
                pairs.append((name, search_type))
                radio_added = True
        elif kind in {"hidden", "text", "range"}:
            pairs.append((name, field.get("value", "")))
        elif kind == "checkbox":
            if "checked" in field:
                pairs.append((name, field.get("value", "on")))
        elif kind == "radio":
            continue
        else:
            raise ValueError("The ClerkBase sidebar contains an unsupported named control.")
    if not radio_added:
        raise ValueError("The ClerkBase public search form has no selectable search type.")
    return pairs


def _page_content(source, content, expression, page_num):
    rows, status = _search_rows(source, content)
    if status["empty"]:
        if status["empty_term"].casefold() != expression.casefold():
            raise ValueError("The ClerkBase empty-result response belongs to a different query.")
        return rows, status
    if status["search_word"].casefold() != expression.casefold():
        raise ValueError("The ClerkBase result page displays a different search expression.")
    expected_first = (page_num or 0) * status["page_size"]
    if status["first"] != expected_first:
        raise ValueError("The ClerkBase result counters do not match the requested page.")
    return rows, status
def _grant_binding(context):
    def selected(values):
        return None if values is None else sorted(values)
    return {"authorization": sorted(context.authorization),
            "allowed_operations": selected(context.allowed_operations),
            "allowed_namespaces": selected(context.allowed_namespaces)}


def native_search(engine, request, content, context, *, transport=None):
    """Search the configured South Kingstown public index, then match captured fields exactly."""
    if request.get("native") is not True:
        raise ValueError("ClerkBase native search requires native=true; saved captures use native=false.")
    source = configured_source(request["source"])
    site = _site_source(source)
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied",
            "Source namespace is not authorized."),), operation_id=context.operation_id)
    if source.provider != "clerkbase" or site != _SITE:
        raise ValueError("ClerkBase native search is limited to the observed South Kingstown site.")
    if content is not None or any(key in request for key in ("content_base64", "records", "bundle", "result")):
        raise ValueError("Native ClerkBase search retrieves public candidates; saved captures use native=false.")
    query = _query(request.get("query", {}))
    bounds = Bounds(**request.get("bounds", {}))
    lower = max(filter(None, (query.date_from, bounds.date_from)), default=None)
    upper = min(filter(None, (query.date_to, bounds.date_to)), default=None)
    if lower and upper and lower > upper:
        raise ValueError("The ClerkBase date range is empty after combining query and request bounds.")
    query = replace(query, date_from=lower, date_to=upper)
    if query.record_types and set(query.record_types) != {"document"}:
        raise ValueError("The observed ClerkBase result table exposes indexed documents only.")
    expressions = (*query.terms, *query.phrases)
    if not expressions:
        raise ValueError("ClerkBase native search requires at least one term or phrase.")
    expression = expressions[0]
    if len(expression.encode("utf-8")) > min(bounds.parser_bytes // 4, 4096):
        raise ValueError("The ClerkBase search expression exceeds the bounded form input.")
    search_type = "AllWords" if query.terms else "Phrase"
    binding = canonical_hash({"source": source.public_dict(), "namespace": namespace,
        "query": asdict(query), "caller_scope": context.scope, "current_grant": _grant_binding(context),
        "expression": expression, "search_type": search_type, "contract": "clerkbase-public-search/v1"})
    if bounds.checkpoint:
        queue, seen = _resume(bounds.checkpoint, binding)
        if len(queue) != 1:
            raise ValueError("ClerkBase search checkpoint must contain one page task.")
        task = queue[0]
        if set(task) - {"page_num", "offset", "sha256"}:
            raise ValueError("ClerkBase search checkpoint contains unsupported task fields.")
    else:
        task, seen = {"page_num": None, "offset": 0}, set()
    page_num = task.get("page_num")
    offset = task.get("offset", 0)
    if ((page_num is not None and (type(page_num) is not int or not 1 <= page_num <= _MAX_PAGE_NUMBER))
            or type(offset) is not int or not 0 <= offset <= bounds.parser_bytes):
        raise ValueError("ClerkBase search checkpoint position is outside its bound.")
    expected_sha = task.get("sha256")
    if expected_sha is not None and (not isinstance(expected_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None):
        raise ValueError("ClerkBase checkpoint page hash is invalid.")
    if offset and expected_sha is None:
        raise ValueError("A ClerkBase mid-page checkpoint must bind the captured response hash.")

    origin = _origin(source.url)
    search_url = _search_url(source)
    active_transport = transport or PublicTransport()
    deadline = monotonic() + bounds.deadline_seconds
    pages, records, bundles, captures, errors = 0, [], [], [], []
    page_counts, omitted_rows = [], 0
    next_task, query_window_exhausted = task, False
    cookie_jar = CookieJar()
    current = task
    try:
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", operation_id=context.operation_id)
        home = active_transport.request(source.url, method="GET", headers={"Accept": "text/html"},
            byte_limit=bounds.parser_bytes, deadline_seconds=max(0.001, deadline - monotonic()),
            allowed_origins=(origin,), allow_redirects=False)
        if (home.status != 200 or home.url != source.url or not isinstance(home.content, bytes)
                or len(home.content) > bounds.parser_bytes
                or home.content_type.split(";")[0].strip().casefold() != "text/html"):
            raise RetrievalError("clerkbase_home_unavailable", status=home.status)
        _cookies(cookie_jar, home, source.url)
        form_pairs = _form_pairs(source, home.content, expression, search_type)
        candidate_limit = bounds.max_records
        while next_task and pages < bounds.max_pages and len(records) < candidate_limit:
            if operation_cancelled(engine.storage, context):
                next_task = next_task or current
                break
            if monotonic() >= deadline:
                errors.append(Error("provider_deadline_exceeded", "The ClerkBase search deadline expired.",
                                    retryable=True, source=source.url))
                next_task = next_task or current
                break
            current, next_task = next_task, None
            page_num, page_offset = current["page_num"], current.get("offset", 0)
            pairs = list(form_pairs)
            if page_num is not None:
                pairs.append(("sm.pageNum", str(page_num)))
            body = urlencode(pairs).encode("ascii")
            if len(body) > bounds.parser_bytes:
                raise ValueError("The ClerkBase search form body exceeds its configured bound.")
            cookie_request = Request(search_url)
            cookie_jar.add_cookie_header(cookie_request)
            headers = {"Accept": "text/html", "Referer": source.url,
                       "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                       "X-Requested-With": "XMLHttpRequest"}
            if cookie_request.has_header("Cookie"):
                headers["Cookie"] = cookie_request.get_header("Cookie")
            response = active_transport.request(search_url, method="POST", body=body, headers=headers,
                byte_limit=bounds.parser_bytes, deadline_seconds=max(0.001, deadline - monotonic()),
                allowed_origins=(origin,), allow_redirects=False)
            if operation_cancelled(engine.storage, context):
                next_task = current
                break
            if (response.status != 200 or response.url != search_url or not isinstance(response.content, bytes)
                    or len(response.content) > bounds.parser_bytes
                    or response.content_type.split(";")[0].strip().casefold() != "text/html"):
                raise RetrievalError("clerkbase_search_unavailable", status=response.status)
            if monotonic() >= deadline:
                raise RetrievalError("provider_deadline_exceeded")
            _cookies(cookie_jar, response, search_url)
            digest = sha256(response.content).hexdigest()
            if current.get("sha256") and current["sha256"] != digest:
                raise ValueError("The resumed ClerkBase result page changed; restart the search.")
            rows, status = _page_content(source, response.content, expression, page_num)
            if status["empty"]:
                query_window_exhausted = True
            else:
                if page_offset > status["row_count"]:
                    raise ValueError("ClerkBase checkpoint offset is outside the captured result page.")
                if len(rows) < status["row_count"]:
                    omitted_rows += status["row_count"] - len(rows)
                page_counts.append({"requested_page_num": page_num, "first": status["first"],
                                    "last": status["last"], "page_size": status["page_size"],
                                    "total": status["total"]})
            bundle = mark_supplied_url_identities(make_bundle(source, namespace, response.content, FORMAT, rows))
            bundle["capture"]["retrieval_url"] = response.url
            if page_offset > len(bundle["records"]):
                raise ValueError("ClerkBase checkpoint offset is outside the mapped result rows.")
            selected = []
            for index in range(page_offset, len(bundle["records"])):
                if (operation_cancelled(engine.storage, context) or monotonic() >= deadline
                        or len(records) >= candidate_limit):
                    next_task = {"page_num": page_num, "offset": index, "sha256": digest}
                    if monotonic() >= deadline:
                        errors.append(Error("provider_deadline_exceeded", "The ClerkBase search deadline expired.",
                                            retryable=True, source=source.url))
                    break
                record = bundle["records"][index]
                key = source_identity_key(record["identity"])
                if key not in seen:
                    seen.add(key)
                    selected.append(record)
                    records.append(record)
            else:
                if not status["empty"] and status["next_page_num"] is not None:
                    next_task = {"page_num": status["next_page_num"], "offset": 0}
                elif status["empty"] or status["last"] + 1 == status["total"]:
                    query_window_exhausted = True
            bundle["records"] = selected
            bundles.append(bundle)
            captures.append(bundle["capture"])
            pages += 1
            context.report(operation="search", pages=pages, returned_records=len(records))
    except Exception as exc:
        code = exc.code if isinstance(exc, RetrievalError) else "provider_search_failed"
        errors.append(Error(code, "The ClerkBase public search page could not be retrieved or validated.",
                            retryable=True, source=source.url))
        if current is not None:
            next_task = current

    body_requested = query.body if query.body is not None else source.body
    coverage = {
        "sources": [{**source.public_dict(), "namespace": namespace}],
        "native_search": True,
        "scope": "South Kingstown public document-index candidates with exact local field matching",
        "provider_query_semantics": "public SearchType and source-index behavior; exact local AND over supplied metadata/snippets",
        "provider_search_expression": expression,
        "provider_search_type": search_type,
        "native_fields": list(_LOCAL_FIELDS),
        "searched_fields": list(_LOCAL_FIELDS),
        "search_snippets_only": True,
        "document_content_retrieved": False,
        "full_source_searched": False,
        "provider_page_counts": page_counts,
        "provider_result_total": page_counts[0]["total"] if page_counts else (0 if query_window_exhausted else None),
        "query_window_exhausted": bool(query_window_exhausted and not errors and not next_task),
        "catalog_complete": False,
        "source_complete": False,
        "status": "partial",
        "pages": pages,
        "unmapped_rows_omitted": omitted_rows,
        "body_filter": {"status": "unknown_retained" if body_requested else "not_requested",
                        "requested": body_requested, "applied": False},
        "checkpoint": _checkpoint(binding, [next_task], seen) if next_task else None,
    }
    if body_requested:
        coverage["limitations"] = ["The captured result exposes search snippets, not full document body text."]
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    if errors and not captures:
        return OperationResult("failed", errors=tuple(errors), coverage=coverage,
                              operation_id=context.operation_id)
    originals = {source_identity_key(record["identity"]): record for record in records}
    local = [{**deepcopy(record),
              "normalized": {key: record.get("normalized", {}).get(key) for key in _LOCAL_FIELDS
                             if record.get("normalized", {}).get(key) is not None},
              "text": [], "relationships": []} for record in records]
    local_query = replace(query, body=None)
    searched = search_records(local, local_query,
        bounds=replace(bounds, checkpoint=None, deadline_seconds=max(0.001, deadline - monotonic())),
        sources=coverage["sources"], inherited_coverage=coverage,
        context=context, storage=engine.storage)
    if searched.data is None or searched.status == "cancelled":
        return searched
    for hit in searched.data["hits"]:
        hit["record"] = originals[source_identity_key(hit["identity"])]
    envelope = {"records": records, "captures": captures, "bundles": bundles}
    return OperationResult("partial", {**searched.data, "bundle": envelope},
                           tuple(errors) + searched.errors, {**searched.coverage, **coverage},
                           context.operation_id)
