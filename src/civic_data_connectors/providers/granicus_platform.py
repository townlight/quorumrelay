"""Pinned vendor SOAP read mappings, separate from legacy Granicus captures."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import xml.etree.ElementTree as ET

from ..models import Error, OperationResult
from .granicus_soap import RPC, SOAP, Session, contract, response_value
from .native import make_bundle

FORMAT = "granicus-platform-soap-xml"
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


def read(source, namespace, request, bounds, context, transport, *, discover=False):
    record_types = request.get("record_types") or []
    if not isinstance(record_types, list) or any(item not in {"meeting", "recording", "agenda_item"} for item in record_types):
        raise ValueError("SOAP reads support meeting, recording and agenda_item record types.")
    if bounds.checkpoint is not None:
        raise ValueError("No paging token is documented for this SOAP operation; use explicit bounded requests.")
    resource = request.get("api_resource", "events" if discover else "event")
    if resource == "events":
        parameters = request.get("api_parameters")
        # Preserve exact vendor dateTime values. Do not invent a timezone or
        # assume the vendor's EndDate is inclusive from date-only bounds.
        if not isinstance(parameters, dict) or set(parameters) != {"StartDate", "EndDate"}:
            raise ValueError("Event discovery requires explicit documented StartDate and EndDate dateTime values.")
        method = "GetEventsByDateRange"
    elif resource == "clips":
        parameters, method = {"FolderID": numeric_id(request.get("parent_id"))}, "GetClips"
    elif resource in READS:
        method, key, _ = READS[resource]
        parameters = {key: numeric_id(request.get("external_id"))}
    else:
        raise ValueError("Use a documented event, clip, agenda_item, related metadata or folder-clips resource.")
    session = Session(replace(source, namespace=namespace), context, bounds, transport)
    bundle, errors = None, []
    try:
        _, raw = session.call(method, parameters)
        bundle = parse_bundle(source, namespace, raw)
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
