"""Portable exact local search over normalized metadata and supplied evidence."""

from __future__ import annotations

import re
import time
import base64
from copy import deepcopy
from dataclasses import asdict
from datetime import date
from html.parser import HTMLParser
from io import BytesIO

from .models import Bounds, Error, OperationResult, Query, Source
from .storage import operation_cancelled, tracked_handler


def extract_text_segments(content: bytes, *, media_type: str, citation_url: str,
                          bounds: Bounds | None = None, context=None) -> OperationResult:
    """Bounded extraction of supplied text, never OCR or transcription.

    The caller/provider owns capture-to-record association. Whole-listing text
    must not be attached to each meeting. Segments explicitly state whole-capture
    scope; only an evidenced document/detail mapping may narrow that scope.
    """
    from .models import OperationContext

    bounds, context = bounds or Bounds(), context or OperationContext()
    coverage = {"sources": [{"url": citation_url}], "available_text": [],
                "failures": [], "truncated": False, "pages": 0,
                "scope": "whole_capture", "extraction": "supplied_text_only_no_ocr_asr"}
    if not isinstance(content, bytes) or len(content) > bounds.parser_bytes:
        return OperationResult("failed", errors=(Error("parser_limit", "Text extraction exceeds parser input limit."),),
                               coverage={**coverage, "failures": ["parser_limit"]})
    started = time.monotonic()
    segments, extracted_bytes = [], 0
    digest = __import__("hashlib").sha256(content).hexdigest()
    def add(text, field, page=None):
        nonlocal extracted_bytes
        if not text or not text.strip():
            return
        data = text.encode("utf-8")
        remaining = bounds.parser_bytes - extracted_bytes
        if len(data) > remaining:
            text = data[:remaining].decode("utf-8", errors="ignore")
            coverage["truncated"] = True
        extracted_bytes += len(text.encode("utf-8"))
        segments.append({
            "field": field, "text": text, "citation_url": citation_url,
            **({"page": page} if page is not None else {}),
            "provenance": {"method": "supplied_text_extraction", "media_type": media_type,
                           "scope": "whole_capture", "capture_sha256": digest},
            "completeness": "truncated" if coverage["truncated"] else "complete",
        })
    if context.check_cancelled():
        return OperationResult("cancelled", data={"segments": []}, coverage=coverage)
    try:
        if media_type in {"text/html", "application/xhtml+xml"}:
            class VisibleText(HTMLParser):
                def __init__(self):
                    super().__init__(convert_charrefs=True)
                    self.hidden = 0
                    self.parts = []
                def handle_starttag(self, tag, attrs):
                    if tag in {"script", "style", "template"}:
                        self.hidden += 1
                    if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3"} and not self.hidden:
                        self.parts.append("\n")
                def handle_endtag(self, tag):
                    if tag in {"script", "style", "template"}:
                        self.hidden = max(0, self.hidden - 1)
                    if tag in {"p", "div", "li", "tr"} and not self.hidden:
                        self.parts.append("\n")
                def handle_data(self, data):
                    if not self.hidden:
                        self.parts.append(data)
            parser = VisibleText()
            parser.feed(content.decode("utf-8-sig", errors="strict"))
            add("".join(parser.parts), "capture.html_text")
            coverage["pages"] = 1
        elif media_type == "application/pdf":
            import pdfplumber
            with pdfplumber.open(BytesIO(content)) as document:
                coverage["total_pages"] = len(document.pages)
                for index, page in enumerate(document.pages, start=1):
                    if context.check_cancelled():
                        return OperationResult("cancelled", data={"segments": segments}, coverage=coverage)
                    if (index > bounds.max_pages or time.monotonic() - started > bounds.deadline_seconds
                            or extracted_bytes >= bounds.parser_bytes):
                        coverage["truncated"] = True
                        break
                    coverage["pages"] += 1
                    try:
                        text = page.extract_text() or ""
                        if text.strip():
                            add(text, "capture.pdf_text", index)
                        else:
                            coverage["failures"].append({"page": index, "reason": "no_supplied_text_unreadable_or_scanned"})
                    except Exception:
                        coverage["failures"].append({"page": index, "reason": "pdf_text_extraction_failed"})
        elif media_type.startswith("text/"):
            add(content.decode("utf-8-sig", errors="strict"), "capture.text")
            coverage["pages"] = 1
        else:
            return OperationResult.unsupported("text_extraction", reason="No supplied-text extractor for this media type.")
    except Exception:
        coverage["failures"].append({"reason": "unreadable_capture"})
    if time.monotonic() - started > bounds.deadline_seconds:
        coverage["truncated"] = True
        coverage["failures"].append({"reason": "extraction_deadline_exceeded"})
    coverage["available_text"] = [{"field": s["field"], "page": s.get("page")} for s in segments]
    coverage["text_bytes"] = extracted_bytes
    if not segments:
        coverage["failures"].append({"reason": "no_supplied_text"})
    partial = bool(coverage["failures"] or coverage["truncated"])
    return OperationResult("partial" if partial else "completed", data={"segments": segments},
                           coverage=coverage, operation_id=context.operation_id)


def _strings(value, path="normalized"):
    if isinstance(value, str):
        yield {"field": path, "text": value, "kind": "metadata"}
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _strings(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _strings(child, f"{path}[{index}]")


def _fold(value: str) -> str:
    return " ".join(value.casefold().split())


def _matches(text: str, expression: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(_fold(expression)) + r"(?!\w)", _fold(text)) is not None


def _query(value: dict) -> Query:
    for key in ("terms", "phrases", "namespaces", "providers", "record_types"):
        values = value.get(key, ())
        if not isinstance(values, (list, tuple)) or any(
            not isinstance(item, str) or not item.strip() for item in values
        ):
            raise ValueError(f"query.{key} must contain nonempty strings.")
    return Query(**value)


def _selected(record, query, sources, capture_hashes):
    identity = record["identity"]
    if query.providers and identity["provider"] not in query.providers:
        return False
    if query.namespaces and identity["namespace"] not in query.namespaces:
        return False
    if query.record_types and identity["record_type"] not in query.record_types:
        return False
    if capture_hashes and record.get("capture_sha256") not in capture_hashes:
        return False
    if sources and not any(
        all(not source.get(key) or source[key] == identity.get(key) for key in ("provider", "namespace"))
        and (not source.get("url") or source["url"] in
             [record.get("source_url"), *record.get("citation_urls", [])])
        for source in sources
    ):
        return False
    return True


def search_records(records, query: Query, *, bounds: Bounds | None = None, sources=(),
                   capture_hashes=(), inherited_coverage=None, context=None, storage=None) -> OperationResult:
    """All terms/phrases must occur; phrases never cross field/page/time segments."""
    from .models import OperationContext

    bounds, context = bounds or Bounds(), context or OperationContext()
    _query(asdict(query))
    if any(not context.allows("search", namespace) for namespace in query.namespaces):
        return OperationResult("failed", errors=(Error("permission_denied",
            "The selected source is outside the caller's namespace policy."),),
            operation_id=context.operation_id)
    start = time.monotonic()
    inherited = deepcopy(inherited_coverage or {})
    failures = list(inherited.get("failures", []))
    coverage = {
        **inherited, "sources": deepcopy(list(sources)), "date_from": query.date_from,
        "date_to": query.date_to, "date_inclusivity": "both", "actual_dates": [],
        "available_text": [], "failures": failures,
        "truncated": bool(inherited.get("truncated")), "searched_records": 0,
        "match_policy": "Unicode casefold, collapsed whitespace, word boundaries; AND terms/phrases",
        "scope": "available captured metadata and supplied text, not a live upstream search",
    }
    hits, dates, searched_sources, visited = [], set(), {}, 0
    expressions = tuple(query.terms) + tuple(query.phrases)
    cancelled = False
    for record in records:
        if operation_cancelled(storage, context):
            cancelled = True
            break
        if time.monotonic() - start > bounds.deadline_seconds:
            failures.append({"reason": "deadline_exceeded"})
            coverage["truncated"] = True
            break
        if (not context.allows("search", record["identity"]["namespace"])
                or not _selected(record, query, sources, capture_hashes)):
            continue
        if visited >= bounds.max_records:
            coverage["truncated"] = True
            break
        visited += 1
        identity, normalized = record["identity"], record.get("normalized", {})
        source = {key: identity[key] for key in ("provider", "namespace")}
        source["url"] = record.get("source_url")
        searched_sources[(identity["provider"], identity["namespace"], source["url"])] = source
        if query.body and normalized.get("body") != query.body:
            if not normalized.get("body"):
                failures.append({"identity": identity, "reason": "body_not_supplied"})
            continue
        day = normalized.get("meeting_date") or (normalized.get("scheduled_start") or "")[:10]
        try:
            if day:
                date.fromisoformat(day)
        except (ValueError, TypeError):
            day = None
        if day and ((query.date_from and day < query.date_from) or (query.date_to and day > query.date_to)):
            continue
        if not day and (query.date_from or query.date_to):
            failures.append({"identity": identity, "reason": "unknown_date"})
        if day:
            dates.add(day)
        metadata = list(_strings(normalized))
        supplied = []
        unavailable = []
        for segment in record.get("text", []):
            if not isinstance(segment, dict):
                raise ValueError("A text segment must be an object.")
            if isinstance(segment.get("text"), str) and segment["text"]:
                supplied.append({**segment, "kind": "supplied_text"})
            else:
                unavailable.append({"field": segment.get("field"), "reason": segment.get("completeness", "no_text")})
            if segment.get("completeness") in {"partial", "truncated", "failed", "unreadable", "metadata_only"}:
                unavailable.append({"field": segment.get("field"), "reason": segment["completeness"]})
        # A document/media link is not its body/transcript, even if meeting text exists.
        for relation in record.get("relationships", []):
            if relation.get("relation") in {"document", "recording"}:
                value = relation.get("value") or {}
                if not any(s.get("citation_url") == value.get("url") for s in supplied):
                    unavailable.append({"citation_url": value.get("citation_url") or value.get("url"),
                                        "reason": "linked_content_not_supplied"})
        coverage["available_text"].append({
            "identity": deepcopy(identity), "capture_sha256": record.get("capture_sha256"),
            "status": "supplied_text" if supplied else "metadata_only",
            "metadata_fields": [s["field"] for s in metadata],
            "supplied_fields": [s.get("field") for s in supplied],
            "unavailable": unavailable,
            "full_source_searched": False,
        })
        if not supplied or unavailable:
            coverage["incomplete_text"] = True
        segments = metadata + supplied
        coverage["searched_records"] += 1
        matching = [s for s in segments if any(_matches(s["text"], e) for e in expressions)]
        if all(any(_matches(s["text"], e) for s in segments) for e in expressions):
            if len(hits) < query.limit:
                hits.append({
                    "record": deepcopy(record), "identity": deepcopy(identity),
                    "citation_urls": deepcopy(record.get("citation_urls", [])),
                    "source_url": record.get("source_url"), "capture_sha256": record.get("capture_sha256"),
                    "normalized_sha256": record.get("normalized_sha256"),
                    "source_revision": deepcopy(record.get("source_revision")),
                    "matches": [{**{k: deepcopy(v) for k, v in s.items() if k != "text"},
                                 "text": s["text"]} for s in matching],
                })
            else:
                coverage["truncated"] = True
        context.report(operation="search", completed=coverage["searched_records"])
    coverage["actual_dates"] = sorted(dates)
    coverage["searched_sources"] = list(searched_sources.values())
    for source in sources:
        if not any(all(not source.get(k) or source[k] == searched.get(k)
                       for k in ("provider", "namespace", "url"))
                   for searched in searched_sources.values()):
            failures.append({"source": deepcopy(source), "reason": "no_available_capture"})
    for field, selected in (("provider", query.providers), ("namespace", query.namespaces)):
        for value in selected:
            if not any(source.get(field) == value for source in searched_sources.values()):
                failures.append({field: value, "reason": "no_available_capture"})
    coverage["selected_providers"] = list(query.providers)
    coverage["selected_namespaces"] = list(query.namespaces)
    if not coverage["sources"]:
        coverage["sources"] = list(searched_sources.values())
    if inherited.get("status") in {"partial", "failed", "cancelled"}:
        coverage["input_status"] = inherited["status"]
    partial = bool(failures or coverage["truncated"] or coverage.get("incomplete_text")
                   or coverage.get("input_status"))
    return OperationResult(
        "cancelled" if cancelled else "partial" if partial else "completed",
        data={"hits": hits, "records": [hit["record"] for hit in hits], "query": asdict(query)},
        errors=tuple(Error("search_coverage", "Some requested evidence was not fully searchable.",
                           details={"failure": failure}) for failure in failures),
        coverage=coverage, operation_id=context.operation_id,
    )


def register(engine) -> None:
    def extract(owner, request, content, context):
        source = Source.from_dict(request["source"])
        if ((context.allowed_namespaces is not None and source.namespace is None)
                or not context.allows("extract_text", source.namespace)):
            return OperationResult("failed", errors=(Error("permission_denied",
                "Text extraction requires an authorized source namespace."),))
        bounds = Bounds(**request.get("bounds", {}))
        if content is not None and "content_base64" in request:
            raise ValueError("Supply content bytes or content_base64, not both.")
        if content is None:
            encoded = request.get("content_base64")
            if not isinstance(encoded, str) or len(encoded) > 4 * ((bounds.parser_bytes + 2) // 3):
                raise ValueError("Text extraction requires bounded content bytes or content_base64.")
            content = base64.b64decode(encoded, validate=True)
        return extract_text_segments(content, media_type=request["media_type"], citation_url=source.url,
                                     bounds=bounds, context=context)

    def search(owner, request, content, context):
        request = dict(request)
        if "native" in request and type(request["native"]) is not bool:
            raise ValueError("native must be a JSON boolean.")
        if request.get("native") is True:
            return OperationResult.unsupported("native_search", reason=(
                "No verified native search mapping is registered for this source. "
                "This does not establish that the provider lacks upstream search; "
                "use an explicit local capture search or a registered connector hook."))
        if "result" in request:
            upstream = request["result"]
            if not isinstance(upstream, dict):
                raise ValueError("result must be a complete operation result object.")
            if not isinstance(upstream.get("data"), dict):
                return OperationResult.from_dict(upstream)
            request["bundle"] = upstream["data"]
            request["coverage"] = {**upstream.get("coverage", {}), "status": upstream["status"]}
        query = _query(request.get("query", {}))
        bundle = request.get("bundle")
        if bundle is not None:
            records = bundle["records"]
        elif "records" in request:
            records = request["records"]
        elif owner.storage is not None:
            iterator = getattr(owner.storage, "iter_values", owner.storage.list)
            records = (item.value for item in iterator("records", scope=context.scope))
        else:
            raise ValueError("Search requires records, a bundle, or configured optional storage.")
        sources = request.get("sources", [])
        if not isinstance(sources, (list, tuple)) or any(not isinstance(s, dict) for s in sources):
            raise ValueError("sources must be an array of source objects.")
        if any(s.get("namespace") and not context.allows("search", s["namespace"]) for s in sources):
            return OperationResult("failed", errors=(Error("permission_denied", "Source namespace not authorized."),))
        result = search_records(
            records, query, bounds=Bounds(**request.get("bounds", {})), sources=sources,
            capture_hashes=request.get("capture_sha256", []), inherited_coverage=request.get("coverage"),
            context=context, storage=owner.storage,
        )
        if "result" in request:
            upstream_errors = tuple(Error(**e) for e in request["result"].get("errors", []))
            return OperationResult(result.status, data=result.data, errors=upstream_errors + result.errors,
                                   coverage=result.coverage, operation_id=context.operation_id)
        return result
    engine.register_operation("search", tracked_handler("search", search))
    engine.register_operation("extract_text", tracked_handler("extract_text", extract))
