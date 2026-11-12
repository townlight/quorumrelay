"""Observed anonymous Simbli meeting and agenda reads from fresh public controls."""

from copy import deepcopy
from datetime import datetime
from http.cookiejar import CookieJar
import json
import re
from time import monotonic
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request

from ..models import Error, OperationResult
from .native import make_bundle
from .novus import _cookies
from .simbli import HOST, _literal

DETAIL = "simbli-meeting-detail-json"
ITEMS = "simbli-agenda-items-json"
CONTENT = "simbli-item-content-json"


def parts(source):
    url = urlsplit(source.url)
    query = parse_qs(url.query, keep_blank_values=True)
    if (url.scheme != "https" or url.hostname != "simbli.eboardsolutions.com"
            or url.port not in {None, 443} or url.path != "/SB_Meetings/ViewMeeting.aspx"
            or url.fragment or set(query) != {"S", "MID"}
            or any(len(query[key]) != 1 or re.fullmatch(r"[1-9][0-9]{0,18}", query[key][0]) is None
                   for key in query)):
        raise ValueError("Simbli detail requires its exact public district/meeting URL.")
    return query["S"][0], query["MID"][0]


def parse_bundle(source, namespace, content, input_format):
    district, meeting = parts(source)
    payload = json.loads(content)
    rows = []
    parents = {}
    if input_format == DETAIL:
        if (not isinstance(payload, dict) or str(payload.get("ID")) != meeting
                or not isinstance(payload.get("Title"), str) or not payload["Title"].strip()):
            raise ValueError("The public meeting response does not match the requested identity.")
        normalized = {"external_id": meeting, "title": payload["Title"],
            "source_date": payload.get("TitleDateTime"), "published": payload.get("IsPublished"),
            "minutes_published": payload.get("IsMinutesPublished"),
            "location": ", ".join(v for v in (payload.get("Address1"), payload.get("Address2"),
                payload.get("Address3")) if isinstance(v, str) and v), "url": source.url,
            "time_zone_status": "unknown", "documents": [], "recordings": [],
            "documents_availability": "secondary_responses_retained_unmapped"}
        try:
            scheduled = datetime.strptime(payload["TitleDateTime"], "%m/%d/%Y - %I:%M %p")
            normalized.update(meeting_date=scheduled.date().isoformat(), scheduled_at=scheduled.isoformat())
        except (ValueError, TypeError, KeyError):
            normalized["date_availability"] = "unmapped"
        rows.append((normalized, payload, "meeting"))
    elif input_format == ITEMS:
        if not isinstance(payload, dict) or not isinstance(payload.get("Items"), list):
            raise ValueError("The public agenda response requires its supplied Items tree.")
        pending = [(row, None) for row in reversed(payload["Items"])]
        seen = set()
        while pending:
            row, parent = pending.pop()
            if (not isinstance(row, dict) or type(row.get("AgendaID")) is not int
                    or row["AgendaID"] <= 0 or not isinstance(row.get("Title"), str)
                    or not isinstance(row.get("Children"), list)):
                raise ValueError("The public agenda tree contains an unmapped item.")
            identity = str(row["AgendaID"])
            if identity in seen:
                raise ValueError("The public agenda tree repeats an item identity.")
            seen.add(identity)
            rows.append(({"external_id": identity, "title": row["Title"],
                "meeting_external_id": meeting, "parent_item_external_id": parent,
                "level": row.get("Level"), "sequence": row.get("SeqUnderParent"),
                "attachment_flag": row.get("HasAttachment"), "documents": [],
                "documents_availability": "links_not_supplied_by_tree", "url": source.url},
                row, "agenda_item"))
            parents[identity] = parent
            pending.extend((child, identity) for child in reversed(row["Children"]))
    elif input_format == CONTENT:
        # Saved context is explicit; encrypted transport identifiers are never
        # promoted to provider identity or normalized attachment URLs.
        if (not isinstance(payload, dict) or type(payload.get("agenda_item_id")) is not int
                or payload["agenda_item_id"] <= 0 or str(payload.get("meeting_id")) != meeting
                or not isinstance(payload.get("response"), dict)):
            raise ValueError("Item content requires supplied meeting/item context.")
        response = payload["response"]
        details, fields = response.get("ItemDetails"), response.get("ItemContents")
        if (not isinstance(details, dict) or not isinstance(details.get("Title"), str)
                or not isinstance(fields, list) or any(not isinstance(f, dict) for f in fields)):
            raise ValueError("The item content response is unavailable or unmapped.")
        documents = []
        contents = []
        for field in fields:
            contents.append({key: deepcopy(field.get(key)) for key in
                ("FieldName", "FieldTitle", "ControlType", "Content", "HasData", "Order")})
            for attachment in field.get("Attachments") or []:
                if not isinstance(attachment, dict) or type(attachment.get("AttachmentID")) is not int:
                    raise ValueError("The item attachment identity is unmapped.")
                document = {"external_id": str(attachment["AttachmentID"]),
                    "title": attachment.get("Title"), "filename": attachment.get("FileName"),
                    "content_type": attachment.get("ContentType"), "size": attachment.get("FileSize"),
                    "availability": "metadata_only_unmapped_attachment_scope"}
                if (str(attachment.get("SchoolID")) == district
                        and str(attachment.get("EnitityID")) == meeting
                        and attachment["AttachmentID"] > 0):
                    document.update(url=HOST + "/Meetings/Attachment.aspx?" + urlencode({
                        "S": district, "AID": attachment["AttachmentID"], "MID": meeting}),
                        availability="supplied_public_client_attachment_route")
                documents.append(document)
        rows.append(({"external_id": str(payload["agenda_item_id"]), "title": details["Title"],
            **{key: payload[key] for key in ("parent_item_external_id", "level", "sequence", "attachment_flag")
               if key in payload},
            "meeting_external_id": meeting, "content_fields": contents, "documents": documents,
            "url": source.url, "content_availability": "supplied_fields",
            "documents_availability": "supplied_same_meeting_attachment_routes_when_bound"}, response, "agenda_item"))
        parents[str(payload["agenda_item_id"])] = payload.get("parent_item_external_id")
    else:
        raise ValueError("No Simbli mapping is registered for this response.")
    bundle = make_bundle(source, namespace, content, input_format, rows)
    for record in bundle["records"]:
        if record["identity"]["record_type"] != "agenda_item":
            continue
        parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
                  "external_id": meeting, "parent": None}
        record["identity"]["parent"] = parent
        record["relationships"].append({"relation": "meeting", "identity": parent})
        if item_parent := parents[record["identity"]["external_id"]]:
            record["relationships"].append({"relation": "parent_agenda_item", "identity": {
                "provider": source.provider, "namespace": namespace, "record_type": "agenda_item",
                "external_id": item_parent, "parent": parent}})
    return bundle


def fetch_detail(source, namespace, bounds, context, transport):
    district, meeting = parts(source)
    deadline = monotonic() + bounds.deadline_seconds
    jar, total, requests = CookieJar(), 0, 0
    bundles, captures, errors = [], [], []

    def read(url):
        nonlocal total, requests
        if context.check_cancelled() or monotonic() >= deadline or total >= bounds.transfer_bytes:
            raise ValueError("The public detail read was cancelled or exceeded its bounds.")
        cookie_request = Request(url)
        jar.add_cookie_header(cookie_request)
        headers = {"Accept": "text/html, application/json"}
        if cookie_request.has_header("Cookie"):
            headers["Cookie"] = cookie_request.get_header("Cookie")
        response = transport.request(url, headers=headers,
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes - total),
            deadline_seconds=max(0.001, deadline - monotonic()), allowed_origins=(HOST,), allow_redirects=False)
        total += len(response.content)
        requests += 1
        if (response.status != 200 or response.url != url or len(response.content) > bounds.parser_bytes
                or total > bounds.transfer_bytes or monotonic() >= deadline):
            raise ValueError("The public detail response was unavailable or outside its exact bounds.")
        _cookies(jar, response, url)
        return response.content

    try:
        html = read(source.url)
        page = html.decode("utf-8-sig", errors="strict")
        if (_literal(page, "isUserLoggedIn") not in {False, "False"}
                or _literal(page, "did") != district or _literal(page, "meetingID") != meeting
                or _literal(page, "enCuUID") != ""):
            raise ValueError("The detail page is not the exact anonymous district/meeting.")
        # Fresh opaque public controls remain private to this call. Never persist
        # their request URLs or include them in public exceptions/checkpoints.
        did, mid, timezone, token = (_literal(page, name) for name in
                                     ("enDID", "enMeetingID", "encrTZ", "sToken"))
        if any(not isinstance(value, str) or not value or len(value) > 4096
               for value in (did, mid, timezone, token)):
            raise ValueError("The current public detail controls are unavailable.")
        routes = [
            ("/Services/api/GetMeeting/", {"endid": did, "enmid": mid, "entz": timezone}, DETAIL),
            ("/Services/api/MeetingView/GetItemsTreeDTO/", {"endid": did, "enmid": mid, "sct": token}, ITEMS),
            ("/Services/api/GetSupportingDocuments/", {"endid": did, "enentityid": mid, "sct": token}, None),
            ("/Services/api/GetMinutes/", {"endid": did, "enmid": mid, "sct": token}, None),
        ]
        selected = source.options.get("agenda_item_id")
        if selected is not None and (type(selected) is not int or selected <= 0):
            raise ValueError("agenda_item_id must be a supplied positive native item ID.")
        tree_payload = None
        for path, parameters, input_format in routes[:bounds.max_pages]:
            raw = read(HOST + path + "?" + urlencode(parameters))
            if input_format == ITEMS:
                tree_payload = json.loads(raw)
            if input_format:
                bundle = parse_bundle(source, namespace, raw, input_format)
                bundle["extensions"]["observed_read_route"] = path
                bundles.append(bundle)
                captures.append(bundle["capture"])
            else:
                capture = make_bundle(source, namespace, raw, "simbli-public-response-json", [])["capture"]
                captures.append({**capture, "observed_read_route": path, "mapping": "raw_response_only"})
        if selected is not None:
            if tree_payload is None or len(captures) >= bounds.max_pages:
                raise ValueError("The item read requires a fresh tree and remaining page budget.")
            pending = list(tree_payload["Items"])
            matching = []
            while pending:
                item = pending.pop()
                if item["AgendaID"] == selected:
                    matching.append(item)
                pending.extend(item["Children"])
            if len(matching) != 1:
                raise ValueError("The requested item is not supplied by this meeting tree.")
            item = matching[0]
            view = _literal(page, "viewMode")
            if not isinstance(view, str) or len(view) > 128:
                raise ValueError("The current public view declaration is unavailable.")
            path = "/Services/api/MeetingView/GetMeetingItemDetailsModel/"
            raw = read(HOST + path + "?" + urlencode({"sct": token, "endid": did,
                "enmid": mid, "enitemid": item["ID"], "enuid": "", "view": view, "stab": 1}))
            response = json.loads(raw)
            if (not isinstance(response, dict) or not isinstance(response.get("ItemDetails"), dict)
                    or response["ItemDetails"].get("EncrID") != item["ID"]):
                raise ValueError("The item response does not match its freshly supplied identity.")
            tree_bundle = next(b for b in bundles if b["capture"]["input_format"] == ITEMS)
            tree_record = next(r for r in tree_bundle["records"]
                if r["identity"]["external_id"] == str(selected))
            wrapped = json.dumps({"meeting_id": meeting, "agenda_item_id": selected,
                **{key: tree_record["normalized"].get(key) for key in
                   ("parent_item_external_id", "level", "sequence", "attachment_flag")},
                "response": response}, ensure_ascii=False).encode("utf-8")
            bundle = parse_bundle(source, namespace, wrapped, CONTENT)
            # Preserve exact network response separately from the contextual saved envelope.
            capture = make_bundle(source, namespace, raw, "simbli-public-response-json", [])["capture"]
            bundle["extensions"]["observed_read_route"] = path
            tree_bundle["records"] = [r for r in tree_bundle["records"]
                if r["identity"]["external_id"] != str(selected)]
            bundles.append(bundle)
            captures.append({**capture, "observed_read_route": path})
    except Exception:
        errors.append(Error("simbli_public_detail_unavailable", "A fresh anonymous meeting/agenda read "
            "could not be retrieved or verified; successful captures are retained.", retryable=True, source=source.url))
    records = [deepcopy(row) for bundle in bundles for row in bundle["records"]]
    truncated = len(records) > bounds.max_records or len(captures) < 4
    remaining = bounds.max_records
    for bundle in bundles:
        bundle["records"] = bundle["records"][:remaining]
        remaining -= len(bundle["records"])
    records = [row for bundle in bundles for row in bundle["records"]]
    return OperationResult("cancelled" if context.check_cancelled() else "failed" if not bundles else "partial",
        {"source": source.public_dict(), "records": records, "bundles": bundles, "captures": captures},
        tuple(errors), {"scope": "one anonymous meeting and supplied agenda tree; selected item fields and supplied same-meeting attachment routes when requested",
            "source_complete": False, "catalog_complete": False, "requests": requests,
            "transfer_bytes": total, "truncated": truncated, "unknown_time_zone": True,
            "supporting_and_minutes_mapping": "raw supplied responses only", "checkpoint": None}, context.operation_id)
