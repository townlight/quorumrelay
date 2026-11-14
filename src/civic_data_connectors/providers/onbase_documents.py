"""Resolve the observed Agenda Online meeting-document download wrapper as data."""

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from time import monotonic
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import Request

from .account_api import reject_credential_echo
from .contracts import _origin
from .novus import _cookies


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active, self.values = False, []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = not dict(attrs).get("src")

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.values.append(data)


def _wait(context, deadline):
    """The pinned wrapper waits one second before ViewDocument; no polling loop."""
    seconds = deadline - monotonic()
    if seconds <= 1:
        raise ValueError("No time remains for the declared document preparation delay.")
    if context.cancellation.wait(1):
        raise InterruptedError()


def resolve_document(source, url, record, first, bounds, context, transport, deadline, *, captures=None):
    selected, configured = urlsplit(url), urlsplit(source.url)
    match = re.fullmatch(r"(.+)/Documents/Downloadfile/[^/]+\.pdf", selected.path, re.I)
    query = parse_qs(selected.query, keep_blank_values=True)
    identity = record.get("identity") or {}
    normalized = record.get("normalized") or {}
    nested_item = identity.get("record_type") == "meeting" and "itemId" in query
    item_scope = identity.get("record_type") == "agenda_item" or nested_item
    packet_scope = (not item_scope and identity.get("record_type") == "meeting" and query.get("documentType", [None])[0] in {"5", "6"}
                    and query.get("isAttachment", [None])[0] in {"true", "True"})
    def positive(v):
        return isinstance(v, str) and re.fullmatch(r"[1-9][0-9]{0,18}", v) is not None
    if (selected.scheme != "https" or _origin(url) != _origin(source.url) or selected.fragment
            or match is None or configured.path.rstrip("/") != match[1]
            or any(len(value) != 1 for value in query.values())):
        raise ValueError("Only a captured same-tenant document download is mapped.")
    if item_scope:
        parent = identity if nested_item else identity.get("parent") or {}
        meeting = parent.get("external_id")
        item = query.get("itemId", [None])[0] if nested_item else identity.get("external_id")
        documents = [d for d in normalized.get("documents", []) if isinstance(d, dict) and d.get("url") == url]
        if (set(query) != {"meetingId", "itemId", "publishId", "documentType", "isSection", "isAttachment"}
                or {k: parent.get(k) for k in ("provider", "namespace", "record_type", "external_id", "parent")} != {
                              "provider": identity.get("provider"), "namespace": identity.get("namespace"),
                              "record_type": "meeting", "external_id": meeting, "parent": None}
                or not all(positive(v) for v in (meeting, item, query["publishId"][0]))
                or query["meetingId"][0] != meeting or query["itemId"][0] != item
                or query["documentType"][0] != "1" or query["isSection"][0].lower() != "false"
                or query["isAttachment"][0].lower() != "true" or len(documents) != 1
                or (identity.get("external_id") if nested_item else normalized.get("meeting_external_id")) != meeting
                or documents[0].get("kind") != "supporting_document"
                or not positive(documents[0].get("external_id"))
                or documents[0].get("meeting_external_id") != meeting
                or documents[0].get("agenda_item_external_id") != item
                or documents[0].get("publish_id") != query["publishId"][0]
                or (nested_item and (documents[0].get("external_id") != query["publishId"][0]
                                     or documents[0].get("publish_type") != 4))):
            raise ValueError("The selected supporting document does not match its item and meeting.")
    elif (identity.get("record_type") != "meeting"
            or set(query) != ({"meetingId", "documentType", "isAttachment"} if packet_scope else {"meetingId", "documentType"})
            or query["meetingId"][0] != identity.get("external_id")
            or not positive(query["meetingId"][0]) or query["documentType"][0] not in {"1", "2", "3", "5", "6"}):
        raise ValueError("Only a captured same-tenant meeting-document download is mapped.")
    if (first.status != 200 or first.url != url or len(first.content) > bounds.parser_bytes
            or len(first.content) >= bounds.transfer_bytes or bounds.max_pages < 3):
        raise ValueError("The document wrapper exceeded its bounds or exact route.")
    parser = Scripts()
    parser.feed(first.content.decode("utf-8-sig", errors="strict"))
    script = "\n".join(parser.values)

    def value(name, pattern):
        values = re.findall(r"\bvar\s+" + re.escape(name) + r"\s*=\s*(" + pattern + r")\s*;", script)
        if len(values) != 1:
            raise ValueError("The document wrapper's supplied constants are missing or ambiguous.")
        return values[0]

    meeting = int(value("g_documentMeetingId", r"[0-9]+"))
    kind = int(value("g_documentType", r"[0-9]+"))
    item_id = int(query["itemId"][0]) if item_scope else 0
    publish_id = int(query["publishId"][0]) if item_scope else 0
    if (str(meeting) != query["meetingId"][0] or str(kind) != query["documentType"][0]
            or value("g_documentStreamId", r"''") != "''"
            or value("g_documentTypeMaxEnum", r"[0-9]+") != "7"
            or value("g_documentItemId", r"[0-9]+") != str(item_id)
            or value("g_documentPublishId", r"[0-9]+") != str(publish_id)
            or value("g_documentIsAttachment", r"true|false") != ("true" if item_scope or packet_scope else "false")
            or value("g_documentIsSection", r"true|false") != "false"):
        raise ValueError("The wrapper did not match the selected meeting-document scope.")
    name = value("g_documentName", r"'[^'\\\r\n]+'")[1:-1]

    def valid_name(filename):
        return (isinstance(filename, str) and 1 <= len(filename) <= 512
                and filename.lower().endswith(".pdf") and not filename.startswith(".")
                and not any(char in filename for char in "/\\%?#:")
                and not any(ord(char) < 32 or ord(char) == 127 for char in filename))

    prefix = match[1]
    invoke_template = prefix + "/Documents/InvokeDownloadMeetingDocument/DOCUMENTNAME?meetingId=MEETINGIDVALUE&documentType=DOCUMENTTYPEVALUE"
    if item_scope or packet_scope:
        invoke_template = prefix + "/Documents/InvokeDownloadAttachment/DOCUMENTNAME?meetingId=MEETINGIDVALUE&itemId=ITEMIDVALUE&publishId=PUBLISHIDVALUE&isSection=ISSECTIONVALUE&documentType=AGENDATYPEVALUE"
    view_template = prefix + "/Documents/ViewDocument/DOCUMENTNAME?meetingId=MEETINGIDVALUE&documentType=DOCUMENTTYPEVALUE&itemId=ITEMIDVALUE&publishId=PUBLISHIDVALUE&isSection=ISSECTIONVALUE"
    if (not valid_name(name) or "'" + invoke_template + "'" not in script
            or "'" + view_template + "'" not in script
            or not re.search(r"\$\.post\s*\(\s*url\s*,", script)
            or not re.search(r"window\.location\.replace\(url\)", script)):
        raise ValueError("The wrapper's declared document protocol changed.")
    origin = _origin(url)
    jar = CookieJar()
    remaining_transfer = bounds.transfer_bytes - len(first.content)
    remaining_parser = bounds.parser_bytes - len(first.content)
    captures = [] if captures is None else captures

    def retain(response, input_format, original):
        # Cookie values stay in this one call's memory, never receipts/captures.
        for cookie in jar:
            reject_credential_echo(response.content, {"token": cookie.value})
        captures.append({"source_url": source.url, "retrieval_url": response.url,
            "input_format": input_format, "captured_at": datetime.now(timezone.utc).isoformat(),
            "sha256": hashlib.sha256(response.content).hexdigest(), "byte_length": len(response.content),
            "content_type": response.content_type, "content_base64": base64.b64encode(response.content).decode("ascii"),
            "original_values": original})

    _cookies(jar, first, url)
    retain(first, "onbase-document-wrapper-html", {"meeting_id": meeting, "document_type": kind, "document_name": name,
        **({"item_id": item_id, "publish_id": publish_id} if item_scope else {})})

    def read(target, *, method="GET", control=False):
        nonlocal remaining_transfer, remaining_parser
        if context.check_cancelled():
            raise InterruptedError()
        limit = min(remaining_transfer, remaining_parser) if control else remaining_transfer
        seconds = deadline - monotonic()
        if limit <= 0 or seconds <= 0:
            raise ValueError("Document resolution exhausted its cumulative byte/deadline bounds.")
        request = Request(target)
        jar.add_cookie_header(request)
        headers = {"Referer": url, "Cookie": request.get_header("Cookie", "")}
        if control:
            headers.update({"X-Requested-With": "XMLHttpRequest", "Accept": "application/json",
                            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        response = transport.request(target, method=method, body=b"" if control else None, headers=headers,
            byte_limit=limit, deadline_seconds=seconds, allowed_origins=(origin,), allow_redirects=False)
        remaining_transfer -= len(response.content)
        if control:
            remaining_parser -= len(response.content)
        if (response.status != 200 or response.url != target or len(response.content) > limit
                or monotonic() >= deadline):
            raise ValueError("The document response violated its exact bounded route.")
        if context.check_cancelled():
            raise InterruptedError()
        _cookies(jar, response, target)
        for cookie in jar:
            reject_credential_echo(response.content, {"token": cookie.value})
        return response

    invoke = origin + prefix + ("/Documents/InvokeDownloadAttachment/" if item_scope or packet_scope else "/Documents/InvokeDownloadMeetingDocument/") + quote(name, safe="")
    params = ({"meetingId": meeting, "itemId": item_id, "publishId": publish_id, "isSection": "false", "documentType": kind}
              if item_scope or packet_scope else {"meetingId": meeting, "documentType": kind})
    prepared = read(invoke + "?" + urlencode(params), method="POST", control=True)
    data = json.loads(prepared.content)
    if (not isinstance(data, dict) or data.get("DocumentName") != name
            or any(type(data.get(key)) is not int or data[key] != expected for key, expected in
                   (("MeetingId", meeting), ("DocumentType", kind), ("ItemId", item_id), ("PublishId", publish_id)))
            or data.get("IsSection") is not False):
        raise ValueError("Prepared document did not match the selected meeting/type.")
    retain(prepared, "onbase-prepared-item-document-json" if item_scope else "onbase-prepared-meeting-document-json", data)
    _wait(context, deadline)
    target = origin + prefix + "/Documents/ViewDocument/" + quote(name, safe="") + "?" + urlencode({
        "meetingId": meeting, "documentType": kind, "itemId": item_id, "publishId": publish_id, "isSection": "false"})
    document = read(target)
    if (not document.content.startswith(b"%PDF-") or document.content_type.split(";", 1)[0].lower().strip()
            not in {"application/pdf", "application/octet-stream"}):
        raise ValueError("The prepared document did not return PDF bytes.")
    return document, {"kind": "onbase_supplied_item_document_wrapper" if item_scope else "onbase_supplied_meeting_document_wrapper", "meeting_id": str(meeting),
        **({"item_id": str(item_id), "publish_id": str(publish_id)} if item_scope else {}),
        "document_type": kind, "captures": captures, "requests": 3, "catalog_complete": False}
