"""One supplied Novus public cover sheet, with native item/meeting bindings."""

from datetime import datetime
import re
from urllib.parse import parse_qsl, urljoin, urlsplit

from .escribe_detail import Page
from .identification import validate_url
from .native import make_bundle

FORMAT = "novus-public-coversheet-html"


def _query(url):
    values = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    if len(dict(values)) != len(values):
        raise ValueError("The supplied Novus URL has ambiguous query values.")
    return dict(values)


def _positive(value):
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value) is not None


def _supplied_text(record, text, method):
    record["text"] = [{"field": "text", "text": text, "citation_url": record["source_url"],
                       "completeness": "supplied_rendered_html_only",
                       "provenance": {"method": method, "capture_sha256": record["capture_sha256"],
                                      "scope": "selected_public_document"}}]


def parse_bundle(source, namespace, content):
    validate_url(source.url)
    origin, values = urlsplit(source.url), _query(source.url)
    item, meeting = values.get("ItemID"), values.get("MeetingID")
    if (origin.scheme != "https" or not origin.hostname.endswith(".novusagenda.com")
            or origin.path not in {"/agendapublic/Coversheet.aspx", "/agendapublic/CoverSheet.aspx"} or origin.fragment
            or set(values) != {"ItemID", "MeetingID"} or not _positive(item) or not _positive(meeting)):
        raise ValueError("Select the exact supplied Novus public cover sheet with native item and meeting IDs.")
    page = Page()
    page.feed(content.decode("utf-8-sig", errors="strict"))
    nodes = list(page.root.walk())
    forms = [n for n in nodes if n.tag == "form" and n.attrs.get("id") == "Form1"]
    areas = [n for n in nodes if n.attrs.get("id") == "ns-ContentArea"]
    if len(forms) != 1 or len(areas) != 1:
        raise ValueError("The supplied Novus cover sheet has no unique public content/form.")
    action = urljoin(source.url, forms[0].attrs.get("action", ""))
    if (urlsplit(action).netloc != origin.netloc or urlsplit(action).path != origin.path
            or _query(action) != values):
        raise ValueError("The cover sheet form disagrees with the selected item/meeting.")
    area = areas[0]
    sections = [n.text() for n in area.walk()
                if n.tag == "td" and n.attrs.get("id") == "column1" and n.text()]
    subjects = [s.removeprefix("SUBJECT:").strip() for s in sections if s.startswith("SUBJECT:")]
    dates = re.findall(r"Meeting Date:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", area.text())
    if len(subjects) != 1 or not subjects[0] or len(dates) != 1:
        raise ValueError("The cover sheet subject/date structure is missing or ambiguous.")
    day = datetime.strptime(dates[0], "%m/%d/%Y").date().isoformat()
    documents, seen = [], set()
    for link in area.walk():
        if link.tag != "a" or not link.attrs.get("href"):
            continue
        url = urljoin(source.url, link.attrs["href"])
        target = urlsplit(url)
        if target.path != "/agendapublic/AttachmentViewer.ashx":
            continue
        validate_url(url)
        query = _query(url)
        identity = query.get("AttachmentID")
        if (target.scheme != "https" or target.netloc != origin.netloc or target.fragment
                or set(query) != {"AttachmentID", "ItemID"} or query.get("ItemID") != item
                or not _positive(identity) or identity in seen):
            raise ValueError("The supplied Novus attachment has an invalid item/origin/native ID binding.")
        seen.add(identity)
        documents.append({"external_id": identity, "title": link.text(), "url": url,
                          "kind": "supporting_document", "agenda_item_external_id": item,
                          "meeting_external_id": meeting, "availability": "supplied_locator_not_fetched"})
    normalized = {"external_id": item, "meeting_external_id": meeting, "title": subjects[0],
                  "meeting_date": day, "source_date_literal": dates[0], "url": source.url,
                  "text": area.text(), "source_sections": sections, "documents": documents,
                  "content_availability": "rendered_cover_sheet", "time_zone_status": "unknown"}
    bundle = make_bundle(source, namespace, content, FORMAT,
                         [(normalized, {"rendered_sections": sections}, "agenda_item")])
    parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
              "external_id": meeting, "parent": None}
    record = bundle["records"][0]
    _supplied_text(record, normalized["text"], "novus_cover_sheet_text")
    record["identity"]["parent"] = parent
    record["relationships"].append({"relation": "meeting", "identity": parent})
    return bundle


def parse_meeting_bundle(source, namespace, content):
    """Read the supplied MeetingView variant of the existing public HTML format."""
    if _query(source.url).get("doctype") == "Minutes":
        return parse_minutes_bundle(source, namespace, content)
    validate_url(source.url)
    origin, values = urlsplit(source.url), _query(source.url)
    meeting, minutes = values.get("MeetingID"), values.get("MinutesMeetingID")
    if (origin.scheme != "https" or not origin.hostname.endswith(".novusagenda.com")
            or origin.path != "/agendapublic/MeetingView.aspx" or origin.fragment
            or set(values) != {"MeetingID", "MinutesMeetingID", "doctype"}
            or not _positive(meeting) or not (minutes == "-1" or _positive(minutes))
            or values.get("doctype") != "Agenda"):
        raise ValueError("Select the exact supplied Novus public Agenda MeetingView context.")
    page = Page()
    page.feed(content.decode("utf-8-sig", errors="strict"))
    forms = [n for n in page.root.walk() if n.tag == "form" and n.attrs.get("id") == "Form1"]
    if len(forms) != 1:
        raise ValueError("The Novus meeting view has no unique public form.")
    form = forms[0]
    action = urljoin(source.url, form.attrs.get("action", ""))
    if (urlsplit(action).netloc != origin.netloc or urlsplit(action).path != origin.path
            or _query(action) != values):
        raise ValueError("The meeting view form disagrees with the selected meeting/minutes/type context.")
    tables = [n for n in form.walk() if n.tag == "table" and n.text()]
    heading = next((n for n in tables if n.attrs.get("cellpadding") == "2"
                    and n.attrs.get("cellspacing") == "2"), None)
    lines = [n.text() for n in heading.walk() if n.tag == "p" and n.text()] if heading else []
    if len(lines) != 4:
        raise ValueError("The supplied Novus agenda heading structure changed.")
    body, title, date_literal, time_literal = lines
    start = datetime.strptime(date_literal + " " + time_literal, "%B %d, %Y %I:%M %p")
    if "Agenda" not in title:
        raise ValueError("The supplied Novus heading is not an agenda.")
    main = tables[0]
    items, seen = [], set()
    for link in main.walk():
        if link.tag != "a" or not link.attrs.get("href"):
            continue
        url = urljoin(source.url, link.attrs["href"])
        target = urlsplit(url)
        if target.path not in {"/agendapublic/Coversheet.aspx", "/agendapublic/CoverSheet.aspx"}:
            continue
        validate_url(url)
        query = _query(url)
        item = query.get("ItemID")
        if (target.scheme != "https" or target.netloc != origin.netloc or target.fragment
                or set(query) != {"ItemID", "MeetingID"} or query.get("MeetingID") != meeting
                or not _positive(item) or item in seen or not link.text()):
            raise ValueError("The supplied Novus item link has an invalid meeting/origin/native ID binding.")
        seen.add(item)
        items.append({"external_id": item, "meeting_external_id": meeting, "title": link.text(),
                      "url": url, "sequence": len(items), "meeting_date": start.date().isoformat(),
                      "documents": [{"url": url, "kind": "linked_source"}],
                      "content_availability": "supplied_title_and_cover_sheet_locator"})
    normalized = {"external_id": meeting, "title": title, "body": body,
                  "meeting_date": start.date().isoformat(), "source_start": start.isoformat(),
                  "source_date_literal": date_literal, "source_time_literal": time_literal,
                  "source_minutes_meeting_id": minutes, "source_document_type": values["doctype"],
                  "time_zone_status": "unknown", "url": source.url, "text": main.text(),
                  "agenda_items": items, "agenda_items_availability": "supplied_native_item_links_only",
                  "documents": []}
    rows = [(normalized, {"source_heading": lines, "source_context": values}, "meeting")]
    rows.extend((item, {"supplied_link": item["url"]}, "agenda_item") for item in items)
    bundle = make_bundle(source, namespace, content, "novus-public-listing-html", rows)
    _supplied_text(bundle["records"][0], normalized["text"], "novus_meeting_view_text")
    parent = bundle["records"][0]["identity"]
    for record in bundle["records"][1:]:
        record["identity"]["parent"] = parent
        record["relationships"].append({"relation": "meeting", "identity": parent})
    return bundle


def minutes_context(source):
    """A supplied Minutes URL identifies its document and parent separately."""
    validate_url(source.url)
    origin, values = urlsplit(source.url), _query(source.url)
    if (source.provider != "novusagenda" or origin.scheme != "https"
            or not origin.hostname.endswith(".novusagenda.com") or origin.port not in {None, 443}
            or origin.path != "/agendapublic/MeetingView.aspx" or origin.fragment
            or set(values) != {"MeetingID", "MinutesMeetingID", "doctype"}
            or values.get("doctype") != "Minutes"
            or not _positive(values.get("MeetingID")) or not _positive(values.get("MinutesMeetingID"))):
        raise ValueError("Select a supplied Novus Minutes URL with native meeting and minutes IDs.")
    return origin, values


def parse_minutes_bundle(source, namespace, content):
    origin, values = minutes_context(source)
    page = Page()
    page.feed(content.decode("utf-8-sig", errors="strict"))
    forms = [n for n in page.root.walk() if n.tag == "form" and n.attrs.get("id") == "Form1"]
    if len(forms) != 1:
        raise ValueError("The Minutes response has no unique public form.")
    form = forms[0]
    action = urljoin(source.url, form.attrs.get("action", ""))
    if (urlsplit(action).netloc != origin.netloc or urlsplit(action).path != origin.path
            or _query(action) != values):
        raise ValueError("The Minutes form disagrees with its selected meeting/document context.")
    tables = [n for n in form.walk() if n.tag == "table" and n.text()]
    heading = next((n for n in tables if n.attrs.get("cellpadding") == "2"
                    and n.attrs.get("cellspacing") == "2"), None)
    lines = [n.text() for n in heading.walk() if n.tag == "p" and n.text()] if heading else []
    if len(lines) != 4 or not tables:
        raise ValueError("The supplied Novus Minutes heading structure is unrecognized.")
    body, date_literal, time_literal, location = lines
    start = datetime.strptime(date_literal + " " + time_literal, "%A, %B %d, %Y %I:%M %p")
    if start.strftime("%A") != date_literal.split(",", 1)[0]:
        raise ValueError("The Minutes weekday disagrees with its calendar date.")
    text = tables[0].text()
    if text == heading.text():
        raise ValueError("The supplied Minutes have no rendered document body.")
    normalized = {"external_id": values["MinutesMeetingID"], "meeting_external_id": values["MeetingID"],
                  "title": "Minutes — " + body, "kind": "minutes", "body": body, "location": location,
                  "meeting_date": start.date().isoformat(), "source_start": start.isoformat(),
                  "source_date_literal": date_literal, "source_time_literal": time_literal,
                  "source_document_type": "Minutes", "time_zone_status": "unknown",
                  "url": source.url, "text": text, "content_availability": "supplied_rendered_minutes",
                  "documents": []}
    bundle = make_bundle(source, namespace, content, "novus-public-listing-html",
                         [(normalized, {"source_heading": lines, "source_context": values}, "document")])
    record = bundle["records"][0]
    parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting",
              "external_id": values["MeetingID"], "parent": None}
    record["identity"]["parent"] = parent
    record["relationships"].append({"relation": "meeting", "identity": parent})
    _supplied_text(record, text, "novus_minutes_rendered_text")
    return bundle
