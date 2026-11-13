"""Repository v2 scoped search candidates and attributable context excerpts."""

import base64
import hashlib
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from time import monotonic
from urllib.parse import quote, urlencode, urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport
from .identification import configured_source, validate_source
from .repository import entry_bundle, repository_source
from .repository_export import run_task


def _literal(value):
    """Vendor syntax paper pp.4/6/14: literal quotes, wildcards and indexed strings."""
    value = value.replace("\\", "\\\\")
    for symbol in "[]?*~":
        value = value.replace(symbol, "\\" + symbol)
    return value.replace("'", "''").replace('"', '""')


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if not context.allows("search", namespace):
        raise ValueError("Repository source namespace is outside the caller's search grant.")
    if urlsplit(source.url).hostname != "api.laserfiche.com":
        return OperationResult.unsupported("native_search", reason=(
            "Repository search requires an explicit account API folder; no WebLink relationship is inferred."))
    _, parent_id, base = repository_source(source)
    if content is not None or any(key in request for key in ("records", "bundle", "result", "content_base64")):
        raise ValueError("Native search retrieves provider candidates; saved captures use local search.")
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    if source.body or query.body or query.date_from or query.date_to or bounds.date_from or bounds.date_to:
        return OperationResult.unsupported("native_search_filters", reason=(
            "Repository entry metadata does not establish meeting dates or governing bodies."))
    if bounds.checkpoint:
        raise ValueError("A Repository search task has no cross-call continuation cursor; retry with larger bounds.")
    if ((query.providers and source.provider not in query.providers)
            or (query.namespaces and namespace not in query.namespaces)):
        raise ValueError("Query provider/namespace filters must select the configured source.")
    expressions = [*query.terms, *query.phrases]
    if (not expressions or len(expressions) > 32
            or any(any(ord(char) < 32 or ord(char) == 127 for char in value) for value in expressions)
            or sum(len(value.encode()) for value in expressions) > min(4096, bounds.parser_bytes)):
        raise ValueError("Repository search needs bounded nonempty literal terms/phrases without control characters.")
    unavailable = sorted(set(query.record_types) - {"document", "folder", "shortcut"})
    if query.record_types and len(unavailable) == len(set(query.record_types)):
        return OperationResult.unsupported("native_search_types", reason="No requested Repository entry types are mapped.")
    size = source.options.get("page_size", 100)
    if type(size) is not int or not 1 <= size <= 150:
        raise ValueError("Repository page_size must be between 1 and 150.")
    token = context.credentials.get("laserfiche_token")
    if not isinstance(token, str) or not token or any(char in token for char in "\r\n\0"):
        raise ValueError("Repository native search requires a trusted repository.Read token.")
    # The provider obtains broad first-expression candidates. The shared local
    # matcher enforces exact terms/phrases over the metadata/excerpts actually obtained.
    command = ('({LF:Basic~="' + _literal(expressions[0]) + '",option="DFAN"}) & '
               '({LF:LookIn="' + str(parent_id) + '",Subfolders=N})')
    root = base.split("/Entries/", 1)[0]
    deadline = monotonic() + bounds.deadline_seconds
    records, bundles, failures, errors = [], [], [], []
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
        "scope": "one configured folder's direct children; available metadata and search context excerpts",
        "provider_query_semantics": "Basic first-expression candidates; exact local AND on available fields/excerpts",
        "catalog_complete": False, "source_complete": False, "full_document_text_searched": False,
        "snapshot_consistency": "one task result set; no atomic repository snapshot",
        "result_pages": 0, "context_pages": 0, "provider_candidates": 0,
        "truncated": False, "result_collection_complete": False, "failures": failures,
        "unavailable_record_types": unavailable}
    if unavailable:
        failures.append({"reason": "unavailable_record_types", "record_types": unavailable})

    def capture(response, block, input_format):
        return {"source_url": source.url, "retrieval_url": response.url,
                "input_format": input_format, "captured_at": datetime.now(timezone.utc).isoformat(),
                "sha256": hashlib.sha256(response.content).hexdigest(), "byte_length": len(response.content),
                "content_type": response.content_type,
                "content_base64": base64.b64encode(response.content).decode("ascii"), "original_values": block}

    def pages(url, read, *, limit, context_hits=False):
        offset, total, seen = 0, None, set()
        for _ in range(bounds.max_pages):
            if operation_cancelled(engine.storage, context):
                raise InterruptedError()
            count = min(size, limit - offset)
            if count <= 0:
                coverage["truncated"] = True
                return
            target = url + "?" + urlencode({"$top": count, "$skip": offset, "$count": "true"})
            block, response = read(target, raw=True)
            if operation_cancelled(engine.storage, context):
                raise InterruptedError()
            rows = block.get("value")
            if not isinstance(rows, list) or len(rows) > count:
                raise ValueError("Search collection exceeded its requested page size.")
            supplied_total = block.get("@odata.count")
            if supplied_total is not None:
                if type(supplied_total) is not int or supplied_total < offset + len(rows):
                    raise ValueError("Invalid search collection count.")
                if total is not None and total != supplied_total:
                    raise ValueError("Search collection count changed within its task.")
                total = supplied_total
            number_key = "hitNumber" if context_hits else "rowNumber"
            numbers = [row.get(number_key) if isinstance(row, dict) else None for row in rows]
            if any(type(number) is not int or number <= 0 or number in seen for number in numbers) or len(set(numbers)) != len(numbers):
                raise ValueError("Search collection repeated or omitted its supplied row identity.")
            seen.update(numbers)
            coverage["context_pages" if context_hits else "result_pages"] += 1
            yield block, response
            offset += len(rows)
            finished = offset == total if total is not None else len(rows) < count
            if finished:
                if not context_hits:
                    coverage["result_collection_complete"] = True
                return
            if not rows or len(rows) < count:
                raise ValueError("Search collection stopped before its declared end.")
        coverage["truncated"] = True

    def consume(result, task_id, read):
        result_url = root + "/Searches/" + quote(task_id, safe="") + "/Results"
        if result.get("uri") != result_url:
            raise ValueError("Search task result left its exact configured repository/task route.")
        seen_keys = set()
        for block, response in pages(result_url, read, limit=min(bounds.max_records, query.limit)):
            bundle = entry_bundle(source, namespace, response.content)
            bundle["capture"]["retrieval_url"] = response.url
            page_keys = [source_identity_key(row["identity"]) for row in bundle["records"]]
            if len(set(page_keys)) != len(page_keys) or seen_keys.intersection(page_keys):
                raise ValueError("Search results repeated a repository entry.")
            seen_keys.update(page_keys)
            bundles.append(bundle)
            bundle["captures"] = []
            for record in bundle["records"]:
                records.append(record)
                coverage["provider_candidates"] = len(records)
                segments = []
                try:
                    row_number = record["original"]["rowNumber"]
                    url = result_url + f"/{row_number}/ContextHits"
                    for hits, raw_response in pages(url, read, limit=bounds.max_records, context_hits=True):
                        saved = capture(raw_response, hits, "laserfiche-repository-search-context-json")
                        mapped = []
                        for hit in hits["value"]:
                            text = hit.get("context")
                            if not isinstance(text, str) or not isinstance(hit.get("hitType"), str):
                                raise ValueError("Search context is missing supplied text/type.")
                            page = hit.get("pageNumber")
                            if hit["hitType"] == "PageContent" and (type(page) is not int or page <= 0):
                                raise ValueError("Page-content context lacks a positive supplied page number.")
                            mapped.append({"field": "native_search.context", "text": text,
                                "citation_url": record["normalized"]["url"], "completeness": "partial",
                                **({"page": page} if hit["hitType"] == "PageContent" else {}),
                                "provenance": {"method": "provider_search_context", "capture_sha256": saved["sha256"],
                                    "hit_number": hit["hitNumber"], "row_number": row_number, "hit_type": hit["hitType"]}})
                        bundle["captures"].append(saved)
                        segments.extend(mapped)
                except InterruptedError:
                    raise
                except Exception:
                    failures.append({"reason": "search_context_unavailable", "external_id": record["identity"]["external_id"]})
                record["text"] = segments
                record["normalized"]["content_availability"] = "search_excerpts_only" if segments else "metadata_only"
                record["normalized"]["search_context_sha256"] = canonical_hash(segments)
                record["normalized_sha256"] = canonical_hash(record["normalized"])

    try:
        run_task(root, root + "/Searches/SearchAsync", "SearchEntry", {"searchCommand": command},
                 bounds, context, transport or PublicTransport(), deadline, coverage, consume,
                 cleanup_completed=True, coverage_key="search_task")
    except InterruptedError:
        coverage["cancelled"] = True
    except Exception:
        failures.append({"reason": "repository_search_failed"})
        errors.append(Error("repository_search_failed", "Repository search could not complete within its verified scope and bounds.",
                            source=source.url, retryable=True))
    matched = search_records(deepcopy(records), query,
        bounds=replace(bounds, deadline_seconds=max(.001, deadline - monotonic())), sources=coverage["sources"],
        inherited_coverage=coverage, context=context, storage=engine.storage)
    status = "cancelled" if coverage.get("cancelled") or matched.status == "cancelled" else "failed" if failures and not bundles else "partial"
    captures = [capture for bundle in bundles for capture in bundle.get("captures", [])]
    return OperationResult(status, {**(matched.data or {}), "records": records, "bundles": bundles,
                                   "captures": captures},
                           tuple(errors) + matched.errors, {**matched.coverage, "scope": coverage["scope"]}, context.operation_id)
