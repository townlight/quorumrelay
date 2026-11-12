"""Map supplied BoardBook public agenda HTML without invoking hidden loaders."""

from datetime import datetime
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from .escribe_detail import Page
from .native import make_bundle

FORMAT = "boardbook-public-agenda-html"


def parse_bundle(source, namespace, content):
    url = urlsplit(source.url)
    organization = re.fullmatch(r"/Public/Agenda/([1-9][0-9]*)", url.path)
    query = parse_qs(url.query)
    ids = query.get("meeting", [])
    if (url.scheme != "https" or url.hostname != "meetings.boardbook.org"
            or url.port not in {None, 443} or organization is None
            or set(query) != {"meeting"} or len(ids) != 1
            or not re.fullmatch(r"[1-9][0-9]*", ids[0])):
        raise ValueError("Use the exact supplied BoardBook public agenda meeting URL.")
    meeting = ids[0]
    page = Page()
    page.feed(content.decode("utf-8-sig", errors="strict"))
    headers = [n for n in page.root.walk() if n.attrs.get("id") == "MeetingHeader"]
    if len(headers) != 1:
        raise ValueError("The public agenda must supply one meeting header.")
    header = headers[0].text()
    temporal, separator, title = header.partition(" - ")
    if not separator or not title:
        raise ValueError("The public agenda has no titled meeting header.")
    start = datetime.strptime(temporal, "%B %d, %Y at %I:%M %p")
    common = {"meeting_date": start.date().isoformat(), "time_zone_status": "unknown"}
    rows = [({"external_id": meeting, "title": title, "url": source.url,
              "scheduled_start": start.isoformat(), "documents": [],
              "agenda_items_availability": "supplied_rendered_items", **common},
             {"html": content.decode("utf-8-sig"), "meeting_id": meeting}, "meeting")]
    for link in page.root.walk():
        if link.tag != "a" or not link.attrs.get("href"):
            continue
        target = urlsplit(urljoin(source.url, link.attrs["href"]))
        if (target.scheme == "https" and target.netloc == url.netloc and not target.fragment
                and target.path == "/Public/DownloadAgenda/" + organization[1]
                and parse_qs(target.query) == query):
            document = {"kind": "agenda", "title": link.text(), "url": target.geturl()}
            if document not in rows[0][0]["documents"]:
                rows[0][0]["documents"].append(document)
    parents = {}
    for node in page.root.walk():
        if node.tag != "tr" or "agenda-item-information" not in node.classes():
            continue
        identity = node.attrs.get("data-agendaitemid", "")
        parent_ids = [m[1] for c in node.classes()
                      if (m := re.fullmatch(r"agenda-item-children-of-([0-9]+)", c))]
        heading = next((n for n in node.walk() if "form-check" in n.classes()), None)
        name = next((n for n in heading.walk() if n.tag == "strong"), None) if heading else None
        name = name or heading
        if (not re.fullmatch(r"[1-9][0-9]*", identity) or identity in parents
                or len(parent_ids) != 1 or name is None or not name.text()):
            raise ValueError("The public agenda item identity, parent or title is ambiguous.")
        parents[identity] = parent_ids[0]
        fields = {key: [n.text() for n in node.walk() if key in n.classes()]
                  for key in ("AgendaItemType", "Description", "Presenter", "Discussion")}
        documents = []
        for link in node.walk():
            if link.tag != "a" or not link.attrs.get("href"):
                continue
            target = urlsplit(urljoin(source.url, link.attrs["href"]))
            file_ids = parse_qs(target.query).get("file", [])
            document = link.attrs.get("data-documentid", "")
            if (target.scheme != "https" or target.netloc != url.netloc
                    or target.path != "/Documents/FileViewerOrPublic/" + organization[1]
                    or set(parse_qs(target.query)) != {"file"}
                    or target.fragment or len(file_ids) != 1 or file_ids[0] != document
                    or not re.fullmatch(r"[1-9][0-9]*", document)
                    or link.attrs.get("data-foragendaitem") != identity):
                continue
            documents.append({"kind": "attachment", "external_id": document,
                "agenda_item_external_id": identity, "title": link.text(), "url": target.geturl()})
        normalized = {"external_id": identity, "title": name.text(), "url": source.url,
                      "meeting_id": meeting, "parent_item_id": parent_ids[0],
                      "source_heading": heading.text(),
                      "sequence": len(rows), "documents": documents, "source_fields": fields, **common}
        rows.append((normalized, {"attributes": node.attrs, "rendered_text": node.text(),
                                  "meeting_id": meeting, "source_fields": fields}, "agenda_item"))
    if len(rows) == 1:
        raise ValueError("The public agenda does not supply mapped agenda items.")
    for identity in parents:
        visited, current = {identity}, parents[identity]
        while current != "0":
            if current not in parents or current in visited:
                raise ValueError("The public agenda parent relationship is missing or cyclic.")
            visited.add(current)
            current = parents[current]
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    meeting_identity = bundle["records"][0]["identity"]
    items = {r["identity"]["external_id"]: r for r in bundle["records"][1:]}
    identities = {}

    def item_identity(identity):
        if identity not in identities:
            parent = meeting_identity if parents[identity] == "0" else item_identity(parents[identity])
            identities[identity] = {**items[identity]["identity"], "parent": parent}
        return identities[identity]

    for identity, record in items.items():
        record["identity"] = item_identity(identity)
        parent = record["identity"]["parent"]
        record["relationships"].append({"relation": "meeting", "identity": dict(meeting_identity)})
        if parents[identity] != "0":
            record["relationships"].append({"relation": "parent_agenda_item", "identity": dict(parent)})
    return bundle
