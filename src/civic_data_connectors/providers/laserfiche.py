"""Observed WebLink folder/page-text mechanics, using an injected guarded session.

Request fields come from Brief's independently captured WebLink 11 traffic.
This is not the separate account-backed Laserfiche Repository API.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date
from time import monotonic
from urllib.parse import parse_qs, urlencode, urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Error, OperationResult
from .contracts import _origin
from .discovery import _binding, _checkpoint, _resume
from .native import make_bundle

LISTING = "/FolderListingService.aspx/GetFolderListing2"
INFO = "/DocumentService.aspx/GetBasicDocumentInfo"
TEXT = "/DocumentService.aspx/GetTextHtmlForPage"
HEADERS = {"X-Lf-Suppress-Login-Redirect": "1"}
YEAR = re.compile(r"^\s*(\d{4})\b(?!\s*(?:-|–|&|and\b|to\b))", re.I)
MONTH = re.compile(r"^\s*(\d{1,2})\s+[a-z]{3}", re.I)


def _parts(url):
    parsed = urlsplit(url)
    params = {key.casefold(): values for key, values in parse_qs(parsed.query).items()}
    identity = (params.get("id") or [""])[0]
    repo = (params.get("repo") or [""])[0]
    dbid = (params.get("dbid") or ["0"])[0]
    if not identity.isdigit() or not repo or not dbid.isdigit():
        raise ValueError("WebLink session capture needs an id, repository and numeric dbid.")
    if not parsed.path.casefold().endswith(("/browse.aspx", "/docview.aspx")):
        raise ValueError("Use a WebLink Browse.aspx folder or DocView.aspx document URL.")
    return parsed.path.rsplit("/", 1)[0], int(identity), repo, int(dbid)


def _session(source, browser):
    if getattr(browser, "guarded", False) is not True or getattr(browser, "origin", None) != _origin(source.url):
        raise ValueError("WebLink requires an explicitly guarded browser scoped to this source origin.")


def _url(source, base, page, identifier, repo, dbid, key="id"):
    return _origin(source.url) + base + "/" + page + "?" + urlencode({
        key: identifier, "dbid": dbid, "repo": repo})


def _json_size(value, limit, browser=None):
    raw = getattr(browser, "captured_content", None)
    encoded = raw if isinstance(raw, bytes) else json.dumps(
        value, ensure_ascii=False, separators=(",", ":")).encode()
    if len(encoded) > limit:
        raise ValueError("WebLink response exceeds the configured parser byte limit.")
    if raw is not None and json.loads(encoded) != value:
        raise ValueError("WebLink captured bytes do not match the returned response.")
    return encoded


def day_of(name):
    for pattern, order in (
        (r"(?<!\d)(\d{4})[ ._-](\d{1,2})[ ._-](\d{1,2})(?!\d)", (1, 2, 3)),
        (r"(?<!\d)(\d{1,2})[./_-](\d{1,2})[./_-](\d{4}|\d{2})(?!\d)", (3, 1, 2)),
    ):
        match = re.search(pattern, name)
        if match:
            year, month, day = (int(match[group]) for group in order)
            try:
                return date(year + 2000 if year < 100 else year, month, day)
            except ValueError:
                return None
    month_names = ["january", "february", "march", "april", "may", "june", "july",
                   "august", "september", "october", "november", "december"]
    match = re.search(r"\b([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", name)
    if match:
        month = next((i for i, full in enumerate(month_names, 1)
                      if len(match[1]) >= 3 and full.startswith(match[1].lower())), None)
        if month:
            try:
                return date(int(match[3]), month, int(match[2]))
            except ValueError:
                pass
    return None


def _folder_in_range(name, year, bounds):
    span = re.match(r"^\s*(\d{4})\s*[-–]\s*(\d{4})\b", name)
    if span:
        return ((not bounds.date_from or int(span[2]) >= int(bounds.date_from[:4])) and
                (not bounds.date_to or int(span[1]) <= int(bounds.date_to[:4]))), year
    y = YEAR.match(name)
    if y:
        year = int(y[1])
        return ((not bounds.date_from or year >= int(bounds.date_from[:4])) and
                (not bounds.date_to or year <= int(bounds.date_to[:4]))), year
    m = MONTH.match(name)
    if m and year is not None and 1 <= int(m[1]) <= 12:
        month = f"{year:04}-{int(m[1]):02}"
        return ((not bounds.date_from or month >= bounds.date_from[:7]) and
                (not bounds.date_to or month <= bounds.date_to[:7])), year
    day = day_of(name)
    if day is not None:
        return ((not bounds.date_from or day.isoformat() >= bounds.date_from) and
                (not bounds.date_to or day.isoformat() <= bounds.date_to)), year
    return True, year


def discover_folders(engine, source, namespace, bounds, context, browser, *, record_types=None):
    _session(source, browser)
    base, root, repo, dbid = _parts(source.url)
    if not bounds.date_from or not bounds.date_to:
        raise ValueError("WebLink folder discovery requires explicit inclusive date bounds.")
    maximum_depth = source.options.get("max_folder_depth", 8)
    size = source.options.get("page_size", 100)
    if type(maximum_depth) is not int or not 1 <= maximum_depth <= 32:
        raise ValueError("max_folder_depth must be between 1 and 32.")
    if type(size) is not int or not 1 <= size <= 500:
        raise ValueError("WebLink page_size must be between 1 and 500.")
    types = record_types or []
    if not isinstance(types, list) or any(kind not in {"meeting", "recording", "document", "agenda_item"}
                                          for kind in types):
        raise ValueError("record_types must be a list of supported civic record types.")
    binding = canonical_hash([_binding(source, bounds, context, "laserfiche-listing-json"),
                              "observed-WebLink11/session-v1", types])
    queue, seen = (_resume(bounds.checkpoint, binding) if bounds.checkpoint else (
        [{"folder": root, "start": 0, "depth": 0, "year": None}], set()))
    deadline = monotonic() + bounds.deadline_seconds
    records, bundles, captures, errors, failures, retry = [], [], [], [], [], []
    depth_limited, unclassified, pages = [], [], 0
    visited = set()
    while queue and pages < bounds.max_pages and len(records) < bounds.max_records:
        if context.check_cancelled() or monotonic() >= deadline:
            break
        task = queue.pop(0)
        folder, start, depth = task.get("folder"), task.get("start"), task.get("depth")
        if (any(type(value) is not int or value < 0 for value in (folder, start, depth)) or
                depth > maximum_depth):
            raise ValueError("The WebLink checkpoint contains an invalid folder task.")
        key = canonical_hash(task)
        if key in visited:
            errors.append(Error("pagination_cycle", "WebLink repeated a folder checkpoint."))
            retry.append(task)
            break
        visited.add(key)
        pages += 1
        try:
            remaining = max(0.001, deadline - monotonic())
            if start == 0:
                result = browser.open_and_catch(
                    _url(source, base, "Browse.aspx", folder, repo, dbid), base + LISTING,
                    byte_limit=bounds.parser_bytes, deadline_seconds=remaining)
            else:
                result = browser.post_json(base + LISTING, {
                    "repoName": repo, "folderId": folder, "getNewListing": True,
                    "start": start, "end": start + size, "sortColumn": "", "sortAscending": True,
                }, HEADERS, byte_limit=bounds.parser_bytes, deadline_seconds=remaining)
            content = _json_size(result, bounds.parser_bytes, browser)
            digest = hashlib.sha256(content).hexdigest()
            if task.get("sha256") and task["sha256"] != digest:
                raise ValueError("The resumed WebLink listing changed.")
            block = result.get("data") if isinstance(result, dict) else None
            if not isinstance(block, dict) or not isinstance(block.get("results"), list):
                raise ValueError("WebLink must return data.results.")
            rows, total = block["results"], block.get("totalEntries")
            if type(total) is not int or total < 0 or any(not isinstance(row, dict) for row in rows):
                raise ValueError("WebLink must return a totalEntries count and entry objects.")
            if block.get("folderId", folder) != folder:
                raise ValueError("The WebLink response belongs to a different folder.")
            year = task.get("year")
            name = block.get("name")
            if isinstance(name, str) and (match := YEAR.match(name)):
                year = int(match[1])
            mapped = []
            offset = task.get("offset", 0)
            if type(offset) is not int or not 0 <= offset <= len(rows):
                raise ValueError("Invalid WebLink checkpoint entry offset.")
            for index in range(offset, len(rows)):
                if context.check_cancelled() or len(records) + len(mapped) >= bounds.max_records:
                    queue.insert(0, {**task, "offset": index, "sha256": digest})
                    break
                row = rows[index]
                identity, entry_type = row.get("entryId"), row.get("type")
                if type(identity) is not int or identity < 0:
                    raise ValueError("WebLink entryId must be a numeric provider identifier.")
                title = str(row.get("name") or "")
                if entry_type == 0:
                    keep, child_year = _folder_in_range(title, year, bounds)
                    folder_key = canonical_hash(["folder", identity])
                    if keep and folder_key not in seen:
                        if depth < maximum_depth:
                            queue.append({"folder": identity, "start": 0, "depth": depth + 1,
                                          "year": child_year})
                            seen.add(folder_key)
                        else:
                            depth_limited.append(identity)
                    continue
                if entry_type != -2:
                    continue
                day = day_of(title)
                if day is None:
                    unclassified.append(identity)
                    continue
                if not bounds.date_from <= day.isoformat() <= bounds.date_to:
                    continue
                if types and "meeting" not in types:
                    continue
                document_kind = ("minutes" if "minute" in title.casefold() else
                                 "packet" if "packet" in title.casefold() else
                                 "agenda" if "agenda" in title.casefold() else "document")
                link = _url(source, base, "ElectronicFile.aspx" if row.get("isEdoc") else "DocView.aspx",
                            identity, repo, dbid, "docid" if row.get("isEdoc") else "id")
                normalized = {
                    "external_id": str(identity), "title": title, "meeting_date": day.isoformat(),
                    "url": _url(source, base, "DocView.aspx", identity, repo, dbid),
                    "body": source.body, "time_zone_status": "unknown",
                    "agenda_items_availability": "absent",
                    "meeting_date_derivation": "dated_document_name",
                    "documents": [{"external_id": str(identity), "kind": document_kind,
                                   "title": title, "url": link}],
                }
                identity_key = source_identity_key({"provider": source.provider, "namespace": namespace,
                                                   "record_type": "meeting", "external_id": str(identity)})
                if identity_key not in seen:
                    seen.add(identity_key)
                    mapped.append((normalized, row, "meeting"))
            else:
                next_start = start + len(rows)
                if next_start < total:
                    if not rows:
                        raise ValueError("WebLink returned an empty page before totalEntries.")
                    queue.insert(0, {"folder": folder, "start": next_start, "depth": depth, "year": year})
            bundle = make_bundle(source, namespace, content, "laserfiche-listing-json", mapped)
            records.extend(bundle["records"])
            bundles.append(bundle)
            captures.append(bundle["capture"])
        except Exception as error:
            access = getattr(error, "code", None) == "weblink_access_required"
            reason = "weblink_access_required" if access else "folder_listing_failed"
            failures.append({"folder": folder, "start": start, "reason": reason})
            errors.append(Error(reason,
                "The source denied the guarded session; supply a saved capture or supported authorized access."
                if access else "A scoped WebLink folder listing could not be read.",
                retryable=not access, source=source.url,
                details={"http_status": error.status} if access else {}))
            retry.append(task)
        context.report(operation="discover", pages=pages, returned_records=len(records))
    queue.extend(retry)
    cancelled = context.check_cancelled()
    status = ("cancelled" if cancelled else "failed" if failures and not captures else
              "partial" if queue or failures or depth_limited else "completed")
    coverage = {
        "sources": [source.public_dict()], "date_from": bounds.date_from, "date_to": bounds.date_to,
        "date_inclusivity": "both", "pages": pages, "returned_records": len(records),
        "actual_dates": sorted({r["normalized"]["meeting_date"] for r in records}),
        "failures": failures, "failed_pages": failures, "truncated": bool(queue or depth_limited),
        "checkpoint": _checkpoint(binding, queue, seen) if queue else None,
        "depth_limited_folders": depth_limited, "unclassified_entries": unclassified,
        "scope": "dated meeting documents in the configured WebLink folder subtree",
        "available_text": "metadata_only; viewer text requires separate page retrieval",
        "browser_safety": "explicit isolated session with guarded transport; see session implementation",
    }
    return OperationResult(status, {"source": source.public_dict(), "records": records,
                                   "captures": captures, "bundles": bundles},
                           tuple(errors), coverage, context.operation_id)


def scanned_text(source, url, bounds, context, browser):
    _session(source, browser)
    base, identity, repo, dbid = _parts(url)
    source_base, _, source_repo, source_dbid = _parts(source.url)
    if (_origin(url) != _origin(source.url) or
            (base.casefold(), repo, dbid) != (source_base.casefold(), source_repo, source_dbid)):
        raise ValueError("The WebLink viewer belongs to a different tenant repository.")
    deadline = monotonic() + bounds.deadline_seconds
    info = browser.open_and_catch(url, base + INFO, byte_limit=bounds.parser_bytes,
                                 deadline_seconds=bounds.deadline_seconds)
    _json_size(info, bounds.parser_bytes, browser)
    count = info.get("data", {}).get("pageCount") if isinstance(info, dict) else None
    if type(count) is not int or count < 1:
        raise ValueError("WebLink supplied no document page count.")
    pages, text_size = [], 0
    for number in range(1, min(count, max(0, bounds.max_pages - 1)) + 1):
        if context.check_cancelled() or monotonic() >= deadline:
            break
        data = browser.post_json(base + TEXT, {
            "repoName": repo, "documentId": identity, "pageNum": number,
            "showAnn": True, "searchUuid": "",
        }, HEADERS, byte_limit=bounds.parser_bytes,
                                deadline_seconds=max(0.001, deadline - monotonic()))
        _json_size(data, bounds.parser_bytes, browser)
        text = data.get("data", {}).get("text") if isinstance(data, dict) else None
        if not isinstance(text, str):
            raise ValueError("WebLink did not supply text for the requested page.")
        plain = html.unescape(re.sub(r"<[^>]{0,2000}>", "", text))
        text_size += len(plain.encode())
        if text_size > bounds.transfer_bytes:
            raise ValueError("WebLink supplied text exceeds the configured transfer byte limit.")
        pages.append({"page": number, "text": plain, "citation_url": url,
                      "provenance": {"method": "provider_supplied_weblink_page_text"}})
    if not any(page["text"].strip() for page in pages):
        raise ValueError("WebLink supplied no readable text; a scan without text is not searched.")
    return {"text": "\n".join(page["text"] for page in pages), "pages": pages,
            "page_count": count, "completeness": "complete" if len(pages) == count else "partial"}
