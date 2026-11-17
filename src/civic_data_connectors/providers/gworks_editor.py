"""Meeting detail from the pinned FrontDesk development editor contract."""

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import re
from time import monotonic
from urllib.parse import urlsplit

from ..models import Error, OperationResult
from .native import make_bundle

FORMAT = "gworks-editor-meeting-json"
ORIGIN = "https://api.dev.gworks.cloud"


def binding(source):
    parsed = urlsplit(source.url)
    match = re.fullmatch(r"/cms/secure/city/meeting/([1-9][0-9]{0,18})", parsed.path)
    city = source.options.get("gworks_city_id")
    if (source.provider != "gworks" or parsed.scheme != "https"
            or parsed.netloc != "api.dev.gworks.cloud" or parsed.query or parsed.fragment
            or not match or not isinstance(city, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", city)):
        raise ValueError("Select the documented development meeting URL and an explicit city ID.")
    return f"//api.dev.gworks.cloud/city/{city}/cms", match[1]


def namespace(source):
    return binding(source)[0]


def parse_bundle(source, bound_namespace, content):
    expected_namespace, meeting = binding(source)
    if expected_namespace != bound_namespace:
        raise ValueError("The selected development city namespace does not match.")
    raw = json.loads(content)
    if (not isinstance(raw, dict) or type(raw.get("cms_meeting.id")) not in {int, str}
            or str(raw["cms_meeting.id"]) != meeting
            or not isinstance(raw.get("cms_meeting.title"), str) or not raw["cms_meeting.title"].strip()
            or not isinstance(raw.get("cms_meeting.data"), list)
            or not isinstance(raw.get("cms_meeting.files"), list)):
        raise ValueError("The editor requires one matching flattened meeting object with section/file arrays.")
    flags = {key: raw.get("cms_meeting." + key)
             for key in ("agenda_published_fl", "minutes_published_fl", "archived_fl", "template_fl")}
    if any(value is not None and type(value) is not bool for value in flags.values()):
        raise ValueError("Supplied publication flags must be booleans.")
    timestamp = raw.get("cms_meeting.meeting_ts")
    start = None
    if isinstance(timestamp, str) and re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", timestamp):
        try:
            start = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            pass
    digest = sha256(content).hexdigest()
    items, texts = [], []
    for section_index, section in enumerate(raw["cms_meeting.data"]):
        if (not isinstance(section, dict) or not isinstance(section.get("title"), str)
                or not isinstance(section.get("items"), list)):
            raise ValueError("Each editor section requires a title and ordered item array.")
        parent = f"capture:{digest}:section:{section_index}"
        items.append({"external_id": parent, "native_item_id": None, "meeting_external_id": meeting,
                      "parent_item_external_id": None, "sequence": len(items), "title": section["title"],
                      "source_fields": deepcopy(section), "documents": [],
                      "identity_derivation": "capture_local_display_position"})
        for item_index, item in enumerate(section["items"]):
            if (not isinstance(item, dict) or not isinstance(item.get("value"), str)
                    or not isinstance(item.get("minute"), str)
                    or not isinstance(item.get("files"), list)):
                raise ValueError("Each editor item requires agenda/minutes text and a file descriptor array.")
            identity = f"{parent}:item:{item_index}"
            items.append({"external_id": identity, "native_item_id": None, "meeting_external_id": meeting,
                          "parent_item_external_id": parent, "sequence": len(items), "title": item["value"],
                          "description": item["value"], "minutes": item["minute"], "documents": [],
                          "source_files": deepcopy(item["files"]), "source_fields": deepcopy(item),
                          "identity_derivation": "capture_local_display_position"})
            for field, value in (("description", item["value"]), ("minutes", item["minute"])):
                if value:
                    texts.append({"field": f"agenda_items.{identity}.{field}", "text": value,
                                  "citation_url": source.url, "completeness": "complete",
                                  "provenance": {"method": "gworks_editor_supplied_text",
                                                 "capture_sha256": digest, "scope": "selected_meeting_item"}})
    normalized = {
        "external_id": meeting, "title": raw["cms_meeting.title"], "url": source.url,
        "location": raw.get("cms_meeting.location"), "source_timestamp": timestamp,
        "scheduled_start": start.isoformat() if start else None,
        "meeting_date": start.date().isoformat() if start else None,
        "time_zone_status": "supplied_offset" if start and start.utcoffset() is not None else "unknown",
        "source_status": flags, "source_updated": raw.get("cms_meeting.mod_ts"),
        "source_files": deepcopy(raw["cms_meeting.files"]), "documents": [], "agenda_items": items,
        "agenda_items_availability": "capture_local_positions",
        "city_binding": "configured_city_not_asserted_by_response",
        "contract_environment": "development_editor",
    }
    bundle = make_bundle(source, bound_namespace, content, FORMAT, [(normalized, raw, "meeting")])
    bundle["records"][0]["text"] = texts
    return bundle


def fetch(source, bound_namespace, request, bounds, context, transport):
    _, meeting = binding(source)
    if (any(key in request for key in ("related", "caption_language", "parent_id", "record_type"))
            or request.get("external_id", meeting) != meeting or bounds.checkpoint
            or bounds.date_from or bounds.date_to or source.body):
        raise ValueError("Select one exact editor meeting; no catalog traversal or additional filters.")
    config = context.credentials.get("gworks")
    allowed = config.get("allowed_namespaces") if isinstance(config, dict) else None
    token = config.get("token") if isinstance(config, dict) else None
    if (not isinstance(config, dict) or not context.tenant or config.get("tenant") != context.tenant
            or config.get("origin") != ORIGIN or config.get("city_id") != source.options["gworks_city_id"]
            or not isinstance(allowed, (list, tuple, set, frozenset)) or bound_namespace not in allowed
            or not isinstance(token, str) or not token or len(token) > 16384
            or any(ord(char) <= 32 or ord(char) == 127 for char in token)):
        return OperationResult("failed", errors=(Error("credentials_required",
            "A trusted development-origin, tenant and city scoped credential is required."),),
            operation_id=context.operation_id)
    if context.check_cancelled():
        return OperationResult("cancelled", operation_id=context.operation_id)
    deadline = monotonic() + bounds.deadline_seconds
    limit = min(bounds.parser_bytes, bounds.transfer_bytes)
    try:
        response = transport.request(source.url, method="GET", headers={
            "Accept": "application/json", "Authorization": "Bearer " + token},
            byte_limit=limit, deadline_seconds=bounds.deadline_seconds,
            allowed_origins=(ORIGIN,), allow_redirects=False)
        if context.check_cancelled():
            return OperationResult("cancelled", operation_id=context.operation_id)
        if response.url != source.url or len(response.content) > limit or monotonic() >= deadline:
            raise ValueError("The selected response exceeded its URL, byte or deadline boundary.")
        if response.status in {401, 403}:
            return OperationResult("failed", errors=(Error("permission_denied",
                "The provider denied the selected meeting read.", source=source.url),),
                operation_id=context.operation_id)
        if (response.status != 200
                or response.content_type.split(";", 1)[0].strip().lower() != "application/json"):
            raise ValueError("The selected meeting did not return JSON.")
        bundle = parse_bundle(source, bound_namespace, response.content)
        if monotonic() >= deadline or bounds.max_records < 1:
            raise ValueError("The selected meeting exceeds configured bounds.")
        if context.check_cancelled():
            return OperationResult("cancelled", operation_id=context.operation_id)
        return OperationResult("completed", bundle, coverage={
            "scope": "one selected development-editor meeting", "catalog_complete": False,
            "source_complete": False, "returned_records": 1,
            "city_binding": "trusted_configuration", "native_item_ids": False},
            operation_id=context.operation_id)
    except (ValueError, TypeError, KeyError, OSError):
        return OperationResult("failed", errors=(Error("gworks_editor_unverified",
            "The selected editor meeting response could not be verified.", source=source.url),),
            operation_id=context.operation_id)

