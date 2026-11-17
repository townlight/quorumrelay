"""Observed secure calendar range read and saved rows, distinct from public JSON."""

from datetime import date, datetime
import json
import re
from time import monotonic

from ..models import Error, OperationResult
from .native import make_bundle

FORMAT = "gworks-secure-calendar-json"
URL = "https://api.gworks.cloud/cms/secure/city/meeting/list"


def namespace(source):
    city = source.options.get("gworks_city_id") if isinstance(source.options, dict) else None
    if source.url != URL or not isinstance(city, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", city):
        raise ValueError("Secure calendar requires the exact API URL and an explicit configured city ID.")
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


def fetch(source, bound_namespace, request, bounds, context, transport):
    """One observed client calendar POST; neither a mutation nor paged discovery."""
    namespace(source)
    if (any(key in request for key in ("external_id", "related", "caption_language"))
            or not bounds.date_from or not bounds.date_to or bounds.checkpoint or source.body):
        raise ValueError("Select one explicit inclusive date range; no detail/body/paging semantics are mapped.")
    start, end = date.fromisoformat(bounds.date_from), date.fromisoformat(bounds.date_to)
    if start > end:
        raise ValueError("Calendar range start must not exceed its end.")
    config = context.credentials.get("gworks")
    allowed = config.get("allowed_namespaces") if isinstance(config, dict) else None
    if (not isinstance(config, dict) or not isinstance(config.get("token"), str) or not config["token"]
            or not context.tenant or config.get("tenant") != context.tenant
            or config.get("city_id") != source.options["gworks_city_id"]
            or config.get("origin") != "https://api.gworks.cloud"
            or not isinstance(allowed, (list, tuple, set, frozenset))
            or bound_namespace not in allowed):
        return OperationResult("failed", errors=(Error("credentials_required",
            "A trusted tenant/city/origin-scoped GWorks read credential is required."),),
            operation_id=context.operation_id)
    payload = {"range": {"cms_meeting.meeting_ts": {
        "f": f"{start.year}-{start.month}-{start.day} 00:00:00",
        "t": f"{end.year}-{end.month}-{end.day} 23:59:59"}},
        "columns": [{"data": "cms_meeting.id"}, {"data": "cms_meeting.meeting_ts", "orderable": "true"},
                    {"data": "cms_meeting.title"}, {"data": "cms_meeting.agenda_published_fl"}],
        "order": [{"column": 1, "dir": "asc"}], "start": 0}
    deadline = monotonic() + bounds.deadline_seconds
    if context.check_cancelled():
        return OperationResult("cancelled", operation_id=context.operation_id)
    try:
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        body = json.dumps(payload, separators=(",", ":")).encode()
        if len(body) > limit:
            raise ValueError("The explicit calendar query exceeds request byte bounds.")
        response = transport.request(URL, method="POST", body=body, headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + config["token"]},
            byte_limit=limit, deadline_seconds=bounds.deadline_seconds,
            allowed_origins=("https://api.gworks.cloud",), allow_redirects=False)
        if context.check_cancelled():
            return OperationResult("cancelled", operation_id=context.operation_id)
        if response.url != URL or len(response.content) > limit or monotonic() >= deadline:
            raise ValueError("The exact bounded secure calendar response was unavailable.")
        if response.status in {401, 403}:
            return OperationResult("failed", errors=(Error("permission_denied",
                "The provider denied the secure calendar read.", source=source.url,
                details={"http_status": response.status}),), operation_id=context.operation_id)
        if (response.status != 200
                or response.content_type.split(";", 1)[0].lower().strip() != "application/json"):
            raise ValueError("The secure calendar did not return its declared JSON response.")
        bundle = parse_bundle(source, bound_namespace, response.content)
        selected, unknown, filtered = [], [], 0
        for record in bundle["records"]:
            day = record["normalized"]["meeting_date"]
            if day and not bounds.date_from <= day <= bounds.date_to:
                filtered += 1
                continue
            if not day:
                unknown.append(record["identity"]["external_id"])
            selected.append(record)
        bundle["records"] = selected
        if context.check_cancelled():
            return OperationResult("cancelled", operation_id=context.operation_id)
        if len(selected) > bounds.max_records or monotonic() >= deadline:
            raise ValueError("The unpaged selected calendar response exceeds configured bounds.")
        return OperationResult("partial", bundle, coverage={"scope": "one observed client calendar range POST",
            "source_complete": False, "catalog_complete": False, "pages": 1, "pagination": "not_established",
            "returned_records": len(selected), "filtered_records": filtered, "unknown_date_records": unknown,
            "city_binding": "trusted_credential_configuration_not_asserted_by_response",
            "timestamp_semantics": "ISO_local_date_checked_numeric_epoch_units_not_inferred"},
            operation_id=context.operation_id)
    except (ValueError, TypeError, KeyError, OSError):
        return OperationResult("failed", errors=(Error("gworks_calendar_unverified",
            "The exact secure calendar read could not be verified.", source=source.url),),
            operation_id=context.operation_id)
