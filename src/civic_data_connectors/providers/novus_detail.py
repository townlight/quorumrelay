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


def parse_bundle(source, namespace, content):
    validate_url(source.url)
    origin, values = urlsplit(source.url), _query(source.url)
    item, meeting = values.get("ItemID"), values.get("MeetingID")
    if (origin.scheme != "https" or not origin.hostname.endswith(".novusagenda.com")
            or origin.path != "/agendapublic/Coversheet.aspx" or origin.fragment
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
    record["identity"]["parent"] = parent
    record["relationships"].append({"relation": "meeting", "identity": parent})
    return bundle
