"""Pinned Boardable weekly recurrence creation and whole-series metadata updates."""

from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
import re
from time import monotonic

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteCancelled, WriteChange, WriteFailure
from .boardable_meeting_write import (
    BoardableMeetingWriteAdapter, _native_id, _change_id, _canonical, _parse_date,
    _parse_clock, _validate_timezone, _local_utc, _utc_text, _parse_server_instant,
    _validate_dates,
    _normalize_meeting, _scrub, _falseish, _text, _check_json_bounds, _check_size,
    _check_prepared_size, _serialized, _PRIVATE_KEYS,
)


_ALLOWED_CREATE = {"title", "description", "location", "timezone", "dates", "recurrence"}
_ALLOWED_UPDATE = {"title", "description", "location"}
_SERIES_FLAGS = (
    "public_member_dashboard", "public_page", "published", "published_level",
    "minutes_published", "enable_recording", "enable_transcription", "enable_ai_summary",
    "starred_public_page", "video_conference_enabled",
)


def _persisted_id(value):
    if isinstance(value, bool):
        raise ValueError("A bounded positive native Boardable identity is required.")
    if type(value) is int:
        return _native_id(value)
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value):
        return int(value)
    raise ValueError("A bounded positive native Boardable identity is required.")


def _series_grant_ids(config):
    grants = config.get("series_ids")
    if not isinstance(grants, (list, tuple, set, frozenset)) or not grants:
        raise WriteFailure("permission_denied", "An explicit Boardable series_ids grant is required.")
    result = set()
    for value in grants:
        if isinstance(value, bool):
            raise WriteFailure("permission_denied", "Boardable series grants cannot contain booleans.")
        if type(value) is int:
            result.add(_native_id(value))
        elif isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value):
            result.add(int(value))
        else:
            raise WriteFailure("permission_denied", "Boardable series grants require positive numeric IDs or decimal strings.")
    if not result:
        raise WriteFailure("permission_denied", "At least one explicit Boardable series grant is required.")
    return result


def _unwrap_meeting(value):
    if isinstance(value, dict) and "data" in value:
        raise ValueError("Unsupported Boardable data envelope; expected the raw meeting object or {meeting}.")
    if isinstance(value, dict) and isinstance(value.get("meeting"), dict):
        value = value["meeting"]
    return value


def _series_response_identity(raw, config, source_url, *, expected_id=None, expected_url=None, expected_series_id=None):
    meeting = _unwrap_meeting(raw)
    if not isinstance(meeting, dict):
        raise ValueError("The Boardable series response is not an object.")
    identity = _native_id(meeting.get("id"))
    if expected_id is not None and identity != expected_id:
        raise ValueError("The Boardable series response identified the wrong meeting.")
    organization_id = _native_id(meeting.get("organization_id"))
    if organization_id != config["organization_id"]:
        raise ValueError("The Boardable series response belongs to the wrong organization.")
    url, slug = _canonical(source_url, meeting.get("url"))
    if meeting.get("slug") != slug:
        raise ValueError("The Boardable series response URL and slug disagree.")
    if expected_url is not None and url != expected_url:
        raise ValueError("The Boardable series response URL differs from the exact requested URL.")
    series = meeting.get("series")
    if not isinstance(series, dict):
        raise ValueError("The Boardable series response lacks its embedded series object.")
    top_series_id = _native_id(meeting.get("series_id"))
    nested_series_id = _native_id(series.get("id"))
    if top_series_id != nested_series_id:
        raise ValueError("The Boardable series response repeats conflicting series IDs.")
    if _native_id(series.get("organization_id")) != config["organization_id"]:
        raise ValueError("The embedded Boardable series belongs to the wrong organization.")
    original_id = _native_id(series.get("original_meeting_id"))
    leader_id = _native_id(series.get("meeting_invite_leader_id"))
    if original_id != identity or leader_id != identity:
        raise ValueError("The Boardable series original meeting or leader binding is inconsistent.")
    if expected_series_id is not None and nested_series_id != expected_series_id:
        raise ValueError("The Boardable series response identified the wrong series.")
    return identity, url, slug, nested_series_id, series


def _generate_weekly_schedule(initial_date_text, end_date_text, timezone_name, from_text, to_text, bounds):
    _validate_timezone(timezone_name)
    initial = _parse_date(initial_date_text)
    ending = _parse_date(end_date_text)
    if ending < initial:
        raise ValueError("The Boardable recurrence end date precedes its first date.")
    if (ending - initial).days > 366:
        raise ValueError("The Boardable recurrence exceeds the bounded 366-day span.")
    from_hour, from_minute, from_norm = _parse_clock(from_text)
    to_hour, to_minute, to_norm = _parse_clock(to_text)
    maximum = min(52, bounds.max_records)
    if maximum < 2:
        raise ValueError("The Boardable recurrence requires room for at least two occurrences.")
    result, day = [], initial
    while day <= ending:
        start = _local_utc(day, from_hour, from_minute, timezone_name)
        end = _local_utc(day, to_hour, to_minute, timezone_name)
        if end <= start:
            raise ValueError("Each Boardable occurrence must end after it starts.")
        result.append({
            "date": day.strftime("%m/%d/%Y"),
            "from": from_norm,
            "to": to_norm,
            "timezone": timezone_name,
            "start": _utc_text(start),
            "end": _utc_text(end),
            "recurrence_id": start.strftime("%Y%m%dT%H%M%SZ"),
        })
        if len(result) > maximum:
            raise ValueError("The Boardable recurrence exceeds the bounded occurrence count.")
        day += timedelta(days=7)
    if len(result) < 2:
        raise ValueError("The Boardable recurrence requires at least two occurrences.")
    return result


def _series_data_schedule(series, bounds):
    data = series.get("data") if isinstance(series, dict) else None
    if not isinstance(data, dict):
        raise ValueError("The embedded Boardable series lacks its saved form data.")
    if data.get("repeat_period") != "week":
        raise WriteFailure("mapping_unverified", "Only the captured weekly Boardable recurrence is mapped.")
    interval = data.get("weekly_interval")
    if isinstance(interval, bool) or str(interval) != "1":
        raise WriteFailure("mapping_unverified", "Only the captured weekly Boardable interval is mapped.")
    timezone_name = _validate_timezone(data.get("timezone"))
    dates = data.get("dates")
    if not isinstance(dates, list) or len(dates) != 1 or not isinstance(dates[0], dict):
        raise ValueError("The embedded Boardable series must contain exactly one initial date.")
    initial = dates[0].get("date")
    if data.get("series_date") != initial:
        raise ValueError("The embedded Boardable series initial date is inconsistent.")
    if dates[0].get("from") != data.get("series_from") or dates[0].get("to") != data.get("series_to"):
        raise ValueError("The embedded Boardable series time fields are inconsistent.")
    return _generate_weekly_schedule(
        initial, data.get("series_ends"), timezone_name,
        data.get("series_from"), data.get("series_to"), bounds,
    )


def _normalize_series_data(data):
    if not isinstance(data, dict):
        raise ValueError("The embedded Boardable series data is not an object.")
    result = _scrub(deepcopy(data))
    for key in ("remote_url", "remote_url_description"):
        value = result.get(key)
        result[key] = None if _falseish(value) else value
    for key in (
        "disable_remote_rsvp", "enable_recording", "enable_transcription", "enable_ai_summary",
        "notify", "public_member_dashboard", "public_page",
    ):
        if key in result:
            result[key] = not _falseish(result[key])
    result["video_conference_enabled"] = not _falseish(result.get("video_conference_enabled"))
    return result


def _normalize_series_object(raw, config, series_id, original_id):
    if not isinstance(raw, dict):
        raise ValueError("The embedded Boardable series is not an object.")
    nested_id = _native_id(raw.get("id"))
    if nested_id != series_id:
        raise ValueError("The embedded Boardable series ID is inconsistent.")
    organization_id = _native_id(raw.get("organization_id"))
    if organization_id != config["organization_id"]:
        raise ValueError("The embedded Boardable series belongs to the wrong organization.")
    embedded_original = _native_id(raw.get("original_meeting_id"))
    if embedded_original != original_id:
        raise ValueError("The embedded Boardable series original meeting is inconsistent.")
    leader_id = _native_id(raw.get("meeting_invite_leader_id"))
    if leader_id != original_id:
        raise ValueError("The embedded Boardable series leader is not the original meeting.")
    result = {
        "id": nested_id,
        "organization_id": organization_id,
        "original_meeting_id": embedded_original,
        "meeting_invite_leader_id": leader_id,
        "create_in_progress": bool(raw.get("create_in_progress")),
        "publish_in_progress": bool(raw.get("publish_in_progress")),
    }
    for key in ("title", "description"):
        if key in raw:
            result[key] = _scrub(raw[key])
    result["data"] = _normalize_series_data(raw.get("data"))
    handled = {
        "id", "organization_id", "original_meeting_id", "meeting_invite_leader_id",
        "create_in_progress", "publish_in_progress", "title", "description", "data",
        "organization", "created_at", "updated_at", "uuid",
    }
    for key, value in raw.items():
        if key in handled or (isinstance(key, str) and key.lower() in _PRIVATE_KEYS):
            continue
        result[key] = _scrub(value)
    return result


def _normalize_previous_meeting(raw, config, series_id):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("The embedded Boardable previous meeting is not an object.")
    result = {"id": _native_id(raw.get("id"))}
    if "organization_id" in raw:
        organization_id = _native_id(raw.get("organization_id"))
        if organization_id != config["organization_id"]:
            raise ValueError("The embedded Boardable previous meeting belongs to the wrong organization.")
        result["organization_id"] = organization_id
    if "series_id" in raw:
        previous_series_id = _native_id(raw.get("series_id"))
        if previous_series_id != series_id:
            raise ValueError("The embedded Boardable previous meeting belongs to the wrong series.")
        result["series_id"] = previous_series_id
    return result


def _normalize_series_occurrence(raw, config, source_url, *, expected_id, expected_url, series_id, original_id):
    meeting = _unwrap_meeting(raw)
    norm = _normalize_meeting(
        meeting, config, source_url, expected_id=expected_id, expected_url=expected_url,
    )
    norm["series"] = _normalize_series_object(meeting.get("series"), config, series_id, original_id)
    norm["previous_meeting"] = _normalize_previous_meeting(meeting.get("previous_meeting"), config, series_id)
    if norm.get("series_id") != series_id:
        raise ValueError("The Boardable occurrence series_id is inconsistent.")
    recurrence = norm.get("recurrence_id")
    if not isinstance(recurrence, str) or not recurrence:
        raise ValueError("The Boardable occurrence lacks its recurrence ID.")
    return norm


def _validate_series_safety(norm, original_id, series_id, *, complete=True):
    try:
        owner_id = _native_id(norm.get("owner_id"))
        members = norm.get("members")
        if not isinstance(members, list) or not members or any(not isinstance(row, dict) for row in members):
            raise ValueError
        member_ids = [_native_id(row.get("id")) for row in members]
        if len(member_ids) != 1 or member_ids != [owner_id]:
            raise ValueError
        if norm.get("minutes_type") != "free_form":
            raise ValueError
        if norm.get("remote_option") != "no_remote":
            raise ValueError
        if norm.get("remote_url") is not None or norm.get("remote_url_description") is not None:
            raise ValueError
        if not _falseish(norm.get("disable_remote_rsvp")):
            raise ValueError
        if norm.get("guests"):
            raise ValueError
        if norm.get("groups"):
            raise ValueError
        if norm.get("series_id") != series_id or not isinstance(norm.get("recurrence_id"), str):
            raise ValueError
        if norm.get("alternative_dates") is not None or norm.get("additional_dates") not in (None, []):
            raise ValueError
        if norm.get("group") is not None or norm.get("group_id") is not None:
            raise ValueError
        for key in _SERIES_FLAGS:
            if not _falseish(norm.get(key)):
                raise ValueError
        if norm.get("published_at") is not None:
            raise ValueError
        if norm.get("materials_published_status") is not None or norm.get("published_materials_status") is not None:
            raise ValueError
        for key in ("agenda_live_version", "agenda_draft_version", "agenda_last_published_at"):
            if norm.get(key) is not None:
                raise ValueError
        series = norm.get("series")
        if not isinstance(series, dict):
            raise ValueError
        if series.get("id") != series_id or series.get("original_meeting_id") != original_id:
            raise ValueError
        if series.get("meeting_invite_leader_id") != original_id:
            raise ValueError
        if complete and (series.get("create_in_progress") or series.get("publish_in_progress")):
            raise ValueError
        data = series.get("data")
        if not isinstance(data, dict):
            raise ValueError
        if data.get("repeat_period") != "week" or str(data.get("weekly_interval")) != "1":
            raise ValueError
        if data.get("timezone") != norm.get("timezone"):
            raise ValueError
        if data.get("remote_option") != "no_remote" or data.get("remote_url") is not None:
            raise ValueError
        if data.get("guests") not in (None, []) or data.get("group_ids") not in (None, []):
            raise ValueError
        if not _falseish(data.get("video_conference_enabled")):
            raise ValueError
        if not _falseish(data.get("public_member_dashboard")) or not _falseish(data.get("public_page")):
            raise ValueError
        if not _falseish(data.get("disable_remote_rsvp")):
            raise ValueError
    except (TypeError, ValueError):
        raise WriteFailure(
            "mapping_unverified",
            "The Boardable series occurrence has an unmapped private, guest, publication, media or recurrence state.",
        ) from None


def _check_result_size(value, bounds):
    if len(_serialized(value)) > min(bounds.parser_bytes, bounds.transfer_bytes):
        raise WriteFailure("provider_rejected", "The Boardable series readback exceeds byte bounds.")


def _collection_entries(value, config, source_url, series_id, bounds):
    required = {"can", "meeting", "past", "today", "future", "unpublished"}
    if not isinstance(value, dict) or set(value) != required:
        raise WriteFailure("provider_rejected", "The Boardable series collection response uses an unsupported envelope.")
    data = value
    if not isinstance(data.get("meeting"), dict):
        raise ValueError("The Boardable series collection lacks its head meeting.")

    def entry(row):
        if not isinstance(row, dict):
            raise ValueError("A Boardable series collection row is not an object.")
        identity = _native_id(row.get("id"))
        url, slug = _canonical(source_url, row.get("url"))
        if url != row.get("url") or row.get("slug") != slug:
            raise ValueError("A Boardable series collection row URL is not canonical.")
        start = _utc_text(_parse_server_instant(row.get("start")))
        end = _utc_text(_parse_server_instant(row.get("end")))
        if end <= start:
            raise ValueError("A Boardable series collection occurrence ends before it starts.")
        if _native_id(row.get("series_id")) != series_id:
            raise ValueError("A Boardable series collection occurrence belongs to the wrong series.")
        return identity, {"id": identity, "url": url, "start": start, "end": end, "series_id": series_id}

    head_id, head = entry(data["meeting"])
    entries = {head_id: head}
    for bucket in ("past", "today", "future", "unpublished"):
        rows = data.get(bucket)
        if not isinstance(rows, list):
            raise ValueError("A Boardable series collection bucket is missing or not a list.")
        if len(rows) > bounds.max_records:
            raise WriteFailure("provider_rejected", "A Boardable series collection bucket exceeds record bounds.")
        seen = set()
        for row in rows:
            identity, item = entry(row)
            if identity in seen:
                raise WriteFailure("provider_rejected", "A Boardable series collection bucket repeats an occurrence ID.")
            seen.add(identity)
            if identity in entries:
                if entries[identity] != item:
                    raise WriteFailure("provider_rejected", "Boardable series collection buckets conflict for one occurrence.")
            else:
                entries[identity] = item
    if len(entries) > bounds.max_records:
        raise WriteFailure("provider_rejected", "The Boardable series collection exceeds record bounds.")
    return entries, head_id


def _metadata_occurrence(norm):
    value = deepcopy(norm)
    value.pop("url", None)
    value.pop("slug", None)
    return value


def _metadata_snapshot(snapshot):
    return {
        "series_id": snapshot["series_id"],
        "original_meeting_id": snapshot["original_meeting_id"],
        "schedule": deepcopy(snapshot["schedule"]),
        "occurrences": [_metadata_occurrence(row) for row in snapshot["occurrences"]],
    }


def _expected_update_snapshot(snapshot, fields):
    base = snapshot["occurrences"][0]
    title = _text(fields.get("title", base["title"]), "title", 500, required=True)
    description = _text(fields.get("description", base.get("description", "")), "description", 20000)
    location = _text(fields.get("location", base.get("location", "")), "location", 500)
    expected = deepcopy(snapshot)
    for occurrence in expected["occurrences"]:
        occurrence["title"] = title
        occurrence["description"] = description
        occurrence["location"] = location
        series = occurrence["series"]
        series["title"] = title
        series["description"] = description
        data = series["data"]
        data["title"] = title
        data["description"] = description
        data["location"] = location
    return expected, title, description, location


def _update_body_series(before, identity, expected, dates_payload):
    members = [row["id"] for row in before["members"]]
    groups = [row["id"] for row in before.get("groups", [])]
    return {
        "id": identity,
        "title": expected["title"],
        "description": expected.get("description", ""),
        "owner_id": before["owner_id"],
        "timezone": expected["timezone"],
        "dates": dates_payload,
        "minutes_type": before["minutes_type"],
        "location": expected.get("location", ""),
        "remote_option": before["remote_option"],
        "remote_url": None,
        "remote_url_description": None,
        "disable_remote_rsvp": bool(before.get("disable_remote_rsvp", False)),
        "invitee_ids": members,
        "group_ids": groups,
        "guests": [],
        "notify": False,
        "notify_changed_invitees": False,
        "guestsChanged": [],
        "usersChanged": [],
        "public_member_dashboard": 0 if _falseish(before.get("public_member_dashboard")) else 1,
        "public_page": 0 if _falseish(before.get("public_page")) else 1,
        "enable_recording": "" if _falseish(before.get("enable_recording")) else before.get("enable_recording"),
        "enable_transcription": "" if _falseish(before.get("enable_transcription")) else before.get("enable_transcription"),
        "enable_ai_summary": "" if _falseish(before.get("enable_ai_summary")) else before.get("enable_ai_summary"),
        "calendar_type": "set",
        "assignable_class": r"App\Boardable\Meetings\Meeting",
        "assignable_id": identity,
        "series_choice": "subsequent",
    }


def _create_plan(change, config, bounds):
    fields = change.fields
    if not isinstance(fields, dict) or set(fields) - _ALLOWED_CREATE:
        raise WriteFailure("unsupported_field", "The Boardable series create contains unsupported fields.")
    title = _text(fields.get("title"), "title", 500, required=True)
    timezone_name = _validate_timezone(fields.get("timezone"))
    if "dates" not in fields:
        raise ValueError("Boardable series creation requires exactly one initial date.")
    dates = _validate_dates(fields["dates"], timezone_name)
    recurrence = fields.get("recurrence")
    if not isinstance(recurrence, dict) or set(recurrence) != {"repeat_period", "weekly_interval", "end_date"}:
        raise ValueError("Boardable series creation requires the captured weekly recurrence shape.")
    if recurrence.get("repeat_period") != "week":
        raise WriteFailure("mapping_unverified", "Only the captured weekly Boardable recurrence period is mapped.")
    interval = recurrence.get("weekly_interval")
    if isinstance(interval, bool) or interval not in (1, "1"):
        raise WriteFailure("mapping_unverified", "Only the captured weekly Boardable interval is mapped.")
    _parse_date(recurrence.get("end_date"))
    initial = dates["normalized"]["date"]
    schedule = _generate_weekly_schedule(
        initial, recurrence["end_date"], timezone_name,
        dates["normalized"]["from"], dates["normalized"]["to"], bounds,
    )
    description = _text(fields.get("description", ""), "description", 20000)
    location = _text(fields.get("location", ""), "location", 500)
    owner_id = _native_id(config.get("owner_id"))
    body = {
        "title": title,
        "description": description,
        "owner_id": owner_id,
        "timezone": timezone_name,
        "dates": [dates["payload"]],
        "meeting_type": "series",
        "minutes_type": "free_form",
        "location": location,
        "remote_option": "no_remote",
        "remote_url": None,
        "remote_url_description": None,
        "disable_remote_rsvp": False,
        "invitee_ids": [owner_id],
        "group_ids": [],
        "guests": [],
        "notify": False,
        "public_member_dashboard": False,
        "public_page": False,
        "enable_recording": False,
        "enable_transcription": False,
        "enable_ai_summary": False,
        "repeat_period": "week",
        "weekly_interval": "1",
        "monthly_interval": "1",
        "monthly_repeat_type": "numbered-day",
        "series_date": initial,
        "series_ends": recurrence["end_date"],
        "series_from": dates["normalized"]["from"],
        "series_to": dates["normalized"]["to"],
    }
    expected = {
        "title": title,
        "description": description,
        "location": location,
        "timezone": timezone_name,
        "owner_id": owner_id,
        "series_date": initial,
        "series_ends": recurrence["end_date"],
        "series_from": dates["normalized"]["from"],
        "series_to": dates["normalized"]["to"],
        "schedule": schedule,
    }
    _check_size(body, bounds)
    return body, expected


def _verify_create_occurrence(occurrence, expected, by_date, series_id, original_id):
    if occurrence.get("title") != expected["title"]:
        return False
    if occurrence.get("description") != expected["description"]:
        return False
    if occurrence.get("location") != expected["location"]:
        return False
    if occurrence.get("timezone") != expected["timezone"] or occurrence.get("owner_id") != expected["owner_id"]:
        return False
    if [row.get("id") for row in occurrence.get("members", [])] != [expected["owner_id"]]:
        return False
    if occurrence.get("groups") != [] or occurrence.get("guests") != []:
        return False
    if occurrence.get("materials_published_at") is not None:
        return False
    if occurrence.get("series_id") != series_id:
        return False
    row = occurrence.get("datesTimezone")
    if not isinstance(row, list) or len(row) != 1:
        return False
    row = row[0]
    scheduled = by_date.get(row.get("date"))
    if scheduled is None:
        return False
    if (row.get("from"), row.get("to"), row.get("timezone")) != (
            scheduled["from"], scheduled["to"], scheduled["timezone"]):
        return False
    if occurrence.get("start") != scheduled["start"] or occurrence.get("end") != scheduled["end"]:
        return False
    if occurrence.get("recurrence_id") != scheduled["recurrence_id"]:
        return False
    series = occurrence.get("series")
    if not isinstance(series, dict) or series.get("id") != series_id:
        return False
    if series.get("original_meeting_id") != original_id or series.get("meeting_invite_leader_id") != original_id:
        return False
    if series.get("create_in_progress") or series.get("publish_in_progress"):
        return False
    if series.get("title") != expected["title"] or series.get("description") != expected["description"]:
        return False
    data = series.get("data")
    if not isinstance(data, dict):
        return False
    if not _falseish(data.get("published")):
        return False
    checks = {
        "title": expected["title"],
        "description": expected["description"],
        "location": expected["location"],
        "timezone": expected["timezone"],
        "series_date": expected["series_date"],
        "series_ends": expected["series_ends"],
        "series_from": expected["series_from"],
        "series_to": expected["series_to"],
        "repeat_period": "week",
        "weekly_interval": "1",
    }
    return all(data.get(key) == value for key, value in checks.items())


def _verify_create_snapshot(snapshot, prepared, series_id, original_id, persisted_url):
    expected = prepared["create_expected"]
    if snapshot.get("series_id") != series_id or snapshot.get("original_meeting_id") != original_id:
        return False
    if canonical_hash(snapshot.get("schedule")) != canonical_hash(expected["schedule"]):
        return False
    by_id = {row["id"]: row for row in snapshot.get("occurrences", [])}
    if len(by_id) != len(expected["schedule"]):
        return False
    original = by_id.get(original_id)
    if original is None or original.get("url") != persisted_url:
        return False
    by_date = {row["date"]: row for row in expected["schedule"]}
    if {row.get("datesTimezone", [{}])[0].get("date") for row in by_id.values()} != set(by_date):
        return False
    if original.get("datesTimezone", [{}])[0].get("date") != expected["schedule"][0]["date"]:
        return False
    return all(
        _verify_create_occurrence(row, expected, by_date, series_id, original_id)
        for row in by_id.values()
    )


def _verify_update_snapshot(snapshot, prepared, original_id, series_id, persisted_url):
    if snapshot.get("series_id") != prepared["series_id"] or snapshot.get("original_meeting_id") != original_id:
        return False
    expected = prepared["expected"]
    expected_ids = {row["id"] for row in expected.get("occurrences", [])}
    actual_ids = {row["id"] for row in snapshot.get("occurrences", [])}
    if expected_ids != actual_ids:
        return False
    original = next((row for row in snapshot["occurrences"] if row["id"] == original_id), None)
    if original is None or original.get("url") != persisted_url:
        return False
    if canonical_hash(_metadata_snapshot(snapshot)) != canonical_hash(_metadata_snapshot(expected)):
        return False
    return True


class BoardableSeriesWriteAdapter(BoardableMeetingWriteAdapter):
    def __init__(self, transport=None):
        super().__init__(transport)

    def credentials(self, source, context):
        config = super().credentials(source, context)
        if not isinstance(config, dict) or config.get("current_meeting_series") is not True:
            raise WriteFailure("permission_denied", "The explicit Boardable recurrence series credential is required.")
        return config

    def authorize(self, source, change, context):
        config = super().authorize(source, change, context)
        if change.operation == "update":
            _series_grant_ids(config)
        return config

    def _read_series_collection(self, source, series_id, context, bounds, deadline):
        url = source.url + "meeting-series/" + str(series_id) + "/data"
        value = self._request(
            source, context, url, "POST", {}, bounds, deadline, write=False, expected_status=200,
        )
        _check_json_bounds(value, bounds)
        return value

    def _snapshot_series(self, source, config, series_id, original_id, context, bounds, deadline):
        raw_collection = self._read_series_collection(source, series_id, context, bounds, deadline)
        entries, head_id = _collection_entries(raw_collection, config, source.url, series_id, bounds)
        if head_id != original_id:
            raise WriteFailure("conflict", "The Boardable series collection head is not the original meeting.")
        occurrences = []
        for entry in sorted(entries.values(), key=lambda item: (item["start"], item["id"])):
            if context.check_cancelled():
                raise WriteCancelled()
            raw = self._read_meeting(source, entry["url"], context, bounds, deadline)
            norm = _normalize_series_occurrence(
                raw, config, source.url,
                expected_id=entry["id"], expected_url=entry["url"],
                series_id=series_id, original_id=original_id,
            )
            if norm.get("start") != entry["start"] or norm.get("end") != entry["end"]:
                raise WriteFailure("provider_rejected", "A Boardable series occurrence instant differs from its collection row.")
            _validate_series_safety(norm, original_id, series_id, complete=True)
            occurrences.append(norm)
        if {row["id"] for row in occurrences} != set(entries):
            raise WriteFailure("provider_rejected", "Boardable series occurrence reads do not cover the exact collection.")
        occurrences.sort(key=lambda item: (item["start"], item["id"]))
        if not occurrences:
            raise WriteFailure("provider_rejected", "The Boardable series has no occurrences.")
        for index, occurrence in enumerate(occurrences):
            previous = occurrence.get("previous_meeting")
            if index == 0:
                if previous is not None:
                    raise WriteFailure("provider_rejected", "The first Boardable series occurrence has an unexpected predecessor.")
            elif not isinstance(previous, dict) or previous.get("id") != occurrences[index - 1]["id"]:
                raise WriteFailure("provider_rejected", "A Boardable series occurrence predecessor is not the independently read prior occurrence.")
        series_norm = occurrences[0]["series"]
        schedule = _series_data_schedule(series_norm, bounds)
        if len(schedule) != len(occurrences):
            raise WriteFailure("provider_rejected", "The Boardable series occurrence count differs from its recurrence schedule.")
        by_date = {row["date"]: row for row in schedule}
        if set(by_date) != {row["datesTimezone"][0]["date"] for row in occurrences}:
            raise WriteFailure("provider_rejected", "The Boardable series occurrence dates differ from its recurrence schedule.")
        for occurrence in occurrences:
            if canonical_hash(occurrence["series"]) != canonical_hash(series_norm):
                raise WriteFailure("provider_rejected", "The Boardable occurrences carry inconsistent embedded series metadata.")
            row = occurrence["datesTimezone"][0]
            scheduled = by_date[row["date"]]
            if (row.get("from"), row.get("to"), row.get("timezone")) != (
                    scheduled["from"], scheduled["to"], scheduled["timezone"]):
                raise WriteFailure("provider_rejected", "A Boardable occurrence local time differs from the series.")
            if occurrence.get("timezone") != scheduled["timezone"]:
                raise WriteFailure("provider_rejected", "A Boardable occurrence timezone differs from the series.")
            if occurrence.get("start") != scheduled["start"] or occurrence.get("end") != scheduled["end"]:
                raise WriteFailure("provider_rejected", "A Boardable occurrence UTC instant differs from the series.")
            if occurrence.get("recurrence_id") != scheduled["recurrence_id"]:
                raise WriteFailure("provider_rejected", "A Boardable occurrence recurrence ID differs from the series.")
        original = next((row for row in occurrences if row["id"] == original_id), None)
        if original is None or original["datesTimezone"][0]["date"] != schedule[0]["date"]:
            raise WriteFailure("provider_rejected", "The Boardable original meeting is not the first series occurrence.")
        snapshot = {
            "series_id": series_id,
            "original_meeting_id": original_id,
            "schedule": schedule,
            "occurrences": occurrences,
            "collection": {str(key): entries[key] for key in sorted(entries)},
            "head_url": entries[original_id]["url"],
        }
        _check_result_size(snapshot, bounds)
        return snapshot

    def prepare(self, source, change, context, bounds, deadline):
        config = self.authorize(source, change, context)
        if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
            raise ValueError("A bounded change key is required.")
        if change.operation == "create":
            body, expected = _create_plan(change, config, bounds)
            prepared = {
                "series_mode": True,
                "change": asdict(change),
                "before": None,
                "create_expected": expected,
                "native": {"method": "POST", "url": source.url + "meetings", "headers": {}, "body": body},
                "meeting_url": None,
                "conflict_semantics": "create_no_preflight",
            }
            _check_prepared_size(prepared, bounds)
            return prepared
        identity = _change_id(change.resource_id)
        original_url = config["meeting_urls"][str(identity)]
        try:
            raw = self._read_meeting(source, original_url, context, bounds, deadline)
            _, _, _, series_id, _ = _series_response_identity(
                raw, config, source.url, expected_id=identity, expected_url=original_url,
            )
        except AmbiguousWrite:
            raise WriteFailure("provider_rejected", "The Boardable series could not be read before planning.") from None
        if series_id not in _series_grant_ids(config):
            raise WriteFailure("permission_denied", "The native Boardable series is outside the explicit series_ids grant.")
        first = _normalize_series_occurrence(
            raw, config, source.url,
            expected_id=identity, expected_url=original_url,
            series_id=series_id, original_id=identity,
        )
        _validate_series_safety(first, identity, series_id, complete=True)
        try:
            snapshot = self._snapshot_series(source, config, series_id, identity, context, bounds, deadline)
        except AmbiguousWrite:
            raise WriteFailure("provider_rejected", "The Boardable series collection could not be read before planning.") from None
        by_id = {row["id"]: row for row in snapshot["occurrences"]}
        if identity not in by_id:
            raise WriteFailure("provider_rejected", "The original Boardable meeting is absent from its series.")
        if canonical_hash(_metadata_occurrence(by_id[identity])) != canonical_hash(_metadata_occurrence(first)):
            raise WriteFailure("conflict", "The Boardable original meeting changed while preparing the series update.")
        fingerprint = canonical_hash(snapshot)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected Boardable series differs from readback.")
        fields = change.fields
        if not isinstance(fields, dict) or not fields or set(fields) - _ALLOWED_UPDATE:
            raise WriteFailure("unsupported_field", "The Boardable series update accepts only title, description and location.")
        expected_snapshot, title, _, _ = _expected_update_snapshot(snapshot, fields)
        before_original = by_id[identity]
        expected_original = next(row for row in expected_snapshot["occurrences"] if row["id"] == identity)
        old_date = before_original["datesTimezone"][0]
        dates_payload = [{
            "date": old_date["date"],
            "from": old_date["from"],
            "id": identity,
            "timezone": old_date["timezone"],
            "to": old_date["to"],
        }]
        body = _update_body_series(before_original, identity, expected_original, dates_payload)
        _check_size(body, bounds)
        prepared = {
            "series_mode": True,
            "change": asdict(change),
            "before": snapshot,
            "expected": expected_snapshot,
            "before_fingerprint": fingerprint,
            "series_id": series_id,
            "original_meeting_id": identity,
            "meeting_url": original_url,
            "title_changed": title != before_original["title"],
            "native": {
                "method": "POST",
                "url": source.url + "meetings_v2/" + str(identity),
                "headers": {},
                "body": body,
            },
            "conflict_semantics": "preflight_compare_not_atomic_upstream_cas",
        }
        _check_prepared_size(prepared, bounds)
        return prepared

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        config = self.authorize(source, change, context)
        if not prepared.get("series_mode"):
            raise WriteFailure("mapping_unverified", "The prepared Boardable series plan lacks its series marker.")
        _check_prepared_size(prepared, bounds)
        native = prepared.get("native")
        if not isinstance(native, dict) or native.get("method") != "POST" or native.get("headers") != {}:
            raise WriteFailure("mapping_unverified", "The prepared Boardable series native request is malformed.")
        native_body = native.get("body")
        if not isinstance(native_body, dict):
            raise WriteFailure("mapping_unverified", "The prepared Boardable series native body is not an object.")
        _check_json_bounds(native_body, bounds)
        _check_size(native_body, bounds)
        if change.operation == "create":
            if native.get("url") != source.url + "meetings":
                raise WriteFailure("permission_denied", "The prepared Boardable series create URL is not the exact trusted endpoint.")
            body, expected = _create_plan(change, config, bounds)
            if canonical_hash(native_body) != canonical_hash(body):
                raise WriteFailure("conflict", "The prepared Boardable series create body no longer matches the trusted owner and fields.")
            if canonical_hash(prepared.get("create_expected")) != canonical_hash(expected):
                raise WriteFailure("conflict", "The prepared Boardable series create expectations no longer match.")
            if context.check_cancelled():
                raise WriteCancelled()
            if persist:
                if persist({"resource_id": None, "meeting_url": None, "series_id": None, "outbound_started": True}):
                    raise WriteCancelled()
            elif context.check_cancelled():
                raise WriteCancelled()
            raw = self._request(
                source, context, native["url"], "POST",
                body, bounds, deadline, write=True, expected_status=201,
            )
            try:
                original_id, canonical_url, _, series_id, _ = _series_response_identity(raw, config, source.url)
            except (TypeError, ValueError):
                raise AmbiguousWrite("Series creation returned no verified original meeting, series ID and canonical URL.") from None
            saved = {
                "resource_id": str(original_id),
                "meeting_url": canonical_url,
                "series_id": str(series_id),
                "outbound_started": True,
            }
            cancelled = persist(saved) if persist else context.check_cancelled()
            if cancelled or monotonic() >= deadline:
                raise AmbiguousWrite("Series creation returned its native identities; readback remains unconfirmed.")
            try:
                return self.reconcile(source, prepared, saved, context, bounds, deadline)
            except (WriteCancelled, WriteFailure, ValueError, TypeError):
                raise AmbiguousWrite("Series creation was sent before readback could be confirmed.") from None
        identity = _change_id(change.resource_id)
        if prepared.get("series_id") not in _series_grant_ids(config):
            raise WriteFailure("permission_denied", "The prepared Boardable series is outside the current trusted series_ids grant.")
        if native.get("url") != source.url + "meetings_v2/" + str(identity):
            raise WriteFailure("permission_denied", "The prepared Boardable series update URL is not the exact trusted endpoint.")
        try:
            current = self._snapshot_series(
                source, config, prepared["series_id"], identity, context, bounds, deadline,
            )
        except (WriteFailure, ValueError, TypeError):
            raise WriteFailure("conflict", "The Boardable series changed after planning.") from None
        if canonical_hash(current) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "The Boardable series changed after planning.")
        fields = change.fields
        if not isinstance(fields, dict) or not fields or set(fields) - _ALLOWED_UPDATE:
            raise WriteFailure("unsupported_field", "The Boardable series update accepts only title, description and location.")
        expected_snapshot, _, _, _ = _expected_update_snapshot(current, fields)
        by_id = {row["id"]: row for row in current["occurrences"]}
        before_original = by_id.get(identity)
        if before_original is None:
            raise WriteFailure("conflict", "The Boardable original meeting is absent from the current series.")
        expected_original = next(row for row in expected_snapshot["occurrences"] if row["id"] == identity)
        old_date = before_original["datesTimezone"][0]
        dates_payload = [{
            "date": old_date["date"],
            "from": old_date["from"],
            "id": identity,
            "timezone": old_date["timezone"],
            "to": old_date["to"],
        }]
        body = _update_body_series(before_original, identity, expected_original, dates_payload)
        _check_size(body, bounds)
        if body.get("series_choice") != "subsequent":
            raise WriteFailure("mapping_unverified", "The prepared Boardable series update lacks the captured subsequent series choice.")
        if canonical_hash(native_body) != canonical_hash(body):
            raise WriteFailure("conflict", "The prepared Boardable series update body no longer matches the trusted current snapshot and fields.")
        if canonical_hash(prepared.get("expected")) != canonical_hash(expected_snapshot):
            raise WriteFailure("conflict", "The prepared Boardable series update expectations no longer match the trusted current snapshot and fields.")
        if context.check_cancelled():
            raise WriteCancelled()
        pre_intent = {
            "resource_id": str(identity),
            "meeting_url": prepared["meeting_url"],
            "series_id": str(prepared["series_id"]),
            "outbound_started": True,
        }
        if persist:
            if persist(pre_intent):
                raise WriteCancelled()
        elif context.check_cancelled():
            raise WriteCancelled()
        raw = self._request(
            source, context, native["url"], "POST",
            body, bounds, deadline, write=True, expected_status=200,
        )
        try:
            returned_id, canonical_url, _, series_id, _ = _series_response_identity(
                raw, config, source.url, expected_id=identity, expected_series_id=prepared["series_id"],
            )
        except (TypeError, ValueError):
            raise AmbiguousWrite("Series update returned no verified original meeting, series ID and canonical URL.") from None
        saved = {
            "resource_id": str(returned_id),
            "meeting_url": canonical_url,
            "series_id": str(series_id),
            "outbound_started": True,
        }
        cancelled = persist(saved) if persist else context.check_cancelled()
        if cancelled or monotonic() >= deadline:
            raise AmbiguousWrite("Series update returned its native identities; readback remains unconfirmed.")
        try:
            return self.reconcile(source, prepared, saved, context, bounds, deadline)
        except (WriteCancelled, WriteFailure, ValueError, TypeError):
            raise AmbiguousWrite("Series update was sent before readback could be confirmed.") from None

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        config = self.credentials(source, context)
        item = item or {}
        raw_identity = item.get("resource_id")
        raw_series = item.get("series_id")
        if raw_identity is None or raw_series is None:
            return {
                "state": "uncertain", "reconciled": True,
                "reason": "No confirmed original meeting and series identity were persisted; no title matching or POST replay.",
            }
        try:
            identity = _persisted_id(raw_identity)
            series_id = _persisted_id(raw_series)
        except (TypeError, ValueError):
            return {
                "state": "uncertain", "reconciled": True,
                "reason": "The persisted Boardable meeting or series identity is invalid.",
            }
        persisted_url = item.get("meeting_url")
        try:
            canonical_url, _ = _canonical(source.url, persisted_url)
            if canonical_url != persisted_url:
                raise ValueError
        except ValueError:
            return {
                "state": "uncertain", "resource_id": str(identity), "series_id": str(series_id),
                "reconciled": True,
                "reason": "The persisted canonical Boardable meeting URL is missing or unsafe.",
            }
        if change.operation == "update":
            try:
                if series_id not in _series_grant_ids(config):
                    return {
                        "state": "uncertain", "resource_id": str(identity), "series_id": str(series_id),
                        "meeting_url": persisted_url, "reconciled": True,
                        "reason": "The persisted Boardable series is outside the narrowed series_ids grant.",
                    }
            except WriteFailure:
                return {
                    "state": "uncertain", "resource_id": str(identity), "series_id": str(series_id),
                    "meeting_url": persisted_url, "reconciled": True,
                    "reason": "The current Boardable series grant cannot be applied to this persisted identity.",
                }
        try:
            raw = self._read_meeting(source, persisted_url, context, bounds, deadline)
            first = _normalize_series_occurrence(
                raw, config, source.url,
                expected_id=identity, expected_url=persisted_url,
                series_id=series_id, original_id=identity,
            )
            if first.get("series", {}).get("create_in_progress") or first.get("series", {}).get("publish_in_progress"):
                return {
                    "state": "uncertain", "resource_id": str(identity), "meeting_url": persisted_url,
                    "series_id": str(series_id), "reconciled": True,
                    "reason": "The Boardable series generation is still in progress.",
                }
            snapshot = self._snapshot_series(source, config, series_id, identity, context, bounds, deadline)
            if snapshot.get("original_meeting_id") != identity or snapshot.get("series_id") != series_id:
                raise ValueError
            original = next((row for row in snapshot["occurrences"] if row["id"] == identity), None)
            if original is None or original.get("url") != persisted_url:
                raise ValueError
            if change.operation == "create":
                matched = _verify_create_snapshot(snapshot, prepared, series_id, identity, persisted_url)
            else:
                if identity != _change_id(change.resource_id):
                    raise ValueError
                matched = _verify_update_snapshot(snapshot, prepared, identity, series_id, persisted_url)
            occurrence_ids = [row["id"] for row in snapshot["occurrences"]]
            occurrence_urls = [row["url"] for row in snapshot["occurrences"]]
            result = {
                "state": "succeeded" if matched else "uncertain",
                "resource_id": str(identity),
                "meeting_url": persisted_url,
                "series_id": str(series_id),
                "occurrence_ids": occurrence_ids,
                "occurrence_urls": occurrence_urls,
                "readback": snapshot,
                "reconciled": True,
            }
            if not matched:
                result["reason"] = "The exact Boardable occurrence and series readback did not confirm the requested complete business state."
            _check_result_size(result, bounds)
            return result
        except (WriteCancelled, WriteFailure, ValueError, TypeError):
            return {
                "state": "uncertain", "resource_id": str(identity), "meeting_url": persisted_url,
                "series_id": str(series_id), "reconciled": True,
                "reason": "The exact persisted Boardable series did not confirm the requested complete business state.",
            }
