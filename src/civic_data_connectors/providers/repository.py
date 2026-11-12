"""Explicit authenticated Laserfiche Repository v2 reads, separate from WebLink.

Only one configured folder's direct children are listed. Repository creation and
modification times are preserved as metadata, never treated as meeting dates.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import replace
from time import monotonic
from urllib.parse import parse_qs, urljoin, urlsplit

from ..engine import _bounded_parser_result, canonical_hash, source_identity_key
from ..models import Error, OperationResult
from .contracts import RetrievalError, _origin
from .native import make_bundle

GUIDE = "https://developer.laserfiche.com/docs/guides/documents-and-folders/guide_get-folder-listing/"


def repository_source(source):
    """No inferred mapping between a public WebLink tenant and an API repository."""
    parsed = urlsplit(source.url)
    match = re.fullmatch(r"/repository/v2/Repositories/([A-Za-z0-9_-]+)/Entries/(0|[1-9][0-9]{0,18})/Folder/Children/?",
                         parsed.path)
    if (parsed.scheme != "https" or parsed.hostname != "api.laserfiche.com" or match is None
            or parsed.query or parsed.fragment):
        raise ValueError("Repository discovery requires an explicit HTTPS v2 folder Children source URL.")
    return match[1], int(match[2]), source.url.rstrip("/")


def _page_url(base, value):
    from .identification import validate_url
    if not isinstance(value, str) or not value or len(value) > 16384:
        raise ValueError("Invalid Repository nextLink.")
    target = urljoin(base, value)
    validate_url(target)
    parsed, expected = urlsplit(target), urlsplit(base)
    if (parsed.scheme != "https" or _origin(target) != _origin(base)
            or parsed.path.rstrip("/") != expected.path.rstrip("/")):
        raise ValueError("Repository nextLink left the exact repository folder collection.")
    if set(parse_qs(parsed.query, keep_blank_values=True)) - {
            "$skiptoken", "$skip", "$top", "$orderby", "$select", "$count", "groupByEntryType"}:
        raise ValueError("Repository nextLink contains unsupported query parameters.")
    return target


def entry_bundle(source, namespace, content):
    _, parent_id, base = repository_source(source)
    original = json.loads(content)
    if not isinstance(original, dict) or not isinstance(original.get("value"), list):
        raise ValueError("Repository children require an OData object with a value array.")
    rows = []
    for raw in original["value"]:
        if (not isinstance(raw, dict) or type(raw.get("id")) is not int or raw["id"] < 0
                or raw.get("parentId") != parent_id or not isinstance(raw.get("name"), str)):
            raise ValueError("Repository entries require supplied identity, name and matching parent folder.")
        kind = {"Document": "document", "Folder": "folder", "Shortcut": "shortcut"}.get(raw.get("entryType"))
        if kind is None:
            raise ValueError("The Repository entry type has no verified mapping.")
        citation = base.split("/Entries/", 1)[0] + "/Entries/" + str(raw["id"])
        rows.append(({"external_id": str(raw["id"]), "title": raw["name"], "url": citation,
                      "parent_folder_id": str(parent_id), "entry_type": raw["entryType"],
                      "full_path": raw.get("fullPath"), "folder_path": raw.get("folderPath"),
                      "source_created": raw.get("creationTime"), "source_updated": raw.get("lastModifiedTime"),
                      "template_id": raw.get("templateId"), "template_name": raw.get("templateName"),
                      "time_zone_status": "unknown", "content_availability": "not_requested"}, raw, kind))
    bundle = make_bundle(source, namespace, content, "laserfiche-repository-entries-json", rows)
    for record in bundle["records"]:
        parent = {"provider": source.provider, "namespace": namespace, "record_type": "folder",
                  "external_id": str(parent_id), "parent": None}
        # Entry IDs are repository-wide: its current folder is a relationship,
        # not part of the source identity (moving an entry must not rename it).
        record["relationships"] = [{"relation": "parent_folder", "identity": parent}]
        supplied = {key: deepcopy(record["original"][key]) for key in ("lastModifiedTime", "rowVersion")
                    if key in record["original"]}
        record["source_revision"] = {"kind": "provider_supplied" if supplied else "not_supplied",
                                     "value": supplied or None}
    return bundle


def discover_children(source, namespace, bounds, context, transport, *, saved=None, record_types=None):
    """Follow only provider-issued same-folder nextLinks under current caller bounds."""
    from .discovery import _checkpoint, _resume
    _, parent_id, base = repository_source(source)
    if source.body or bounds.date_from or bounds.date_to:
        raise ValueError("Repository entries have no mapped meeting body/date; select a folder explicitly.")
    types = record_types or []
    if not isinstance(types, list) or set(types) - {"document", "folder", "shortcut"}:
        raise ValueError("Repository record_types must select document, folder or shortcut.")
    size = source.options.get("page_size", 100)
    if type(size) is not int or not 1 <= size <= 150:
        raise ValueError("Repository page_size must be between 1 and 150.")
    token = context.credentials.get("laserfiche_token")
    if saved is None and (not isinstance(token, str) or not token):
        raise ValueError("Authenticated Repository discovery requires a trusted laserfiche_token with repository.Read.")
    binding = canonical_hash({"source": source.public_dict(), "namespace": namespace, "scope": context.scope,
                              "record_types": types, "saved_hash": hashlib.sha256(saved).hexdigest() if saved is not None else None})
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else ([{"url": base}], set())
    if len(queue) > 1 or any(set(task) != {"url"} for task in queue):
        raise ValueError("Invalid Repository checkpoint task.")
    records, bundles, failures, visited = [], [], [], set()
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}],
                "scope": "one Repository folder's direct children", "parent_folder_id": str(parent_id),
                "catalog_complete": False, "collection_complete": False,
                "recursive": False, "content_fetched": False, "pages": 0,
                "snapshot_consistency": "not_guaranteed", "failures": failures}
    deadline = monotonic() + bounds.deadline_seconds
    try:
        while queue and coverage["pages"] < bounds.max_pages and len(records) < bounds.max_records:
            if context.check_cancelled():
                return OperationResult("cancelled", {"records": records, "bundles": bundles},
                                       coverage=coverage, operation_id=context.operation_id)
            url = _page_url(base, queue[0]["url"])
            if url in visited:
                raise ValueError("Repository pagination cycle.")
            visited.add(url)
            limit = min(size, bounds.max_records - len(records))
            if saved is not None:
                content = saved
            else:
                response = transport.request(url, headers={"Accept": "application/json",
                    "Authorization": "Bearer " + token, "Prefer": "odata.maxpagesize=" + str(limit)},
                    byte_limit=bounds.parser_bytes, deadline_seconds=max(0.001, deadline - monotonic()),
                    allowed_origins=("https://api.laserfiche.com",))
                if context.check_cancelled():
                    return OperationResult("cancelled", {"records": records, "bundles": bundles},
                                           coverage=coverage, operation_id=context.operation_id)
                if response.status != 200:
                    raise RetrievalError("provider_http_error", status=response.status)
                if _page_url(base, response.url) != url:
                    raise ValueError("Repository response did not match the requested page.")
                content = response.content
            if len(content) > bounds.parser_bytes or monotonic() >= deadline:
                raise ValueError("Repository response exceeded parser/deadline bounds.")
            original = json.loads(content)
            bundle = entry_bundle(replace(source, url=base), namespace, content)
            if len(bundle["records"]) > limit:
                raise ValueError("Repository response exceeded its requested maximum page size.")
            parsed = _bounded_parser_result(OperationResult("completed", bundle), bounds, context)
            if parsed.status != "completed":
                raise ValueError("Repository normalized response exceeded parser bounds.")
            page_keys = [source_identity_key(record["identity"]) for record in bundle["records"]]
            if len(set(page_keys)) != len(page_keys) or any(key in seen for key in page_keys):
                raise ValueError("Repository pagination repeated an entry identity.")
            bundle["records"] = [record for record in bundle["records"]
                                 if not types or record["identity"]["record_type"] in types]
            next_link = original.get("@odata.nextLink")
            if next_link is not None:
                next_link = _page_url(base, next_link)
                if next_link in visited:
                    raise ValueError("Repository pagination repeated a page URL.")
            seen.update(page_keys)
            records.extend(bundle["records"])
            bundles.append(bundle)
            coverage["pages"] += 1
            queue = [{"url": next_link}] if next_link else []
            if saved is not None:
                break  # Saved captures never initiate authenticated network continuation.
        coverage.update({"returned_records": len(records), "source_complete": not queue,
                         "collection_complete": not queue, "truncated": bool(queue),
                         "checkpoint": _checkpoint(binding, queue, seen) if queue else None})
        return OperationResult("partial" if queue else "completed", {"records": records, "bundles": bundles},
                               coverage=coverage, operation_id=context.operation_id)
    except Exception as error:
        code = error.code if isinstance(error, RetrievalError) else "repository_discovery_failed"
        details = {"http_status": error.status} if isinstance(error, RetrievalError) and error.status else {}
        failures.append({"reason": code, **details})
        coverage["checkpoint"] = _checkpoint(binding, queue, seen) if queue else None
        return OperationResult("partial" if records else "failed", {"records": records, "bundles": bundles} if records else None,
            (Error(code, "Repository folder children could not be retrieved or verified.",
                   source=source.url, retryable=True, details=details),), coverage, context.operation_id)
