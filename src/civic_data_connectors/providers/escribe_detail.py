"""Public eSCRIBE rendered agenda; display positions are not native item IDs."""

from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urljoin, urlsplit
from uuid import UUID

from .native import make_bundle

FORMAT = "escribe-meeting-detail-html"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Node:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def classes(self):
        return set(self.attrs.get("class", "").split())

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        return " ".join(" ".join(child.text() if isinstance(child, Node) else child
                                  for child in self.children).split())


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.stack[-1].tag not in {"script", "style"}:
            self.stack[-1].children.append(data)


def _first(node, classname):
    return next((n for n in node.walk() if classname in n.classes()), None)


def parse_bundle(source, namespace, content):
    url = urlsplit(source.url)
    query = parse_qs(url.query)
    ids = query.get("Id", [])
    if (url.scheme != "https" or not url.hostname or not url.hostname.startswith("pub-")
            or not url.hostname.endswith(".escribemeetings.com") or url.port not in {None, 443}
            or url.path.lower() != "/meeting.aspx" or len(ids) != 1):
        raise ValueError("eSCRIBE detail requires its supplied public Meeting.aspx UUID citation.")
    meeting = str(UUID(ids[0]))
    if meeting != ids[0].lower():
        raise ValueError("The meeting citation must supply a UUID.")
    page = Page()
    page.feed(content.decode("utf-8-sig", errors="strict"))
    agenda = _first(page.root, "AgendaItems")
    title = _first(page.root, "AgendaHeaderTitle")
    if agenda is None or title is None or not title.text():
        raise ValueError("The supplied page is not a rendered public agenda.")
    digest = sha256(content).hexdigest()
    temporal = {"date_availability": "unmapped_or_absent", "time_zone_status": "unknown"}
    for node in page.root.walk():
        if "AgendaMeetingTime" not in node.classes():
            continue
        try:
            day = datetime.strptime(node.text(), "%A, %B %d, %Y").date()
            temporal.update(meeting_date=day.isoformat(), source_date=node.text(), date_availability="supplied_header")
            break
        except ValueError:
            continue
    start = _first(page.root, "AgendaMeetingTimeStart")
    if start:
        temporal["source_time"] = start.text()
        try:
            clock = datetime.strptime(re.sub(r"[\s.]", "", start.text()), "%I:%M%p").time()
            if "meeting_date" in temporal:
                temporal["scheduled_at"] = temporal["meeting_date"] + "T" + clock.isoformat()
        except ValueError:
            pass
    location = _first(page.root, "LocationValue")
    rows = [({"external_id": meeting, "title": title.text(), "url": source.url,
        "documents": [], **temporal, "location": location.text() if location else None,
        "agenda_items_availability": "supplied_rendered_positions"},
        {"html": content.decode("utf-8-sig"), "meeting_id": meeting}, "meeting")]
    positions = set()
    attachments = {}
    for node in agenda.walk():
        for classname in node.classes():
            if match := re.fullmatch(r"AgendaItemAttachment([1-9][0-9]*)", classname):
                attachments.setdefault(match[1], []).append(node)
    for item in agenda.walk():
        if "AgendaItem" not in item.classes():
            continue
        keys = [re.fullmatch(r"AgendaItem([1-9][0-9]*)", c) for c in item.classes()]
        keys = [m[1] for m in keys if m]
        name = _first(item, "AgendaItemTitle")
        counter = _first(item, "AgendaItemCounter")
        if len(keys) != 1 or keys[0] in positions or name is None or not name.text():
            raise ValueError("The rendered agenda item position is missing or ambiguous.")
        position = keys[0]
        positions.add(position)
        documents = []
        for node in attachments.get(position, []):
            for link in node.walk():
                if link.tag != "a" or not link.attrs.get("href"):
                    continue
                target = urlsplit(urljoin(source.url, link.attrs["href"]))
                docid = parse_qs(target.query).get("DocumentId", [])
                if (target.scheme != "https" or target.netloc != url.netloc
                        or target.path.lower() != "/filestream.ashx" or len(docid) != 1
                        or re.fullmatch(r"[1-9][0-9]*", docid[0]) is None):
                    continue
                document = {"kind": "supporting_document", "external_id": docid[0],
                    "title": link.text(), "url": target.geturl()}
                if document not in documents:
                    documents.append(document)
        rows.append(({"external_id": "capture:" + digest + ":item:" + position,
            "title": name.text(), "agenda_number": counter.text() if counter else None,
            "source_display_position": position, "meeting_external_id": meeting, **temporal,
            "native_item_id": None, "documents": documents,
            "content_availability": "rendered_title_and_supplied_links_only", "url": source.url},
            {"display_position": position, "capture_sha256": digest}, "agenda_item"))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    parent = bundle["records"][0]["identity"]
    for record in bundle["records"][1:]:
        record["identity"].update(parent=parent, derivation="capture_local_display_position",
                                  stability="one_exact_capture_only_not_native_item_id")
        record["relationships"].append({"relation": "meeting", "identity": parent})
    return bundle
