"""Explicit documented account reads; no guessed pagination or response schema."""

import json
import re
from copy import deepcopy
from dataclasses import replace
from time import monotonic
from uuid import UUID

from ..models import Error, OperationResult
from .account_api import ORIGINS, credentials, headers, reject_credential_echo
from .native import make_bundle


def guid(value):
    if not isinstance(value, str) or str(UUID(value)) != value.lower():
        raise ValueError("A canonical GUID is required.")
    return value


def essential_filters(value):
    fields = {"Words", "CreatedMeetingFromDate", "CreatedMeetingToDate", "ArchivedState", "MeetingTypeIds"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("Supply exactly the documented MeetingListFilters fields.")
    if (not isinstance(value["Words"], str) or type(value["ArchivedState"]) is not int
            or value["ArchivedState"] not in {-1, 0, 1, 2}
            or not isinstance(value["MeetingTypeIds"], list)
            or any(not isinstance(v, str) for v in value["MeetingTypeIds"])):
        raise ValueError("Invalid MeetingListFilters values.")
    for key in ("CreatedMeetingFromDate", "CreatedMeetingToDate"):
        date = value[key]
        if (not isinstance(date, dict) or set(date) != {"Day", "Month", "Year"}
                or any(type(v) is not int for v in date.values())):
            raise ValueError("Filter dates require integer Day, Month and Year.")
        if set(date.values()) != {-1}:
            from datetime import date as calendar_date
            calendar_date(date["Year"], date["Month"], date["Day"])
    return deepcopy(value)


def route(source, request):
    resource = request.get("api_resource", "meeting" if source.provider == "municode-meetings" else "media")
    identity = request.get("external_id")
    if source.provider == "municode-meetings":
        if resource == "collection":
            offset = request.get("offset")
            if type(offset) is not int or offset < 0:
                raise ValueError("Essential collection requires an explicit nonnegative offset; no stride is inferred.")
            return "POST", f"/PublicApi/meeting/collection/{offset}", essential_filters(request.get("filters")), resource
        if resource not in {"meeting", "item", "multimedia"}:
            raise ValueError("Use a documented meeting, item, multimedia or collection resource.")
        if resource == "multimedia":
            identity = guid(identity)
        elif not isinstance(identity, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identity) is None:
            raise ValueError("Meeting/item detail requires a bounded path-safe supplied ID.")
        path = "/PublicApi/" + ("meeting/multimedia/" if resource == "multimedia" else resource + "/")
        return "GET", path + identity, None, resource
    if resource not in {"media", "videos", "playlists"}:
        raise ValueError("Use the documented TelVue media, videos or playlists resource.")
    suffix = ""
    if identity is not None:
        if resource == "videos" or not isinstance(identity, str) or re.fullmatch(r"[1-9][0-9]{0,18}", identity) is None:
            raise ValueError("Only media/playlists have documented detail routes, requiring a decimal ID.")
        suffix = "/" + identity
    return "GET", "/api/v2/" + resource + suffix + ".json", None, resource


def telvue_bundle(source, namespace, content, input_format):
    raw = json.loads(content)
    plural = {"telvue-connect-media-json": "media", "telvue-connect-videos-json": "videos",
              "telvue-connect-playlists-json": "playlists"}[input_format]
    singular = {"media": "medium", "playlists": "playlist"}.get(plural)
    values = raw.get(plural) if isinstance(raw, dict) else None
    if values is None and singular and isinstance(raw, dict) and singular in raw:
        values = [raw[singular]]
    if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
        raise ValueError("The documented TelVue JSON envelope was not supplied.")
    rows, seen = [], set()
    for value in values:
        identity = value.get("id")
        if type(identity) is not int or identity <= 0 or identity in seen:
            raise ValueError("TelVue rows require distinct positive provider IDs.")
        seen.add(identity)
        normalized = {"external_id": str(identity), "title": value.get("title", value.get("name")),
                      "description": value.get("description", value.get("short_summary")),
                      "url": source.url, "source_created": value.get("created_at"),
                      "source_updated": value.get("updated_at"), "time_zone_status": "unknown"}
        recordings = []
        for item in value.get("sources") or []:
            if not isinstance(item, dict):
                raise ValueError("TelVue sources must be objects.")
            from .native import _url
            if url := _url(source, item.get("url")):
                recordings.append({"url": url, "media_type": item.get("type"),
                                   "duration_seconds": value.get("duration_in_seconds"), "source_fields": deepcopy(item)})
        normalized["recordings"] = recordings
        normalized["chapters"] = deepcopy(value.get("chapters", []))
        normalized["playables_count"] = value.get("playables_count")
        kind = "playlist" if plural == "playlists" else ("video" if plural == "videos" else "media")
        rows.append((normalized, value, kind))
    bundle = make_bundle(source, namespace, content, input_format, rows)
    for record in bundle["records"]:
        original = record["original"]
        if isinstance(original.get("transcript"), str):
            record["text"] = [{"text": original["transcript"], "field": "transcript", "citation_url": source.url}]
        if "updated_at" in original:
            record["source_revision"] = {"kind": "provider_supplied", "value": original["updated_at"]}
    return bundle


def essential_bundle(source, namespace, content):
    raw = json.loads(content)
    structure = raw.get("meetingStructure") if isinstance(raw, dict) else None
    if not isinstance(structure, dict):
        raise ValueError("The documented meetingStructure wrapper is required.")
    identity = guid(structure.get("MeetingId"))
    normalized = {"external_id": identity, "url": source.url,
                  "multimedia": deepcopy(structure), "time_zone_status": "unknown"}
    bundle = make_bundle(source, namespace, content, "essential-multimedia-json", [(normalized, structure, "meeting_multimedia")])
    parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
              "external_id": identity, "parent": None}
    bundle["records"][0]["identity"]["parent"] = parent
    bundle["records"][0]["relationships"] = [{"relation": "meeting", "identity": deepcopy(parent)}]
    return bundle


def fetch_account(source, namespace, request, bounds, context, transport):
    if not context.allows("fetch", namespace):
        raise ValueError("The account namespace is not authorized for fetch.")
    if bounds.checkpoint:
        raise ValueError("These routes have no verified continuation contract; supply an explicit offset only where documented.")
    if bounds.date_from or bounds.date_to or source.body:
        raise ValueError("These response schemas do not establish meeting date/body filtering; use explicit documented collection filters.")
    config = credentials(source, context)
    method, path, body, resource = route(source, request)
    encoded = None if body is None else json.dumps(body, allow_nan=False).encode()
    if encoded and len(encoded) > bounds.parser_bytes:
        raise ValueError("The request exceeds parser bounds.")
    coverage = {"scope": "one explicitly requested account API response", "catalog_complete": False,
                "source_complete": False, "pagination": "unverified; no automatic continuation",
                "date_filter": "provider CreatedMeeting filters only" if resource == "collection" else "not applied",
                "meeting_dates": "not inferred from media creation timestamps"}
    if context.check_cancelled():
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    url = ORIGINS[source.provider] + path
    deadline = monotonic() + bounds.deadline_seconds
    try:
        request_headers = headers(source, context)
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        response = transport.request(url, method=method, body=encoded, headers=request_headers,
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes), deadline_seconds=bounds.deadline_seconds,
            allowed_origins=(ORIGINS[source.provider],), allow_redirects=False)
        if context.check_cancelled():
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if (response.status != 200 or response.url != url or monotonic() >= deadline
                or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)):
            raise ValueError("The response did not satisfy status, exact route, byte or deadline bounds.")
        reject_credential_echo(response.content, config)
        captured_source = replace(source, url=url)
        if source.provider == "telvue":
            bundle = telvue_bundle(captured_source, namespace, response.content, f"telvue-connect-{resource}-json")
            if request.get("external_id") is not None and (len(bundle["records"]) != 1 or
                    bundle["records"][0]["identity"]["external_id"] != request["external_id"]):
                raise ValueError("The detail response identity does not match the requested resource.")
        elif resource == "multimedia":
            bundle = essential_bundle(captured_source, namespace, response.content)
            if bundle["records"][0]["identity"]["external_id"].lower() != request["external_id"].lower():
                raise ValueError("The multimedia response belongs to another meeting.")
        else:
            # Generic HttpResponseMessage is the entire documented response contract.
            # Capture exact bytes without interpreting an unknown envelope as rows.
            bundle = make_bundle(captured_source, namespace, response.content, "essential-unmapped-response", [])
            coverage["schema_mapping"] = "unverified; raw response only, no normalized records inferred"
        returned = len(bundle["records"])
        bundle["records"] = bundle["records"][:bounds.max_records]
        coverage.update({"returned_records": returned, "selected_records": len(bundle["records"]),
                         "truncated": returned > bounds.max_records, "api_resource": resource,
                         "requested_id": request.get("external_id"), "offset": request.get("offset")})
        return OperationResult("partial", bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception:
        return OperationResult("failed", errors=(Error("account_read_failed",
            "The account response could not be safely retrieved or verified; no credential or response details are exposed."),),
            coverage=coverage, operation_id=context.operation_id)
