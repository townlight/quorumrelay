"""Read existing Repository page text; never generate text, OCR or image pages."""

import base64
import hashlib
import json
from datetime import datetime, timezone
from time import monotonic

from ..engine import canonical_hash
from ..models import Error, OperationResult
from .account_api import reject_credential_echo
from .repository import _page_url


def enrich_text(source, bundle, bounds, context, transport, deadline, inherited):
    record = bundle["records"][0]
    citation = record["normalized"]["url"]
    base = citation + "/Document/Pages"
    captures = []
    segments = []
    failures = []
    coverage = {**inherited, "scope": "one document's supplied page text",
                "text_complete": False, "truncated": False, "pages": 0,
                "snapshot_consistency": "not_guaranteed", "failures": failures,
                "text_generation_requested": False}
    remaining_bytes = min(bounds.parser_bytes, bounds.transfer_bytes)
    token = context.credentials["laserfiche_token"]
    seen_urls, seen_numbers, seen_ids = set(), set(), set()
    next_url = base

    def read(url):
        nonlocal remaining_bytes
        if context.check_cancelled():
            raise InterruptedError()
        remaining = deadline - monotonic()
        if remaining <= 0 or remaining_bytes <= 0:
            raise ValueError("Page text exhausted its deadline or cumulative byte bound.")
        limit = remaining_bytes
        # Reserve the budget before the request: a transport failure may have
        # consumed it even when no response object was returned.
        remaining_bytes = 0
        response = transport.request(url, headers={"Accept": "application/json",
            "Authorization": "Bearer " + token,
            **({"Prefer": "odata.maxpagesize=" + str(min(150, bounds.max_pages - coverage["pages"]))}
               if url.split("?", 1)[0] == base else {})},
            byte_limit=limit, deadline_seconds=remaining,
            allowed_origins=("https://api.laserfiche.com",), allow_redirects=False)
        remaining_bytes = limit - min(len(response.content), limit)
        if context.check_cancelled():
            raise InterruptedError()
        if (response.status != 200 or response.url != url or len(response.content) > limit
                or monotonic() >= deadline):
            raise ValueError("The page response did not satisfy its bounded read contract.")
        reject_credential_echo(response.content, {"token": token})
        value = json.loads(response.content)
        if not isinstance(value, dict):
            raise ValueError("Page responses must be JSON objects.")
        capture = {"source_url": source.url, "retrieval_url": url,
                   "input_format": "laserfiche-repository-page-info-json" if url.split("?", 1)[0] == base
                                   else "laserfiche-repository-page-text-json",
                   "captured_at": datetime.now(timezone.utc).isoformat(),
                   "sha256": hashlib.sha256(response.content).hexdigest(),
                   "byte_length": len(response.content), "content_type": response.content_type,
                   "content_base64": base64.b64encode(response.content).decode("ascii"),
                   "original_values": value}
        captures.append(capture)
        return value, capture

    try:
        if record["identity"]["record_type"] != "document":
            raise ValueError("Only documents have supplied page text.")
        while next_url and coverage["pages"] < bounds.max_pages:
            url = _page_url(base, next_url)
            if url in seen_urls:
                raise ValueError("Page collection repeated a continuation URL.")
            seen_urls.add(url)
            block, _ = read(url)
            rows = block.get("value")
            if not isinstance(rows, list) or len(rows) > 150:
                raise ValueError("Invalid page collection.")
            for info in rows:
                if coverage["pages"] >= bounds.max_pages:
                    coverage["truncated"] = True
                    break
                if (not isinstance(info, dict) or type(info.get("entryId")) is not int
                        or str(info["entryId"]) != record["identity"]["external_id"]
                        or type(info.get("pageNumber")) is not int or info["pageNumber"] <= 0
                        or type(info.get("pageId")) is not int or info["pageId"] <= 0
                        or type(info.get("hasText")) is not bool
                        or info["pageNumber"] in seen_numbers or info["pageId"] in seen_ids):
                    raise ValueError("Page information did not identify a unique supplied document page.")
                number = info["pageNumber"]
                seen_numbers.add(number)
                seen_ids.add(info["pageId"])
                coverage["pages"] += 1
                if not info["hasText"]:
                    failures.append({"page": number, "reason": "no_supplied_text"})
                    continue
                try:
                    text_url = base + f"/{number}/Text"
                    text_block, captured = read(text_url)
                    text = text_block.get("text")
                    if not isinstance(text, str) or not text.strip():
                        raise ValueError("Page text is absent or invalid.")
                    segments.append({"field": "document.page_text", "text": text,
                        "page": number, "citation_url": text_url, "completeness": "complete",
                        "provenance": {"method": "provider_supplied_page_text", "page_id": info["pageId"],
                                       "capture_sha256": captured["sha256"], "scope": "one_document_page"}})
                except InterruptedError:
                    raise
                except Exception:
                    failures.append({"page": number, "reason": "page_text_unavailable"})
            next_link = block.get("@odata.nextLink")
            next_url = _page_url(base, next_link) if next_link is not None else None
            if not rows and next_url:
                raise ValueError("Empty page listing cannot advance a text read.")
        coverage["truncated"] = coverage["truncated"] or bool(next_url)
    except InterruptedError:
        coverage["cancelled"] = True
    except Exception:
        failures.append({"reason": "page_collection_unavailable"})
    if not segments:
        failures.append({"reason": "no_supplied_text"})
    coverage["content_fetched"] = bool(segments)
    coverage["text_complete"] = bool(segments) and not failures and not coverage["truncated"] and not coverage.get("cancelled")
    coverage["available_text"] = [{"page": s["page"], "citation_url": s["citation_url"]} for s in segments]
    if not coverage["text_complete"]:
        segments.append({"field": "document.page_text_coverage", "text": "", "citation_url": citation,
                         "completeness": "partial"})
    record["text"] = segments
    record["normalized"]["content_availability"] = "supplied_page_text" if coverage["content_fetched"] else "no_supplied_text"
    record["normalized"]["page_text_sha256"] = canonical_hash(segments)
    record["normalized_sha256"] = canonical_hash(record["normalized"])
    record.setdefault("extensions", {})["page_text_coverage"] = {
        "text_complete": coverage["text_complete"], "truncated": coverage["truncated"],
        "failures": list(failures), "snapshot_consistency": "not_guaranteed"}
    bundle["captures"] = captures
    status = "cancelled" if coverage.get("cancelled") else "completed" if coverage["text_complete"] else "partial"
    errors = (Error("page_text_incomplete", "Only available supplied page text is returned; metadata is retained.",
                    source=citation, retryable=True),) if status == "partial" else ()
    return OperationResult(status, bundle, errors, coverage, context.operation_id)
