"""Published FrontDesk HTML; rendered positions are capture-local, never native IDs."""

from datetime import datetime
from hashlib import sha256
import re
from urllib.parse import urlsplit

from .escribe_detail import Node, Page
from .native import make_bundle

FORMAT = "gworks-published-meeting-html"


def _visible(node):
    if node.tag in {"script", "style", "template", "noscript"}:
        return ""
    return " ".join(" ".join(_visible(c) if isinstance(c, Node) else c
                              for c in node.children).split())


def parse_bundle(source, namespace, content):
    url = urlsplit(source.url)
    match = re.fullmatch(r"/city/([1-9][0-9]*)/cms/([1-9][0-9]*)_(agenda|minute)\.html", url.path)
    if (source.provider != "gworks" or url.scheme != "https" or url.hostname != "files.frontdeskgworks.com"
            or url.port not in {None, 443} or url.username or url.password or url.query or url.fragment or not match):
        raise ValueError("The published GWorks HTML URL must bind one city, meeting and document kind.")
    city, meeting, kind = match.groups()
    page = Page()
    page.feed(content.decode("utf-8-sig", errors="strict"))
    nodes = list(page.root.walk())

    def one_class(name):
        found = [n for n in nodes if name in n.classes()]
        if len(found) != 1 or not _visible(found[0]):
            raise ValueError("The published GWorks meeting metadata is absent or ambiguous.")
        return found[0]

    title = _visible(one_class("contentTitle"))
    info = one_class("contentInformation")
    dates = [n for n in info.walk() if "date" in n.classes()]
    if len(dates) != 1:
        raise ValueError("The published GWorks meeting date is absent or ambiguous.")
    start = datetime.strptime(_visible(dates[0]), "%b %d, %Y %I:%M %p")
    locations = [n for n in info.walk() if "location" in n.classes()]
    if len(locations) > 1:
        raise ValueError("The published GWorks meeting location is ambiguous.")
    root = one_class("mainSection")
    digest = sha256(content).hexdigest()
    items, documents, texts = [], [], []
    sections = [n for n in root.children if isinstance(n, Node) and n.tag == "li"]
    for section in sections:
        headings = [n for n in section.children if isinstance(n, Node) and n.tag == "h1"]
        if len(headings) != 1 or not _visible(headings[0]):
            raise ValueError("The rendered GWorks section heading is ambiguous.")
        children = [n for ul in section.children if isinstance(ul, Node) and "subSection" in ul.classes()
                    for n in ul.children if isinstance(n, Node) and n.tag == "li"]
        parent = None
        for node in [section, *children]:
            position = len(items)
            identity = f"capture:{digest}:item:{position + 1}"
            description = " ".join(_visible(n) for n in node.children if isinstance(n, Node) and n.tag == "p")
            item = {"external_id": identity, "native_item_id": None, "meeting_external_id": meeting,
                    "parent_item_external_id": parent, "sequence": position,
                    "title": _visible(headings[0]) if node is section else description,
                    "description": description, "url": source.url, "documents": [],
                    "identity_derivation": "capture_local_display_position",
                    "identity_stability": "one_exact_capture_only_not_native_item_id"}
            if node is section:
                parent = identity
            # Links only from the selected item's own agenda_files; never neighboring sections.
            for files in node.children:
                if not isinstance(files, Node) or "agenda_files" not in files.classes():
                    continue
                for link in files.walk():
                    target = urlsplit(link.attrs.get("href", ""))
                    if (link.tag != "a" or target.scheme != "https" or target.hostname != url.hostname
                            or target.port not in {None, 443} or target.username or target.password
                            or target.query or target.fragment
                            or not re.fullmatch(rf"/city/{city}/media/[^/]+", target.path)
                            or re.search(r"(?:%2e|%2f|%5c|\\)", target.path, re.I)
                            or target.path.rsplit("/", 1)[-1] in {".", ".."}):
                        continue
                    doc = {"kind": "supporting_document", "title": _visible(link), "url": target.geturl(),
                           "meeting_external_id": meeting, "agenda_item_external_id": identity,
                           "availability": "supplied_locator_not_fetched"}
                    if doc not in item["documents"]:
                        item["documents"].append(doc)
                        documents.append(doc)
            items.append(item)
            if description:
                texts.append({"field": f"agenda_items.{identity}.description", "text": description,
                              "citation_url": source.url, "completeness": "complete",
                              "provenance": {"method": "gworks_rendered_item_content",
                                             "scope": "selected_rendered_item", "capture_sha256": digest}})
    expected = f"/cms/public/city/{city}/{'agenda' if kind == 'agenda' else 'minutes'}/pdf/{meeting}/"
    resolvers = [n.attrs.get("gworks-uri") for n in nodes if "gworks-evt-pdf-download" in n.classes()]
    if resolvers != [expected]:
        raise ValueError("The published GWorks PDF resolver does not match its city, meeting and kind.")
    documents.insert(0, {"kind": "agenda" if kind == "agenda" else "minutes",
                         "url": "https://api.gworks.cloud" + expected,
                         "availability": "supplied_locator_not_fetched"})
    normalized = {"external_id": meeting, "title": title, "scheduled_start": start.isoformat(),
                  "meeting_date": start.date().isoformat(), "time_zone_status": "unknown",
                  "location": _visible(locations[0]) if locations else None, "url": source.url,
                  "documents": documents, "agenda_items": items,
                  "agenda_items_availability": "capture_local_rendered_positions"}
    bundle = make_bundle(source, namespace, content, FORMAT,
                         [(normalized, {"capture_sha256": digest, "document_kind": kind}, "meeting")])
    bundle["records"][0]["text"] = texts
    return bundle
