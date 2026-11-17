"""Supplied iQM2 legislative-file text; related reads replay the stored meeting capture."""
import base64
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from time import monotonic
from urllib.parse import urljoin, urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .contracts import _origin
from .escribe_detail import Page
from .identification import validate_source, validate_url
from .iqm2_detail import _query, _positive
from .native import make_bundle

FORMAT = "iqm2-legislative-file-html"


def parse_bundle(source, namespace, content):
    validate_url(source.url)
    origin, values = urlsplit(source.url), _query(source.url)
    identity, meeting = values.get("ID"), values.get("MeetingID")
    if (origin.scheme != "https" or not origin.hostname.endswith(".iqm2.com")
            or origin.path != "/Citizens/Detail_LegiFile.aspx" or origin.fragment
            or not _positive(identity) or (meeting is not None and not _positive(meeting))
            or set(values) - {"ID", "MeetingID", "Frame", "MediaPosition", "CssClass"}
            or any(values.get(k, "") != "" for k in ("Frame", "MediaPosition", "CssClass"))):
        raise ValueError("Use the supplied public legislative-file ID and unmodified presentation context.")
    page = Page()
    page.feed(content.decode("utf-8-sig", errors="strict"))
    nodes = list(page.root.walk())

    def one(name):
        matches = [n for n in nodes if n.attrs.get("id") == name]
        if len(matches) != 1:
            raise ValueError("The legislative file requires unique native identity/content controls.")
        return matches[0]

    if one("ContentPlaceholder1_txtLegiFileID").attrs.get("value") != identity:
        raise ValueError("The response legislative-file ID differs from the selected source.")
    action = urljoin(source.url, one("aspnetForm").attrs.get("action", ""))
    parsed = urlsplit(action)
    if (_origin(action) != _origin(source.url) or parsed.path != "/Agency/LegiFile.aspx"
            or parsed.fragment or _query(action) != values):
        raise ValueError("The rendered file form does not preserve its selected source context.")
    title = one("ContentPlaceholder1_lblLegiFileTitle").text()
    if not title:
        raise ValueError("The selected legislative file has no rendered title.")
    downloads = one("ContentPlaceholder1_divDownloads")
    documents, references = [], []
    for node in downloads.walk():
        if node.tag != "a" or not node.attrs.get("href"):
            continue
        url = urljoin(source.url, node.attrs["href"])
        target = urlsplit(url)
        if _origin(url) == _origin(source.url) and target.path == "/Citizens/FileOpen.aspx":
            validate_url(url)
            query = _query(url)
            if (target.scheme != "https" or target.fragment or set(query) != {"Type", "ID"}
                    or query["Type"] not in {"4", "30"} or not _positive(query["ID"])):
                raise ValueError("The supplied legislative-file download has an unknown native binding.")
            document = {"url": url, "external_id": query["ID"], "source_type": query["Type"],
                "kind": "staff_report" if query["Type"] == "30" else "supporting_document",
                "title": node.text(), "legislative_file_external_id": identity,
                "availability": "supplied_locator_not_fetched"}
            if document not in documents:
                documents.append(document)
        else:
            references.append({"url": url, "title": node.text(),
                               "association": "related_reference_not_current_file_attachment"})
    info = one("tblLegiFileInfo")
    fields = [{"cells": [{"tag": c.tag, "text": c.text()} for c in n.children
                         if hasattr(c, "tag") and c.tag in {"td", "th"}]}
              for n in info.walk() if n.tag == "tr"]
    def supplied_text(node):
        parts = []
        blocks = {"div", "p", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4"}
        def visit(value):
            if isinstance(value, str):
                parts.append(value)
                return
            if value.tag in blocks:
                parts.append(" ")
            for child in value.children:
                visit(child)
            if value.tag in blocks:
                parts.append(" ")
        visit(node)
        return " ".join("".join(parts).split())

    discussion = supplied_text(one("divItemDiscussion"))
    body = supplied_text(one("divBody"))
    normalized = {"external_id": identity, "title": title, "url": source.url,
        "source_file_type": one("ContentPlaceholder1_lblLegiFileType").text(),
        "source_reference_number": one("ContentPlaceholder1_lblResNum").text(),
        "source_agency": one("ContentPlaceholder1_lblAgency").text(), "information_rows": fields,
        "rendered_discussion": discussion, "rendered_body": body, "documents": documents, "related_references": references,
        "source_meeting_context": meeting, "meeting_membership": "not_verified_by_file_page_alone",
        "time_zone_status": "unknown"}
    bundle = make_bundle(source, namespace, content, FORMAT,
                         [(normalized, {"information_rows": fields, "source_meeting_context": meeting}, "legislative_file")])
    record = bundle["records"][0]
    record["text"] = [{"field": field, "text": text, "citation_url": source.url,
        "completeness": "supplied_rendered_html_only", "provenance": {
            "method": "iqm2_public_legislative_file", "capture_sha256": bundle["capture"]["sha256"],
            "scope": "selected_rendered_file_text_not_adopted_action_or_complete_history"}}
        for field, text in (("rendered_discussion", discussion), ("rendered_body", body))]

    return bundle


def fetch_related(engine, source, namespace, request, bounds, context, transport):
    parent, item = request.get("parent_id"), request.get("external_id")
    if (request.get("record_type") != "legislative_file" or not _positive(parent) or not _positive(item)
            or bounds.checkpoint is not None):
        raise ValueError("Select one supplied legislative_file ID, parent meeting ID and no checkpoint.")
    if not context.allows("fetch", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "The source fetch is not authorized."),))
    coverage = {"scope": "one captured meeting's supplied legislative-file detail", "source_complete": False,
        "catalog_complete": False, "document_bytes_verified": False, "available_text": "selected_rendered_file_text"}
    if operation_cancelled(engine.storage, context):
        return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
    deadline = monotonic() + bounds.deadline_seconds
    expected = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
                "external_id": parent, "parent": None}
    stored = engine.storage.get("records", source_identity_key(expected), scope=context.scope) if engine.storage else None
    record = stored.value if stored else None
    if (not isinstance(record, dict) or not isinstance(record.get("identity"), dict)
            or any(record["identity"].get(k) != v for k, v in expected.items()) or record.get("source_url") != source.url):
        raise ValueError("Import the exact configured meeting detail into this caller scope first.")
    digest = record.get("capture_sha256")
    captured = engine.storage.get("captures", digest, scope=context.scope) if isinstance(digest, str) else None
    capture = captured.value if captured else None
    if (not isinstance(capture, dict) or capture.get("source_url") != source.url
            or capture.get("input_format") != "iqm2-meeting-detail-html" or capture.get("sha256") != digest):
        raise ValueError("The meeting's scoped detail capture is unavailable or belongs to another source.")
    encoded = capture.get("content_base64")
    if not isinstance(encoded, str) or len(encoded) > 4 * ((bounds.parser_bytes + 2) // 3):
        raise ValueError("The stored meeting capture exceeds its current parser bound.")
    content = base64.b64decode(encoded, validate=True)
    if len(content) > bounds.parser_bytes or len(content) != capture.get("byte_length") or sha256(content).hexdigest() != digest:
        raise ValueError("The stored meeting capture bytes do not match their identity and bounds.")
    from .iqm2_detail import parse_bundle as meeting_bundle
    replay = meeting_bundle(source, namespace, content)
    matches = [r for r in replay["records"] if r["identity"]["record_type"] == "legislative_file"
               and r["identity"]["external_id"] == item and isinstance(r["identity"].get("parent"), dict)
               and all(r["identity"]["parent"].get(k) == v for k, v in expected.items())]
    if len(matches) != 1:
        raise ValueError("The captured meeting does not uniquely supply this legislative file.")
    listed = matches[0]
    target = replace(source, url=listed["normalized"]["url"], input_format=FORMAT)
    if validate_source(target, context) != namespace:
        raise ValueError("The supplied legislative file left its source namespace.")
    coverage["meeting_capture_sha256"] = digest
    try:
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise ValueError("The selected detail deadline expired before its request.")
        response = transport.request(target.url, allowed_origins=(_origin(source.url),), allow_redirects=False,
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes), deadline_seconds=max(.001, deadline-monotonic()))
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        if (response.status != 200 or response.url != target.url
                or response.content_type.split(";", 1)[0].strip().lower() != "text/html"
                or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes) or monotonic() >= deadline):
            raise ValueError("The exact supplied file detail was not returned within its bounds.")
        bundle = parse_bundle(target, namespace, response.content)
        detail = bundle["records"][0]
        if detail["identity"]["external_id"] != item or detail["normalized"]["source_meeting_context"] != parent:
            raise ValueError("The selected detail changed its native file or supplied meeting context.")
        detail["identity"] = deepcopy(listed["identity"])
        detail["relationships"].extend(deepcopy(listed["relationships"]))
        detail["normalized"].update(meeting_membership="verified_by_retained_meeting_capture",
            meeting_external_id=parent, meeting_date=listed["normalized"]["meeting_date"], body=listed["normalized"]["body"])
        detail["normalized_sha256"] = canonical_hash(detail["normalized"])
        detail.setdefault("extensions", {})["iqm2_meeting_capture_sha256"] = digest
        bundle["captures"] = [deepcopy(capture)]
        if operation_cancelled(engine.storage, context):
            return OperationResult("cancelled", coverage=coverage, operation_id=context.operation_id)
        return OperationResult("partial", bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception:
        return OperationResult("failed", errors=(Error("provider_detail_unavailable",
            "The supplied legislative-file detail could not be verified within its bounds.", source=target.url),),
            coverage=coverage, operation_id=context.operation_id)
