"""Pinned public search with capture-bound numeric identities, never guessed aliases."""

import base64
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from html.parser import HTMLParser
import json
from time import monotonic
from urllib.parse import urlencode

from ..engine import source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .boardable import API_ORIGIN, FORMAT, SITE_ORIGIN, _site_id, _source_slug
from .contracts import PublicTransport
from .identification import configured_source, validate_source
from .native import make_bundle, parse_native


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.hidden += 1
        elif tag in {"br", "p", "div"} and not self.hidden:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def _known(engine, source, namespace, context, bounds, deadline):
    """Only exact original listing bytes can supply a numeric identity for a slug."""
    found, visited = {}, 0
    if engine.storage is None:
        return found
    for stored in engine.storage.list("captures", scope=context.scope):
        if operation_cancelled(engine.storage, context) or monotonic() >= deadline or visited >= bounds.max_records:
            break
        capture = stored.value
        if capture.get("source_url") != source.url or capture.get("input_format") != FORMAT:
            continue
        visited += 1
        encoded, digest = capture.get("content_base64"), capture.get("sha256")
        if not isinstance(encoded, str) or len(encoded) > 4 * ((bounds.parser_bytes + 2) // 3):
            continue
        try:
            content = base64.b64decode(encoded, validate=True)
            if (len(content) > bounds.parser_bytes or capture.get("byte_length") != len(content)
                    or sha256(content).hexdigest() != digest):
                continue
            bundle = parse_native(source, namespace, content, FORMAT)
            for record in bundle["records"]:
                url = record["normalized"]["url"]
                identity = record["identity"]["external_id"]
                found.setdefault(url, {})[identity] = {"record": record, "capture": capture}
        except (ValueError, TypeError, KeyError):
            continue
    return {url: next(iter(rows.values())) for url, rows in found.items() if len(rows) == 1}


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    slug = _source_slug(source)
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "The source namespace is not authorized."),))
    if request.get("native") is not True or content is not None or any(k in request for k in (
            "content_base64", "records", "bundle", "result")):
        raise ValueError("Use native=true for Boardable provider search; saved captures use local search.")
    bounds = Bounds(**request.get("bounds", {}))
    if bounds.checkpoint:
        raise ValueError("The published client has no verified paging contract; no Boardable search cursor is inferred.")
    query = _query(request.get("query", {}))
    query = replace(query, date_from=query.date_from or bounds.date_from, date_to=query.date_to or bounds.date_to)
    expressions = [*query.terms, *query.phrases]
    if not expressions or len(expressions[0].encode()) > min(bounds.parser_bytes, 4096):
        raise ValueError("A nonempty bounded first term or phrase is required for provider candidates.")
    if source.body or query.body or (query.record_types and set(query.record_types) != {"meeting"}):
        raise ValueError("The mapped Boardable search covers meetings without an inferred body filter.")
    year = query.date_from[:4] if query.date_from and query.date_to and query.date_from[:4] == query.date_to[:4] else ""
    month = (str(int(query.date_from[5:7])) if year and query.date_from[:7] == query.date_to[:7] else "")
    url = API_ORIGIN + "/api/public-sites/search?" + urlencode({
        "query": expressions[0], "year": year, "month": month, "type": "meetings"})
    deadline = monotonic() + bounds.deadline_seconds
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
                "catalog_complete": False, "source_complete": False, "status": "partial", "pages": 0,
                "provider_query_semantics": "first expression supplies candidates; exact local matching uses supplied text only",
                "pagination": "not established by pinned client; no total/terminal condition inferred",
                "identity_resolution": "exact URL match to same-source scope-bound listing capture; no new slug IDs",
                "date_filter_basis": "captured listing date, not an independently returned search date",
                "failures": []}
    active = transport or PublicTransport()
    bundles, captures, candidates, records, errors = [], [], [], [], []

    def get(target, media_type, headers, origin):
        if operation_cancelled(engine.storage, context):
            raise InterruptedError()
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise TimeoutError()
        response = active.request(target, headers=headers, byte_limit=bounds.parser_bytes,
            deadline_seconds=seconds, allowed_origins=(origin,), allow_redirects=False)
        if operation_cancelled(engine.storage, context):
            raise InterruptedError()
        if (monotonic() >= deadline or response.status != 200 or response.url != target
                or response.content_type.split(";", 1)[0].strip().lower() != media_type
                or len(response.content) > bounds.parser_bytes):
            raise ValueError("The search response is outside the exact bounded contract.")
        return response

    try:
        if bounds.max_pages < 1:
            raise ValueError("A search page budget is required.")
        landing = get(source.url, "text/html", {"Accept": "text/html"}, SITE_ORIGIN)
        site_id = _site_id(landing.content, slug)
        response = get(url, "application/json", {"Accept": "application/json", "SiteId": str(site_id)}, API_ORIGIN)
        raw_bundle = make_bundle(source, namespace, response.content, "boardable-public-search-json", [])
        raw_bundle["capture"]["retrieval_url"] = url
        bundles, captures = [raw_bundle], [raw_bundle["capture"]]
        payload = json.loads(response.content)
        if not isinstance(payload, dict) or not isinstance(payload.get("meetings"), list):
            raise ValueError("The client-declared meetings array is missing.")
        lookup = _known(engine, source, namespace, context, bounds, deadline)
        seen, rows, proofs = set(), [], []
        for raw in payload["meetings"][:bounds.max_records]:
            if operation_cancelled(engine.storage, context):
                raise InterruptedError()
            if monotonic() >= deadline:
                raise TimeoutError()
            if (not isinstance(raw, dict) or not isinstance(raw.get("title"), str) or not raw["title"].strip()
                    or not isinstance(raw.get("slug"), str)):
                raise ValueError("A search candidate lacks the client-declared title or slug.")
            from .boardable import _SLUG
            if not _SLUG.fullmatch(raw["slug"]) or raw["slug"] in seen:
                raise ValueError("A search candidate has an unsafe or repeated slug.")
            seen.add(raw["slug"])
            target = SITE_ORIGIN + "/" + slug + "/meetings/" + raw["slug"]
            candidates.append({"url": target, "title": raw["title"], "original": deepcopy(raw)})
            known = lookup.get(target)
            if known is None:
                coverage["failures"].append({"url": target, "reason": "numeric_identity_not_bound_to_listing_capture"})
                continue
            original = known["record"]
            normalized = {"external_id": original["identity"]["external_id"], "title": raw["title"], "url": target,
                          "meeting_date": original["normalized"].get("meeting_date"),
                          "date_provenance": {"source": "stored_listing", "capture_sha256": known["capture"]["sha256"]}}
            rows.append((normalized, raw, "meeting"))
            proofs.append(known["capture"])
        bundle = make_bundle(source, namespace, response.content, "boardable-public-search-json", rows)
        bundle["capture"]["retrieval_url"] = url
        for record, proof in zip(bundle["records"], proofs):
            record.setdefault("extensions", {})["listing_identity_capture"] = proof["sha256"]
            raw = record["original"]
            highlights = raw.get("search_highlight")
            if isinstance(highlights, dict):
                for field in ("agenda", "minutes"):
                    value = highlights.get(field)
                    if isinstance(value, str):
                        parser = _Text()
                        parser.feed(value)
                        text = "".join(parser.parts)
                        record.setdefault("text", []).append({"field": "search_highlight." + field, "text": text,
                            "citation_url": record["normalized"]["url"], "completeness": "partial",
                            "provenance": {"method": "vendor_search_highlight", "capture_sha256": bundle["capture"]["sha256"]}})
            matches = raw.get("attachment_matches")
            if isinstance(matches, list):
                for index, match in enumerate(matches[:bounds.max_records]):
                    if not isinstance(match, dict) or not isinstance(match.get("context"), str):
                        continue
                    parser = _Text()
                    parser.feed(match["context"])
                    record.setdefault("text", []).append({"field": f"attachment_matches[{index}].context",
                        "text": "".join(parser.parts), "citation_url": record["normalized"]["url"],
                        "completeness": "partial", "provenance": {"method": "vendor_attachment_search_context",
                            "capture_sha256": bundle["capture"]["sha256"], "supplied_attachment_id": match.get("id")}})
        records = bundle["records"]
        bundles = [bundle]
        captures = [bundle["capture"], *{c["sha256"]: c for c in proofs}.values()]
        coverage.update(pages=1, returned_candidates=len(candidates), resolved_records=len(records),
                        truncated=len(payload["meetings"]) > bounds.max_records, checkpoint=None,
                        unmapped_policy_results=bool(payload.get("policy_items")))
        context.report(operation="search", pages=1, returned_records=len(records))
    except InterruptedError:
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    except Exception:
        errors.append(Error("provider_search_failed", "The Boardable search could not be retrieved or mapped.", retryable=True, source=source.url))
        coverage["failures"].append({"reason": "provider_search_failed"})
        return OperationResult("failed", {"candidates": candidates, "bundle": {"records": [], "captures": captures, "bundles": bundles}}, errors=tuple(errors), coverage=coverage, operation_id=context.operation_id)
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    originals = {source_identity_key(r["identity"]): r for r in records}
    local = [{**deepcopy(r), "normalized": {k: r["normalized"].get(k) for k in ("title", "meeting_date")}}
             for r in records]
    searched = search_records(local, query, bounds=replace(bounds, checkpoint=None,
        deadline_seconds=max(.001, deadline - monotonic())), sources=coverage["sources"],
        inherited_coverage=coverage, context=context, storage=engine.storage)
    if searched.status == "cancelled":
        return searched
    if searched.data:
        for hit in searched.data["hits"]:
            hit["record"] = originals[source_identity_key(hit["identity"])]
        searched.data["records"] = [h["record"] for h in searched.data["hits"]]
    return OperationResult("partial", {**(searched.data or {}), "candidates": candidates,
        "bundle": {"records": records, "captures": captures, "bundles": bundles}},
        searched.errors, {**searched.coverage, **coverage, "failures": searched.coverage.get("failures", []),
            "truncated": bool(coverage.get("truncated") or searched.coverage.get("truncated"))}, context.operation_id)
