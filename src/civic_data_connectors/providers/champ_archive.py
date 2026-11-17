"""Bounded CHAMP calendar-group summaries from the public archive client."""
from __future__ import annotations

import base64
import calendar
import hashlib
import json
import re
from datetime import date, datetime
from time import monotonic
from urllib.parse import urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .civicweb_filepro import plain_html
from .discovery import _checkpoint, _resume
from .native import make_bundle

API = "https://playapi.champds.com"


def discover_public(engine, source, namespace, bounds, context, transport, *, record_types=None):
    parts = urlsplit(source.url)
    match = re.fullmatch(r"/([A-Za-z0-9_-]+)/archive/([1-9][0-9]*)/?", parts.path)
    if (parts.scheme != "https" or parts.hostname != "play.champds.com" or parts.port not in (None, 443)
            or parts.username or parts.password or parts.query or parts.fragment or not match):
        raise ValueError("CHAMP archive requires an exact public tenant archive URL.")
    tenant, archive = match.groups()
    group = source.options.get("archive_group_id")
    if type(group) is not int or group < 1:
        raise ValueError("Select one positive numeric archive_group_id.")
    if not bounds.date_from or not bounds.date_to:
        raise ValueError("CHAMP calendar discovery requires explicit date bounds within one month.")
    start, end = date.fromisoformat(bounds.date_from), date.fromisoformat(bounds.date_to)
    if start > end or (start.year, start.month) != (end.year, end.month):
        raise ValueError("CHAMP calendar discovery requires dates within one month.")
    if source.body:
        raise ValueError("CHAMP calendar group names are not verified body filters.")
    types = [] if record_types is None else record_types
    if not isinstance(types, list) or any(t != "meeting" for t in types):
        raise ValueError("CHAMP archive exposes meeting summaries only.")
    binding = canonical_hash([source.public_dict(), namespace, context.scope, bounds.date_from, bounds.date_to, types,
                              "champ-calendar-group/v1"])
    if bounds.checkpoint:
        queue, seen = _resume(bounds.checkpoint, binding)
        if len(queue) != 1 or queue[0].get("kind") not in {"archive", "group"}:
            raise ValueError("Invalid CHAMP calendar checkpoint.")
        task = queue[0]
    else:
        task, seen = {"kind": "archive"}, set()
    deadline = monotonic() + bounds.deadline_seconds
    pages = transferred = filtered = malformed = 0
    captures, bundles, records, errors = [], [], [], []
    eci = task.get("eci")
    group_name = task.get("group_name")

    def stopped():
        return operation_cancelled(engine.storage, context) or monotonic() >= deadline

    def get(url):
        nonlocal pages, transferred
        remaining = bounds.transfer_bytes - transferred
        if remaining <= 0:
            raise ValueError("CHAMP aggregate transfer limit exhausted.")
        response = transport.request(url, headers={"Accept": "application/json"},
            byte_limit=min(bounds.parser_bytes, remaining), deadline_seconds=max(.001, deadline - monotonic()),
            allowed_origins=(API,), allow_redirects=False)
        pages += 1
        transferred += len(response.content)
        if response.status != 200 or response.url != url or len(response.content) > min(bounds.parser_bytes, remaining):
            raise ValueError("CHAMP returned an unexpected endpoint, status, or response size.")
        if stopped():
            raise ValueError("CHAMP request exceeded cancellation or deadline.")
        return response.content

    try:
        if task["kind"] == "archive" and pages < bounds.max_pages and not stopped():
            content = get(f"{API}/{tenant}/archive/{archive}")
            metadata_capture = make_bundle(source, namespace, content, "champ-archive-metadata-json", [])["capture"]
            metadata_capture["retrieval_url"] = f"{API}/{tenant}/archive/{archive}"
            task = {"kind": "group", "offset": 0, "sha256": None, "metadata_capture": metadata_capture}
        if task["kind"] == "group":
            try:
                metadata_capture = task["metadata_capture"]
                metadata_content = base64.b64decode(metadata_capture["content_base64"], validate=True)
            except (KeyError, ValueError, TypeError):
                raise ValueError("CHAMP continuation lacks valid archive metadata.") from None
            if (len(metadata_content) > bounds.parser_bytes
                    or hashlib.sha256(metadata_content).hexdigest() != metadata_capture.get("sha256")
                    or len(metadata_content) != metadata_capture.get("byte_length")
                    or metadata_capture.get("retrieval_url") != f"{API}/{tenant}/archive/{archive}"
                    or not isinstance(metadata_capture.get("captured_at"), str)):
                raise ValueError("CHAMP continuation archive metadata failed its bounds or hash check.")
            metadata = json.loads(metadata_content)
            customer = metadata.get("Customer") if isinstance(metadata, dict) else None
            archive_data = metadata.get("Archive") if isinstance(metadata, dict) else None
            groups = metadata.get("ArchiveGroups") if isinstance(metadata, dict) else None
            if (not isinstance(customer, dict) or customer.get("CustomerAccessID") != tenant
                    or not isinstance(archive_data, dict) or archive_data.get("CustomerArchiveID") != int(archive)
                    or not isinstance(groups, list)):
                raise ValueError("CHAMP archive metadata does not identify the requested tenant and archive.")
            selected = [g for g in groups if isinstance(g, dict) and g.get("CustomerArchiveGroupID") == group
                        and g.get("CustomerArchiveID") == int(archive)]
            if len(selected) != 1 or selected[0].get("DisplayTypeID") != 1:
                raise ValueError("Selected CHAMP group is not a uniquely identified calendar group.")
            group_name = selected[0].get("GroupName")
            if not isinstance(group_name, str) or not group_name:
                raise ValueError("Selected CHAMP group has no usable name.")
            eci_data = metadata.get("CDSECI")
            eci = eci_data.get("isEnabled") if isinstance(eci_data, dict) else None
            captures.append(metadata_capture)
        if task["kind"] == "group" and pages < bounds.max_pages and not stopped():
            last = calendar.monthrange(start.year, start.month)[1]
            first_day = start.replace(day=1).isoformat()
            last_day = start.replace(day=last).isoformat()
            url = f"{API}/{tenant}/archiveGroupDate/{group}/LOCAL/{first_day}T00:00:00/{last_day}T23:59:59"
            content = get(url)
            digest = hashlib.sha256(content).hexdigest()
            if task.get("sha256") and task["sha256"] != digest:
                raise ValueError("The CHAMP calendar response changed; restart without its checkpoint.")
            payload = json.loads(content)
            if not isinstance(payload, list):
                raise ValueError("CHAMP calendar response must be an event array.")
            rows = []
            for raw in payload:
                if not isinstance(raw, dict) or type(raw.get("CustomerEventID")) is not int or raw["CustomerEventID"] < 1:
                    malformed += 1
                    continue
                title = raw.get("EventTitle")
                try:
                    local = datetime.strptime(raw["EventDateTimeLocal"], "%Y-%m-%d %H:%M:%S")
                    utc = datetime.strptime(raw["EventDateTimeUTC"], "%Y-%m-%d %H:%M:%S")
                    if not isinstance(title, str) or not title.strip():
                        raise ValueError("missing title")
                except (KeyError, TypeError, ValueError):
                    malformed += 1
                    continue
                if raw.get("EventPublishStatusID") != 2:
                    filtered += 1
                    continue
                ident = str(raw["CustomerEventID"])
                row = {"external_id": ident, "title": title, "meeting_date": local.date().isoformat(),
                       "source_start": local.isoformat(), "scheduled_start": utc.isoformat() + "Z",
                       "url": f"https://play.champds.com/{tenant}/event/{ident}",
                       "archive_group_id": group, "archive_group_name": group_name}
                if isinstance(raw.get("EventDescription"), str):
                    row["description"] = plain_html(raw["EventDescription"])
                    row["description_source"] = "EventDescription (provider HTML rendered as text)"
                rows.append((row, raw, "meeting"))
            bundle = make_bundle(source, namespace, content, "champ-archive-calendar-json", rows)
            bundle["capture"]["retrieval_url"] = url
            bundle["extensions"]["champ_archive_context"] = {
                "archive_metadata_capture": metadata_capture,
                "archive_id": int(archive), "archive_group_id": group,
                "date_from": bounds.date_from, "date_to": bounds.date_to,
                "window_start_local": first_day + "T00:00:00",
                "window_end_local": last_day + "T23:59:59", "group_retrieval_url": url,
                "external_eci_enabled": eci, "external_eci_included": False,
            }
            offset = task.get("offset")
            if type(offset) is not int or not 0 <= offset <= len(bundle["records"]):
                raise ValueError("Invalid CHAMP calendar continuation offset.")
            for index in range(offset, len(bundle["records"])):
                if stopped() or len(records) >= bounds.max_records:
                    task.update(offset=index, sha256=digest)
                    break
                record = bundle["records"][index]
                revision = record["original"].get("LastModifyDateTimeUTC")
                if isinstance(revision, str) and revision:
                    record["source_revision"] = {"kind": "provider_supplied", "value": {"LastModifyDateTimeUTC": revision}}
                key = source_identity_key(record["identity"])
                day = record["normalized"]["meeting_date"]
                if key in seen or not bounds.date_from <= day <= bounds.date_to:
                    filtered += 1
                    continue
                seen.add(key)
                records.append(record)
            else:
                task = None
            bundle["records"] = records
            bundles.append(bundle)
            captures.append(bundle["capture"])
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        errors.append(Error("champ_archive_error", str(error), source=source.url))
    except Exception:
        errors.append(Error("champ_archive_error", "CHAMP calendar retrieval failed.", source=source.url))
    checkpoint = _checkpoint(binding, [task], seen) if task else None
    cancelled = operation_cancelled(engine.storage, context)
    coverage = {"sources": [source.public_dict()], "date_from": bounds.date_from, "date_to": bounds.date_to,
                "date_inclusivity": "both", "archive_group_id": group, "archive_group_name": group_name,
                "external_eci_enabled": eci, "external_eci_included": False,
                "returned_records": len(records), "filtered_records": filtered, "malformed_rows_omitted": malformed,
                "pages": pages, "checkpoint": checkpoint, "truncated": bool(task),
                "catalog_complete": False, "source_complete": False,
                "scope": "One selected calendar group and month; CHAMP summaries only; external ECI events omitted."}
    status = "cancelled" if cancelled else "failed" if errors else "partial"
    return OperationResult(status, {"source": source.public_dict(), "records": records, "captures": captures,
                                    "bundles": bundles}, tuple(errors), coverage, context.operation_id)
