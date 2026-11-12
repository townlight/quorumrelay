"""Pinned vendor SOAP read mappings, separate from legacy Granicus captures."""

from copy import deepcopy
import base64
import hashlib
from urllib.parse import urlsplit
from dataclasses import replace
from datetime import datetime
import xml.etree.ElementTree as ET

from ..models import Error, OperationResult
from .granicus_soap import RPC, SOAP, Session, contract, response_value
from .native import make_bundle

FORMAT = "granicus-platform-soap-xml"
SUPPORTING = {
    "clip_captions": ("GetClipCaptions", "ClipID", "recording", "caption"),
    "event_video": ("GetEventVideoLocation", "EventID", "meeting", "recording"),
    "clip_video": ("GetClipVideoLocation", "ClipID", "recording", "recording"),
    "item_video": ("GetMetaDataVideoLocation", "MetaDataID", "agenda_item", "recording"),
    "attachment": ("FetchAttachment", "MetaDataID", "agenda_item", "document"),
    "clip_minutes": ("GetClipMinutesDocuments", "ClipID", "recording", "document"),
}
READS = {
    "event": ("GetEvent", "EventID", "meeting"),
    "clip": ("GetClip", "ClipID", "recording"),
    "agenda_item": ("GetMetaData", "MetaDataID", "agenda_item"),
    "event_items": ("GetEventMetaData", "EventID", "agenda_item"),
    "clip_items": ("GetClipMetaData", "ClipID", "agenda_item"),
    "clip_indices": ("GetClipIndices", "ClipID", "agenda_item"),
}


def numeric_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("A supplied positive Granicus Int32 identity is required.")
    number = int(value)
    if str(number) != str(value) or not 0 < number < 2**31:
        raise ValueError("A supplied positive Granicus Int32 identity is required.")
    return number


def parse_bundle(source, namespace, content):
    # response_value first enforces XML/DTD, nesting, references and exact method.
    # Locate the method only after rejecting hostile XML declarations/encodings.
    import re
    if b"\0" in content or re.search(br"<!\s*(?:DOCTYPE|ENTITY)", content, re.I):
        raise ValueError("Unsupported SOAP XML declaration.")
    root = ET.fromstring(content)
    body = root.find(f"{{{SOAP}}}Body")
    if body is None or not len(body):
        raise ValueError("Missing SOAP result body.")
    tag = body[0].tag
    if not tag.startswith("{" + RPC + "}") or not tag.endswith("Response"):
        raise ValueError("No mapped SOAP response.")
    operation = tag.rsplit("}", 1)[1].removesuffix("Response")
    kinds = {value[0]: value[2] for value in READS.values()}
    kinds.update(GetEvents="meeting", GetEventsByDateRange="meeting", GetClips="recording")
    if operation not in kinds:
        raise ValueError("This SOAP response has no normalized record mapping.")
    values = response_value(operation, content, byte_limit=len(content))
    value = next(iter(values.values()))
    if value is None:
        entries = []
    elif isinstance(value, list):
        entries = value
    else:
        entries = [value]
    rows, seen = [], set()
    for raw in entries:
        if not isinstance(raw, dict):
            raise ValueError("A documented Granicus record object is required.")
        identity = str(numeric_id(raw.get("ID")))
        if identity in seen:
            raise ValueError("The SOAP response repeats a provider record identity.")
        seen.add(identity)
        normalized = {"external_id": identity, "title": raw.get("Name"),
            "description": raw.get("Description"), "status": raw.get("Status"),
            "url": source.url, "source_updated": raw.get("LastModified"),
            "time_zone_status": "unknown", "documents": [], "recordings": []}
        date = raw.get("MeetingTime") or raw.get("StartTime") or raw.get("Date")
        if isinstance(date, str) and date:
            try:
                normalized["meeting_date"] = datetime.fromisoformat(date.replace("Z", "+00:00")).date().isoformat()
                normalized["scheduled_at"] = date
            except ValueError:
                normalized["source_date"] = date
        if kinds[operation] == "agenda_item":
            normalized.update(source_parent_id=raw.get("ParentID"), timestamp_seconds=raw.get("TimeStamp"),
                              sequence=raw.get("OrderID"), supplied_payload=deepcopy(raw.get("Payload")))
        rows.append((normalized, deepcopy(raw), kinds[operation]))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    bundle["extensions"]["vendor_contract"] = {"revision": contract()["source_revision"], "method": operation}
    for record in bundle["records"]:
        revision = record["original"].get("LastModified")
        if revision:
            record["source_revision"] = {"kind": "provider_supplied", "value": revision}
    return bundle


def supporting_bundle(source, namespace, raw, resource, identity):
    method, _, parent_kind, kind = SUPPORTING[resource]
    values = response_value(method, raw, byte_limit=len(raw))
    value = next(iter(values.values()))
    rows = []
    entries = value if resource == "clip_minutes" else [value]
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise ValueError("A documented SOAP supporting collection is required.")
    for entry in entries:
        if resource == "clip_minutes":
            if not isinstance(entry, dict) or not isinstance(entry.get("UID"), str) or not entry["UID"]:
                raise ValueError("Minutes documents require their supplied UID.")
            external = entry["UID"]
        else:
            external = resource + ":" + str(identity)
        normalized = {"external_id": external, "url": source.url, "documents": [], "recordings": [],
                      "time_zone_status": "unknown"}
        if resource == "clip_captions":
            if not isinstance(entry, str):
                raise ValueError("The documented caption response is supplied text.")
            normalized.update(title="Supplied clip captions", caption_text=entry)
        elif resource.endswith("_video"):
            if not isinstance(entry, str):
                raise ValueError("The documented video location is a URI string.")
            parsed = urlsplit(entry)
            if (parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username
                    or parsed.password or any(c in entry for c in "\r\n\0")):
                raise ValueError("The supplied video URI cannot become a public citation.")
            normalized.update(title="Supplied video location", recordings=[{"url": entry}])
        elif resource == "attachment":
            if not isinstance(entry, dict) or not isinstance(entry.get("FileContents"), str):
                raise ValueError("The documented Document requires base64 FileContents.")
            data = base64.b64decode(entry["FileContents"], validate=True)
            normalized.update(title=entry.get("Description"), document_extension=entry.get("FileExtension"),
                              byte_length=len(data), document_sha256=hashlib.sha256(data).hexdigest())
        else:
            normalized.update(title=entry.get("Name"), document_type=entry.get("Type"),
                              published=entry.get("Published"), default=entry.get("Default"))
        rows.append((normalized, deepcopy(entry), kind))
    bundle = make_bundle(source, namespace, raw, FORMAT, rows)
    parent = {"provider": source.provider, "namespace": namespace, "record_type": parent_kind,
              "external_id": str(identity), "parent": None}
    for record in bundle["records"]:
        record["identity"]["parent"] = deepcopy(parent)
        record["relationships"].append({"relation": parent_kind, "identity": deepcopy(parent)})
        if resource != "clip_minutes":
            record["identity"].update(derivation="supplied_parent_and_documented_resource",
                stability="Local composite resource key; no independent provider child ID supplied.")
        if resource == "clip_captions" and record["normalized"]["caption_text"]:
            record["text"] = [{"field": "caption_text", "text": record["normalized"]["caption_text"],
                               "citation_url": source.url}]
    bundle["extensions"]["vendor_contract"] = {"revision": contract()["source_revision"], "method": method,
        "request_identity": str(identity), "api_resource": resource,
        "limits": "One supplied parent/resource; no inferred caption format, media download or document URL."}
    return bundle


def read(source, namespace, request, bounds, context, transport, *, discover=False):
    record_types = request.get("record_types") or []
    if not isinstance(record_types, list) or any(item not in {"meeting", "recording", "agenda_item", "caption", "document"} for item in record_types):
        raise ValueError("SOAP reads support meeting, recording, agenda_item, caption and document record types.")
    if bounds.checkpoint is not None:
        raise ValueError("No paging token is documented for this SOAP operation; use explicit bounded requests.")
    default = "events" if discover else "clip_captions" if "caption_language" in request else "event"
    resource = request.get("api_resource", default)
    if resource == "clip_captions" and request.get("caption_language", "*") != "*":
        raise ValueError("The pinned SOAP caption method supplies the entire transcript; no language filter is documented.")
    if resource == "events":
        parameters = request.get("api_parameters")
        # Preserve exact vendor dateTime values. Do not invent a timezone or
        # assume the vendor's EndDate is inclusive from date-only bounds.
        if not isinstance(parameters, dict) or set(parameters) != {"StartDate", "EndDate"}:
            raise ValueError("Event discovery requires explicit documented StartDate and EndDate dateTime values.")
        method = "GetEventsByDateRange"
    elif resource == "clips":
        parameters, method = {"FolderID": numeric_id(request.get("parent_id"))}, "GetClips"
    elif resource in SUPPORTING:
        method, key, _, _ = SUPPORTING[resource]
        parameters = {key: numeric_id(request.get("external_id"))}
    elif resource in READS:
        method, key, _ = READS[resource]
        parameters = {key: numeric_id(request.get("external_id"))}
    else:
        raise ValueError("Use a documented event, clip, agenda_item, related metadata or folder-clips resource.")
    session = Session(replace(source, namespace=namespace), context, bounds, transport)
    bundle, errors = None, []
    try:
        _, raw = session.call(method, parameters)
        bundle = (supporting_bundle(source, namespace, raw, resource, request["external_id"])
                  if resource in SUPPORTING else parse_bundle(source, namespace, raw))
        if resource in {"event", "clip", "agenda_item"} and any(
                record["identity"]["external_id"] != str(request["external_id"]) for record in bundle["records"]):
            raise ValueError("The SOAP response differs from the requested provider identity.")
        if resource in {"event_items", "clip_items", "clip_indices"}:
            parent = {"provider": source.provider, "namespace": namespace,
                      "record_type": "meeting" if resource == "event_items" else "recording",
                      "external_id": str(request["external_id"]), "parent": None}
            for record in bundle["records"]:
                record["identity"]["parent"] = deepcopy(parent)
                record["relationships"].append({"relation": "meeting" if resource == "event_items" else "recording",
                                                "identity": deepcopy(parent)})
    except Exception:
        errors.append(Error("granicus_soap_read_unavailable", "The bounded SOAP read could not be verified.",
                            source=source.url, retryable=True))
    finally:
        try:
            session.close()
        except ValueError:
            errors.append(Error("granicus_soap_logout_unconfirmed", "Private SOAP session logout was not confirmed.",
                                source=source.url, retryable=True))
    records = bundle["records"] if bundle else []
    filtered = []
    unknown_dates = []
    for record in records:
        if record_types and record["identity"]["record_type"] not in record_types:
            continue
        date = record["normalized"].get("meeting_date")
        if date and ((bounds.date_from and date < bounds.date_from) or (bounds.date_to and date > bounds.date_to)):
            continue
        if not date and (bounds.date_from or bounds.date_to):
            unknown_dates.append(record["identity"]["external_id"])
        filtered.append(record)
    truncated = len(filtered) > bounds.max_records
    if bundle:
        bundle["records"] = filtered[:bounds.max_records]
    return OperationResult("cancelled" if context.check_cancelled() else "partial" if bundle else "failed",
        bundle or {}, tuple(errors), {"scope": "one documented SOAP result; no archive/paging completeness inferred",
        "source_complete": False, "catalog_complete": False, "truncated": truncated,
        "unknown_date_records": unknown_dates,
        "unknown_body_records": [r["identity"]["external_id"] for r in filtered] if source.body else [],
        "requests": session.requests, "transfer_bytes": session.transferred,
        "contract_revision": contract()["source_revision"], "checkpoint": None}, context.operation_id)
