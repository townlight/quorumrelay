"""Public Peak archive search form and rendered results, with explicit partial coverage."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import re
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

from ..compat import ViewPublisherRows
from ..engine import canonical_hash
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, _origin
from .discovery import _checkpoint, _resume
from .identification import configured_source, validate_source, validate_url
from .native import make_bundle

FORMAT = "peak-public-search-html"


def _view(source):
    p = urlsplit(source.url)
    pairs = parse_qsl(p.query, keep_blank_values=True)
    if (source.provider != "peak" or p.scheme != "https" or not (p.hostname or "").endswith(".granicus.com")
            or p.path != "/ViewPublisher.php" or p.fragment or len(pairs) != 1
            or pairs[0][0] != "view_id" or not re.fullmatch(r"[1-9][0-9]{0,18}", pairs[0][1])):
        raise ValueError("Peak search requires an exact HTTPS ViewPublisher view source.")
    return pairs[0][1]


class _Results(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.depth = self.target = self.tables = self.hidden = 0
        self.group = None
        self.main = False
        self.cell = None
        self.groups = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "table":
            self.depth += 1
            if a.get("id") == "searchList":
                self.tables += 1
                self.target = self.depth
        if not self.target or self.hidden:
            return
        if tag == "tbody" and self.depth == self.target:
            if self.group is not None:
                raise ValueError("Search groups cannot overlap.")
            self.group = {"Name": "", "Date": "", "links": [], "excerpts": []}
        if self.group is None:
            return
        if tag == "tr" and self.depth == self.target:
            self.main = "listingRow" in a.get("class", "").split()
        if tag == "td":
            self.cell = ((a.get("headers") or "").split(" ", 1)[0] if self.main else
                         "excerpt" if "searchSubItem" in a.get("class", "").split() else None)
        if tag == "a" and self.main:
            href = a.get("href", "")
            player = ViewPublisherRows.PLAYER.search(a.get("onclick", "") or href)
            self.group["links"].append(player.group() if player else href)

    def handle_endtag(self, tag):
        if tag == "td":
            self.cell = None
        if tag == "tr" and self.depth == self.target:
            self.main = False
        if tag == "tbody" and self.depth == self.target and self.group is not None:
            self.groups.append(self.group)
            self.group = None
        if tag == "table":
            if self.target == self.depth:
                self.target = 0
            self.depth -= 1
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, value):
        if self.group is not None and not self.hidden:
            if self.cell in {"Name", "Date"}:
                self.group[self.cell] += value
            elif self.cell == "excerpt":
                self.group["excerpts"].append(value)


def search_rows(source, content):
    view = _view(source)
    text = content.decode("utf-8-sig", errors="strict")
    parser = _Results(text)
    if parser.tables != 1 or parser.group is not None:
        raise ValueError("Expected one complete Peak search result table.")
    pages = re.findall(r"\bpagination\.load\(\s*([0-9]+)\s*,\s*([0-9]+)\s*,\s*true\s*\)", text)
    if len(pages) != 1:
        raise ValueError("The selected result has no unambiguous declared page position/total.")
    current, total = map(int, pages[0])
    if not 1 <= current <= total <= 10000:
        raise ValueError("Search pagination is outside local bounds.")
    rows, omitted, seen = [], 0, set()
    for raw in parser.groups:
        title = " ".join(raw["Name"].split())
        date_text = " ".join(raw["Date"].split())
        if not title:
            omitted += 1
            continue
        day = datetime.strptime(date_text.split(" - ", 1)[0], "%B %d, %Y").date().isoformat()
        links, identities = [], set()
        for href in raw["links"]:
            url = urljoin(source.url, href)
            p = urlsplit(url)
            if p.path not in {"/AgendaViewer.php", "/MinutesViewer.php", "/MediaPlayer.php"}:
                continue
            validate_url(url)
            pairs = parse_qsl(p.query, keep_blank_values=True)
            q = dict(pairs)
            if (_origin(url) != _origin(source.url) or p.fragment or len(pairs) != 2
                    or set(q) != {"view_id", "clip_id"} or q["view_id"] != view
                    or not re.fullmatch(r"[1-9][0-9]{0,18}", q["clip_id"])):
                raise ValueError("Search viewer escaped its source view or lacks a literal clip identity.")
            identities.add(q["clip_id"])
            if url not in links:
                links.append(url)
        if not identities:
            omitted += 1
            continue
        if len(identities) != 1:
            raise ValueError("Search viewers disagree about their native clip identity.")
        identity = identities.pop()
        if identity in seen:
            raise ValueError("Search page repeats a native clip group.")
        seen.add(identity)
        documents = [{"kind": "agenda" if "/AgendaViewer.php?" in u else "minutes", "url": u}
                     for u in links if "/MediaPlayer.php?" not in u]
        players = [{"url": u} for u in links if "/MediaPlayer.php?" in u]
        rows.append(({"external_id": identity, "title": title, "meeting_date": day,
            "source_date": date_text, "time_zone_status": "unknown", "url": links[0],
            "documents": documents, "recordings": players,
            "search_excerpt": " ".join(" ".join(raw["excerpts"]).split())}, raw, "meeting"))
    if not rows:
        raise ValueError("No native-bound result groups; no complete empty result is inferred.")
    return rows, current, total, omitted


def parse_bundle(source, namespace, content):
    rows, page, total, omitted = search_rows(source, content)
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    bundle["extensions"]["peak_search"] = {"page": page, "declared_pages": total, "omitted_groups": omitted}
    return bundle


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    view = _view(source)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Search namespace is not authorized."),))
    if content is not None or any(k in request for k in ("content_base64", "records", "bundle", "result")):
        raise ValueError("Native search retrieves public results; saved captures use native=false.")
    bounds, query = Bounds(**request.get("bounds", {})), _query(request.get("query", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from, date_to=query.date_to or bounds.date_to)
    expressions = [*query.terms, *query.phrases]
    if (not expressions or not expressions[0].strip() or len(expressions[0]) > 255
            or len(expressions[0].encode()) > bounds.parser_bytes
            or any(ord(c) < 32 or ord(c) == 127 for c in expressions[0]) or source.body or query.body
            or query.record_types and set(query.record_types) != {"meeting"}):
        raise ValueError("Use a bounded term/phrase; only meeting groups with no inferred body field are mapped.")
    binding = canonical_hash({"source": source.public_dict(), "query": asdict(query), "scope": context.scope,
                              "contract": "peak-public-search/v1"})
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else ([{"page": 1, "offset": 0}], set())
    if (len(queue) != 1 or set(queue[0]) - {"page", "offset", "sha256"}
            or type(queue[0].get("page")) is not int or not 1 <= queue[0]["page"] <= 10000
            or type(queue[0].get("offset")) is not int or not 0 <= queue[0]["offset"] <= 10000):
        raise ValueError("Invalid Peak search continuation.")
    task = queue[0]
    fields = [("view_id", view), *[("types[" + k + "]", "on") for k in
              ("Clip", "AgendaItem", "AttachmentItem", "Note", "Vote,Motion")],
              ("keywords", expressions[0]), ("search_scope", "past")]
    if task["page"] > 1:
        fields.append(("pagenumber", str(task["page"])))
    url = _origin(source.url) + "/ViewSearchResults.php?" + urlencode(fields)
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
        "catalog_complete": False, "source_complete": False, "status": "partial", "pages": 0,
        "scope": "public archive meeting groups and rendered search excerpts; one provider page per call",
        "full_document_text_searched": False, "provider_query_semantics": "provider-defined first expression; exact local AND",
        "pagination": "declared page-number continuation; empty/inconsistent pages fail, never prove exhaustion"}
    deadline = monotonic() + bounds.deadline_seconds

    def stopped():
        if operation_cancelled(engine.storage, context):
            raise InterruptedError
        if monotonic() >= deadline:
            raise TimeoutError

    try:
        stopped()
        response = (transport or PublicTransport()).request(url, headers={"Accept": "text/html"},
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes), deadline_seconds=deadline-monotonic(),
            allowed_origins=(_origin(source.url),), allow_redirects=False)
        stopped()
        if (response.status != 200 or response.url != url or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)
                or response.content_type.split(";", 1)[0].strip().lower() != "text/html"):
            raise ValueError("The search response changed route/type or exceeded bounds.")
        rows, page, total, omitted = search_rows(source, response.content)
        stopped()
        digest = sha256(response.content).hexdigest()
        if page != task["page"] or task.get("sha256") and task["sha256"] != digest or task["offset"] > len(rows):
            raise ValueError("Search continuation changed; restart explicitly.")
        end = min(len(rows), task["offset"] + min(bounds.max_records, query.limit))
        selected = [row for row in rows[task["offset"]:end] if canonical_hash(row[0]["external_id"]) not in seen]
        seen.update(canonical_hash(row[0]["external_id"]) for row in selected)
        pending = ([{"page": page, "offset": end, "sha256": digest}] if end < len(rows) else
                   [{"page": page+1, "offset": 0}] if page < total else [])
        bundle = make_bundle(source, namespace, response.content, FORMAT, selected)
        bundle["capture"]["retrieval_url"] = url
        bundle["extensions"]["public_search_request"] = {"method": "GET", "url": url}
        for record in bundle["records"]:
            record["citation_urls"] = list(dict.fromkeys([*record["citation_urls"], url]))
            excerpt = record["normalized"]["search_excerpt"]
            if excerpt:
                record.setdefault("text", []).append({"field": "peak_search.group_excerpt", "text": excerpt,
                    "citation_url": url, "completeness": "partial",
                    "provenance": {"method": "vendor_rendered_search_group", "capture_sha256": digest}})
        coverage.update(pages=1, provider_page=page, declared_pages=total, provider_returned_rows=len(rows),
            unmapped_groups_omitted=omitted, checkpoint=_checkpoint(binding, pending, seen) if pending else None)
        result = search_records(deepcopy(bundle["records"]), query,
            bounds=replace(bounds, checkpoint=None, deadline_seconds=max(.001, deadline-monotonic())),
            sources=coverage["sources"], inherited_coverage=coverage, context=context, storage=engine.storage)
        stopped()
        if result.data is None:
            return result
        return OperationResult(result.status, {**result.data, "bundle": bundle}, result.errors,
                               {**result.coverage, **coverage}, context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    except (ValueError, TimeoutError):
        return OperationResult("failed", errors=(Error("provider_search_failed",
            "Peak results or continuation could not be verified; no empty completeness inferred."),),
            coverage=coverage, operation_id=context.operation_id)
