"""Preserve supplied CHAMP item hierarchy, documents and timeline references."""

from copy import deepcopy
from html.parser import HTMLParser
from urllib.parse import urlsplit

from ..engine import canonical_hash

class DescriptionText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden, self.parts = 0, []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _positive(value):
    return type(value) is int and value > 0


def _items(original, event, documents):
    agenda = original.get("Agenda")
    if not isinstance(agenda, dict) or not isinstance(agenda.get("AgendaItems"), list):
        return None
    items, known = [], set()
    pending = [(row, None) for row in reversed(agenda["AgendaItems"])]
    while pending:
        raw, parent = pending.pop()
        if (not isinstance(raw, dict) or not _positive(raw.get("CustomerAgendaItemID"))
                or type(raw.get("CustomerEventID")) is not int
                or raw.get("CustomerEventID") != event or not isinstance(raw.get("Title"), str)
                or not raw["Title"].strip()):
            raise ValueError("Item identity/title/event binding is invalid.")
        identity = raw["CustomerAgendaItemID"]
        if (identity in known or type(raw.get("OrderParentID")) is not int
                or raw.get("OrderParentID") != (parent or 0)):
            raise ValueError("Item identity/parent binding is ambiguous.")
        known.add(identity)
        description = raw.get("Description")
        visible = DescriptionText()
        if isinstance(description, str):
            visible.feed(description)
        attached = []
        for attachment in raw.get("Attachments") or []:
            if (not isinstance(attachment, dict) or not _positive(attachment.get("CustomerMediaID"))
                    or type(attachment.get("CustomerEventID")) is not int
                    or not _positive(attachment.get("MediaTargetID"))
                    or attachment.get("CustomerEventID") != event
                    or attachment.get("MediaTargetID") != identity):
                continue
            location, filename = attachment.get("MediaFileLocation"), attachment.get("MediaFileName")
            if not isinstance(location, str) or not isinstance(filename, str):
                continue
            matches = [d for d in documents if isinstance(d, dict) and isinstance(d.get("url"), str)
                       and urlsplit(d["url"]).path.endswith("/" + location + "/" + filename)]
            if len(matches) == 1:
                attached.append({**deepcopy(matches[0]), "external_id": str(attachment["CustomerMediaID"]),
                                 "agenda_item_external_id": str(identity), "source_fields": deepcopy(attachment)})
        item = {"external_id": str(identity), "title": raw["Title"].strip(),
                "parent_external_id": str(parent) if parent else None,
                "meeting_external_id": str(event), "sequence": len(items),
                "source_ordinal": raw.get("OrderOrdinal"), "description": " ".join(" ".join(visible.parts).split()),
                "documents": attached, "timeline": [],
                "source_fields": {k: deepcopy(v) for k, v in raw.items() if k != "Children"}}
        items.append(item)
        children = raw.get("Children", [])
        if not isinstance(children, list):
            raise ValueError("Item children must be an explicit list.")
        pending.extend((child, identity) for child in reversed(children))
    by_id = {item["external_id"]: item for item in items}
    unassociated = []
    for timeline in original.get("Timeline") or []:
        # The captured vendor player expressly maps ContainerTypeID 2 to Agenda Item.
        if (not isinstance(timeline, dict) or type(timeline.get("ContainerTypeID")) is not int
                or timeline.get("ContainerTypeID") != 2 or not _positive(timeline.get("ContainerID"))
                or type(timeline.get("CustomerEventID")) is not int
                or timeline.get("CustomerEventID") != event
                or not _positive(timeline.get("CustomerTimelineID"))
                or str(timeline.get("ContainerID")) not in by_id):
            unassociated.append(deepcopy(timeline))
            continue
        start, end = timeline.get("TimeStartSeconds"), timeline.get("TimeEndSeconds")
        if type(start) is not int or type(end) is not int or not 0 <= start <= end:
            unassociated.append(deepcopy(timeline))
            continue
        by_id[str(timeline["ContainerID"])]["timeline"].append({
            "external_id": str(timeline["CustomerTimelineID"]), "start_seconds": start,
            "end_seconds": end, "units": "seconds", "source_fields": deepcopy(timeline)})
    return items, unassociated


def enrich_bundle(bundle):
    enriched = deepcopy(bundle)
    for record in enriched.get("records", []):
        identity, raw, normalized = record.get("identity", {}), record.get("original"), record.get("normalized")
        if identity.get("provider") != "champ" or not isinstance(raw, dict) or not isinstance(normalized, dict):
            continue
        if not isinstance(raw.get("Event"), dict) or not isinstance(raw.get("Customer"), dict):
            continue
        event = raw["Event"].get("CustomerEventID")
        customer = raw["Customer"].get("CustomerAccessID")
        player = urlsplit(normalized.get("url", ""))
        if (not _positive(event) or identity.get("external_id") != str(event)
                or not isinstance(customer, str) or player.scheme != "https"
                or player.hostname != "play.champds.com" or player.port not in {None, 443}
                or player.path.casefold() != f"/{customer}/event/{event}".casefold()):
            continue
        board = raw.get("Board")
        if (isinstance(board, dict) and _positive(board.get("CustomerBoardID"))
                and type(raw["Event"].get("CustomerBoardID")) is int
                and board["CustomerBoardID"] == raw["Event"]["CustomerBoardID"]
                and isinstance(board.get("BoardName"), str) and board["BoardName"].strip()):
            normalized["body"] = board["BoardName"]
            normalized["body_external_id"] = str(board["CustomerBoardID"])
        try:
            result = _items(raw, event, normalized.get("documents", []))
        except (ValueError, TypeError):
            normalized["agenda_relationships_availability"] = "unmapped_ambiguous_source_binding"
            record["normalized_sha256"] = canonical_hash(normalized)
            continue
        if result is None:
            record["normalized_sha256"] = canonical_hash(normalized)
            continue
        items, unassociated = result
        normalized.update(agenda_items=items, agenda_relationships_availability="supplied_native_items",
                          unassociated_timeline=unassociated)
        record["relationships"] = [r for r in record.get("relationships", []) if r.get("relation") != "agenda_item"]
        record["relationships"].extend({"relation": "agenda_item", "value": deepcopy(item)} for item in items)
        record["text"] = [s for s in record.get("text", [])
                          if s.get("provenance", {}).get("method") != "champ_supplied_item_description"]
        for item in items:
            if not item["description"]:
                continue
            segment = {"field": "agenda_items." + item["external_id"] + ".description",
                       "text": item["description"], "citation_url": normalized["url"],
                       "provenance": {"method": "champ_supplied_item_description",
                           "capture_sha256": record.get("capture_sha256"),
                           "agenda_item_external_id": item["external_id"]}, "completeness": "supplied_field"}
            if len(item["timeline"]) == 1:
                seconds = item["timeline"][0]["start_seconds"]
                segment["timestamp"] = f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
            record["text"].append(segment)
        record["normalized_sha256"] = canonical_hash(normalized)
    return enriched
