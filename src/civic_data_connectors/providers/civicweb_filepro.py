"""CivicWeb FilePro document records; no inferred meeting/calendar association."""

import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
from html.parser import HTMLParser
import re
from time import monotonic
import xml.etree.ElementTree as ET

from ..engine import canonical_hash
from ..models import Error, OperationResult
from .civicweb_soap import NS, SOAP, PublicClient, response_value
from .contracts import RetrievalError, _origin
from .native import make_bundle

FORMAT = "civicweb-filepro-soap-xml"
FILE_METHODS = {"original": "GetOriginalFile", "pdf": "GetPdfFile",
                "meeting_pdf": "GetMeetingAttachmentPdfFile"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_html(value):
    parser = _Text()
    parser.feed(value or "")
    return " ".join(" ".join(parser.parts).split())


def numeric_id(value, *, root=False):
    if type(value) is int:
        number = value
    elif isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,9}", value):
        number = int(value)
    else:
        raise ValueError("A supplied FilePro Int32 identity is required.")
    if not (0 if root else 1) <= number < 2**31:
        raise ValueError("A supplied FilePro Int32 identity is required.")
    return number


def _method(content):
    # Validate before ElementTree parses; response_value performs remaining limits.
    if b"\0" in content or re.search(br"<!\s*(?:DOCTYPE|ENTITY)", content, re.I):
        raise ValueError("Unsupported FilePro XML declaration.")
    root = ET.fromstring(content)
    body = root.find(f"{{{SOAP}}}Body")
    if body is None or not len(body):
        raise ValueError("Missing FilePro SOAP response body.")
    tag = body[0].tag
    if not tag.startswith("{" + NS + "}") or not tag.endswith("Response"):
        raise ValueError("Missing FilePro response method.")
    return tag.split("}", 1)[1].removesuffix("Response")


def parse_bundle(source, namespace, content, *, expected_id=None):
    method = _method(content)
    value = response_value(method, content, byte_limit=len(content))
    rows, parent = [], None
    if method == "GetChildList":
        if not isinstance(value, dict):
            raise ValueError("Missing FilePro child-list result.")
        parent = numeric_id(value["ID"], root=True)
        if expected_id is not None and parent != numeric_id(expected_id, root=True):
            raise ValueError("FilePro child list differs from its requested parent.")
        for raw in value.get("Nodes") or []:
            identity = numeric_id(raw.get("ID"))
            kind = "folder" if raw["Folder"] else "document"
            rows.append(({"external_id": str(identity), "title": raw.get("Name"),
                "source_path": raw.get("Path"), "is_public": raw.get("IsPublic"),
                "url": _origin(source.url) + "/Documents/DocumentList.aspx?ID=" + str(identity),
                "documents": [], "recordings": [], "time_zone_status": "unknown"}, raw, kind))
    elif method in {"GetSearchResultDetails", "GetSearchResultDetailsBySearchCriteria"}:
        for raw in value or []:
            identity = numeric_id(raw["Id"])
            rows.append(({"external_id": str(identity), "title": plain_html(raw.get("TitleHtml")),
                "search_excerpts": [plain_html(raw.get("SampleHtml"))],
                "source_path": plain_html(raw.get("PathHtml")),
                "url": _origin(source.url) + "/Documents/DocumentList.aspx?ID=" + str(identity),
                "documents": [], "recordings": [], "time_zone_status": "unknown"}, raw, "document"))
    elif method in FILE_METHODS.values():
        identity = numeric_id(expected_id if expected_id is not None else source.options.get("document_id"))
        if value is not None:
            rows.append(({"external_id": str(identity), "title": None,
                "url": _origin(source.url) + "/Documents/DocumentList.aspx?ID=" + str(identity),
                "extension": value.get("Extension"), "documents": [], "recordings": [],
                "time_zone_status": "unknown", "file_bytes_supplied": bool(value.get("FileBytes")),
                "html_supplied": bool(value.get("Html"))}, value, "document"))
    else:
        raise ValueError("This SOAP response requires context before it can become a document record.")
    identities = [(row[2], row[0]["external_id"]) for row in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("FilePro result repeats a document/folder identity.")
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    bundle["extensions"]["vendor_contract"] = {"guide_date": "2014-04-24", "wsdl_captured": "2026-11-12",
        "method": method, "scope": "FilePro documents only; deployment compatibility must be configured"}
    bundle["capture"]["original_values"] = deepcopy(value)
    if parent is not None:
        bundle["extensions"]["folder_id"] = parent
        for record in bundle["records"]:
            if parent:
                identity = {"provider": "civicweb", "namespace": namespace, "record_type": "folder",
                            "external_id": str(parent), "parent": None}
                record["identity"]["parent"] = deepcopy(identity)
                record["relationships"].append({"relation": "folder", "identity": identity})
    elif method in FILE_METHODS.values() and value is not None:
        # SOAP file results have no ID: bind only the explicit request/caller ID.
        for record in bundle["records"]:
            record["identity"]["derivation"] = "requested_provider_identifier"
            record["identity"]["stability"] = "Supplied request document ID; SOAP file result does not echo identity."
        encoded = value.get("FileBytes")
        if encoded:
            raw = base64.b64decode(encoded, validate=True)
            extension = value.get("Extension")
            if method != "GetOriginalFile" and (not raw.startswith(b"%PDF-")
                    or not isinstance(extension, str) or extension.lower() != ".pdf"):
                raise ValueError("FilePro PDF result does not contain PDF bytes/extension.")
            bundle["extensions"]["file"] = {"content_base64": encoded, "byte_length": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(), "extension": extension,
                "content_type": "application/pdf" if extension == ".pdf" and raw.startswith(b"%PDF-")
                                else "application/octet-stream"}
        if value.get("Html"):
            for record in bundle["records"]:
                record["text"] = [{"text": plain_html(value["Html"]), "kind": "provider_html_text",
                                   "coverage": "supplied_html_version_not_original_file_text"}]
    return bundle


def read(source, namespace, request, bounds, context, transport, *, discover=False):
    from .discovery import _checkpoint, _resume

    resource = source.options.get("filepro_resource", "children")
    if resource == "children":
        identity = numeric_id(source.options.get("folder_id", 0), root=True)
        method = "GetChildList"
        parameters = dict(id=identity, path="", includeDocuments=True,
            documentProvider="iCompass.CivicWeb.Items.DocumentProvider", controlId="")
    elif resource in FILE_METHODS:
        if discover:
            raise ValueError("Use fetch for a supplied FilePro document identity.")
        identity = numeric_id(request.get("external_id", source.options.get("document_id")))
        method, parameters = FILE_METHODS[resource], {"id": identity}
        if resource == "meeting_pdf":
            parameters = {"documentId": identity, "meetingId": numeric_id(source.options.get("meeting_id"))}
    else:
        raise ValueError("Choose documented FilePro children/original/pdf/meeting_pdf resource.")
    if request.get("attachment") is not None:
        raise ValueError("FilePro SOAP retrieval uses a supplied document identity, not arbitrary URLs.")
    binding = canonical_hash({"source": source.public_dict(), "scope": context.scope,
        "method": method, "parameters": parameters, "dates": [bounds.date_from, bounds.date_to],
        "record_types": request.get("record_types")})
    offset, prior_hash = 0, None
    if bounds.checkpoint:
        tasks, seen = _resume(bounds.checkpoint, binding)
        if resource != "children" or seen or len(tasks) != 1 or set(tasks[0]) != {"offset", "sha256"}:
            raise ValueError("Invalid FilePro single-folder continuation.")
        offset, prior_hash = tasks[0]["offset"], tasks[0]["sha256"]
        if type(offset) is not int or offset < 0 or not isinstance(prior_hash, str):
            raise ValueError("Invalid FilePro capture position.")
    coverage = {"scope": "one FilePro folder result" if resource == "children" else "one supplied FilePro document",
        "source_complete": False, "catalog_complete": False, "meeting_association_inferred": False,
        "resource": resource, "checkpoint": None}
    try:
        client = PublicClient(source, bounds, context, transport)
        _, raw = client.call(method, parameters)
        digest = hashlib.sha256(raw).hexdigest()
        if prior_hash is not None and digest != prior_hash:
            raise ValueError("FilePro response changed during continuation; restart this folder.")
        bundle = parse_bundle(replace(source, options={**source.options, "document_id": identity}),
                              namespace, raw, expected_id=identity)
        records = bundle["records"]
        types = request.get("record_types")
        if types:
            records = [r for r in records if r["identity"]["record_type"] in types]
        if offset > len(records):
            raise ValueError("FilePro continuation offset exceeds its response.")
        selected = records[offset:offset + bounds.max_records]
        bundle["records"] = selected
        following = offset + len(selected)
        if following < len(records):
            coverage["checkpoint"] = _checkpoint(binding, [{"offset": following, "sha256": digest}], set())
        coverage.update(transfer_bytes=client.transferred, truncated=following < len(records),
            unknown_date_records=[r["identity"]["external_id"] for r in selected]
                                 if bounds.date_from or bounds.date_to else [],
            unknown_body_records=[r["identity"]["external_id"] for r in selected] if source.body else [])
        if resource == "meeting_pdf":
            parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
                      "external_id": str(parameters["meetingId"]), "parent": None}
            for record in selected:
                record["identity"]["parent"] = deepcopy(parent)
                record["relationships"].append({"relation": "meeting", "identity": deepcopy(parent)})
            coverage["meeting_association_inferred"] = False
        has_bytes = "file" in bundle["extensions"]
        status = "completed" if resource != "children" and has_bytes else "partial"
        data = {"records": selected, "bundles": [bundle], "captures": [bundle["capture"]]} if discover else bundle
        return OperationResult(status, data, coverage=coverage, operation_id=context.operation_id)
    except (ValueError, OSError) as error:
        code = error.code if isinstance(error, RetrievalError) else "civicweb_filepro_invalid_response"
        return OperationResult("cancelled" if context.check_cancelled() else "failed",
            errors=(Error(code, "The bounded FilePro document read could not be verified.", source=source.url),),
            coverage=coverage, operation_id=context.operation_id)


def native_search(engine, request, content, context, *, transport=None):
    """Vendor full-document candidates; exact local matches cover only returned snippets."""
    from ..models import Bounds
    from ..search import _query, search_records
    from .contracts import PublicTransport
    from .discovery import _checkpoint, _resume
    from .identification import configured_source, validate_source

    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if source.input_format != FORMAT:
        raise ValueError("FilePro native search requires the explicit civicweb-filepro-soap-xml format.")
    if not context.allows("search", namespace):
        raise ValueError("The FilePro source is outside the caller's search scope.")
    if content is not None or any(key in request for key in ("content_base64", "records", "bundle", "result")):
        raise ValueError("Saved FilePro search results use native=false.")
    query, bounds = _query(request.get("query", {})), Bounds(**request.get("bounds", {}))
    lower = max(filter(None, (query.date_from, bounds.date_from)), default=None)
    upper = min(filter(None, (query.date_to, bounds.date_to)), default=None)
    if lower and upper and lower > upper:
        raise ValueError("The requested FilePro date range is empty.")
    query = replace(query, date_from=lower, date_to=upper)
    if not query.terms and not query.phrases:
        raise ValueError("FilePro native search requires a nonempty term or phrase.")
    if any(not word.strip() for word in (*query.terms, *query.phrases)):
        raise ValueError("FilePro search expressions must not be blank.")
    params = dict(exactPhrase=query.phrases[0] if query.phrases else "",
                  allWords=" ".join(query.terms), atLeastOneWord="", wordsInProximity1="",
                  wordsInProximity2="", wordsNotIncluded="")
    binding = canonical_hash({"source": source.public_dict(), "scope": context.scope,
        "query": request.get("query", {}), "dates": [bounds.date_from, bounds.date_to],
        "grants": {"authorization": sorted(context.authorization),
                   "operations": sorted(context.allowed_operations) if context.allowed_operations is not None else None,
                   "namespaces": sorted(context.allowed_namespaces) if context.allowed_namespaces is not None else None}})
    position, batch_start, batch_hash, ids_hash = 0, 0, None, None
    if bounds.checkpoint:
        tasks, seen = _resume(bounds.checkpoint, binding)
        if seen or len(tasks) != 1 or set(tasks[0]) != {"position", "batch_start", "batch_hash", "ids_hash"}:
            raise ValueError("Invalid FilePro search continuation.")
        state = tasks[0]
        position, batch_start, batch_hash, ids_hash = (state[k] for k in
            ("position", "batch_start", "batch_hash", "ids_hash"))
        if (type(position) is not int or type(batch_start) is not int or not 0 <= batch_start <= position
                or position - batch_start >= 50 or not isinstance(ids_hash, str)
                or (position != batch_start and not isinstance(batch_hash, str))):
            raise ValueError("Invalid FilePro search continuation position.")
    coverage = {"scope": "vendor document candidates and exact local title/snippet/path matches only",
        "sources": [{**source.public_dict(), "namespace": namespace}], "native_search": True,
        "catalog_complete": False, "source_complete": False, "checkpoint": None,
        "provider_query_semantics": "documented exactPhrase AND allWords; local AND expressions over returned text",
        "available_text_scope": "search excerpts, not full original document or inferred meeting text",
        "status": "partial", "failures": []}
    records, bundles, captures, hits, errors = [], [], [], [], []
    client = PublicClient(source, bounds, context, transport or PublicTransport())
    visited, pages, ids = 0, 0, None
    try:
        ids, id_raw = client.call("GetSearchResults", params)
        ids = [] if ids is None else ids
        if not isinstance(ids, list) or any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("FilePro search must return distinct positive document IDs.")
        current_hash = hashlib.sha256(id_raw).hexdigest()
        if ids_hash is not None and current_hash != ids_hash:
            raise ValueError("FilePro candidate response changed; restart the query.")
        ids_hash = current_hash
        captures.append({"method": "GetSearchResults", "sha256": ids_hash,
                         "content_base64": base64.b64encode(id_raw).decode(), "byte_length": len(id_raw)})
        if position > len(ids):
            raise ValueError("FilePro continuation exceeds its candidate list.")
        while position < len(ids) and visited < bounds.max_records and len(hits) < query.limit:
            if pages >= bounds.max_pages:
                break
            subset = ids[batch_start:batch_start + 50]
            values, raw = client.call("GetSearchResultDetails", {"searchResultsSubset": subset, **params})
            pages += 1
            digest = hashlib.sha256(raw).hexdigest()
            if batch_hash is not None and digest != batch_hash:
                raise ValueError("FilePro detail batch changed during continuation; restart the query.")
            bundle = parse_bundle(source, namespace, raw)
            by_id = {numeric_id(r["identity"]["external_id"]): r for r in bundle["records"]}
            if any(i not in subset for i in by_id):
                raise ValueError("FilePro details returned an identity outside the requested subset.")
            bundles.append(bundle)
            captures.append(bundle["capture"])
            batch_hash = digest
            while position < batch_start + len(subset):
                if visited >= bounds.max_records or len(hits) >= query.limit:
                    break
                identity = ids[position]
                record = by_id.get(identity)
                position += 1
                visited += 1
                if record is None:
                    coverage["failures"].append({"external_id": str(identity), "reason": "document_detail_not_returned"})
                    continue
                records.append(record)
                remaining = bounds.deadline_seconds - (monotonic() - client.started)
                if remaining <= 0:
                    raise RetrievalError("provider_deadline_exceeded")
                local = search_records([record], replace(query, body=None),
                    bounds=replace(bounds, checkpoint=None, max_records=1, deadline_seconds=remaining),
                    sources=coverage["sources"], inherited_coverage=coverage,
                    context=context, storage=engine.storage)
                if local.status == "cancelled":
                    raise RetrievalError("cancelled")
                hits.extend(local.data.get("hits", []))
            if position >= batch_start + len(subset):
                batch_start, batch_hash = position, None
        coverage.update(provider_candidates=len(ids), searched_records=visited, pages=pages,
                        transfer_bytes=client.transferred, query_candidates_exhausted=position >= len(ids),
                        unknown_date_records=[r["identity"]["external_id"] for r in records]
                                             if query.date_from or query.date_to else [],
                        unknown_body_records=[r["identity"]["external_id"] for r in records]
                                             if query.body or source.body else [])
        if position < len(ids):
            coverage["checkpoint"] = _checkpoint(binding, [{"position": position, "batch_start": batch_start,
                "batch_hash": batch_hash, "ids_hash": ids_hash}], set())
    except (ValueError, OSError) as error:
        code = error.code if isinstance(error, RetrievalError) else "civicweb_filepro_search_invalid"
        errors.append(Error(code, "The bounded FilePro search could not be verified.", source=source.url))
        coverage["failures"].append({"reason": code})
    return OperationResult("cancelled" if context.check_cancelled() else "partial" if captures else "failed",
        {"hits": hits, "bundle": {"records": records, "bundles": bundles, "captures": captures}},
        tuple(errors), coverage, context.operation_id)
