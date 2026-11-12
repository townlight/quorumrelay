"""Observed Utah public-notice search result table; no search transport."""

from datetime import datetime
from urllib.parse import urljoin, urlsplit
import re

from ..compat import DocumentTable
from .identification import validate_url

FORMAT = "utah-public-search-html"


class _Results(DocumentTable):
    def __init__(self):
        super().__init__()
        self.active = False
        self.found = False

    def handle_starttag(self, tag, attrs):
        if tag == "table" and dict(attrs).get("id") in {"browseResults-table", "searchResultsTable"}:
            if self.found:
                raise ValueError("Multiple Utah search result tables were supplied.")
            self.active = self.found = True
        if self.active:
            super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if self.active:
            super().handle_endtag(tag)
            if tag == "table":
                self.active = False

    def handle_data(self, data):
        if self.active:
            super().handle_data(data)


def search_rows(source, content):
    """Map only supplied notices and attachments; search and paging remain separate."""
    parser = _Results()
    parser.feed(content.decode("utf-8-sig"))
    if not parser.found:
        raise ValueError("The supplied page has no Utah search result table.")
    result = {}
    for cells in parser.rows:
        if len(cells) != 5:
            continue
        title, time, body, entity, attachments = cells
        links = title["links"]
        if len(links) != 1:
            continue
        url = urljoin(source.url, links[0]["url"])
        try:
            validate_url(url)
            p = urlsplit(url)
        except ValueError:
            continue
        match = re.fullmatch(r"/pmn/sitemap/notice/([0-9]+)\.html", p.path)
        name = " ".join(title["text"].split())
        if p.scheme != "https" or p.hostname != "www.utah.gov" or p.query or not match or not name:
            continue
        try:
            start = datetime.strptime(" ".join(time["text"].split()), "%Y/%m/%d %I:%M %p")
        except ValueError:
            continue
        documents = []
        for link in attachments["links"]:
            address = urljoin(source.url, link["url"])
            try:
                validate_url(address)
                target = urlsplit(address)
            except ValueError:
                continue
            if (target.scheme == "https" and target.hostname == "www.utah.gov" and not target.query
                    and re.fullmatch(r"/pmn/files/[0-9]+\.[A-Za-z0-9]+", target.path)):
                documents.append({"kind": "attachment", "url": address,
                                  "title": " ".join(link["text"].split())})
        normalized = {"external_id": match.group(1), "title": name,
                      "meeting_date": start.date().isoformat(), "source_start": start.isoformat(),
                      "time_zone_status": "unknown", "body": " ".join(body["text"].split()),
                      "entity": " ".join(entity["text"].split()), "url": url,
                      "documents": documents, "recordings": [], "agenda_items_availability": "unverified"}
        result.setdefault(match.group(1), (normalized, {"cells": cells}, "meeting"))
    if any(parser.rows) and not result:
        raise ValueError("No Utah notice rows with valid identities and dates were found.")
    return list(result.values())

