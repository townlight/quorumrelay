"""Selected Municode PublishPage HTML summaries; no automatic paging or downloads."""
from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

from .native import make_bundle

FORMAT = "municode-publishpage-html"
HOST = "meetings.municode.com"
ID = re.compile(r"[0-9a-f]{32}")
GUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


def context(source):
    p = urlsplit(source.url)
    q = parse_qs(p.query, keep_blank_values=True)
    if (p.scheme != "https" or p.hostname != HOST or p.port not in (None, 443) or p.username or p.password
            or p.fragment or p.path not in {"/PublishPage", "/PublishPage/index"}
            or set(q) != {"cid", "ppid", "p"} or any(len(v) != 1 for v in q.values())
            or not re.fullmatch(r"[A-Za-z0-9_-]+", q["cid"][0])
            or not GUID.fullmatch(q["ppid"][0]) or not re.fullmatch(r"[1-9][0-9]*", q["p"][0])):
        raise ValueError("PublishPage requires an exact HTTPS URL with unique cid, ppid and positive page.")
    return q["cid"][0], q["ppid"][0], q["p"][0]


def namespace(source):
    cid, _, _ = context(source)
    return f"//{HOST}/cid/{cid}"


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.main = False
        self.row = self.cell = None
        self.rows = []
        self.table = None
        self.tables = []
        self.in_select = False
        self.options = []
        self.selected = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self.main = "mcm" in (a.get("class") or "").split()
            self.table = {"links": [], "pager": False}
        elif tag == "tr" and self.main:
            self.row = {}
        elif tag == "td" and self.main and self.row is not None:
            classes = (a.get("class") or "").split()
            keys = set(classes) & {"meeting", "venue", "date", "time", "agenda", "packet", "minutes", "multimedia", "adahtmlagenda", "adahtmlpacket"}
            if len(keys) != 1 or next(iter(keys)) in self.row:
                raise ValueError("Malformed PublishPage meeting cells.")
            key = next(iter(keys))
            self.cell = {"text": "", "links": [], "attributes": a, "elements": []}
            self.row[key] = self.cell
        elif tag == "a" and self.table is not None:
            href = a.get("href")
            if self.main and self.cell is not None and href:
                self.cell["links"].append(href)
                self.cell["elements"].append({"tag": tag, "attributes": a})
            elif not self.main and href:
                self.table["links"].append(href)
        elif self.main and self.cell is not None:
            self.cell["elements"].append({"tag": tag, "attributes": a})
        elif tag == "select" and a.get("id") == "agendapal.page.dropbox" and self.table is not None:
            self.in_select = True
            self.table["pager"] = True
        elif tag == "option" and self.in_select:
            value = a.get("value")
            self.options.append(value)
            if "selected" in a:
                self.selected.append(value)

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag == "td":
            self.cell = None
        elif tag == "tr" and self.main and self.row:
            self.rows.append(self.row)
            self.row = None
        elif tag == "select":
            self.in_select = False
        elif tag == "table":
            if self.table and self.table["pager"]:
                self.tables.append(self.table)
            self.table = None
            self.main = False


def _safe_link(source, href):
    link = urljoin(source.url, href)
    p = urlsplit(link)
    if (p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password
            or (p.hostname == HOST and (p.scheme != "https" or p.port not in (None, 443)))):
        raise ValueError("PublishPage supplied an unsafe locator.")
    return link


def parse_bundle(source, namespace, content):
    cid, ppid, selected = context(source)
    page = Page()
    page.feed(content.decode("utf-8"))
    page.close()
    if (len(page.tables) != 1 or page.selected != [selected] or not page.options
            or len(page.options) != len(set(page.options))
            or any(not isinstance(v, str) or not re.fullmatch(r"[1-9][0-9]*", v) for v in page.options)):
        raise ValueError("PublishPage selected page/options do not match the request.")
    links = []
    for href in page.tables[0]["links"]:
        if href.startswith("javascript:"):
            continue
        link = _safe_link(source, href)
        try:
            other_cid, other_ppid, other_page = context(type("S", (), {"url": link})())
        except ValueError:
            raise ValueError("PublishPage control is not a valid same-origin page URL.") from None
        if (other_cid, other_ppid) != (cid, ppid) or other_page not in page.options:
            raise ValueError("PublishPage controls do not match the requested tenant/publication.")
        links.append(link)
    if not links or not page.rows:
        raise ValueError("PublishPage lacks its declared page context or meeting rows.")
    rows, seen = [], set()
    required = {"meeting", "venue", "date", "time", "agenda", "packet", "minutes", "multimedia", "adahtmlagenda", "adahtmlpacket"}
    for cells in page.rows:
        if set(cells) != required:
            raise ValueError("PublishPage row does not supply the expected columns.")
        title = " ".join(cells["meeting"]["text"].split())
        day_literal = " ".join(cells["date"]["text"].split())
        time_literal = " ".join(cells["time"]["text"].split())
        try:
            day = datetime.strptime(day_literal, "%m/%d/%Y").date().isoformat()
        except ValueError:
            raise ValueError("PublishPage meeting date is invalid.") from None
        if not title:
            raise ValueError("PublishPage meeting title is missing.")
        identities, filename_ids, documents, recordings = set(), set(), [], []
        for field in ("agenda", "packet", "minutes", "multimedia", "adahtmlagenda", "adahtmlpacket"):
            for href in cells[field]["links"]:
                url = _safe_link(source, href)
                parts = urlsplit(url)
                verified_pdf = False
                if field.startswith("adahtml"):
                    q = parse_qs(parts.query, keep_blank_values=True)
                    expected_ip = "false" if field == "adahtmlagenda" else "true"
                    if (parts.scheme != "https" or parts.hostname != HOST or parts.port not in (None, 443)
                            or parts.path != "/adaHtmlDocument/index" or set(q) != {"cc", "me", "ip"}
                            or any(len(v) != 1 for v in q.values()) or q["cc"] != [cid]
                            or not ID.fullmatch(q["me"][0]) or q["ip"] != [expected_ip]):
                        raise ValueError("PublishPage HTML locator has an invalid tenant or meeting identity.")
                    identities.add(q["me"][0])
                elif parts.hostname == HOST and parts.path == "/d/f":
                    q = parse_qs(parts.query)
                    target = q.get("u", [])
                    if len(target) != 1:
                        raise ValueError("PublishPage document locator is ambiguous.")
                    found = re.search(r"/MEET-(?:Agenda|Packet|Minutes)-([0-9a-f]{32})\.pdf$", urlsplit(target[0]).path)
                    if not found or found[0].split("/")[-1].split("-")[1].lower() != field:
                        raise ValueError("PublishPage document locator has an invalid meeting identity or kind.")
                    filename_ids.add(found[1])
                    verified_pdf = True
                item = {"url": url, "kind": {"adahtmlagenda": "agenda", "adahtmlpacket": "packet"}.get(field, field),
                        "source_column": field}
                if field.startswith("adahtml"):
                    item["format"] = "html"
                elif verified_pdf:
                    item["format"] = "pdf"
                (recordings if field == "multimedia" else documents).append(item)
        if len(identities) != 1:
            raise ValueError("PublishPage row lacks one consistent native meeting identity.")
        identity = identities.pop()
        if filename_ids - {identity}:
            raise ValueError("PublishPage document filenames conflict with the supplied meeting selector.")
        if identity in seen:
            raise ValueError("PublishPage contains a duplicate native meeting identity.")
        seen.add(identity)
        normalized = {"external_id": identity, "title": title, "meeting_date": day,
                      "source_date": day_literal, "source_time": time_literal,
                      "time_zone_status": "unknown", "location": " ".join(cells["venue"]["text"].split()),
                      "documents": documents, "recordings": recordings}
        rows.append((normalized, cells, "meeting"))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    for record in bundle["records"]:
        record["identity"]["derivation"] = "public_document_selector"
        record["identity"]["stability"] = "Public portal me selector within cid; equivalence to API IDs is unverified."
    bundle["extensions"]["publishpage_controls"] = {"selected": selected, "options": page.options,
        "declared_links": links, "cid": cid, "ppid": ppid}
    return bundle
