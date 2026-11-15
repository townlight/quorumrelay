"""Anonymous BoardBook search-index entries; no inferred canonical parent IDs."""
from dataclasses import asdict, replace
from hashlib import sha256
from html.parser import HTMLParser
import re
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

from ..engine import canonical_hash
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, _origin
from .discovery import _checkpoint, _resume
from .identification import configured_source, validate_source
from .native import make_bundle

FORMAT = "boardbook-public-search-html"
HOST = "https://meetings.boardbook.org"
INDEXES = {"sparqmeetingsagendaitems", "sparqmeetingsagendaitemtexts",
           "sparqmeetingsagendaitemactions", "sparqmeetingsdocuments"}


def _organization(source):
    p = urlsplit(source.url)
    match = re.fullmatch(r"/Public/Organization/([1-9][0-9]{0,18})", p.path)
    if source.provider != "boardbook" or _origin(source.url) != HOST or p.query or p.fragment or not match:
        raise ValueError("BoardBook search requires an exact HTTPS public organization source.")
    return match[1]


class _Results(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.depth = self.target = self.targets = self.li = self.hidden = 0
        self.current = None
        self.link = False
        self.rows = []
        self.feed(content.decode("utf-8-sig", errors="strict"))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "div":
            self.depth += 1
            if a.get("id") == "SearchResults":
                self.target = self.depth
                self.targets += 1
        if not self.target or self.hidden:
            return
        if tag == "li":
            self.li += 1
            if self.li == 1:
                self.current = {"title": [], "excerpt": [], "hrefs": []}
        if self.current is None:
            return
        if tag == "a":
            self.link = True
            self.current["hrefs"].append(a.get("href", ""))
        if tag == "br":
            self.current["title" if self.link else "excerpt"].append(" ")

    def handle_endtag(self, tag):
        if tag == "a":
            self.link = False
        if tag == "li" and self.target:
            if self.li == 1 and self.current is not None:
                self.rows.append(self.current)
                self.current = None
            self.li -= 1
        if tag == "div":
            if self.depth == self.target:
                self.target = 0
            self.depth -= 1
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, text):
        if self.current is not None and not self.hidden:
            self.current["title" if self.link else "excerpt"].append(text)


def parse_bundle(source, namespace, content):
    organization = _organization(source)
    parsed = _Results(content)
    if parsed.targets != 1 or parsed.target or parsed.current is not None or not parsed.rows:
        raise ValueError("No complete nonempty BoardBook result container; empty completeness is not inferred.")
    rows, seen = [], set()
    for raw in parsed.rows:
        if len(raw["hrefs"]) != 1:
            raise ValueError("Search entry lacks one native locator.")
        url = urljoin(source.url, raw["hrefs"][0])
        p = urlsplit(url)
        m = re.fullmatch(r"/Search/GoToResult/([A-Za-z0-9-]{1,80})", p.path)
        pairs = parse_qsl(p.query, keep_blank_values=True)
        q = dict(pairs)
        if (_origin(url) != HOST or p.username or p.password or p.fragment or not m or len(pairs) != len(q)
                or set(q) - {"Index", "PublicOrgID", "returnUrl"}
                or q.get("PublicOrgID") != organization or q.get("Index") not in INDEXES):
            raise ValueError("Search locator lacks a supported native index/organization binding.")
        identity = q["Index"] + ":" + m[1]
        title = " ".join(" ".join(raw["title"]).split())
        if identity in seen or not title:
            raise ValueError("Duplicate or untitled native search entry.")
        seen.add(identity)
        # Drop navigation returnUrl from the durable citation, never follow it.
        citation = HOST + p.path + "?" + urlencode({"Index": q["Index"], "PublicOrgID": organization})
        rows.append(({"external_id": identity, "title": title, "url": citation,
            "search_index": q["Index"], "search_index_id": m[1],
            "search_excerpt": " ".join(" ".join(raw["excerpt"]).split()),
            "parent_identity_status": "not_supplied", "time_zone_status": "unknown",
            "canonical_record_identity_status": "not_established_by_search_index"}, raw, "search_result"))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    for record in bundle["records"]:
        record["identity"].update(derivation="vendor_search_index_locator",
            stability="Index and native ID identify this search entry; canonical meeting/item equivalence is not established.")
        record["text"] = [{"field": "boardbook_search.excerpt", "text": record["normalized"]["search_excerpt"],
            "citation_url": record["normalized"]["url"], "completeness": "partial",
            "provenance": {"method": "vendor_rendered_search_excerpt", "capture_sha256": sha256(content).hexdigest()}}]
    return bundle


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    organization = _organization(source)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Search namespace is not authorized."),))
    if content is not None or any(k in request for k in ("content_base64", "records", "bundle", "result")):
        raise ValueError("Saved search captures require native=false.")
    bounds, query = Bounds(**request.get("bounds", {})), _query(request.get("query", {}))
    expressions = [*query.terms, *query.phrases]
    if (not expressions or not expressions[0].strip() or len(expressions[0]) > 255
            or any(ord(c) < 32 or ord(c) == 127 or c in "<>" for c in expressions[0])
            or source.body or query.body or query.date_from or query.date_to or bounds.date_from or bounds.date_to
            or query.record_types and set(query.record_types) != {"search_result"}):
        raise ValueError("Use a bounded search expression; canonical record types, body and date semantics are not inferred.")
    binding = canonical_hash({"source": source.public_dict(), "query": asdict(query),
                              "scope": context.scope, "contract": "boardbook-search/v1"})
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else ([{"offset": 0}], set())
    if (len(queue) != 1 or set(queue[0]) - {"offset", "sha256"}
            or type(queue[0].get("offset")) is not int or not 0 <= queue[0]["offset"] <= 100000):
        raise ValueError("Invalid BoardBook search continuation.")
    task = queue[0]
    url = HOST + "/Search/Index/" + organization + "?" + urlencode({"q": expressions[0]})
    coverage = {"native_search": True, "sources": [{**source.public_dict(), "namespace": namespace}],
        "source_complete": False, "catalog_complete": False, "status": "partial",
        "scope": "rendered public search-index entries/excerpts; no canonical parent identity inferred",
        "provider_query_semantics": "provider-defined first expression; exact local AND",
        "pagination": "local offset in one hash-bound capture; provider truncation/exhaustion unverified",
        "full_document_text_searched": False, "pages": 0}
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
            allowed_origins=(HOST,), allow_redirects=False)
        stopped()
        if (response.status != 200 or response.url != url or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)
                or response.content_type.split(";", 1)[0].strip().lower() != "text/html"):
            raise ValueError("Search response changed route/type or exceeded bounds.")
        bundle = parse_bundle(source, namespace, response.content)
        stopped()
        digest = sha256(response.content).hexdigest()
        rows = bundle["records"]
        if task.get("sha256") and task["sha256"] != digest or task["offset"] > len(rows):
            raise ValueError("Search result changed; restart explicitly.")
        end = min(len(rows), task["offset"] + min(bounds.max_records, query.limit))
        selected = [r for r in rows[task["offset"]:end] if canonical_hash(r["identity"]["external_id"]) not in seen]
        seen.update(canonical_hash(r["identity"]["external_id"]) for r in selected)
        bundle["records"] = selected
        bundle["capture"]["retrieval_url"] = url
        bundle["extensions"]["public_search_request"] = {"method": "GET", "url": url}
        coverage.update(pages=1, provider_returned_rows=len(rows),
            checkpoint=_checkpoint(binding, [{"offset": end, "sha256": digest}], seen) if end < len(rows) else None)
        result = search_records(selected, query,
            bounds=replace(bounds, checkpoint=None, deadline_seconds=max(.001, deadline-monotonic())), sources=coverage["sources"],
            inherited_coverage=coverage, context=context, storage=engine.storage)
        stopped()
        if result.data is None:
            return result
        return OperationResult(result.status, {**result.data, "bundle": bundle}, result.errors,
            {**result.coverage, **coverage}, context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    except (ValueError, TimeoutError):
        return OperationResult("failed", errors=(Error("provider_search_failed",
            "BoardBook search result could not be verified; no empty completeness inferred."),),
            coverage=coverage, operation_id=context.operation_id)
