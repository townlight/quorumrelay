"""Public TelVue player-wide keyword candidates, with explicit metadata-only coverage."""
from dataclasses import asdict, replace
from datetime import datetime
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

HOST = "https://videoplayer.telvue.com"
FORMAT = "telvue-public-search-html"


def _player(source):
    p = urlsplit(source.url)
    m = re.fullmatch(r"/player/([A-Za-z0-9_-]{1,100})/videos", p.path)
    if source.provider != "telvue" or _origin(source.url) != HOST or p.query or p.fragment or not m:
        raise ValueError("Use an explicit HTTPS TelVue player /videos source; playlist scope is not silently broadened.")
    return m[1]


class Results(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.depth = self.container = self.row_depth = self.summary = 0
        self.totals, self.rows = [], []
        self.row = None
        self.slot = None
        self.hidden = 0
        self.feed(content.decode("utf-8-sig", errors="strict"))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in {"script", "style", "template"}:
            self.hidden += 1
        classes = set(a.get("class", "").split())
        if tag == "div":
            self.depth += 1
            if "video-rows-container" in classes:
                if self.container:
                    raise ValueError("Overlapping video containers.")
                self.container = self.depth
                self.totals.append(a.get("data-total-available-count", ""))
            if self.container and "video-item-container" in classes:
                if self.row is not None:
                    raise ValueError("Overlapping video entries.")
                self.row_depth = self.depth
                self.row = {"id": a.get("data-video-id", ""), "type": a.get("data-video-type", ""),
                            "title": [], "summary": [], "duration": [], "hrefs": []}
            if self.row is not None and "summary" in classes:
                self.summary = self.depth
        if self.row is not None:
            if tag == "a":
                self.row["hrefs"].append(a.get("href", ""))
            if tag == "span":
                self.slot = "title" if {"h4", "title", "block"} <= classes else "duration" if "duration" in classes else None

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "span":
            self.slot = None
        if tag == "div":
            if self.depth == self.summary:
                self.summary = 0
            if self.depth == self.row_depth and self.row is not None:
                self.rows.append(self.row)
                self.row = None
                self.row_depth = 0
            if self.depth == self.container:
                self.container = 0
            self.depth -= 1

    def handle_data(self, text):
        if self.row is not None and not self.hidden:
            if self.slot:
                self.row[self.slot].append(text)
            elif self.summary:
                self.row["summary"].append(text)


def parse_bundle(source, namespace, content):
    player = _player(source)
    parsed = Results(content)
    if (len(parsed.totals) != 1 or not re.fullmatch(r"[0-9]{1,6}", parsed.totals[0])
            or parsed.container or parsed.row is not None or not parsed.rows):
        raise ValueError("No complete nonempty TelVue result container; no complete empty result inferred.")
    total = int(parsed.totals[0])
    if not len(parsed.rows) <= total <= 100000:
        raise ValueError("Inconsistent declared search total.")
    rows, seen = [], set()
    for raw in parsed.rows:
        identity = raw["id"]
        if raw["type"] != "media" or not re.fullmatch(r"[1-9][0-9]{0,18}", identity) or identity in seen:
            raise ValueError("Duplicate, invalid or unsupported native media entry.")
        seen.add(identity)
        locators = set()
        for href in raw["hrefs"]:
            url = urljoin(source.url, href)
            p = urlsplit(url)
            pairs = parse_qsl(p.query, keep_blank_values=True)
            q = dict(pairs)
            if (_origin(url) != HOST or p.username or p.password or p.fragment
                    or p.path != f"/player/{player}/videos/search/{identity}" or len(pairs) != len(q)
                    or set(q) != {"highlight", "terms", "vid_type", "showtabssearch", "fullscreen"}
                    or q["vid_type"] != "medium" or q["highlight"] != "on" or not q["terms"]
                    or q["showtabssearch"] != "true" or q["fullscreen"] != "false"):
                raise ValueError("Search locator escaped its native player/media binding.")
            locators.add(url)
        title = " ".join(" ".join(raw["title"]).split())
        if len(locators) != 1 or not title:
            raise ValueError("Media entry lacks one unambiguous native locator/title.")
        url = locators.pop()
        value = {"external_id": identity, "title": title,
                 "description": " ".join(" ".join(raw["summary"]).split()),
                 "source_duration_display": " ".join(" ".join(raw["duration"]).split()),
                 "time_zone_status": "unknown", "caption_text_availability": "not_retrieved"}
        date = re.search(r"([A-Za-z]+ [0-9]{1,2}, [0-9]{4})$", title)
        if date:
            for pattern in ("%B %d, %Y", "%b %d, %Y"):
                try:
                    value["meeting_date"] = datetime.strptime(date[1], pattern).date().isoformat()
                    value["date_derivation"] = "calendar_date_in_supplied_title"
                    break
                except ValueError:
                    continue
        rows.append((value, raw, "recording"))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    bundle["extensions"]["telvue_search"] = {"declared_total": total, "caption_chapter_match_metadata": "not_requested"}
    for record in bundle["records"]:
        # Search-result links echo the query. Preserve them as citations and
        # relationships, outside searchable metadata, to avoid false matches
        # both now and after storage/reopening.
        locator = urljoin(source.url, record["original"]["hrefs"][0])
        record["citation_urls"].append(locator)
        record["relationships"].append({"relation": "recording", "value": {
            "url": locator, "availability": "supplied_public_search_locator_not_media_bytes"}})
        if record["normalized"]["description"]:
            record["text"] = [{"field": "telvue_search.summary", "text": record["normalized"]["description"],
                "citation_url": locator, "completeness": "partial",
                "provenance": {"method": "vendor_rendered_media_summary", "capture_sha256": sha256(content).hexdigest()}}]
    return bundle


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    player = _player(source)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Search namespace is not authorized."),))
    if content is not None or any(k in request for k in ("content_base64", "records", "bundle", "result")):
        raise ValueError("Saved search captures require native=false.")
    bounds, query = Bounds(**request.get("bounds", {})), _query(request.get("query", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from, date_to=query.date_to or bounds.date_to)
    expressions = [*query.terms, *query.phrases]
    if (not expressions or not expressions[0].strip() or len(expressions[0]) > 255
            or any(ord(c) < 32 or ord(c) == 127 or c in "<>" for c in expressions[0])
            or source.body or query.body
            or query.record_types and set(query.record_types) != {"recording"}):
        raise ValueError("Use a bounded search expression; only supplied recording metadata is searched and body is unavailable.")
    binding = canonical_hash({"source": source.public_dict(), "query": asdict(query),
                              "scope": context.scope, "contract": "telvue-public-search/v1"})
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else ([{"offset": 0}], set())
    if (len(queue) != 1 or set(queue[0]) - {"offset", "sha256"}
            or type(queue[0].get("offset")) is not int or not 0 <= queue[0]["offset"] <= 100000):
        raise ValueError("Invalid TelVue search continuation.")
    task = queue[0]
    url = HOST + "/player/" + player + "/videos/search?" + urlencode({"showtabssearch": "true", "fullscreen": "false", "search": expressions[0]})
    coverage = {"native_search": True, "sources": [{**source.public_dict(), "namespace": namespace}],
        "source_complete": False, "catalog_complete": False, "status": "partial",
        "scope": "player-wide public media candidates; supplied title/summary metadata, not caption/chapter/full-document text",
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
        if any(dict(parse_qsl(urlsplit(row["original"]["hrefs"][0]).query))["terms"] != expressions[0]
               for row in bundle["records"]):
            raise ValueError("Search result locators do not match the requested expression.")
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
            provider_declared_total=bundle["extensions"]["telvue_search"]["declared_total"],
            provider_remaining_unretrieved=bundle["extensions"]["telvue_search"]["declared_total"]-len(rows),
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
            "TelVue search result could not be verified; no empty completeness inferred."),),
            coverage=coverage, operation_id=context.operation_id)
