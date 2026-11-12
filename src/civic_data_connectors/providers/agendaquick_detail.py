"""Captured public AgendaQuick agenda, supplied memo IDs and packet locator."""

import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, parse_qsl, urljoin, urlsplit

from ..compat import LinkList, _table_rows
from .identification import validate_url
from .native import make_bundle

FORMAT = "agendaquick-public-agenda-html"


class Header(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.strong, self.parts, self.headings, self.tenants = False, [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "strong":
            self.strong, self.parts = True, []
        if tag == "input" and a.get("name") == "id":
            self.tenants.append(a.get("value"))

    def handle_data(self, data):
        if self.strong:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "strong" and self.strong:
            self.headings.append(" ".join(" ".join(self.parts).split()))
            self.strong = False


def _query(url):
    pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    if len(dict(pairs)) != len(pairs):
        raise ValueError("The supplied AgendaQuick URL contains ambiguous query values.")
    return dict(pairs)


def parse_bundle(source, namespace, content):
    validate_url(source.url)
    origin = urlsplit(source.url)
    query = _query(source.url)
    tenant, meeting = query.get("id", ""), query.get("seq", "")
    if (origin.scheme != "https" or origin.path != "/agenda_publish.cfm" or origin.fragment
            or query.get("dsp") != "ag" or not re.fullmatch(r"[0-9]{1,12}", tenant)
            or not re.fullmatch(r"[1-9][0-9]{0,18}", meeting)):
        raise ValueError("Select the supplied AgendaQuick public agenda URL with its tenant and meeting sequence.")
    page = Header()
    page.feed(content.decode("utf-8", errors="strict"))
    if page.tenants != [tenant] or page.headings.count("MEETING NOTICE AND AGENDA") != 1:
        raise ValueError("The public agenda header does not establish this tenant/template.")
    header = page.headings.index("MEETING NOTICE AND AGENDA")
    if len(page.headings) < header + 3:
        raise ValueError("The public agenda body/date heading is unavailable.")
    body, date_literal = page.headings[header + 1:header + 3]
    date = re.fullmatch(r"([A-Za-z]+ [0-9]{1,2}, [0-9]{4})\s+—\s+(.+)", date_literal)
    if not body or date is None:
        raise ValueError("The captured public agenda date/body structure is unavailable.")
    day = datetime.strptime(date[1].title(), "%B %d, %Y").date().isoformat()
    print_bindings = []
    documents = [{"kind": "agenda", "url": source.url, "media_type": "text/html"}]
    links = LinkList()
    links.feed(content.decode("utf-8", errors="strict"))
    for link in links.links:
        url = urljoin(source.url, link["href"])
        try:
            validate_url(url)
        except ValueError:
            continue
        target = urlsplit(url)
        if target.netloc != origin.netloc or target.scheme != "https" or target.fragment:
            continue
        if target.path == "/print_prompt.cfm":
            values = _query(url)
            print_bindings.append((values.get("id"), values.get("seq")))
        elif (target.path.lower().endswith(".pdf") and not target.query
                and " ".join(link["text"].split()).upper() == "DOWNLOAD PDF PACKET"):
            doc = {"kind": "packet", "url": url, "availability": "supplied_locator_not_fetched"}
            if doc not in documents:
                documents.append(doc)
    if not print_bindings or any(binding != (tenant, meeting) for binding in print_bindings):
        raise ValueError("The supplied print control does not bind this agenda meeting sequence.")
    items, known = [], set()
    for row in _table_rows(content):
        for cell in row:
            for link in cell["links"]:
                url = urljoin(source.url, link["url"])
                values = parse_qs(urlsplit(url).query)
                if values.get("dsp") != ["agm"] or link["title"] != "View Agenda Memo":
                    continue
                validate_url(url)
                target, values = urlsplit(url), _query(url)
                item, line, revision = values.get("seq", ""), values.get("ln", ""), values.get("rev", "")
                if (target.scheme != "https" or target.netloc != origin.netloc
                        or target.path != origin.path or target.fragment
                        or values.get("id") != tenant or values.get("ag") != meeting
                        or not re.fullmatch(r"[1-9][0-9]{0,18}", item)
                        or not re.fullmatch(r"[1-9][0-9]{0,18}", line)
                        or not re.fullmatch(r"[0-9]+", revision) or item in known):
                    raise ValueError("A supplied agenda memo has an ambiguous tenant/meeting/item binding.")
                title = " ".join(link["text"].split())
                if not title:
                    raise ValueError("The supplied agenda memo has no title.")
                known.add(item)
                items.append({"external_id": item, "meeting_external_id": meeting, "title": title,
                    "url": url, "sequence": len(items), "agenda_number": row[1]["text"].strip() if len(row) > 1 else None,
                    "source_line_id": line, "source_revision_literal": revision, "source_cells": row,
                    "content_availability": "supplied_memo_locator_not_fetched"})
    normalized = {"external_id": meeting, "title": body + " — " + day, "body": body,
        "meeting_date": day, "source_time": date[2], "time_zone_status": "unknown", "url": source.url,
        "documents": documents, "agenda_items": items, "recordings": [],
        "agenda_items_availability": "supplied_linked_items_only"}
    raw = {"source_headers": page.headings, "tenant_id": tenant, "meeting_sequence": meeting}
    return make_bundle(source, namespace, content, FORMAT, [(normalized, raw, "meeting")])
