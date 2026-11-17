"""Pinned Boardable native meeting create/update through the shared write coordinator."""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import re
from time import monotonic
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure
from ..write_transport import WriteResponse


_ORG_RE = re.compile(r"/([A-Za-z0-9_-]{1,128})/")
_SLUG_RE = re.compile(r"[A-Za-z0-9_-]{1,200}")
_COOKIE_RE = re.compile(r"[A-Za-z0-9_-]+=[^;, ]+(?:; [A-Za-z0-9_-]+=[^;, ]+)*")
_CLOCK_RE = re.compile(r"([1-9]|1[0-2]):([0-5][0-9]) ([ap]m)", re.I)
_DATE_RE = re.compile(r"[0-9]{2}/[0-9]{2}/[0-9]{4}")
_MAX_JSON_DEPTH = 64

_PRIVATE_KEYS = {
    "email", "email_2fa", "email_confirmed", "email_notification_frequency",
    "contact_email", "contact_phone", "additional_notifications_email", "phone",
    "password", "has_password", "token", "confirmation_email_token", "api_key",
    "access_token", "authorization", "cookie", "set-cookie", "csrf_token",
    "session_cookie", "secret_passphrase", "access_key", "profile", "roles",
    "personal_address", "personal_address_2", "personal_city", "personal_state",
    "personal_zip", "personal_phone", "pin_code", "two_factor_auth",
    "accepted_terms", "accepted_privacy_policy", "accepted_cookie_policy",
    "saml_only", "saml_last_login_at", "account_setup_link",
}

_PIVOT_KEYS = {
    "meeting_id", "user_id", "rsvp", "rsvp_note", "attendance", "collaborator",
    "automated_attendance", "automated_attendance_override", "left_meeting", "is_voter",
}

_VOLATILE_KEYS = {
    "created_at", "updated_at", "formattedMeetingTime", "timeUntilStart",
    "meetingHasStarted", "name", "blurb", "active_until",
    "video_session_currently_active", "videoLink", "globalAi", "globalTranscripts",
}

_SAFE_FIELDS = {
    "title", "description", "location", "remote_option", "remote_url",
    "remote_url_description", "disable_remote_rsvp", "minutes_type",
    "public_member_dashboard", "public_page", "published", "published_level",
    "published_at", "minutes_published", "materials_published_status",
    "published_materials_status", "agenda_live_version", "agenda_draft_version",
    "agenda_last_published_at", "enable_recording", "enable_transcription",
    "enable_ai_summary", "series_id", "recurrence_id", "alternative_dates",
    "additional_dates", "video_conference_enabled", "starred_public_page",
    "notify", "group_id",
}

_ALLOWED_CREATE = {"title", "description", "location", "timezone", "dates", "remote_option"}
_ALLOWED_UPDATE = {"title", "description", "location", "timezone", "dates"}


def _native_id(value):
    if type(value) is not int or not 0 < value < 10 ** 19:
        raise ValueError("A bounded positive native Boardable ID is required.")
    return value


def _change_id(value):
    if not isinstance(value, str) or re.fullmatch(r"[1-9][0-9]{0,18}", value) is None:
        raise ValueError("A bounded positive ASCII Boardable change ID string is required.")
    return int(value)


def _source_org(url):
    if not isinstance(url, str):
        raise ValueError("An exact Boardable organization URL is required.")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ValueError("The Boardable organization URL is invalid.") from None
    if (parsed.scheme != "https" or parsed.netloc != "app.boardable.com" or parsed.username
            or parsed.password or port is not None or parsed.query or parsed.fragment):
        raise ValueError("Only an exact app.boardable.com organization URL without a port, query or fragment is allowed.")
    match = _ORG_RE.fullmatch(parsed.path)
    if match is None:
        raise ValueError("The Boardable source must identify exactly one organization path.")
    return match.group(1)


def _canonical(source_url, value):
    if not isinstance(value, str):
        raise ValueError("A canonical Boardable meeting URL is required.")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("The Boardable meeting URL is invalid.") from None
    prefix = urlsplit(source_url).path + "meetings/"
    if (parsed.scheme != "https" or parsed.netloc != "app.boardable.com" or parsed.username
            or parsed.password or port is not None or parsed.query or parsed.fragment
            or not parsed.path.startswith(prefix)):
        raise ValueError("The Boardable meeting URL is outside the exact organization scope.")
    slug = parsed.path[len(prefix):]
    if "/" in slug or _SLUG_RE.fullmatch(slug) is None:
        raise ValueError("The Boardable meeting URL does not contain one safe bounded native slug.")
    return value, slug


def _parse_date(value):
    if not isinstance(value, str) or _DATE_RE.fullmatch(value) is None:
        raise ValueError("Boardable dates must use MM/DD/YYYY.")
    parsed = datetime.strptime(value, "%m/%d/%Y")
    if not 2000 <= parsed.year <= 2050:
        raise ValueError("The meeting date is outside the bounded range.")
    return parsed


def _parse_clock(value):
    if not isinstance(value, str):
        raise ValueError("Boardable clock times require h:mm am/pm.")
    match = _CLOCK_RE.fullmatch(value)
    if match is None:
        raise ValueError("Boardable clock times require h:mm am/pm.")
    hour, minute = int(match.group(1)), int(match.group(2))
    half = match.group(3).lower()
    hour24 = hour % 12 + (12 if half == "pm" else 0)
    return hour24, minute, f"{hour}:{minute:02d} {half}"


def _validate_timezone(value):
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError("A bounded recognized IANA timezone is required.")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise ValueError("The meeting timezone is not recognized.") from None
    return value


def _local_utc(date, hour, minute, timezone_name):
    tz = ZoneInfo(timezone_name)
    naive = datetime(date.year, date.month, date.day, hour, minute)
    candidates = []
    for fold in (0, 1):
        aware = naive.replace(tzinfo=tz, fold=fold)
        if aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) == naive:
            candidates.append(aware)
    if len(candidates) != 2:
        raise ValueError("The local meeting time does not exist in the selected timezone.")
    if candidates[0].utcoffset() != candidates[1].utcoffset():
        raise ValueError("The local meeting time is ambiguous in the selected timezone.")
    return candidates[0].astimezone(timezone.utc)


def _utc_text(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_server_instant(value):
    if not isinstance(value, str):
        raise ValueError("The native meeting instant is missing.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("The native meeting instant is invalid.") from None
    if parsed.tzinfo is None:
        raise ValueError("The native meeting instant lacks a timezone.")
    return parsed.astimezone(timezone.utc)


def _validate_dates(value, timezone_name, *, original_id=None, update=False):
    _validate_timezone(timezone_name)
    if not isinstance(value, list) or len(value) != 1:
        raise ValueError("Exactly one captured single-meeting date is supported.")
    entry = value[0]
    if not isinstance(entry, dict):
        raise ValueError("Each meeting date must be an object.")
    allowed = {"date", "from", "to"} | ({"id", "timezone"} if update else set())
    if set(entry) - allowed:
        raise ValueError("Unsupported meeting date field.")
    if update:
        if "id" in entry and _native_id(entry["id"]) != original_id:
            raise ValueError("The supplied meeting date ID does not match the native meeting.")
        if "timezone" in entry and entry["timezone"] != timezone_name:
            raise ValueError("The supplied date timezone differs from the meeting timezone.")
    date_text = entry.get("date")
    date = _parse_date(date_text)
    from_hour, from_minute, from_text = _parse_clock(entry.get("from"))
    to_hour, to_minute, to_text = _parse_clock(entry.get("to"))
    start = _local_utc(date, from_hour, from_minute, timezone_name)
    end = _local_utc(date, to_hour, to_minute, timezone_name)
    if end <= start:
        raise ValueError("The meeting end must be after its start.")
    payload = {"date": date_text, "from": from_text, "to": to_text}
    normalized = {"date": date_text, "from": from_text, "to": to_text, "timezone": timezone_name}
    if update:
        payload.update({"id": original_id, "timezone": timezone_name})
        normalized["id"] = original_id
    return {"payload": payload, "normalized": normalized, "start": start, "end": end}


def _normalize_dates_timezone(raw, meeting_id, timezone_name):
    _validate_timezone(timezone_name)
    rows = raw.get("datesTimezone")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("The native readback must contain one captured single-meeting date.")
    row = rows[0]
    if set(row) - {"date", "from", "to", "id", "timezone"}:
        raise ValueError("The native datesTimezone contains an unsupported field.")
    date_text = row.get("date")
    _parse_date(date_text)
    _, _, from_text = _parse_clock(row.get("from"))
    _, _, to_text = _parse_clock(row.get("to"))
    identity = _native_id(row.get("id"))
    if identity != meeting_id:
        raise ValueError("The native date ID does not match the meeting ID.")
    if row.get("timezone") != timezone_name:
        raise ValueError("The native date timezone differs from the meeting timezone.")
    return [{"date": date_text, "from": from_text, "to": to_text,
             "id": identity, "timezone": timezone_name}]


def _scrub(value):
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items()
                if isinstance(key, str) and key.lower() not in _PRIVATE_KEYS}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _owner_id(raw):
    if raw.get("owner_id") is not None:
        return _native_id(raw["owner_id"])
    owner = raw.get("owner")
    if isinstance(owner, dict) and owner.get("id") is not None:
        return _native_id(owner["id"])
    raise ValueError("The native meeting does not identify its owner.")


def _normalize_members(raw):
    rows = raw.get("members")
    if rows is None:
        rows = raw.get("members_and_guest_users", [])
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise ValueError("The native meeting members are not a list.")
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("A native meeting member is not an object.")
        identity = _native_id(row.get("id"))
        if identity in seen:
            raise ValueError("The native meeting repeats a member ID.")
        seen.add(identity)
        pivot = row.get("pivot") or {}
        if not isinstance(pivot, dict):
            raise ValueError("A native member pivot is not an object.")
        safe = {key: _scrub(pivot[key]) for key in _PIVOT_KEYS if key in pivot}
        result.append({"id": identity, "pivot": safe})
    return result


def _normalize_groups(raw):
    rows = raw.get("groups") or []
    if not isinstance(rows, list):
        raise ValueError("The native meeting groups are not a list.")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("A native meeting group is not an object.")
        identity = _native_id(row.get("id"))
        safe = {"id": identity}
        for key, value in row.items():
            if key == "id" or (isinstance(key, str) and key.lower() in _PRIVATE_KEYS):
                continue
            safe[key] = _scrub(value)
        result.append(safe)
    return result


def _normalize_guests(raw):
    rows = raw.get("guests")
    if rows is None:
        rows = raw.get("guest_members", [])
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise ValueError("The native meeting guests are not a list.")
    result = []
    for row in rows:
        if isinstance(row, dict) and row.get("id") is not None:
            result.append({"id": _native_id(row["id"])})
        else:
            result.append(_scrub(row))
    return result


def _normalize_meeting(raw, config, source_url, *, expected_id=None, expected_url=None):
    if isinstance(raw, dict) and isinstance(raw.get("meeting"), dict):
        raw = raw["meeting"]
    if not isinstance(raw, dict):
        raise ValueError("The Boardable meeting response is not an object.")
    identity = _native_id(raw.get("id"))
    organization_id = _native_id(raw.get("organization_id"))
    if organization_id != config["organization_id"]:
        raise ValueError("The Boardable meeting belongs to a different organization.")
    url, slug = _canonical(source_url, raw.get("url"))
    if raw.get("slug") != slug:
        raise ValueError("The Boardable meeting URL and slug disagree.")
    if expected_id is not None and identity != expected_id:
        raise ValueError("The Boardable meeting returned the wrong native ID.")
    if expected_url is not None and url != expected_url:
        raise ValueError("The Boardable readback URL differs from the exact requested meeting URL.")
    owner_id = _owner_id(raw)
    timezone_name = raw.get("timezone")
    _validate_timezone(timezone_name)
    result = {"id": identity, "organization_id": organization_id, "url": url,
              "slug": slug, "owner_id": owner_id, "timezone": timezone_name}
    for key in _SAFE_FIELDS:
        if key in raw:
            result[key] = _scrub(raw[key])
    result["datesTimezone"] = _normalize_dates_timezone(raw, identity, timezone_name)
    if "start" in raw:
        result["start"] = _utc_text(_parse_server_instant(raw["start"]))
    if "end" in raw:
        result["end"] = _utc_text(_parse_server_instant(raw["end"]))
    result["members"] = _normalize_members(raw)
    result["groups"] = _normalize_groups(raw)
    result["guests"] = _normalize_guests(raw)
    handled = set(_SAFE_FIELDS) | {
        "id", "organization_id", "url", "slug", "owner_id", "owner", "timezone",
        "members", "members_and_guest_users", "selected_collaborators",
        "selected_additional_collaborators", "groups", "guests", "guest_members",
        "dates", "datesTimezone", "start", "end",
    } | _VOLATILE_KEYS
    for key, value in raw.items():
        if key in handled or (isinstance(key, str) and key.lower() in _PRIVATE_KEYS):
            continue
        result[key] = _scrub(value)
    return result


def _business(value):
    result = deepcopy(value)
    for key in ("id", "organization_id", "url", "slug"):
        result.pop(key, None)
    return result


def _falseish(value):
    return value is None or value is False or (type(value) is int and value == 0)


def _text(value, name, maximum, *, required=False):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string.")
    if required and not value.strip():
        raise ValueError(f"{name} is required.")
    if required and value != value.strip():
        raise ValueError(f"{name} must not have leading or trailing whitespace.")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds its bounded length.")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError(f"{name} contains unsafe control characters.")
    return value


def _serialized(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _check_serialized_size(value, bounds, message):
    if len(_serialized(value)) > min(bounds.parser_bytes, bounds.transfer_bytes):
        raise ValueError(message)


def _check_size(body, bounds):
    _check_serialized_size(body, bounds, "The native meeting request exceeds byte bounds.")


def _check_prepared_size(prepared, bounds):
    _check_serialized_size(prepared, bounds, "The prepared Boardable meeting exceeds byte bounds.")


def _check_json_bounds(value, bounds, depth=0):
    if depth > _MAX_JSON_DEPTH:
        raise WriteFailure("provider_rejected", "The Boardable readback exceeds the supported JSON nesting depth.")
    if isinstance(value, dict):
        for item in value.values():
            _check_json_bounds(item, bounds, depth + 1)
    elif isinstance(value, list):
        if len(value) > bounds.max_records:
            raise WriteFailure("provider_rejected", "The Boardable readback contains an oversized list.")
        for item in value:
            _check_json_bounds(item, bounds, depth + 1)


def _validate_update_state(before):
    try:
        _native_id(before.get("owner_id"))
        members = before.get("members")
        if not isinstance(members, list) or not members:
            raise ValueError
        if any(not isinstance(row, dict) for row in members):
            raise ValueError
        if before.get("minutes_type") != "free_form":
            raise ValueError
        if before.get("remote_option") != "no_remote":
            raise ValueError
        if before.get("remote_url") is not None or before.get("remote_url_description") is not None:
            raise ValueError
        if not _falseish(before.get("disable_remote_rsvp")):
            raise ValueError
        if before.get("guests"):
            raise ValueError
        if before.get("series_id") not in (0, None) or before.get("recurrence_id") is not None:
            raise ValueError
        if before.get("alternative_dates") is not None or before.get("additional_dates") not in (None, []):
            raise ValueError
        if before.get("group") is not None or before.get("group_id") is not None:
            raise ValueError
        for key in (
            "public_member_dashboard", "public_page", "published", "published_level",
            "minutes_published", "enable_recording", "enable_transcription", "enable_ai_summary",
            "starred_public_page", "video_conference_enabled",
        ):
            if not _falseish(before.get(key)):
                raise ValueError
        if before.get("published_at") is not None:
            raise ValueError
        if before.get("materials_published_status") is not None or before.get("published_materials_status") is not None:
            raise ValueError
        for key in ("agenda_live_version", "agenda_draft_version", "agenda_last_published_at"):
            if before.get(key) is not None:
                raise ValueError
    except (TypeError, ValueError):
        raise WriteFailure(
            "mapping_unverified",
            "The existing Boardable meeting has an unmapped guest, series, video or publication state.",
        ) from None


def _create_plan(change, config):
    fields = change.fields
    if not isinstance(fields, dict) or set(fields) - _ALLOWED_CREATE:
        raise WriteFailure("unsupported_field", "The Boardable meeting create contains unsupported fields.")
    title = _text(fields.get("title"), "title", 500, required=True)
    timezone_name = _validate_timezone(fields.get("timezone"))
    if "dates" not in fields:
        raise ValueError("Boardable meeting creation requires exactly one date.")
    dates = _validate_dates(fields["dates"], timezone_name)
    description = _text(fields.get("description", ""), "description", 20000)
    location = _text(fields.get("location", ""), "location", 500)
    remote_option = fields.get("remote_option", "no_remote")
    if remote_option != "no_remote":
        raise WriteFailure("mapping_unverified", "Only the captured no_remote option is mapped for creation.")
    owner_id = _native_id(config.get("owner_id"))
    body = {
        "title": title,
        "description": description,
        "owner_id": owner_id,
        "timezone": timezone_name,
        "dates": [dates["payload"]],
        "meeting_type": "single",
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
    }
    expected = {
        "title": title,
        "description": description,
        "location": location,
        "timezone": timezone_name,
        "owner_id": owner_id,
        "start": _utc_text(dates["start"]),
        "end": _utc_text(dates["end"]),
        "date": dates["normalized"]["date"],
        "from": dates["normalized"]["from"],
        "to": dates["normalized"]["to"],
    }
    return body, expected


def _update_body(before, identity, expected, dates_payload):
    members = [row["id"] for row in before["members"]]
    groups = [row["id"] for row in before.get("groups", [])]
    return {
        "id": identity,
        "title": expected["title"],
        "description": expected.get("description", ""),
        "owner_id": before["owner_id"],
        "timezone": expected["timezone"],
        "dates": dates_payload,
        "meeting_type": "single",
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
        "guestsChanged": False,
        "usersChanged": False,
        "public_member_dashboard": bool(before.get("public_member_dashboard", False)),
        "public_page": bool(before.get("public_page", False)),
        "enable_recording": bool(before.get("enable_recording", False)),
        "enable_transcription": bool(before.get("enable_transcription", False)),
        "enable_ai_summary": bool(before.get("enable_ai_summary", False)),
        "calendar_type": "set",
        "assignable_class": "App\\Boardable\\Meetings\\Meeting",
        "assignable_id": identity,
        "series_choice": "single",
    }


def _response_identity(raw, config, source_url, *, expected_id=None):
    if not isinstance(raw, dict):
        raise ValueError("The Boardable mutation response is not an object.")
    identity = _native_id(raw.get("id"))
    if expected_id is not None and identity != expected_id:
        raise ValueError("The Boardable mutation response identified the wrong meeting.")
    organization_id = _native_id(raw.get("organization_id"))
    if organization_id != config["organization_id"]:
        raise ValueError("The Boardable mutation response belongs to the wrong organization.")
    url, slug = _canonical(source_url, raw.get("url"))
    if raw.get("slug") != slug:
        raise ValueError("The Boardable mutation response URL and slug disagree.")
    return identity, url, slug


def _verify_create(norm, prepared, config):
    expected = prepared["create_expected"]
    if norm.get("title") != expected["title"]:
        return False
    if norm.get("description") != expected["description"]:
        return False
    if norm.get("location") != expected["location"]:
        return False
    if norm.get("timezone") != expected["timezone"] or norm.get("owner_id") != expected["owner_id"]:
        return False
    members = norm.get("members")
    if not isinstance(members, list) or [row.get("id") for row in members] != [expected["owner_id"]]:
        return False
    if norm.get("groups") != [] or norm.get("guests") != []:
        return False
    if norm.get("remote_option") != "no_remote":
        return False
    if norm.get("remote_url") is not None or norm.get("remote_url_description") is not None:
        return False
    if not _falseish(norm.get("disable_remote_rsvp")):
        return False
    for key in (
        "public_member_dashboard", "public_page", "published", "published_level",
        "minutes_published", "enable_recording", "enable_transcription", "enable_ai_summary",
        "starred_public_page", "video_conference_enabled",
    ):
        if not _falseish(norm.get(key)):
            return False
    if norm.get("published_at") is not None or norm.get("materials_published_at") is not None:
        return False
    if norm.get("materials_published_status") is not None or norm.get("published_materials_status") is not None:
        return False
    if norm.get("series_id") not in (0, None) or norm.get("recurrence_id") is not None:
        return False
    if norm.get("alternative_dates") is not None or norm.get("additional_dates") not in (None, []):
        return False
    dates = norm.get("datesTimezone")
    if not isinstance(dates, list) or len(dates) != 1:
        return False
    row = dates[0]
    if row.get("id") != norm.get("id"):
        return False
    if (row.get("date"), row.get("from"), row.get("to"), row.get("timezone")) != (
            expected["date"], expected["from"], expected["to"], expected["timezone"]):
        return False
    return norm.get("start") == expected["start"] and norm.get("end") == expected["end"]


class BoardableMeetingWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__("boardable", transport)

    def credentials(self, source, context):
        config = context.credentials.get(self.provider)
        if not isinstance(config, dict) or config.get("current_meeting_form") is not True:
            raise WriteFailure("permission_denied", "The explicit Boardable native meeting form credential is required.")
        _source_org(source.url)
        if (config.get("org_url") != source.url or config.get("tenant") != context.tenant
                or not context.tenant):
            raise WriteFailure("permission_denied", "The exact trusted Boardable organization and tenant binding is required.")
        try:
            _native_id(config.get("organization_id"))
        except ValueError:
            raise WriteFailure("permission_denied", "A bounded native Boardable organization ID is required.") from None
        allowed = config.get("allowed_namespaces")
        if (not isinstance(allowed, (list, tuple, set, frozenset)) or source.namespace not in allowed
                or (context.allowed_namespaces is not None and source.namespace not in context.allowed_namespaces)):
            raise WriteFailure("permission_denied", "The Boardable source namespace is outside current policy.")
        if source.options or source.body or source.input_format is not None:
            raise WriteFailure("mapping_unverified", "The native meeting form source accepts no options or body.")
        session_cookie = config.get("session_cookie")
        xsrf_token = config.get("xsrf_token")
        for value in (session_cookie, xsrf_token):
            if (not isinstance(value, str) or not value or len(value) > 16384
                    or any(ord(char) < 32 or ord(char) == 127 for char in value)):
                raise WriteFailure("credentials_required", "Safe trusted Boardable session and XSRF values are required.")
        if _COOKIE_RE.fullmatch(session_cookie) is None:
            raise WriteFailure("credentials_required", "The supplied Boardable session cookie is not a safe header.")
        if "owner_id" in config:
            try:
                _native_id(config["owner_id"])
            except ValueError:
                raise WriteFailure("permission_denied", "The trusted Boardable owner ID is invalid.") from None
        return config

    def validate_source(self, source, context):
        if source.provider != self.provider or not source.namespace:
            raise ValueError("A Boardable native meeting source requires the exact provider and namespace.")
        self.credentials(source, context)

    def authorize(self, source, change, context):
        config = self.credentials(source, context)
        if (change.entity != "meeting" or change.operation not in {"create", "update"} or change.files
                or any(value is not None for value in (
                    change.parent_id, change.language, change.page_number,
                ))):
            raise WriteFailure("mapping_unverified", "Only Boardable meeting create/update without files or parents is mapped.")
        if not isinstance(change.fields, dict):
            raise ValueError("The Boardable meeting fields must be an object.")
        if change.operation == "create":
            if change.resource_id is not None or change.meeting_id is not None:
                raise ValueError("Boardable meeting creation cannot select an existing meeting.")
            try:
                _native_id(config.get("owner_id"))
            except ValueError:
                raise WriteFailure("permission_denied", "Creation requires an explicit trusted owner ID.") from None
            operation = "meeting:create"
        else:
            identity = _change_id(change.resource_id)
            if change.meeting_id is not None and str(change.meeting_id) != str(identity):
                raise ValueError("The optional meeting_id must equal the native resource_id.")
            ids = config.get("meeting_ids")
            urls = config.get("meeting_urls")
            if (not isinstance(ids, (list, tuple, set, frozenset))
                    or not any(not isinstance(value, bool) and str(value) == str(identity) for value in ids)
                    or not isinstance(urls, dict) or not isinstance(urls.get(str(identity)), str)):
                raise WriteFailure("permission_denied", "The selected meeting is outside current Boardable policy.")
            url = urls[str(identity)]
            canonical, _ = _canonical(source.url, url)
            if canonical != url:
                raise WriteFailure("permission_denied", "The trusted meeting URL is not canonical.")
            operation = "meeting:update"
        permissions = config.get("permissions")
        if (not isinstance(permissions, (list, tuple, set, frozenset))
                or operation not in permissions):
            raise WriteFailure("permission_denied", "This Boardable meeting operation is outside current policy.")
        return config

    def _request(self, source, context, url, method, body, bounds, deadline, *, write=False, expected_status=200):
        config = self.credentials(source, context)
        if context.check_cancelled():
            raise WriteCancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure("deadline_exceeded", "The Boardable operation deadline expired.")
        headers = {
            "Accept": "application/json",
            "Cookie": config["session_cookie"],
            "X-Requested-With": "XMLHttpRequest",
            "X-XSRF-TOKEN": config["xsrf_token"],
        }
        encoded = None
        if body is not None:
            encoded = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
            limit = min(bounds.parser_bytes, bounds.transfer_bytes)
            if len(encoded) > limit:
                raise ValueError("The Boardable native request exceeds byte bounds.")
            headers["Content-Type"] = "application/json"
        response_limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        try:
            response = self.transport.send(
                url, method=method, body=encoded, headers=headers,
                byte_limit=response_limit, deadline_seconds=remaining,
            )
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite() from None
        if not isinstance(response, WriteResponse) or len(response.content) > response_limit:
            raise AmbiguousWrite("Invalid or oversized Boardable response.")
        if response.status in {401, 403}:
            raise WriteFailure("permission_denied", "Boardable denied the operation.")
        if response.status in {409, 412}:
            raise WriteFailure("conflict", "Boardable rejected a conflicting change.")
        if not 200 <= response.status < 300:
            if write:
                raise AmbiguousWrite("Boardable did not return a confirmed success response.")
            raise WriteFailure("provider_rejected", f"Boardable rejected the read request (HTTP {response.status}).")
        if response.status != expected_status:
            if write:
                raise AmbiguousWrite("Boardable returned an unexpected success status.")
            raise WriteFailure("provider_rejected", f"Boardable returned unexpected HTTP {response.status} for a read request.")
        try:
            return json.loads(response.content)
        except (UnicodeError, ValueError):
            if write:
                raise AmbiguousWrite("Boardable returned an invalid JSON mutation response.") from None
            raise WriteFailure("provider_rejected", "Boardable returned an invalid JSON read response.") from None

    def _read_meeting(self, source, canonical_url, context, bounds, deadline):
        value = self._request(
            source, context, canonical_url + "?format=json", "GET", None, bounds, deadline, write=False,
        )
        _check_json_bounds(value, bounds)
        if not isinstance(value, dict) or not isinstance(value.get("meeting"), dict):
            raise WriteFailure("provider_rejected", "The Boardable readback does not contain a meeting object.")
        return value

    def prepare(self, source, change, context, bounds, deadline):
        config = self.authorize(source, change, context)
        if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
            raise ValueError("A bounded change key is required.")
        if change.operation == "create":
            body, expected = _create_plan(change, config)
            _check_size(body, bounds)
            prepared = {
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
        before_raw = self._read_meeting(source, original_url, context, bounds, deadline)
        before = _normalize_meeting(
            before_raw, config, source.url, expected_id=identity, expected_url=original_url,
        )
        _validate_update_state(before)
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected Boardable meeting differs from readback.")
        fields = change.fields
        if not isinstance(fields, dict) or not fields or set(fields) - _ALLOWED_UPDATE:
            raise WriteFailure("unsupported_field", "The Boardable meeting update contains unsupported fields.")
        title = _text(fields.get("title", before["title"]), "title", 500, required=True)
        description = _text(fields.get("description", before.get("description", "")), "description", 20000)
        location = _text(fields.get("location", before.get("location", "")), "location", 500)
        timezone_name = _validate_timezone(fields.get("timezone", before["timezone"]))
        if "dates" in fields:
            dates = _validate_dates(
                fields["dates"], timezone_name, original_id=identity, update=True,
            )
        else:
            old = before["datesTimezone"][0]
            dates = _validate_dates(
                [{"date": old["date"], "from": old["from"], "to": old["to"], "id": identity}],
                timezone_name, original_id=identity, update=True,
            )
        expected = deepcopy(before)
        expected.update({
            "title": title,
            "description": description,
            "location": location,
            "timezone": timezone_name,
            "start": _utc_text(dates["start"]),
            "end": _utc_text(dates["end"]),
            "datesTimezone": [dates["normalized"]],
        })
        body = _update_body(before, identity, expected, [dates["payload"]])
        _check_size(body, bounds)
        prepared = {
            "change": asdict(change),
            "before": before,
            "expected": expected,
            "before_fingerprint": fingerprint,
            "meeting_url": original_url,
            "native": {
                "method": "POST", "url": source.url + "meetings_v2/" + str(identity),
                "headers": {}, "body": body,
            },
            "conflict_semantics": "preflight_compare_not_atomic_upstream_cas",
        }
        _check_prepared_size(prepared, bounds)
        return prepared

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        config = self.authorize(source, change, context)
        if change.operation == "create":
            if context.check_cancelled():
                raise WriteCancelled()
            if persist:
                if persist({"resource_id": None, "meeting_url": None, "outbound_started": True}):
                    raise WriteCancelled()
            elif context.check_cancelled():
                raise WriteCancelled()
            raw = self._request(
                source, context, prepared["native"]["url"], "POST",
                prepared["native"]["body"], bounds, deadline, write=True, expected_status=201,
            )
            try:
                identity, canonical_url, _ = _response_identity(raw, config, source.url)
            except (TypeError, ValueError):
                raise AmbiguousWrite("Creation returned no verified native ID and canonical URL.") from None
            saved = {"resource_id": str(identity), "meeting_url": canonical_url, "outbound_started": True}
            cancelled = persist(saved) if persist else context.check_cancelled()
            if cancelled or monotonic() >= deadline:
                raise AmbiguousWrite("Creation returned its native identity; readback remains unconfirmed.")
            try:
                return self.reconcile(source, prepared, saved, context, bounds, deadline)
            except (WriteCancelled, WriteFailure, ValueError):
                raise AmbiguousWrite("Creation was sent before readback could be confirmed.") from None
        identity = _change_id(change.resource_id)
        original_url = prepared["meeting_url"]
        try:
            current_raw = self._read_meeting(source, original_url, context, bounds, deadline)
            current = _normalize_meeting(
                current_raw, config, source.url, expected_id=identity, expected_url=original_url,
            )
        except (WriteFailure, ValueError):
            raise WriteFailure("conflict", "The Boardable meeting changed after planning.") from None
        if canonical_hash(current) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "The Boardable meeting changed after planning.")
        if context.check_cancelled():
            raise WriteCancelled()
        if persist:
            if persist({"resource_id": str(identity), "meeting_url": original_url, "outbound_started": True}):
                raise WriteCancelled()
        elif context.check_cancelled():
            raise WriteCancelled()
        raw = self._request(
            source, context, prepared["native"]["url"], "POST",
            prepared["native"]["body"], bounds, deadline, write=True, expected_status=200,
        )
        try:
            returned_id, canonical_url, _ = _response_identity(
                raw, config, source.url, expected_id=identity,
            )
        except (TypeError, ValueError):
            raise AmbiguousWrite("Update returned no verified native ID and canonical URL.") from None
        saved = {"resource_id": str(returned_id), "meeting_url": canonical_url, "outbound_started": True}
        cancelled = persist(saved) if persist else context.check_cancelled()
        if cancelled or monotonic() >= deadline:
            raise AmbiguousWrite("Update returned its native identity; readback remains unconfirmed.")
        try:
            return self.reconcile(source, prepared, saved, context, bounds, deadline)
        except (WriteCancelled, WriteFailure, ValueError):
            raise AmbiguousWrite("Update was sent before readback could be confirmed.") from None

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        config = self.credentials(source, context)
        item = item or {}
        raw_identity = item.get("resource_id")
        if raw_identity is None:
            return {
                "state": "uncertain", "reconciled": True,
                "reason": "No confirmed native identity was persisted; no title matching or POST replay.",
            }
        try:
            identity = _native_id(raw_identity if isinstance(raw_identity, int) else int(raw_identity))
        except (TypeError, ValueError):
            return {"state": "uncertain", "reconciled": True,
                    "reason": "The persisted native identity is invalid."}
        persisted_url = item.get("meeting_url")
        try:
            canonical_url, _ = _canonical(source.url, persisted_url)
            if canonical_url != persisted_url:
                raise ValueError
        except ValueError:
            return {"state": "uncertain", "resource_id": str(identity), "reconciled": True,
                    "reason": "The persisted canonical meeting URL is missing or unsafe."}
        try:
            raw = self._read_meeting(source, persisted_url, context, bounds, deadline)
            if change.operation == "create":
                norm = _normalize_meeting(
                    raw, config, source.url, expected_id=identity, expected_url=persisted_url,
                )
                match = _verify_create(norm, prepared, config)
            else:
                expected_id = _change_id(change.resource_id)
                if identity != expected_id:
                    raise ValueError
                norm = _normalize_meeting(
                    raw, config, source.url, expected_id=expected_id, expected_url=persisted_url,
                )
                match = canonical_hash(_business(norm)) == canonical_hash(_business(prepared["expected"]))
            return {
                "state": "succeeded" if match else "uncertain",
                "resource_id": str(identity),
                "meeting_url": persisted_url,
                "readback": norm,
                "reconciled": True,
            }
        except (WriteFailure, ValueError, TypeError):
            return {
                "state": "uncertain", "resource_id": str(identity), "meeting_url": persisted_url,
                "reconciled": True,
                "reason": "The exact persisted Boardable URL did not confirm the requested business state.",
            }
