"""Saved secure-calendar response, distinct from FrontDesk's public JSON."""

from datetime import date, datetime
import json
import re

from .native import make_bundle

FORMAT = "gworks-secure-calendar-json"
URL = "https://api.gworks.cloud/cms/secure/city/meeting/list"


def namespace(source):
    city = source.options.get("gworks_city_id") if isinstance(source.options, dict) else None
    if source.url != URL or not isinstance(city, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", city):
        raise ValueError("Saved secure calendar requires the exact API URL and an explicit configured city ID.")
    return f"//files.frontdeskgworks.com/city/{city}/cms/data.json"


def parse_bundle(source, bound_namespace, content):
    if source.provider != "gworks" or namespace(source) != bound_namespace:
        raise ValueError("The saved calendar city namespace does not match its configuration.")
    value = json.loads(content)
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        raise ValueError("The secure calendar response requires its declared data array.")
    rows, seen = [], set()
    for raw in value["data"]:
        if (not isinstance(raw, dict) or type(raw.get("cms_meeting.id")) is not int
                or not 0 < raw["cms_meeting.id"] < 10 ** 19 or raw["cms_meeting.id"] in seen
                or not isinstance(raw.get("cms_meeting.title"), str) or not raw["cms_meeting.title"].strip()
                or type(raw.get("cms_meeting.meeting_ts")) not in {str, int}):
            raise ValueError("A secure calendar row requires unambiguous native meeting identity, title and supplied time.")
        seen.add(raw["cms_meeting.id"])
        flags = {key: raw.get("cms_meeting." + key) for key in ("agenda_published_fl", "minutes_published_fl")}
        if any(v is not None and type(v) is not bool for v in flags.values()):
            raise ValueError("Secure publication flags must be supplied booleans or unknown.")
        timestamp = raw["cms_meeting.meeting_ts"]
        start, day = None, None
        if isinstance(timestamp, str):
            try:
                if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", timestamp):
                    day = date.fromisoformat(timestamp).isoformat()
                elif re.match(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}", timestamp):
                    start = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    day = start.date().isoformat()
            except ValueError:
                pass
        normalized = {"external_id": str(raw["cms_meeting.id"]), "title": raw["cms_meeting.title"],
                      "source_timestamp": timestamp, "scheduled_start": start.isoformat() if start else None,
                      "meeting_date": day, "time_zone_status": "unknown",
                      "source_status": flags, "url": source.url, "documents": [],
                      "agenda_items_availability": "not_supplied",
                      "city_binding": "configured_city_not_asserted_by_response",
                      "timestamp_semantics": "ISO_string_only_no_numeric_epoch_unit_inference"}
        rows.append((normalized, raw, "meeting"))
    # Publication flags do not themselves provide document locators, staff URLs,
    # item IDs, pagination, date-window provenance or a complete catalog.
    return make_bundle(source, bound_namespace, content, FORMAT, rows)
