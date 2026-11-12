"""Observed public AgendaQuick calendar rows and agenda-item search rows."""

from datetime import datetime
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from ..compat import _table_rows, _visible_text
from .identification import validate_url

FORMAT = "agendaquick-public-listing-html"
SEARCH_FORMAT = "agendaquick-item-search-html"


def _tenant(source):
    values = parse_qs(urlsplit(source.url).query).get("id", [])
    if len(values) != 1 or re.fullmatch(r"[0-9]{1,12}", values[0]) is None:
        raise ValueError("The public AgendaQuick source requires its numeric tenant id.")
    return values[0]


def _link(source, value, mode):
    url = urljoin(source.url, value)
    try:
        validate_url(url)
    except ValueError:
        return None
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    if (
        parts.scheme != "https"
        or parts.netloc.lower() != urlsplit(source.url).netloc.lower()
        or parts.path.lower() != "/agenda_publish.cfm"
        or query.get("id") != [_tenant(source)]
        or query.get("dsp") != [mode]
        or len(query.get("seq", [])) != 1
        or re.fullmatch(r"[1-9][0-9]{0,18}", query["seq"][0]) is None
    ):
        return None
    return url, query["seq"][0]


def listing_rows(source, content):
    page = content.decode("utf-8", errors="replace")
    if 'name="form2"' not in page or "adv_search_results.cfm?" not in page:
        raise ValueError("The public AgendaQuick calendar controls are unavailable.")
    result = {}
    for row in _table_rows(content):
        if len(row) < 2 or not row[0]["links"]:
            continue
        link = row[0]["links"][0]
        target = _link(source, link["url"], "ag")
        if target is None:
            continue
        url, identity = target
        try:
            day = datetime.strptime(" ".join(link["text"].split()), "%B %d, %Y").date().isoformat()
        except ValueError:
            continue
        title = " ".join(row[1]["text"].split())
        if not title:
            continue
        documents = [{"kind": "agenda", "url": url}]
        recordings = []
        for cell in row[2:]:
            for item in cell["links"]:
                value = urljoin(source.url, item["url"])
                try:
                    validate_url(value)
                except ValueError:
                    continue
                parts = urlsplit(value)
                label = item["title"].lower()
                text = item["text"].lower()
                if (
                    parts.scheme == "https"
                    and parts.netloc.lower() == urlsplit(source.url).netloc.lower()
                    and parts.path.lower().endswith(".pdf")
                ):
                    kind = "minutes" if "minutes document" in label else "supporting_document"
                    document = {"kind": kind, "url": value, "title": item["text"].strip()}
                    if document not in documents:
                        documents.append(document)
                elif (
                    parts.scheme == "https"
                    and "view agenda link" in label
                    and ("video" in text or "audio" in text)
                ):
                    recordings.append(
                        {"url": value, "title": item["text"].strip(), "availability": "supplied_player_link"}
                    )
        normalized = {
            "external_id": identity,
            "title": title,
            "meeting_date": day,
            "url": url,
            "documents": documents,
            "recordings": recordings,
            "time_zone_status": "unknown",
            "agenda_items_availability": "detail_not_fetched",
        }
        result.setdefault(identity, (normalized, {"cells": row}, "meeting"))
    return list(result.values())


def search_rows(source, content):
    page = content.decode("utf-8", errors="replace")
    if "No records were found matching the search criteria." in page:
        return []
    if not re.search(r"Displaying\s+[0-9]+\s+to\s+[0-9]+\s+of\s+[0-9]+\s+Records", _visible_text(page)):
        raise ValueError("The public agenda-item search result counter is unavailable.")
    pending = None
    result = {}
    for row in _table_rows(content):
        if len(row) == 4:
            match = re.match(r"\s*([0-9]{2}/[0-9]{2}/[0-9]{4})\s*/\s*(.+)", row[0]["text"])
            if match:
                try:
                    day = datetime.strptime(match[1], "%m/%d/%Y").date().isoformat()
                except ValueError:
                    continue
                pending = {
                    "day": day,
                    "meeting_type": match[2].strip(),
                    "title": " ".join(row[1]["text"].split()),
                    "department": " ".join(row[2]["text"].split()),
                    "submitted_for": " ".join(row[3]["text"].split()),
                    "cells": row,
                }
                continue
        if pending is None:
            continue
        for cell in row:
            for link in cell["links"]:
                target = _link(source, link["url"], "agm")
                if target is None:
                    continue
                url, identity = target
                normalized = {
                    "external_id": identity,
                    "title": pending["title"],
                    "meeting_date": pending["day"],
                    "meeting_type": pending["meeting_type"],
                    "department": pending["department"],
                    "submitted_for": pending["submitted_for"],
                    "description": " ".join(cell["text"].strip().removesuffix(link["text"].strip()).split()),
                    "url": url,
                    "documents": [],
                    "recordings": [],
                    "time_zone_status": "unknown",
                }
                result.setdefault(
                    identity,
                    (
                        normalized,
                        {"heading_cells": pending["cells"], "description_cells": row},
                        "agenda_item",
                    ),
                )
    return list(result.values())


def controls(content):
    class Calendar(HTMLParser):
        def __init__(self):
            super().__init__()
            self.active = False
            self.select = None
            self.fields = {}
            self.options = {}

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "form":
                self.active = values.get(
                    "method", ""
                ).lower() == "get" and "agenda_publish.cfm" in values.get("action", "")
            if not self.active:
                return
            if tag == "input" and values.get("name") in {"id", "downloadFile", "loc", "term"}:
                self.fields[values["name"]] = values.get("value", "")
            if tag == "select":
                self.select = values.get("name")
                self.options.setdefault(self.select, [])
            if tag == "option" and self.select in {"mt", "get_month", "get_year"}:
                value = values.get("value", "")
                self.options[self.select].append(value)
                if "selected" in values:
                    self.fields[self.select] = value

        def handle_endtag(self, tag):
            if tag == "form":
                self.active = False
            if tag == "select":
                self.select = None

    parser = Calendar()
    parser.feed(content.decode("utf-8", errors="replace"))
    fields = parser.fields
    if set(fields) - {"id", "downloadFile", "loc", "term", "get_month", "get_year", "mt"}:
        raise ValueError("Unknown AgendaQuick calendar controls.")
    if (
        not fields.get("id", "").isdigit()
        or fields.get("downloadFile") != ""
        or fields.get("loc") != ""
        or fields.get("term") != "N"
    ):
        raise ValueError("The public AgendaQuick calendar form is unavailable.")
    meeting_type = fields.get("mt") or next(iter(parser.options.get("mt", [])), None)
    if not meeting_type or len(meeting_type) > 64:
        raise ValueError("The calendar meeting-type control is unavailable.")
    years = parser.options.get("get_year", [])
    months = parser.options.get("get_month", [])
    if len(years) * len(months) > 2400:
        raise ValueError("The public calendar controls exceed their bound.")
    return [
        {**fields, "mt": meeting_type, "get_month": month, "get_year": year}
        for year in dict.fromkeys(years)
        for month in dict.fromkeys(months)
        if re.fullmatch(r"20[0-9]{2}", year) and month.isdigit() and 1 <= int(month) <= 12
    ]


def calendar_url(source, fields):
    if (
        not isinstance(fields, dict)
        or set(fields) != {"id", "mt", "downloadFile", "loc", "term", "get_month", "get_year"}
        or fields.get("id") != _tenant(source)
        or fields.get("downloadFile") != ""
        or fields.get("loc") != ""
        or fields.get("term") != "N"
        or not isinstance(fields.get("mt"), str)
        or len(fields["mt"]) > 64
        or not isinstance(fields.get("get_month"), str)
        or not fields["get_month"].isdigit()
        or not 1 <= int(fields["get_month"]) <= 12
        or not isinstance(fields.get("get_year"), str)
        or re.fullmatch(r"20[0-9]{2}", fields["get_year"]) is None
    ):
        raise ValueError("Invalid public AgendaQuick month/year controls.")
    parts = urlsplit(source.url)
    if parts.scheme != "https":
        raise ValueError("Public AgendaQuick calendar controls require HTTPS.")
    return parts.scheme + "://" + parts.netloc + "/agenda_publish.cfm?" + urlencode(fields)
