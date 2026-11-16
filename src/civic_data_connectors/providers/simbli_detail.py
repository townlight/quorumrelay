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
from ..engine import canonical_hash
from .native import make_bundle, _url
from .escribe_detail import Page
from .novus import _cookies
from .simbli import HOST, _literal

DETAIL = "simbli-meeting-detail-json"
ITEMS = "simbli-agenda-items-json"
CONTENT = "simbli-item-content-json"
SUPPORTING = "simbli-supporting-documents-json"
MEETING_MINUTES = "simbli-meeting-minutes-json"
SIMPLE_MINUTES = "simbli-simple-minutes-json"


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
    if input_format in {MEETING_MINUTES, SIMPLE_MINUTES}:
        if (not isinstance(payload, dict) or str(payload.get("meeting_id")) != meeting
                or "response" not in payload):
            raise ValueError("Minutes require explicit matching meeting context.")
        response = payload["response"]
        if response is not None and not isinstance(response, dict):
            raise ValueError("The minutes response is not an object or null.")
        item = payload.get("agenda_item_id")
        if input_format == SIMPLE_MINUTES and item is not None and (type(item) is not int or item <= 0):
            raise ValueError("Item minutes require a positive supplied item identity.")
        if input_format == MEETING_MINUTES and item is not None:
            raise ValueError("Meeting-wide minutes cannot claim a supplied item identity.")
        if response is not None:
            required = {"MeetingMinutes", "AttendessHtml", "LstItemMinutes", "RSSFeedLink"} if input_format == MEETING_MINUTES else {"Minutes"}
            if not required.intersection(response):
                raise ValueError("The minutes response has no demonstrated DTO fields.")
            if input_format == MEETING_MINUTES:
                minutes = response.get("MeetingMinutes")
                if minutes is not None and not isinstance(minutes, dict):
                    raise ValueError("The meeting minutes field is malformed.")
                if response.get("LstItemMinutes") is not None and not isinstance(response["LstItemMinutes"], list):
                    raise ValueError("The item minutes hierarchy is malformed.")
                texts = {"MeetingMinutes.Minutes": (minutes or {}).get("Minutes"), "AttendessHtml": response.get("AttendessHtml")}
                stack = [(node, f"LstItemMinutes[{i}]") for i, node in enumerate(response.get("LstItemMinutes") or [])]
                while stack:
                    node, field_path = stack.pop()
                    if not isinstance(node, dict) or (node.get("ChildMinutesLst") is not None and not isinstance(node["ChildMinutesLst"], list)):
                        raise ValueError("The item minutes hierarchy is malformed.")
                    texts[field_path + ".Minutes"] = node.get("Minutes")
                    stack.extend((child, f"{field_path}.ChildMinutesLst[{i}]") for i, child in enumerate(node.get("ChildMinutesLst") or []))
                extra = {"minutes_item_hierarchy": deepcopy(response.get("LstItemMinutes")), "minutes_rss_url": _url(source, response.get("RSSFeedLink"))}
            else:
                texts = {"Minutes": response.get("Minutes")}
                extra = {}
            if any(value is not None and not isinstance(value, str) for value in texts.values()):
                raise ValueError("The supplied minutes text is malformed.")
            typ = "agenda_item" if item is not None else "meeting"
            rows.append(({"external_id": str(item) if item is not None else meeting,
                "meeting_external_id": meeting, "url": source.url, **extra}, response, typ))
    elif input_format == DETAIL:
        if (not isinstance(payload, dict) or str(payload.get("ID")) != meeting
                or not isinstance(payload.get("Title"), str) or not payload["Title"].strip()):
            raise ValueError("The public meeting response does not match the requested identity.")
        normalized = {"external_id": meeting, "title": payload["Title"],
            "source_date": payload.get("TitleDateTime"), "published": payload.get("IsPublished"),
            "minutes_published": payload.get("IsMinutesPublished"),
            "location": ", ".join(v for v in (payload.get("Address1"), payload.get("Address2"),
                payload.get("Address3")) if isinstance(v, str) and v), "url": source.url,
            "time_zone_status": "unknown", "documents": [{"kind": "agenda",
                "url": HOST + "/SB_Meetings/PrintAgenda.aspx?" + urlencode({"S": district, "MID": meeting}),
                "availability": "client_declared_print_locator_unverified",
                "provenance": "public_meeting_client_print_agenda_route"}], "recordings": [],
            "documents_availability": "client_declared_print_locator_and_separate_supporting_response"}
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
    elif input_format == SUPPORTING:
        if (not isinstance(payload, dict) or not isinstance(payload.get("Attachment"), list)
                or not isinstance(payload.get("HyperLink"), list)):
            raise ValueError("Supporting documents require the supplied attachment and hyperlink arrays.")
        seen = set()
        for attachment in payload["Attachment"]:
            if not isinstance(attachment, dict) or type(attachment.get("AttachmentID")) is not int:
                raise ValueError("The supporting attachment identity is unmapped.")
            identity = attachment["AttachmentID"]
            if identity <= 0 or identity in seen:
                raise ValueError("Supporting attachment identities must be positive and distinct.")
            seen.add(identity)
            if str(attachment.get("SchoolID")) != district or str(attachment.get("EnitityID")) != meeting:
                continue
            url = HOST + "/Meetings/Attachment.aspx?" + urlencode({
                "S": district, "AID": identity, "MID": meeting})
            document = {"external_id": str(identity), "title": attachment.get("Title"),
                "filename": attachment.get("FileName"), "content_type": attachment.get("ContentType"),
                "size": attachment.get("FileSize"), "url": url,
                "availability": "supplied_public_client_attachment_route"}
            rows.append(({"external_id": str(identity), "title": attachment.get("Title"),
                "meeting_external_id": meeting, "documents": [document], "url": source.url},
                attachment, "document"))
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
    if input_format == SUPPORTING:
        bundle["extensions"]["supporting_scope"] = {
            "unbound_attachments_retained_in_capture": len(payload["Attachment"]) - len(rows),
            "hyperlinks_retained_in_capture": len(payload["HyperLink"]),
            "context": {"district_id": district, "meeting_id": meeting},
        }
    if input_format in {MEETING_MINUTES, SIMPLE_MINUTES} and bundle["records"]:
        record = bundle["records"][0]
        for field, value in texts.items():
            if value:
                html = Page()
                html.feed(value)
                if text := html.root.text():
                    record["text"].append({"field": field, "text": text, "citation_url": source.url,
                        "completeness": "supplied_minutes_html_only", "provenance": {
                            "method": "simbli_public_minutes_html", "source_field": field,
                            "capture_sha256": bundle["capture"]["sha256"]}})
        if input_format == SIMPLE_MINUTES and item is not None:
            parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting", "external_id": meeting, "parent": None}
            record["identity"]["parent"] = parent
            record["relationships"].append({"relation": "meeting", "identity": parent})
        return bundle
    for record in bundle["records"]:
        if input_format == SUPPORTING:
            parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
                      "external_id": meeting, "parent": None}
            record["identity"]["parent"] = parent
            record["relationships"].append({"relation": "meeting", "identity": parent})
            continue
        if record["identity"]["record_type"] != "agenda_item":
            continue
        if input_format == CONTENT:
            for field in record["normalized"]["content_fields"]:
                if (field.get("ControlType") != 11 or field.get("HasData") is not True
                        or not isinstance(field.get("Content"), str)):
                    continue
                html = Page()
                html.feed(field["Content"])
                if text := html.root.text():
                    record["text"].append({"field": "content_fields.Content", "text": text,
                        "citation_url": source.url, "completeness": "supplied_rich_text_field_only",
                        "provenance": {"method": "simbli_public_item_rich_text",
                            "source_field": field.get("FieldName"), "source_control_type": 11,
                            "capture_sha256": bundle["capture"]["sha256"]}})
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
    minutes_budget_truncated = False
    page_quota_truncated = False

    def check_completion():
        nonlocal minutes_budget_truncated
        if monotonic() >= deadline:
            minutes_budget_truncated = True
        if context.check_cancelled() or monotonic() >= deadline:
            raise ValueError("The public detail read was cancelled or exceeded its deadline.")

    def read(url):
        nonlocal total, requests, minutes_budget_truncated
        if monotonic() >= deadline or total >= bounds.transfer_bytes:
            minutes_budget_truncated = True
        if context.check_cancelled() or monotonic() >= deadline or total >= bounds.transfer_bytes:
            raise ValueError("The public detail read was cancelled or exceeded its bounds.")
        cookie_request = Request(url)
        jar.add_cookie_header(cookie_request)
        headers = {"Accept": "text/html, application/json"}
        if cookie_request.has_header("Cookie"):
            headers["Cookie"] = cookie_request.get_header("Cookie")
        requests += 1
        response = transport.request(url, headers=headers,
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes - total),
            deadline_seconds=max(0.001, deadline - monotonic()), allowed_origins=(HOST,), allow_redirects=False)
        total += len(response.content)
        if total > bounds.transfer_bytes:
            minutes_budget_truncated = True
        check_completion()
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
            ("/Services/api/GetSupportingDocuments/", {"endid": did, "enentityid": mid, "enitemid": "", "sct": token}, SUPPORTING),
            ("/Services/api/GetMinutes/", {"endid": did, "enmid": mid, "sct": token, "enuid": "", "enitemid": "", "searchText": "", "matchType": ""}, SIMPLE_MINUTES),
        ]
        page_quota_truncated = bounds.max_pages < len(routes)
        selected = source.options.get("agenda_item_id")
        if selected is not None and (type(selected) is not int or selected <= 0):
            raise ValueError("agenda_item_id must be a supplied positive native item ID.")
        tree_payload = None
        for path, parameters, input_format in routes[:bounds.max_pages]:
            try:
                raw = read(HOST + path + "?" + urlencode(parameters))
            except Exception:
                if input_format not in {SUPPORTING, SIMPLE_MINUTES} or context.check_cancelled() or monotonic() >= deadline or total >= bounds.transfer_bytes:
                    raise
                errors.append(Error("simbli_supporting_documents_unavailable" if input_format == SUPPORTING else "simbli_simple_minutes_unavailable", "The supporting or minutes response was unavailable; other supplied responses remain independent.",
                                    retryable=True, source=source.url))
                continue
            if input_format == ITEMS:
                tree_payload = json.loads(raw)
            if input_format:
                try:
                    payload = json.dumps({"meeting_id": meeting, "response": json.loads(raw)}).encode() if input_format == SIMPLE_MINUTES else raw
                    bundle = parse_bundle(source, namespace, payload, input_format)
                except (ValueError, TypeError, KeyError):
                    if input_format not in {SUPPORTING, SIMPLE_MINUTES}:
                        raise
                    capture = make_bundle(source, namespace, raw, "simbli-public-response-json", [])["capture"]
                    check_completion()
                    captures.append({**capture, "observed_read_route": path, "mapping": "raw_response_only"})
                    errors.append(Error("simbli_supporting_documents_unmapped" if input_format == SUPPORTING else "simbli_simple_minutes_unmapped", "The supporting or minutes response could not be mapped; its capture is retained.",
                                        retryable=True, source=source.url))
                    continue
                check_completion()
                bundle["extensions"]["observed_read_route"] = path
                if input_format == SIMPLE_MINUTES:
                    exact_capture = make_bundle(source, namespace, raw, "simbli-public-response-json", [])["capture"]
                    captures.append({**exact_capture, "observed_read_route": path})
                    bundle["extensions"]["network_response_capture"] = exact_capture
                    for record in bundle["records"]:
                        for text in record["text"]:
                            text["provenance"]["capture_sha256"] = exact_capture["sha256"]
                    if bundle["records"]:
                        meeting_record = next((r for b in bundles for r in b["records"] if r["identity"]["record_type"] == "meeting"), None)
                        if meeting_record:
                            meeting_record["text"].extend(bundle["records"][0]["text"])
                            meeting_bundle = next(b for b in bundles if meeting_record in b["records"])
                            meeting_bundle.setdefault("captures", []).append(exact_capture)
                    bundle["records"] = []
                    bundles.append(bundle)
                else:
                    bundles.append(bundle)
                    captures.append(bundle["capture"])
            else:
                capture = make_bundle(source, namespace, raw, "simbli-public-response-json", [])["capture"]
                check_completion()
                captures.append({**capture, "observed_read_route": path, "mapping": "raw_response_only"})
        if selected is not None:
            if tree_payload is None or requests - 1 >= bounds.max_pages:
                minutes_budget_truncated = minutes_budget_truncated or requests - 1 >= bounds.max_pages
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
            check_completion()
            bundle["extensions"]["observed_read_route"] = path
            tree_bundle["records"] = [r for r in tree_bundle["records"]
                if r["identity"]["external_id"] != str(selected)]
            bundles.append(bundle)
            captures.append({**capture, "observed_read_route": path})
            try:
                if requests - 1 >= bounds.max_pages:
                    minutes_budget_truncated = True
                    raise ValueError("No remaining page budget for item minutes.")
                path = "/Services/api/GetMinutes/"
                raw = read(HOST + path + "?" + urlencode({"sct": token, "endid": did,
                    "enmid": mid, "enuid": "", "enitemid": item["ID"],
                    "searchText": "", "matchType": ""}))
                capture = make_bundle(source, namespace, raw, "simbli-public-response-json", [])["capture"]
                captures.append({**capture, "observed_read_route": path})
                bundle.setdefault("captures", []).append(capture)
                wrapped = json.dumps({"meeting_id": meeting, "agenda_item_id": selected,
                    "response": json.loads(raw)}).encode("utf-8")
                minutes = parse_bundle(source, namespace, wrapped, SIMPLE_MINUTES)
                if minutes["records"]:
                    for text in minutes["records"][0]["text"]:
                        text["provenance"]["capture_sha256"] = capture["sha256"]
                    bundle["records"][0]["text"].extend(minutes["records"][0]["text"])
            except Exception:
                errors.append(Error("simbli_item_minutes_unavailable", "The selected item's minutes could not be read or mapped; independent results are retained.", retryable=True, source=source.url))
        try:
            flag = _literal(page, "enAjSFlag")
            if not isinstance(flag, str) or len(flag) > 4096:
                raise ValueError("Invalid public minutes declaration.")
            if requests - 1 >= bounds.max_pages:
                minutes_budget_truncated = True
                raise ValueError("No remaining page budget for public meeting minutes.")
            path = "/Services/api/GetMeetingMinutes/"
            raw = read(HOST + path + "?" + urlencode({"sct": token, "endid": did, "enmid": mid,
                "enuid": "", "enajs": flag, "searchText": "", "matchType": ""}))
            capture = make_bundle(source, namespace, raw, "simbli-public-response-json", [])["capture"]
            captures.append({**capture, "observed_read_route": path})
            wrapped = json.dumps({"meeting_id": meeting, "response": json.loads(raw)}).encode()
            bundle = parse_bundle(source, namespace, wrapped, MEETING_MINUTES)
            bundle["extensions"]["network_response_capture"] = capture
            for record in bundle["records"]:
                for text in record["text"]:
                    text["provenance"]["capture_sha256"] = capture["sha256"]
            if bundle["records"]:
                target = next((r for b in bundles for r in b["records"] if r["identity"]["record_type"] == "meeting"), None)
                if target:
                    meeting_bundle = next(b for b in bundles if target in b["records"])
                    meeting_bundle.setdefault("captures", []).append(capture)
                    target["normalized"].update({k: v for k, v in bundle["records"][0]["normalized"].items() if k.startswith("minutes_")})
                    target["normalized_sha256"] = canonical_hash(target["normalized"])
                    target["text"].extend(bundle["records"][0]["text"])
            bundle["records"] = []
            bundle["extensions"]["observed_read_route"] = path
            bundles.append(bundle)
        except Exception:
            errors.append(Error("simbli_meeting_minutes_unavailable", "Public meeting minutes could not be read or mapped; independent results are retained.", retryable=True, source=source.url))
    except Exception:
        errors.append(Error("simbli_public_detail_unavailable", "A fresh anonymous meeting/agenda read "
            "could not be retrieved or verified; successful captures are retained.", retryable=True, source=source.url))
    records = [deepcopy(row) for bundle in bundles for row in bundle["records"]]
    truncated = (len(records) > bounds.max_records or page_quota_truncated
        or minutes_budget_truncated)
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
            "deadline_exceeded": monotonic() >= deadline,
            "supporting_and_minutes_mapping": "same-meeting supporting attachments and supplied meeting minutes mapped", "checkpoint": None}, context.operation_id)
