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
    if input_format == "boardable-public-meetings-json":
        from .boardable import _meeting_row
        payload = json.loads(content)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("The saved Boardable listing must contain a data array.")
        if any(not isinstance(row, dict) for row in payload["data"]):
            raise ValueError("The saved Boardable listing contains an invalid row.")
        return make_bundle(source, namespace, content, input_format,
                           [_meeting_row(source, row) for row in payload["data"]])
    if input_format == "clerkbase-public-tree-html":
        from .clerkbase_listing import listing_bundle
        return listing_bundle(source, namespace, content)
    if input_format == "clerkbase-search-html":
        from .clerkbase_search import _search_rows, mark_supplied_url_identities
        rows, _ = _search_rows(source, content)
        return mark_supplied_url_identities(make_bundle(source, namespace, content, input_format, rows))
    if input_format == "iqm2-public-search-html":
        from .iqm2_search import _rows
        rows, _ = _rows(source, content)
        return make_bundle(source, namespace, content, input_format, rows)
    if input_format == "utah-public-search-html":
        from .utah_public import search_rows
        return make_bundle(source, namespace, content, input_format, search_rows(source, content))
    if input_format == "civicplus-search-json":
        from .civicplus_search import search_bundle
        return search_bundle(source, namespace, content)
    if input_format in {"agendaquick-public-listing-html", "agendaquick-item-search-html"}:
        from .agendaquick import listing_rows, search_rows
        mapper = listing_rows if input_format == "agendaquick-public-listing-html" else search_rows
        return make_bundle(source, namespace, content, input_format, mapper(source, content))
    if input_format == "towncloud-public-listing-json":
        from .towncloud_public import listing_rows
        return make_bundle(source, namespace, content, input_format, listing_rows(source, content))
    if input_format == "digital-towpath-listing-html":
        from .towpath import listing_bundle
        return listing_bundle(source, namespace, content)
    if input_format == "onbase-public-listing-html":
        from .onbase import listing_rows
        return make_bundle(source, namespace, content, input_format, listing_rows(source, content))
    if input_format == "swagit-listing-html":
        from .swagit import listing_rows
        return make_bundle(source, namespace, content, input_format, listing_rows(source, content))
    if input_format == "civicweb-detail-html":
        from .civicweb import detail_bundle
        return detail_bundle(source, namespace, content)
    if input_format.startswith("telvue-connect-") or input_format == "essential-multimedia-json":
        from .account_reads import essential_bundle, telvue_bundle
        return (essential_bundle(source, namespace, content) if input_format == "essential-multimedia-json"
                else telvue_bundle(source, namespace, content, input_format))
    if input_format == "novus-public-listing-html":
        from .novus import listing_bundle
        return listing_bundle(source, namespace, content)[0]
    if input_format == "laserfiche-repository-entries-json":
        from .repository import entry_bundle
        return entry_bundle(source, namespace, content)
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
    if input_format in {"legistar-votes-json", "legistar-rollcalls-json"}:
        return legistar_related_bundle(source, namespace, content, raw, input_format)
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


def legistar_related_bundle(source, namespace, content, original, input_format):
    """Preserve supplied per-person votes and attendance, never infer a tally."""
    from urllib.parse import urlsplit
    from .discovery import _api_source
    prefix, kind, route = (("Vote", "vote", "Votes") if input_format == "legistar-votes-json"
                           else ("RollCall", "roll_call", "RollCalls"))
    entries = original if isinstance(original, list) else [original]
    rows = []
    for raw in entries:
        if (not isinstance(raw, dict) or any(type(raw.get(prefix + field)) is not int
                for field in ("Id", "EventItemId", "PersonId", "ValueId"))
                or any(raw[prefix + field] <= 0 for field in ("Id", "EventItemId"))):
            raise ValueError("A related Legistar record requires supplied IDs and its parent item.")
        base = _api_source(source).removesuffix("/Events")
        citation = f"{base}/EventItems/{raw[prefix + 'EventItemId']}/{route}/{raw[prefix + 'Id']}"
        # The citation is fixed from the validated configured tenant, never a response URL.
        if urlsplit(citation).hostname != "webapi.legistar.com":
            raise ValueError("Invalid related-record origin.")
        rows.append(({"external_id": str(raw[prefix + "Id"]),
                      "title": raw.get(prefix + "PersonName") or kind,
                      "person_id": str(raw[prefix + "PersonId"]),
                      "person_name": raw.get(prefix + "PersonName"),
                      "value_id": str(raw[prefix + "ValueId"]), "value_name": raw.get(prefix + "ValueName"),
                      "result": raw.get(prefix + "Result"), "sort": raw.get(prefix + "Sort"),
                      "agenda_item_external_id": str(raw[prefix + "EventItemId"]),
                      "url": citation, "time_zone_status": "unknown"}, raw, kind))
    bundle = make_bundle(source, namespace, content, input_format, rows)
    for record in bundle["records"]:
        parent = {"provider": source.provider, "namespace": namespace, "record_type": "agenda_item",
                  "external_id": record["normalized"]["agenda_item_external_id"], "parent": None}
        record["identity"]["parent"] = parent
        record["relationships"] = [{"relation": "agenda_item", "identity": parent}]
        supplied = {key: deepcopy(record["original"][key]) for key in
                    (prefix + "RowVersion", prefix + "LastModifiedUtc") if key in record["original"]}
        record["source_revision"] = {"kind": "provider_supplied" if supplied else "not_supplied",
                                     "value": supplied or None}
    return bundle


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
