"""Explicit authenticated Laserfiche Repository v2 reads, separate from WebLink.

Only one configured folder's direct children are listed. Repository creation and
modification times are preserved as metadata, never treated as meeting dates.
"""

from __future__ import annotations

import base64
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
    if not isinstance(original, dict):
        raise ValueError("Repository entries require a JSON object.")
    if type(original.get("id")) is int:
        # The pinned SDK's GetEntry returns one Entry, not a children wrapper.
        # Preserve unknown Entry extensions, including a future field named value.
        entries = [original]
    elif isinstance(original.get("value"), list):
        entries = original["value"]
    else:
        raise ValueError("Repository entries require one Entry or an OData value array.")
    rows = []
    for raw in entries:
        if (not isinstance(raw, dict) or type(raw.get("id")) is not int or raw["id"] < 0
                or type(raw.get("parentId")) is not int or raw["parentId"] != parent_id
                or not isinstance(raw.get("name"), str)):
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


def fetch_entry(source, namespace, external_id, bounds, context, transport, *, include_text=False):
    """GetEntry from the pinned vendor SDK; metadata only, within the configured folder."""
    from .account_api import reject_credential_echo

    _, parent_id, base = repository_source(source)
    if not isinstance(external_id, str) or re.fullmatch(r"[1-9][0-9]{0,18}", external_id) is None:
        raise ValueError("Repository entry detail requires a positive decimal entry ID string.")
    if source.body or bounds.date_from or bounds.date_to or bounds.checkpoint:
        raise ValueError("Repository entry metadata accepts no meeting body/date or continuation filter.")
    token = context.credentials.get("laserfiche_token")
    if not isinstance(token, str) or not token or any(c in token for c in "\r\n\0"):
        raise ValueError("Repository metadata retrieval requires a trusted repository.Read token.")
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}],
                "scope": "one Repository entry's metadata in the configured folder",
                "external_id": external_id, "parent_folder_id": str(parent_id),
                "catalog_complete": False, "content_fetched": False, "pages": 0, "failures": []}
    if context.check_cancelled():
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    url = base.split("/Entries/", 1)[0] + "/Entries/" + external_id
    deadline = monotonic() + bounds.deadline_seconds
    try:
        response = transport.request(url, headers={"Accept": "application/json",
            "Authorization": "Bearer " + token}, byte_limit=bounds.parser_bytes,
            deadline_seconds=bounds.deadline_seconds,
            allowed_origins=("https://api.laserfiche.com",), allow_redirects=False)
        coverage["pages"] = 1
        if context.check_cancelled():
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if response.status != 200:
            raise RetrievalError("provider_http_error", status=response.status)
        if (response.url != url or len(response.content) > bounds.parser_bytes
                or monotonic() >= deadline):
            raise ValueError("Repository detail response exceeded its URL/byte/deadline contract.")
        reject_credential_echo(response.content, {"token": token})
        value = json.loads(response.content)
        if not isinstance(value, dict) or type(value.get("id")) is not int or value["id"] != int(external_id):
            raise ValueError("Repository entry response did not identify the requested entry.")
        bundle = entry_bundle(source, namespace, response.content)
        if (len(bundle["records"]) != 1
                or bundle["records"][0]["identity"]["external_id"] != external_id):
            raise ValueError("Repository detail must normalize exactly the requested entry.")
        bundle["capture"]["retrieval_url"] = url
        result = _bounded_parser_result(OperationResult("completed", bundle), bounds, context)
        if result.status != "completed":
            raise ValueError("Repository normalized entry exceeded configured bounds.")
        if include_text:
            from .repository_text import enrich_text
            return enrich_text(source, bundle, bounds, context, transport, deadline, coverage)
        return OperationResult("completed", bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception as error:
        code = error.code if isinstance(error, RetrievalError) else "repository_entry_failed"
        details = {"http_status": error.status} if isinstance(error, RetrievalError) and error.status else {}
        return OperationResult("failed", errors=(Error(code,
            "Repository entry metadata could not be retrieved or verified.", retryable=True,
            source=url, details=details),), coverage={**coverage, "failures": [code]},
            operation_id=context.operation_id)


def fetch_document(source, namespace, record, bundle, bounds, context, transport):
    """Export a captured document representation without exposing its single-use URL."""
    from .account_api import reject_credential_echo
    from .identification import validate_url
    from .retrieval import _download_origins

    _, parent_id, base = repository_source(source)
    part = source.options.get("repository_export_part", "Edoc")
    asynchronous = source.options.get("repository_export_async", False)
    if type(asynchronous) is not bool:
        raise ValueError("repository_export_async must be a JSON boolean.")
    if not isinstance(part, str) or part not in {"Edoc", "Image", "Text", "AlternateEdoc"}:
        raise ValueError("repository_export_part must be Edoc, Image, Text or AlternateEdoc.")
    export_request = {"part": part}
    if part == "Image":
        image_format = source.options.get("repository_image_format", "PDF")
        if not isinstance(image_format, str) or image_format not in {"PDF", "MultiPageTIFF", "SinglePageTIFF", "PNG", "JPEG"}:
            raise ValueError("Select a documented Repository image format.")
        export_request["imageOptions"] = {"format": image_format, "includeRedactions": True,
                                          "includeAnnotations": True}
        if image_format in {"MultiPageTIFF", "SinglePageTIFF"}:
            export_request["imageOptions"]["encoding"] = "AsStored"
    elif "repository_image_format" in source.options:
        raise ValueError("repository_image_format applies only to Image export.")
    if part == "Text":
        export_request["textOptions"] = {"includeRedactions": True}
    alternate = source.options.get("repository_alternate_edoc_name")
    if part == "AlternateEdoc":
        if not isinstance(alternate, str) or re.fullmatch(r"[A-Za-z0-9!@#$%^&()\-+={}\[\]_~]{1,15}", alternate) is None:
            raise ValueError("AlternateEdoc requires a documented 1-15 character alternate name.")
        export_request["alternateEdocName"] = alternate
    elif "repository_alternate_edoc_name" in source.options:
        raise ValueError("An alternate document name applies only to AlternateEdoc export.")
    identity = record["identity"]
    external_id = identity.get("external_id")
    original = record.get("original", {})
    if (not isinstance(external_id, str) or re.fullmatch(r"[1-9][0-9]{0,18}", external_id) is None
            or type(original.get("parentId")) is not int or original["parentId"] != parent_id
            or type(original.get("id")) is not int or str(original["id"]) != external_id
            or original.get("entryType") != "Document"):
        raise ValueError("Repository content requires a captured document in the configured folder.")
    citation = base.split("/Entries/", 1)[0] + "/Entries/" + external_id
    coverage = {"sources": [source.public_dict()], "scope": "one document export representation",
                "catalog_complete": False, "content_fetched": False, "export_part": part,
                "text_availability": "not_extracted", "failures": []}
    retained = {"record": record, "bundle": bundle, "attachment": None}
    deadline = monotonic() + bounds.deadline_seconds

    def cancelled():
        return OperationResult("cancelled", retained, coverage=coverage, operation_id=context.operation_id)

    def remaining():
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise ValueError("Repository content deadline expired.")
        return seconds

    if context.check_cancelled():
        return cancelled()
    try:
        # A stored capture alone cannot authorize an entry moved outside this folder.
        detail = fetch_entry(source, namespace, external_id,
                             replace(bounds, deadline_seconds=remaining()), context, transport)
        if detail.status == "cancelled":
            return cancelled()
        if detail.status != "completed" or detail.data["records"][0]["identity"]["record_type"] != "document":
            raise ValueError("Repository document no longer matches the configured scope.")
        token = context.credentials["laserfiche_token"]
        if context.check_cancelled():
            return cancelled()
        if asynchronous:
            from .repository_export import export_async
            signed = export_async(citation, export_request, bounds, context, transport, deadline, coverage)
        else:
            export_url = citation + "/Export"
            exported = transport.request(export_url, method="POST", body=json.dumps(export_request).encode(),
                headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                         "Content-Type": "application/json"}, byte_limit=bounds.parser_bytes,
                deadline_seconds=remaining(), allowed_origins=("https://api.laserfiche.com",),
                allow_redirects=False)
            if exported.status != 200 or exported.url != export_url or len(exported.content) > bounds.parser_bytes:
                raise ValueError("Repository export did not return a bounded successful response.")
            reject_credential_echo(exported.content, {"token": token})
            block = json.loads(exported.content)
            signed = block.get("value") if isinstance(block, dict) else None
        if context.check_cancelled():
            return cancelled()
        if not isinstance(signed, str) or len(signed) > 16384 or urlsplit(signed).scheme != "https":
            raise ValueError("Repository export returned an invalid download link.")
        # Source citations forbid credential query keys; this private transfer is
        # intentionally signed. Validate its address without persisting its query.
        validate_url(urlsplit(signed)._replace(query="").geturl())
        allowed = _download_origins(source, signed)
        response = transport.request(signed, headers={}, byte_limit=bounds.transfer_bytes,
            deadline_seconds=remaining(), allowed_origins=allowed, allow_redirects=False)
        if context.check_cancelled():
            return cancelled()
        remaining()
        if response.status != 200 or response.url != signed or len(response.content) > bounds.transfer_bytes:
            raise ValueError("Repository download exceeded its response contract.")
        if ((response.content_type.split(";", 1)[0].strip().lower() == "application/pdf"
                or (part == "Image" and export_request["imageOptions"]["format"] == "PDF"))
                and not response.content.startswith(b"%PDF-")):
            raise ValueError("Repository download did not return the declared PDF content.")
        if part == "Image":
            prefixes = {"PDF": (b"%PDF-",), "MultiPageTIFF": (b"II*\x00", b"MM\x00*"),
                        "SinglePageTIFF": (b"PK\x03\x04", b"PK\x05\x06"),
                        "PNG": (b"\x89PNG\r\n\x1a\n", b"PK\x03\x04"),
                        "JPEG": (b"\xff\xd8\xff", b"PK\x03\x04")}
            if not response.content.startswith(prefixes[export_request["imageOptions"]["format"]]):
                raise ValueError("Repository image export did not return its declared representation.")
        reject_credential_echo(response.content, {"token": token})
        attachment = {"citation_url": citation, "selected_url_field": "url",
                      "content_type": response.content_type, "byte_length": len(response.content),
                      "sha256": hashlib.sha256(response.content).hexdigest(),
                      "content_base64": base64.b64encode(response.content).decode("ascii"),
                      "text_availability": "not_extracted", "export_part": part,
                      "export_options": {key: value for key, value in export_request.items() if key != "part"},
                      "metadata_revision": detail.data["records"][0]["source_revision"],
                      "metadata_capture_sha256": detail.data["capture"]["sha256"]}
        return OperationResult("completed", {**retained, "attachment": attachment},
            coverage={**coverage, "content_fetched": True}, operation_id=context.operation_id)
    except InterruptedError:
        return cancelled()
    except Exception:
        # Never include raw provider errors, export JSON or ephemeral URLs in public output.
        return OperationResult("partial", retained, errors=(Error("attachment_unavailable",
            "The Repository original document could not be retrieved; the record is retained.",
            retryable=True, source=citation),), coverage={**coverage, "failures": ["attachment_unavailable"]},
            operation_id=context.operation_id)


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
