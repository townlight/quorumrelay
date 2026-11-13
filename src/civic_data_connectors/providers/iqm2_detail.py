"""One supplied public iQM2 meeting detail, not staff actions or inferred parents."""

from datetime import datetime
import re
from urllib.parse import parse_qsl, urljoin, urlsplit

from .escribe_detail import Node, Page
from .identification import validate_url
from .native import make_bundle

FORMAT = "iqm2-meeting-detail-html"


def _query(url):
    pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    if len(dict(pairs)) != len(pairs):
        raise ValueError("The supplied iQM2 URL has ambiguous query values.")
    return dict(pairs)


def _positive(value):
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value) is not None


def parse_bundle(source, namespace, content):
    validate_url(source.url)
    origin, query = urlsplit(source.url), _query(source.url)
    meeting = query.get("ID")
    if (origin.scheme != "https" or not origin.hostname.endswith(".iqm2.com")
            or origin.path != "/Citizens/Detail_Meeting.aspx" or origin.fragment
            or set(query) != {"ID"} or not _positive(meeting)):
        raise ValueError("Select the exact supplied iQM2 public meeting detail URL and native ID.")
    html = content.decode("utf-8-sig", errors="strict")
    page = Page()
    page.feed(html)
    all_nodes = list(page.root.walk())

    def one_id(name):
        nodes = [n for n in all_nodes if n.attrs.get("id") == name]
        if len(nodes) != 1:
            raise ValueError("The public iQM2 detail is missing a unique declared meeting control.")
        return nodes[0]

    if one_id("ContentPlaceholder1_txtMeetingID").attrs.get("value") != meeting:
        raise ValueError("The public iQM2 hidden meeting ID disagrees with the selected citation.")
    form = one_id("aspnetForm")
    action = urljoin(source.url, form.attrs.get("action", ""))
    if (urlsplit(action).netloc != origin.netloc or urlsplit(action).path != origin.path
            or _query(action) != query):
        raise ValueError("The public meeting form does not bind this source meeting.")
    body = one_id("ContentPlaceholder1_lblMeetingGroup").text()
    kind = one_id("ContentPlaceholder1_lblMeetingType").text()
    date_literal = one_id("ContentPlaceholder1_lblMeetingDate").text()
    start = datetime.strptime(date_literal, "%m/%d/%Y %I:%M %p")
    status = one_id("ContentPlaceholder1_lblMeetingStatus").text()
    agenda = one_id("ContentPlaceholder1_txtAgendaID").attrs.get("value")
    minutes = one_id("ContentPlaceholder1_txtMinutesID").attrs.get("value")
    if not body or not kind:
        raise ValueError("The public meeting heading has no body/type.")
    main = one_id("MeetingDetail")
    documents, files, references, seen = [], [], [], set()
    for link in all_nodes:
        if link.tag != "a" or not link.attrs.get("href"):
            continue
        url = urljoin(source.url, link.attrs["href"])
        target = urlsplit(url)
        if target.scheme != "https" or target.netloc != origin.netloc or target.fragment:
            continue
        if target.path not in {"/Citizens/FileOpen.aspx", "/Citizens/Detail_LegiFile.aspx"}:
            continue
        validate_url(url)
        values = _query(url)
        identity = values.get("ID")
        if not _positive(identity):
            raise ValueError("The supplied iQM2 document/file ID is invalid.")
        if target.path.endswith("FileOpen.aspx"):
            doc_type, context = values.get("Type"), values.get("MeetingID")
            control = link.attrs.get("id")
            named = {"ContentPlaceholder1_hlPublicAgendaFile": ("agenda", "14"),
                     "ContentPlaceholder1_hlFullAgendaFile": ("packet", "1")}
            if control in named:
                doc_kind, expected_type = named[control]
                if (doc_type != expected_type or identity != agenda or values.get("Inline") != "True"
                        or set(values) != {"ID", "Type", "Inline"}):
                    raise ValueError("The public agenda download control changed its supplied type/context.")
            elif context == meeting and doc_type in {"4", "30"} and set(values) == {"ID", "Type", "MeetingID"}:
                doc_kind = "supporting_document" if doc_type == "4" else "staff_report"
            else:
                references.append({"url": url, "title": link.text(), "source_query": values,
                                   "association": "not_bound_to_current_meeting"})
                continue
            document = {"kind": doc_kind, "external_id": identity, "source_type": doc_type,
                        "title": link.text(), "url": url, "meeting_external_id": meeting,
                        "availability": "supplied_locator_not_fetched"}
            if document not in documents:
                documents.append(document)
        else:
            context = values.get("MeetingID")
            if not _positive(context):
                raise ValueError("The supplied legislative-file link has no native meeting context.")
            value = {"external_id": identity, "meeting_external_id": context, "title": link.text(),
                     "url": url, "source_query": values}
            if context != meeting:
                references.append({**value, "association": "historical_or_other_meeting_reference"})
                continue
            if identity in seen:
                raise ValueError("The public agenda repeats a native legislative-file identity ambiguously.")
            seen.add(identity)
            files.append(value)
    # Rendered rows preserve layout/hierarchy cues and comments, without inferring
    # an item parent or adopted motion from adjacent rows or presentation columns.
    rendered = [{"attributes": n.attrs, "cells": [{"attributes": c.attrs, "text": c.text()}
                 for c in n.children if isinstance(c, Node) and c.tag == "td"]}
                for n in main.walk() if n.tag == "tr"]
    normalized = {"external_id": meeting, "title": body + " - " + kind, "body": body,
        "meeting_type": kind, "meeting_date": start.date().isoformat(), "source_start": start.isoformat(),
        "source_date_literal": date_literal, "source_status_literal": status, "time_zone_status": "unknown",
        "source_agenda_id": agenda, "source_minutes_id": minutes,
        "location": [n.text() for n in all_nodes if "MeetingAddress" in n.classes()],
        "url": source.url, "documents": documents, "agenda_items": files, "related_references": references,
        "rendered_agenda_rows": rendered, "agenda_items_availability": "supplied_native_legislative_file_links_only"}
    rows = [(normalized, {"rendered_rows": rendered, "meeting_id": meeting}, "meeting")]
    for value in files:
        rows.append(({**value, "meeting_date": start.date().isoformat(), "body": body,
                      "documents": [], "content_availability": "supplied_title_and_link_only"},
                     {"supplied_link": value}, "legislative_file"))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    bundle["records"][0]["text"] = [{"field": "rendered_agenda_rows", "text": main.text(),
        "citation_url": source.url, "completeness": "supplied_rendered_html_only",
        "provenance": {"method": "iqm2_public_meeting_detail", "scope": "selected_meeting_detail",
                       "capture_sha256": bundle["capture"]["sha256"]}}]
    parent = bundle["records"][0]["identity"]
    for record in bundle["records"][1:]:
        record["identity"]["parent"] = parent
        record["relationships"].append({"relation": "meeting", "identity": parent})
    return bundle
