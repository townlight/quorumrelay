"""Native Tyler public-row mapping, separate from the frozen compatibility reader."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from urllib.parse import urlsplit


_SOURCE_FIELDS = (
    "id", "meetingId", "recurringId", "meetingTitle", "meetingTypeId", "meetingTypeName",
    "startDateTime", "startTime", "endDateTime", "endTime", "newMeetingDate", "newMeetingTime",
    "isPublicVisibility", "canceled", "adjourned", "agendaStatus", "minutesStatus", "videoStatus",
    "agendaItemTitles",
)
_STATUS_FIELDS = ("canceled", "adjourned", "agendaStatus", "minutesStatus", "videoStatus")


def _source_day(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A visible Tyler meeting requires its supplied startDateTime.")
    if "T" not in value:
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            raise ValueError("A visible Tyler meeting has an invalid supplied startDateTime.") from None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.fromisoformat(value.split("T", 1)[0]).isoformat()
    except ValueError:
        raise ValueError("A visible Tyler meeting has an invalid supplied startDateTime.") from None


def meeting_row(source_url: str, raw: dict) -> tuple[dict, str] | None:
    """Map one public native row; return None for non-public visibility only."""
    source = urlsplit(source_url)
    if not source.hostname or not source.hostname.endswith(".meetingmanager.tylerapp.com"):
        raise ValueError("Tyler native rows require the configured public calendar host.")
    if not isinstance(raw, dict):
        raise ValueError("A Tyler calendar row is not an object.")
    # Only literal integer visibility 1 is public. No other visibility value is reinterpreted.
    if type(raw.get("isPublicVisibility")) is not int or raw["isPublicVisibility"] != 1:
        return None

    identity = raw.get("id")
    title = raw.get("meetingTitle")
    source_start = raw.get("startDateTime")
    if (not isinstance(identity, str) or not identity.strip() or identity != identity.strip()
            or any(ord(char) < 32 for char in identity) or len(identity) > 256):
        raise ValueError("A visible Tyler meeting requires its native string id.")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("A visible Tyler meeting requires its supplied meetingTitle.")
    day = _source_day(source_start)

    status = {key: deepcopy(raw[key]) for key in _STATUS_FIELDS if key in raw}
    supplied_titles = raw.get("agendaItemTitles")
    normalized = {
        "external_id": identity,
        "title": title,
        "meeting_date": day,
        "date_basis": "literal date component of supplied startDateTime",
        "source_start": source_start,
        "source_time": deepcopy(raw.get("startTime")),
        "source_end": deepcopy(raw.get("endDateTime")),
        "source_end_time": deepcopy(raw.get("endTime")),
        "source_new_meeting_date": deepcopy(raw.get("newMeetingDate")),
        "source_new_meeting_time": deepcopy(raw.get("newMeetingTime")),
        "source_meeting_id": deepcopy(raw.get("meetingId")),
        "source_recurring_id": deepcopy(raw.get("recurringId")),
        "source_meeting_type_id": deepcopy(raw.get("meetingTypeId")),
        "source_meeting_type_name": deepcopy(raw.get("meetingTypeName")),
        "source_status": status,
        "source_fields": {key: deepcopy(raw[key]) for key in _SOURCE_FIELDS if key in raw},
        "agenda_item_titles": deepcopy(supplied_titles),
        "agenda_items_availability": ("titles_supplied_without_native_item_ids"
                                      if isinstance(supplied_titles, list) else "not_supplied"),
        "location": deepcopy(raw.get("location")) if isinstance(raw.get("location"), str) else None,
        "url": source_url,
        "documents": [],
        "recordings": [],
        "time_zone_status": "source_literal_unverified",
    }
    return normalized, "meeting"


def calendar_rows(source_url: str, raw_rows) -> list[tuple[dict, dict, str]]:
    """Validate a native calendar/search array, excluding non-public visibility rows."""
    if not isinstance(raw_rows, list):
        raise ValueError("The Tyler public calendar response must be a JSON array.")
    result = []
    for raw in raw_rows:
        mapped = meeting_row(source_url, raw)
        if mapped is not None:
            normalized, record_type = mapped
            result.append((normalized, deepcopy(raw), record_type))
    return result
