"""Explicit additive mappings, separate from the original 34 compatibility readers."""

from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urljoin

from ..engine import canonical_hash
from ..models import CaptureBundle, Identity, Record, Source


def _url(source, value):
    if not isinstance(value, str) or not value.strip():
        return None
    result = urljoin(source.url, value)
    from .identification import validate_url
    try:
        validate_url(result)
    except ValueError:
        return None
    return result


def legistar_row(source: Source, raw: dict) -> tuple[dict, str]:
    if type(raw.get("EventId")) is not int:
        raise ValueError("The Legistar Events API requires a numeric EventId.")
    start = raw.get("EventDate")
    if not isinstance(start, str):
        raise ValueError("The Legistar Events API requires EventDate.")
    day = datetime.fromisoformat(start.replace("Z", "+00:00")).date().isoformat()
    documents = []
    for field, kind in (("EventAgendaFile", "agenda"), ("EventMinutesFile", "minutes")):
        if link := _url(source, raw.get(field)):
            documents.append({"kind": kind, "url": link})
    recordings = [{"url": link} for field in ("EventVideoPath", "EventMedia")
                  if (link := _url(source, raw.get(field)))]
    items = []
    for item in raw.get("EventItems") or []:
        if not isinstance(item, dict):
            continue
        # Keep supplied motion/vote values verbatim, never infer a vote from text.
        items.append({"external_id": str(item.get("EventItemId") or ""),
                      "title": item.get("EventItemTitle"),
                      "agenda_number": item.get("EventItemAgendaNumber"),
                      "source_fields": deepcopy(item)})
        for attachment in item.get("EventItemMatterAttachments") or []:
            if not isinstance(attachment, dict):
                continue
            if link := _url(source, attachment.get("MatterAttachmentHyperlink")):
                documents.append({"kind": "supporting_document", "url": link,
                                  "title": attachment.get("MatterAttachmentName"),
                                  "external_id": str(attachment.get("MatterAttachmentId") or ""),
                                  "agenda_item_external_id": str(item.get("EventItemId") or ""),
                                  "source_fields": deepcopy(attachment)})
    return {
        "external_id": str(raw["EventId"]),
        "title": str(raw.get("EventBodyName") or "Meeting"),
        "body": raw.get("EventBodyName"), "meeting_date": day,
        # EventDate is commonly midnight and EventTime is a separate source value.
        # Do not manufacture a zoned meeting instant from that pair.
        "source_date": start, "source_time": raw.get("EventTime"),
        "time_zone_status": "unknown", "location": raw.get("EventLocation"),
        "url": _url(source, raw.get("EventInSiteURL")) or source.url,
        "documents": documents, "recordings": recordings, "agenda_items": items,
        "agenda_items_availability": "supplied" if "EventItems" in raw else "absent",
        "source_status": {key: raw[key] for key in (
            "EventAgendaStatusId", "EventAgendaStatusName", "EventMinutesStatusId",
            "EventMinutesStatusName", "EventVideoStatus") if key in raw},
    }, "meeting"


def wistia_row(source: Source, raw: dict) -> tuple[dict, str]:
    identity = raw.get("hashed_id")
    if not isinstance(identity, str) or not identity:
        raise ValueError("Wistia account media requires hashed_id.")
    recordings = [{"url": f"https://fast.wistia.com/embed/medias/{identity}",
                   "duration_seconds": raw.get("duration"), "media_type": raw.get("type"),
                   "status": raw.get("status"), "thumbnail": raw.get("thumbnail")}]
    for asset in raw.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        if link := _url(source, asset.get("url")):
            recordings.append({"url": link, "asset_type": asset.get("type"),
                               "content_type": asset.get("content_type"),
                               "width": asset.get("width"), "height": asset.get("height"),
                               "byte_length": asset.get("file_size"), "source_fields": deepcopy(asset)})
    return {
        "external_id": identity, "title": raw.get("name") or "Media",
        "description": raw.get("description"),
        "url": f"https://fast.wistia.com/embed/medias/{identity}",
        "recordings": recordings,
        "time_zone_status": "unknown", "agenda_items_availability": "absent",
        # Upload time is not the meeting date.
        "source_created": raw.get("created"), "source_updated": raw.get("updated"),
    }, "recording"


def make_bundle(source: Source, namespace: str, content: bytes, input_format: str,
                rows: list[tuple[dict, dict, str]]) -> dict:
    captured = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    digest = hashlib.sha256(content).hexdigest()
    records = []
    for normalized, raw, record_type in rows:
        revision = {"kind": "not_supplied", "value": None}
        revision_keys = (("EventRowVersion", "EventLastModifiedUtc") if source.provider == "legistar"
                         else ("updated",) if source.provider == "wistia" else ())
        supplied = {key: deepcopy(raw[key]) for key in revision_keys if key in raw}
        if supplied:
            revision = {"kind": "provider_supplied", "value": supplied}
        relations = tuple(
            {"relation": kind, "value": deepcopy(value)}
            for field, kind in (("documents", "document"), ("recordings", "recording"),
                                ("agenda_items", "agenda_item"))
            for value in normalized.get(field, [])
        )
        records.append(Record(
            Identity(source.provider, namespace, record_type, normalized["external_id"],
                     derivation="provider_identifier",
                     stability="Provider-issued identifier within the configured namespace."),
            normalized, source.url,
            tuple(dict.fromkeys([source.url, normalized.get("url") or source.url])),
            digest, captured, canonical_hash(normalized), revision, deepcopy(raw), relations,
        ))
    try:
        original = json.loads(content)
    except (ValueError, UnicodeError):
        original = None
    capture = {
        "sha256": digest, "captured_at": captured, "byte_length": len(content),
        "source_url": source.url, "input_format": input_format,
        "content_base64": base64.b64encode(content).decode("ascii"), "original_values": original,
    }
    configured = Source.from_dict({**source.public_dict(), "namespace": namespace,
                                   "input_format": input_format})
    legacy = {
        "version": 1,
        "source": {"connector": source.provider, "url": source.url, "namespace": namespace,
                   "format": input_format, "sha256": digest},
        "meetings": [deepcopy(record.normalized) for record in records
                     if record.identity.record_type == "meeting"],
    }
    return CaptureBundle(configured, tuple(records), capture, legacy,
                         extensions={"compatibility_origin": "native_projection",
                                     "compatibility": "projected additive API format; not a legacy export input"}
                         ).public_dict()


def parse_native(source, namespace, content, input_format):
    if input_format == "granicus-listing-html":
        from .granicus import listing_rows
        bundle = make_bundle(source, namespace, content, input_format, listing_rows(source, content))
        for record in bundle["records"]:
            if record["identity"]["external_id"].startswith("derived:"):
                record["identity"]["derivation"] = "configured_url_date_title"
                record["identity"]["stability"] = (
                    "Fallback for an attachment-free listing row; changes if source URL, date or title changes.")
        return bundle
    raw = json.loads(content)
    if input_format == "wistia-caption-json":
        return caption_bundle(source, namespace, content, raw)
    if input_format in {"legistar-event-json", "wistia-media-detail-json"}:
        if not isinstance(raw, dict):
            raise ValueError("The provider detail response must be a JSON object.")
        mapper = legistar_row if input_format == "legistar-event-json" else wistia_row
        normalized, kind = mapper(source, raw)
        return make_bundle(source, namespace, content, input_format, [(normalized, raw, kind)])
    if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
        raise ValueError("The provider API response must be a JSON array of objects.")
    mapper = {"legistar-events-json": legistar_row,
              "wistia-api-media-json": wistia_row}[input_format]
    rows = []
    for item in raw:
        normalized, kind = mapper(source, item)
        rows.append((normalized, item, kind))
    return make_bundle(source, namespace, content, input_format, rows)


def caption_bundle(source, namespace, content, original):
    """Map only supplied Wistia caption tracks/cues, including nullable payloads."""
    tracks = original if isinstance(original, list) else [original]
    rows = []
    for raw in tracks:
        if (not isinstance(raw, dict) or any(not isinstance(raw.get(key), str) or not raw[key]
                for key in ("id", "media_id", "language"))):
            raise ValueError("A caption track requires its supplied ID, parent media ID and language.")
        rows.append(({"external_id": raw["id"], "title": "Captions (" + raw["language"] + ")",
                      "language": raw["language"], "media_id": raw["media_id"],
                      "url": "https://fast.wistia.com/embed/medias/" + raw["media_id"],
                      "source_status": {"is_draft": raw.get("is_draft")},
                      "time_zone_status": "unknown", "agenda_items_availability": "absent"}, raw, "transcript"))
    bundle = make_bundle(source, namespace, content, "wistia-caption-json", rows)
    for record in bundle["records"]:
        raw = record["original"]
        parent = {"provider": source.provider, "namespace": namespace, "record_type": "recording",
                  "external_id": raw["media_id"], "parent": None}
        record["identity"]["parent"] = parent
        record["relationships"] = [{"relation": "recording", "identity": parent,
                                    "value": {"url": record["normalized"]["url"]}}]
        record["source_revision"] = {"kind": "provider_supplied", "value": {"version": raw.get("version")}}
        segments = raw.get("segments")
        text = []
        if segments is not None:
            if not isinstance(segments, list):
                raise ValueError("Supplied caption cues must be an array or null.")
            for index, segment in enumerate(segments):
                if (not isinstance(segment, dict) or not isinstance(segment.get("text"), str)
                        or type(segment.get("start_ms")) is not int or type(segment.get("end_ms")) is not int
                        or not 0 <= segment["start_ms"] <= segment["end_ms"]):
                    raise ValueError("Supplied caption cues require valid text and millisecond bounds.")
                text.append({**deepcopy(segment), "field": f"segments[{index}]",
                             "timestamp_seconds": segment["start_ms"] / 1000,
                             "citation_url": record["normalized"]["url"], "completeness": "complete"})
        if not text and isinstance(raw.get("text"), str) and raw["text"]:
            text.append({"field": "caption_srt", "text": raw["text"], "format": "srt",
                         "citation_url": record["normalized"]["url"], "completeness": "complete"})
        if not text:
            text.append({"field": "caption_payload", "completeness": "unavailable"})
        record["text"] = text
    return bundle
