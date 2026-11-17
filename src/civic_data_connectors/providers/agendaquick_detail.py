"""Captured public AgendaQuick agenda, supplied memo IDs and packet locator."""

import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, parse_qsl, urljoin, urlsplit

from ..compat import LinkList, _table_rows
from .identification import validate_url
from .native import make_bundle

FORMAT = "agendaquick-public-agenda-html"
MEMO_FORMAT = "agendaquick-public-memo-html"


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


def parse_memo_bundle(source, namespace, content):
    """One supplied memo; navigation and print controls independently bind its IDs."""
    validate_url(source.url)
    origin, query = urlsplit(source.url), _query(source.url)
    tenant, item, meeting, line, revision = (query.get(k, "") for k in ("id", "seq", "ag", "ln", "rev"))
    if (origin.scheme != "https" or origin.path != "/agenda_publish.cfm" or origin.fragment
            or query.get("dsp") != "agm" or not re.fullmatch(r"[0-9]{1,12}", tenant)
            or any(not re.fullmatch(r"[1-9][0-9]{0,18}", v) for v in (item, meeting, line))
            or not re.fullmatch(r"[0-9]+", revision)):
        raise ValueError("Select the supplied public memo URL with tenant, item, meeting, line and revision.")
    html = content.decode("utf-8", errors="strict")
    page, links = Header(), LinkList()
    page.feed(html)
    links.feed(html)
    bindings = {"print": [], "return": []}
    for link in links.links:
        url = urljoin(source.url, link["href"])
        target = urlsplit(url)
        if target.scheme != "https" or target.netloc != origin.netloc or target.fragment:
            continue
        values = _query(url)
        if target.path == "/print_ag_memo.cfm" and link["text"].strip() == "Print":
            bindings["print"].append((values.get("id"), values.get("seq"), values.get("rev_num")))
        if target.path == origin.path and link["text"].strip() == "Return":
            bindings["return"].append((values.get("id"), values.get("ag"), values.get("ln"), values.get("dsp")))
    rows = _table_rows(content)
    cells = [[" ".join(c["text"].split()) for c in row] for row in rows]
    if (page.tenants != [tenant] or bindings["print"] != [(tenant, item, revision)]
            or bindings["return"] != [(tenant, meeting, line, "ag")]
            or sum(row[0] == "AIR- " + item for row in cells if row) != 1):
        raise ValueError("The memo controls do not establish the supplied tenant/item/meeting/revision binding.")
    titles = [row[0][len("Title:"):].strip() for row in cells if len(row) == 1 and row[0].startswith("Title:")]
    dates = [row[1] for row in cells if len(row) > 1 and row[0] == "Meeting Date:"]
    if len(titles) != 1 or not titles[0] or len(dates) != 1:
        raise ValueError("The supplied memo title/date structure is unavailable.")
    day = datetime.strptime(dates[0], "%m/%d/%Y").date().isoformat()
    section_labels = ("1. REQUESTED BOARD ACTION:", "2. SUMMARY:", "3. RECOMMENDED MOTION:",
                      "4. FISCAL IMPACT: (Finance, OMB, & Human Res.)", "5. COUNTY ATTORNEY:",
                      "6. COUNTY ADMINISTRATOR:")
    sections = []
    for index, row in enumerate(cells):
        if len(row) == 1 and row[0] in section_labels:
            if index + 1 >= len(cells) or len(cells[index + 1]) != 1:
                raise ValueError("The supplied memo section is ambiguous.")
            sections.append({"label": row[0], "text": cells[index + 1][0]})
    if len(sections) != 6 or len({s["label"] for s in sections}) != 6:
        raise ValueError("The supplied memo information sections are unavailable.")

    class Attachments(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.paths = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "a" and "popupAttachments" in values.get("onclick", ""):
                match = re.fullmatch(r"popupAttachments\('([^'\\\r\n]+)','ATTACHMENTS'\)", values["onclick"])
                if match is None:
                    raise ValueError("The memo attachment declaration is not a literal supplied path.")
                self.paths.append(match[1])

    attachments = Attachments()
    attachments.feed(html)
    documents = []
    for path in attachments.paths:
        url = urljoin(source.url, path)
        validate_url(url)
        target = urlsplit(url)
        if (not path.startswith("/") or path.startswith("//") or target.scheme != "https"
                or target.netloc != origin.netloc or target.query or target.fragment
                or not target.path.lower().endswith(".pdf")):
            raise ValueError("The supplied memo attachment leaves its safe public source boundary.")
        doc = {"kind": "supporting_document", "url": url, "media_type": "application/pdf",
               "availability": "supplied_locator_not_fetched"}
        if doc not in documents:
            documents.append(doc)
    normalized = {"external_id": item, "meeting_external_id": meeting, "title": titles[0],
        "meeting_date": day, "time_zone_status": "unknown", "url": source.url,
        "source_line_id": line, "source_revision_literal": revision, "sections": sections,
        "documents": documents, "content_availability": "supplied_memo_sections_only"}
    bundle = make_bundle(source, namespace, content, MEMO_FORMAT,
                         [(normalized, {"source_rows": rows, "tenant_id": tenant}, "agenda_item")])
    record = bundle["records"][0]
    parent = {"provider": source.provider, "namespace": namespace, "record_type": "meeting", "external_id": meeting}
    record["identity"]["parent"] = parent
    record["relationships"].append({"relation": "meeting", "identity": parent})
    record["text"] = [{"field": "memo.section", "label": section["label"], "text": section["text"],
                       "citation_url": source.url, "completeness": "complete",
                       "provenance": {"method": "supplied_memo_section", "scope": "selected_item",
                                      "capture_sha256": record["capture_sha256"]}}
                      for section in sections if section["text"]]
    return bundle
