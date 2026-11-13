"""Bounded CivicWeb (iCompass) meeting and meeting-document listing from the public MeetingsService.

Routes read (all GET, public, no sign-in), relative to the configured tenant origin:

* ``/Services/MeetingsService.svc/meetings?from=YYYY-MM-DD&to=YYYY-MM-DD`` - meetings in a date range
* ``/Services/MeetingsService.svc/meetings/{id}/meetingDocuments`` - one meeting's documents
* ``/Portal/MeetingTypeList.aspx`` - the portal's meeting types (bodies), used to name each meeting's
  body and to leave out calendar and notice types that are not meetings

A document opens at ``/document/{id}/{name}.html`` or ``.pdf``. Nothing here downloads a document.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from html import unescape
from html.parser import HTMLParser
from time import monotonic
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .contracts import RetrievalError, _origin
from .discovery import _checkpoint, _resume
from .identification import validate_source
from .native import make_bundle

MEETINGS_FORMAT = "civicweb-meetings-json"
DOCUMENTS_FORMAT = "civicweb-meeting-documents-json"
SERVICE = "/Services/MeetingsService.svc/meetings"
TYPE_LIST = "/Portal/MeetingTypeList.aspx"
_RECORD_TYPES = {"meeting", "recording", "document", "agenda_item", "transcript"}
_ID = re.compile(r"[1-9][0-9]{0,18}")
_TENANT = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.civicweb\.net")
_DATE_SUFFIX = re.compile(r"\s*-\s*\d{1,2} [A-Za-z]{3,9} \d{4}\s*$")
_CANCEL_MARK = re.compile(r"^[\s*\-]*cancel{1,2}ed\b[\s*\-]*|[\s*\-]*\bcancel{1,2}ed[\s*\-]*$", re.I)
# Calendar and notice meeting types are not meetings ("Rolling Calendar", "Public Meetings Notice").
_NOT_MEETINGS = re.compile(
    r"\b(?:notices?|reports?|budgets?|ordinances?|financials?|newsletters?|messages?|profile|"
    r"applications?|articles?)\b|\bcalendar\b", re.I)
# DocumentType numbers as the portal's own pages use them; others are kept unmapped.
_DOCUMENT_KINDS = {1: ("agenda", "html"), 4: ("agenda_packet", "pdf"), 9: ("minutes", "html"),
                   10: ("minutes", "pdf"), 53: ("minutes_adopted", "pdf")}


def _squash(value):
    return " ".join(str(value or "").split())


def tenant_origin(source):
    """The configured tenant origin; i.civicweb.net is iCompass's own host, not a city tenant."""
    parts = urlsplit(source.url)
    host = (parts.hostname or "").lower()
    if (parts.scheme != "https" or not _TENANT.fullmatch(host) or host == "i.civicweb.net"
            or parts.port not in {None, 443}):
        raise ValueError("CivicWeb listing requires an HTTPS https://{tenant}.civicweb.net source URL.")
    return f"https://{host}"


class _TypeList(HTMLParser):
    """Meeting types that have a meetings page: links titled ``meeting-type-item-title``."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.types, self._active = [], None

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "a" and "meeting-type-item-title" in (fields.get("class") or "").split():
            href = urlsplit(fields.get("href") or "")
            found = parse_qs(href.query).get("type", [""])[0]
            if href.path.lower() == "/portal/meetinginformation.aspx" and _ID.fullmatch(found):
                self._active = {"id": found, "name": ""}
                self.types.append(self._active)

    def handle_data(self, data):
        if self._active is not None:
            self._active["name"] += data

    def handle_endtag(self, tag):
        if tag == "a":
            self._active = None


def meeting_types(content):
    parser = _TypeList()
    parser.feed(content.decode("utf-8", errors="replace"))
    parser.close()
    found = {}
    for item in parser.types:
        name = _squash(unescape(item["name"]))
        if name:
            found.setdefault(item["id"], name)
    if not found:
        raise ValueError("The CivicWeb meeting-type list exposed no linked meeting types.")
    return found


def derived_body(name):
    """"LOVELAND CITY COUNCIL MEETING - 04 Nov 2026" is the body "LOVELAND CITY COUNCIL MEETING"."""
    return _squash(_CANCEL_MARK.sub("", _DATE_SUFFIX.sub("", _squash(name))))


def _json_list(content, label):
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeError):
        raise ValueError(f"The CivicWeb {label} response was not valid JSON.") from None
    if not isinstance(payload, list):
        raise ValueError(f"The CivicWeb {label} response must be a JSON array.")
    return payload


def _meeting_row(source, raw, types=None):
    """One meeting row, or None when it lacks the identity, title or date every record needs."""
    identifier = raw.get("Id")
    name = _squash(raw.get("Name"))
    day = str(raw.get("MeetingDate") or "")[:10]
    if type(identifier) is not int or identifier <= 0 or not name or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return None
    start = str(raw.get("MeetingDateTime") or "")
    type_id = raw.get("TypeId")
    type_name = (types or {}).get(str(type_id)) if type(type_id) is int else None
    normalized = {
        "external_id": str(identifier), "title": name, "meeting_date": day,
        "source_start": start.replace(" ", "T") + ":00" if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", start) else None,
        "time_zone_status": "unknown",
        "body": type_name or derived_body(name),
        "body_source": "meeting_type_list" if type_name else "title_with_date_and_cancellation_markers_removed",
        "meeting_type_id": str(type_id) if type(type_id) is int else None,
        "location": _squash(raw.get("MeetingLocation")) or None,
        "url": _origin(source.url) + f"/Portal/MeetingInformation.aspx?Id={identifier}",
        "documents": [], "recordings": [], "agenda_items": [],
        "documents_availability": "not_supplied_by_meeting_listing",
        "recordings_availability": "not_supplied_by_meeting_listing",
        "agenda_items_availability": "not_supplied_by_meeting_listing",
        "source_status": {"published": raw.get("Published"), "external_calendar": raw.get("ExternalCalendar"),
                          "video_icon": raw.get("VideoIcon"),
                          "title_marks_cancelled": "cancel" in name.casefold()},
    }
    return normalized, deepcopy(raw), "meeting"


def meetings_bundle(source, namespace, content, *, rows=None, types=None):
    payload = _json_list(content, "meetings")
    chosen = rows if rows is not None else [
        row for item in payload if isinstance(item, dict) and (row := _meeting_row(source, item, types))]
    return make_bundle(source, namespace, content, MEETINGS_FORMAT, chosen)


def _document_url(origin, row):
    kind = _DOCUMENT_KINDS.get(row.get("DocumentType"))
    if row.get("IsPublic") is not True:
        return None
    stem = quote(_squash(row.get("Name")) or "document", safe="")
    # The mapped DocumentType gives the suffix; an unmapped type opens at the bare document route.
    return f"{origin}/document/{row['Id']}/{stem}.{kind[1]}" if kind else f"{origin}/document/{row['Id']}/"


def _document_rows(source, payload):
    origin = _origin(source.url)
    rows = []
    for raw in payload:
        if (not isinstance(raw, dict) or type(raw.get("Id")) is not int or raw["Id"] <= 0
                or type(raw.get("MeetingId")) is not int or raw["MeetingId"] <= 0):
            continue
        kind = _DOCUMENT_KINDS.get(raw.get("DocumentType"))
        url = _document_url(origin, raw)
        original = {key: deepcopy(value) for key, value in raw.items() if key != "Html"}
        original["Html"] = {"omitted_from_record": True, "characters": len(raw.get("Html") or ""),
                            "note": "The exact bytes are in the capture."}
        rows.append(({
            "external_id": str(raw["Id"]), "title": _squash(raw.get("Name")) or None,
            "kind": kind[0] if kind else "document", "format": kind[1] if kind else None,
            "document_type": raw.get("DocumentType"), "url": url,
            "url_availability": "public_link" if url else "not_public",
            "is_public": raw.get("IsPublic"), "meeting_external_id": str(raw["MeetingId"]),
            "has_html_body": bool(raw.get("Html")), "time_zone_status": "unknown",
        }, original, "document"))
    return rows


def documents_bundle(source, namespace, content):
    bundle = make_bundle(source, namespace, content, DOCUMENTS_FORMAT,
                         _document_rows(source, _json_list(content, "meeting documents")))
    for record in bundle["records"]:
        parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
                  "external_id": record["normalized"]["meeting_external_id"], "parent": None}
        record["identity"]["parent"] = parent
        record["relationships"] = [{"relation": "meeting", "identity": parent}]
    return bundle


def _get(transport, url, origin, bounds, deadline):
    response = transport.request(url, byte_limit=bounds.parser_bytes,
                                 deadline_seconds=max(.001, deadline - monotonic()),
                                 allowed_origins=(origin,), allow_redirects=False,
                                 headers={"Accept": "application/json, text/html"})
    if monotonic() >= deadline:
        raise RetrievalError("provider_deadline_exceeded")
    if response.status != 200:
        raise RetrievalError("provider_http_error", status=response.status)
    if response.url != url or len(response.content) > bounds.parser_bytes:
        raise RetrievalError("provider_response_outside_contract", status=response.status)
    return response


def _failure(errors, failures, source, pages, kind, error):
    code = error.code if isinstance(error, RetrievalError) else "provider_page_failed"
    details = ({"http_status": error.status} if isinstance(error, RetrievalError) and error.status is not None
               else {})
    errors.append(Error(code, "A CivicWeb public page could not be retrieved or parsed.",
                        retryable=True, source=source.url, details=details))
    failures.append({"page": pages, "kind": kind, "reason": code, **details})


def _task(value):
    if not isinstance(value, dict):
        raise ValueError("The CivicWeb continuation task is invalid.")
    kind = value.get("kind")
    if kind == "meetings" and set(value) <= {"kind", "offset", "sha256"}:
        offset, digest = value.get("offset", 0), value.get("sha256")
        if (type(offset) is not int or not 0 <= offset <= 100000 or (offset and digest is None)
                or (digest is not None and not re.fullmatch(r"[0-9a-f]{64}", str(digest)))):
            raise ValueError("The CivicWeb continuation position is invalid.")
        return {"kind": "meetings", "offset": offset, "sha256": digest}
    if kind == "documents" and set(value) == {"kind", "meeting"} and _ID.fullmatch(str(value["meeting"])):
        return {"kind": "documents", "meeting": value["meeting"]}
    raise ValueError("The CivicWeb continuation task is invalid.")


def discover_public(engine, source, namespace, bounds, context, transport, *, record_types=None):
    """List a tenant's public meetings in an explicit date range, and optionally their documents.

    ``record_types`` of ``["meeting"]`` (the default) lists meetings; adding ``"document"`` also reads
    each returned meeting's document list, one request per meeting inside the page/deadline bounds.
    """
    origin = tenant_origin(source)
    resolved = validate_source(source, context)
    if namespace is not None and namespace != resolved:
        raise ValueError("The CivicWeb source namespace did not match the configured tenant.")
    namespace = resolved
    if not context.allows("discover", namespace):
        return OperationResult("failed", errors=(Error(
            "permission_denied", "The source namespace is outside the caller's discovery grant."),))
    if not bounds.date_from or not bounds.date_to:
        raise ValueError("CivicWeb meeting listing requires explicit inclusive date_from and date_to.")
    record_types = [] if record_types is None else record_types
    if not isinstance(record_types, list) or any(value not in _RECORD_TYPES for value in record_types):
        raise ValueError("record_types must be a list of supported civic record types.")
    want_meetings = not record_types or "meeting" in record_types
    want_documents = "document" in record_types
    binding = canonical_hash({"source": source.public_dict(), "namespace": namespace, "body": source.body,
                              "dates": [bounds.date_from, bounds.date_to], "record_types": record_types,
                              "scope": context.scope, "semantics": "civicweb-meetings-service/v1"})
    if bounds.checkpoint:
        saved, seen = _resume(bounds.checkpoint, binding)
        queue = [_task(item) for item in saved]
    else:
        queue, seen = [{"kind": "meetings", "offset": 0, "sha256": None}], set()
    deadline = monotonic() + bounds.deadline_seconds
    records, bundles, captures, errors, failures = [], [], [], [], []
    pages = filtered = 0
    stats = {"unpublished_omitted": 0, "malformed_rows_omitted": 0, "non_meeting_omitted": 0}
    omitted_types, type_status, type_names = {}, "not_requested_by_checkpoint", None
    query = urlencode({"from": bounds.date_from, "to": bounds.date_to})

    def budget():
        return (pages < bounds.max_pages and monotonic() < deadline
                and not operation_cancelled(engine.storage, context))

    while queue and budget() and len(records) < bounds.max_records:
        task = queue.pop(0)
        try:
            if task["kind"] == "documents":
                pages += 1
                url = f"{origin}{SERVICE}/{task['meeting']}/meetingDocuments"
                response = _get(transport, url, origin, bounds, deadline)
                bundle = documents_bundle(source, namespace, response.content)
                bundle["capture"]["retrieval_url"] = url
                wrong = [r for r in bundle["records"]
                         if r["normalized"]["meeting_external_id"] != task["meeting"]]
                if wrong:
                    raise ValueError("A document row names a different meeting than the requested one.")
                bundle["records"] = [r for r in bundle["records"] if source_identity_key(r["identity"]) not in seen]
                seen.update(source_identity_key(r["identity"]) for r in bundle["records"])
                records.extend(bundle["records"])
                bundles.append(bundle)
                captures.append(bundle["capture"])
                context.report(operation="discover", pages=pages, returned_records=len(records))
                continue
            if type_names is None:
                type_status = "unavailable_page_budget"
                if pages + 1 < bounds.max_pages:
                    pages += 1
                    try:
                        listed = _get(transport, origin + TYPE_LIST, origin, bounds, deadline)
                        type_names = meeting_types(listed.content)
                        type_status = "applied"
                    except Exception as error:
                        type_names, type_status = {}, "unavailable_request_failed"
                        _failure(errors, failures, source, pages, "meeting_types", error)
                    if not budget():
                        queue.insert(0, task)
                        break
            pages += 1
            url = f"{origin}{SERVICE}?{query}"
            response = _get(transport, url, origin, bounds, deadline)
            digest = hashlib.sha256(response.content).hexdigest()
            if task["sha256"] and task["sha256"] != digest:
                raise ValueError("The resumed CivicWeb listing changed; restart discovery without its checkpoint.")
            payload = _json_list(response.content, "meetings")
            candidates = []
            for item in payload:
                row = _meeting_row(source, item, type_names) if isinstance(item, dict) else None
                if row is None:
                    stats["malformed_rows_omitted"] += 1
                elif item.get("Published") is not True:
                    stats["unpublished_omitted"] += 1
                elif type_names and (name := type_names.get(str(item.get("TypeId")))) and _NOT_MEETINGS.search(name):
                    stats["non_meeting_omitted"] += 1
                    omitted_types[str(item["TypeId"])] = name
                else:
                    candidates.append(row)
            candidates.sort(key=lambda row: (row[0]["source_start"] or row[0]["meeting_date"],
                                             int(row[0]["external_id"])), reverse=True)
            bundle = meetings_bundle(source, namespace, response.content, rows=candidates)
            bundle["capture"]["retrieval_url"] = url
            selected, doc_tasks = [], []
            for index in range(task["offset"], len(bundle["records"])):
                if (operation_cancelled(engine.storage, context) or monotonic() >= deadline
                        or len(records) + len(selected) >= bounds.max_records):
                    queue.insert(0, {"kind": "meetings", "offset": index, "sha256": digest})
                    break
                record = bundle["records"][index]
                key = source_identity_key(record["identity"])
                value = record["normalized"]
                if key in seen:
                    continue
                if not bounds.date_from <= value["meeting_date"] <= bounds.date_to:
                    filtered += 1
                    continue
                if source.body and value["body"].casefold() != source.body.casefold():
                    filtered += 1
                    continue
                seen.add(key)
                if want_documents:
                    doc_tasks.append({"kind": "documents", "meeting": value["external_id"]})
                if want_meetings:
                    selected.append(record)
            if task["offset"] > len(bundle["records"]):
                raise ValueError("The CivicWeb continuation offset exceeds this listing.")
            bundle["records"] = selected
            records.extend(selected)
            bundles.append(bundle)
            captures.append(bundle["capture"])
            queue[0:0] = doc_tasks
            context.report(operation="discover", pages=pages, returned_records=len(records))
        except Exception as error:
            _failure(errors, failures, source, pages, task["kind"], error)
            queue.insert(0, task)
            break

    queue = [_task(item) for item in queue]
    checkpoint = _checkpoint(binding, queue, seen) if queue else None
    cancelled = operation_cancelled(engine.storage, context)
    coverage = {
        "sources": [{**source.public_dict(), "namespace": namespace, "input_format": MEETINGS_FORMAT}],
        "date_from": bounds.date_from, "date_to": bounds.date_to, "date_inclusivity": "both",
        "record_types": record_types, "unobserved_record_types": sorted(set(record_types) - {"meeting", "document"}),
        "body": source.body, "returned_records": len(records), "filtered_records": filtered,
        "actual_dates": sorted({r["normalized"]["meeting_date"] for r in records
                                if r["normalized"].get("meeting_date")}),
        "unknown_date_records": [], "unknown_body_records": [],
        "pages": pages, "failed_pages": failures, "failures": failures,
        "meeting_types": type_status,
        "non_meeting_filter": ("meeting types matching notice/report/calendar-style names are left out"
                               if type_status == "applied" else "not_applied_meeting_types_unavailable"),
        "omitted_meeting_types": [{"id": key, "name": name} for key, name in sorted(omitted_types.items())],
        **stats,
        "listing_exhausted": not queue and not failures,
        "catalog_complete": False, "source_complete": False,
        "documents": ("read for each returned meeting; links only, nothing downloaded"
                      if want_documents else "not_requested; use record_types document or a related read"),
        "available_text": "metadata_and_document_links_only",
        "truncated": bool(queue), "deadline_exceeded": monotonic() >= deadline, "checkpoint": checkpoint,
        "scope": ("bounded public MeetingsService date-range listing; the tenant's full archive, "
                  "unpublished meetings and document content are not claimed"),
    }
    status = "cancelled" if cancelled else "failed" if failures and not captures else "partial"
    data = {"source": source.public_dict(), "records": records, "captures": captures, "bundles": bundles}
    return OperationResult(status, data, tuple(errors), coverage, context.operation_id)


def fetch_related(source, namespace, request, bounds, context, transport):
    """Read the document list of one explicitly selected meeting (links only, no downloads)."""
    if request.get("record_type") != "document":
        raise ValueError("CivicWeb related reads require record_type document.")
    parent = request.get("parent_id")
    if not isinstance(parent, str) or not _ID.fullmatch(parent):
        raise ValueError("The CivicWeb meeting ID must be a positive decimal string.")
    if request.get("external_id") is not None or bounds.checkpoint or bounds.date_from or bounds.date_to or source.body:
        raise ValueError("One meeting's documents take no document ID, date, body or checkpoint.")
    origin = tenant_origin(source)
    url = f"{origin}{SERVICE}/{parent}/meetingDocuments"
    coverage = {"sources": [{**source.public_dict(), "namespace": namespace}], "parent_id": parent,
                "scope": "the document list the public service returns for one meeting; links only",
                "catalog_complete": False, "collection_complete": False, "failures": [], "pages": 0}
    if context.check_cancelled():
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    try:
        response = _get(transport, url, origin, bounds, monotonic() + bounds.deadline_seconds)
        coverage["pages"] = 1
        bundle = documents_bundle(source, namespace, response.content)
        bundle["capture"]["retrieval_url"] = url
        if any(r["normalized"]["meeting_external_id"] != parent for r in bundle["records"]):
            raise ValueError("A document row names a different meeting than the requested one.")
    except (ValueError, OSError) as error:
        code = error.code if isinstance(error, RetrievalError) else "invalid_documents"
        return OperationResult("failed", errors=(Error(
            "civicweb_documents_unavailable",
            "The meeting's documents could not be retrieved or validated.", source=url,
            details={"reason": code}),), coverage={**coverage, "failures": [code]},
            operation_id=context.operation_id)
    return OperationResult("partial", {"source": source.public_dict(), "records": bundle["records"],
                                       "captures": [bundle["capture"]], "bundles": [bundle]},
                           coverage={**coverage, "returned_records": len(bundle["records"])},
                           operation_id=context.operation_id)
