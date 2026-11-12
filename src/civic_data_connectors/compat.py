"""Shared meeting source readers. The host owns authorization and record writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit

CONTRACT_VERSION = 1
MAX_INPUT_BYTES = 16 * 1024 * 1024


class ImportInputError(ValueError):
    """Input that could not be normalized into an import preview."""


def _public_link(base: str, value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        link = urljoin(base, value)
        parsed = urlsplit(link)
        if parsed.scheme in {"http", "https"} and parsed.hostname and parsed.username is None:
            return link
    except ValueError:
        pass
    return None


def read_json(content: bytes):
    try:
        return json.loads(content)
    except (ValueError, RecursionError) as error:
        raise ImportInputError("The export is not readable JSON. Export the meeting again.") from error


def read_meeting_export(connector: str, content: bytes) -> list[dict]:
    from civic_data_connectors.normalization import ConnectorImportError, import_meeting_payload

    payload = read_json(content)
    if not isinstance(payload, dict):
        raise ImportInputError("Select a vendor JSON export containing one meeting object.")
    try:
        record = import_meeting_payload(connector_name=connector, payload=payload)
    except ConnectorImportError as error:
        raise ImportInputError(f"{error.message} {error.fix}") from error
    try:
        start = datetime.fromisoformat(record.scheduled_start)
    except ValueError as error:
        raise ImportInputError("The meeting start is invalid. Export an ISO 8601 date and time.") from error
    if start.utcoffset() is None:
        raise ImportInputError("The meeting start has no time zone. Export it with a UTC offset.")

    return [{
        "external_id": record.external_meeting_id,
        "title": record.title,
        "scheduled_start": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "agenda_items": [{
            "external_id": item.external_item_id,
            "title": item.title,
            "department": item.department,
        } for item in record.agenda_items],
    }]


def read_primegov_portal(source_url: str, content: bytes) -> list[dict]:
    payload = read_json(content)
    if not isinstance(payload, list):
        raise ImportInputError("Save a PrimeGov public meeting list response as JSON and try again.")
    meetings = {}
    for row in payload:
        if not isinstance(row, dict) or not isinstance(row.get("dateTime"), str):
            continue
        try:
            meeting_id = int(row["id"])
            start = datetime.fromisoformat(row["dateTime"])
        except (KeyError, TypeError, ValueError):
            continue
        meeting_url = urljoin(source_url, f"/Portal/Meeting?meetingId={meeting_id}")
        documents = []
        document_list = row.get("documentList")
        for document in document_list if isinstance(document_list, list) else ():
            if not isinstance(document, dict):
                continue
            try:
                template = int(document["templateId"])
                external_id = int(document.get("id") or 0)
                output_type = int(document.get("compileOutputType") or 0)
            except (KeyError, TypeError, ValueError):
                continue
            title = str(document.get("templateName") or "")
            label = title.lower()
            kind = next((name for name in ("cancel", "minutes", "packet", "agenda") if name in label), "attachment")
            citation_url = f"{meeting_url}&meetingTemplateId={template}"
            link = _public_link(source_url, document.get("url") or document.get("link"))
            if not link and (output_type != 0 or document.get("compileOutputType") is None):
                link = urljoin(source_url, f"/Public/CompiledDocument?meetingTemplateId={template}&compileOutputType={output_type or 1}")
            documents.append({
                "external_id": str(external_id),
                "kind": kind,
                "title": title,
                "url": link or citation_url,
                "citation_url": citation_url,
                "published_at": document.get("publishDate"),
                "source_metadata": {"template_id": template, "compile_output_type": output_type},
            })
        video_url = _public_link(source_url, row.get("videoUrl"))
        meetings.setdefault(meeting_id, {
            "external_id": str(meeting_id),
            "title": " ".join(str(row.get("title") or "").split()),
            "meeting_date": start.date().isoformat(),
            "source_start": start.isoformat(),
            "location": str(row.get("location") or "").strip() or None,
            "url": meeting_url,
            "documents": documents,
            "recordings": [{"url": video_url}] if video_url else [],
        })
    if payload and not meetings:
        raise ImportInputError("No valid PrimeGov meetings were found in the selected response.")
    return list(meetings.values())


class ViewPublisherRows(HTMLParser):
    """Read labeled table cells without evaluating the portal's JavaScript."""

    PLAYER = re.compile(r"""(?:https?://|//)?[\w.:-]*/?MediaPlayer\.php\?[^'"\s)]+""", re.I)

    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = {}
            self.cell = None
        if self.row is None:
            return
        fields = dict(attrs)
        if tag == "td":
            self.cell = (fields.get("headers") or "").split(" ", 1)[0]
        if tag != "a":
            return
        if self.cell == "VideoLink":
            player = self.PLAYER.search(fields.get("onclick") or fields.get("href") or "")
            if player:
                self.row["player"] = player.group()
        href = fields.get("href") or ""
        for path, kind in (("agendaviewer.php", "agenda"), ("minutesviewer.php", "minutes")):
            if self.cell and path in href.lower():
                self.row[kind] = href
        if self.cell == "MP3Link" and href:
            self.row["audio"] = href
        if self.cell == "MP4Link" and href:
            self.row["video"] = href

    def handle_endtag(self, tag):
        if tag == "td":
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.row is not None and self.cell in {"Name", "Date"}:
            self.row[self.cell] = self.row.get(self.cell, "") + data


def read_viewpublisher(source_url: str, content: bytes) -> list[dict]:
    parser = ViewPublisherRows()
    parser.feed(content.decode("utf-8", errors="replace"))
    meetings = {}
    for row in parser.rows:
        if not {"Name", "Date", "player"} <= row.keys():
            continue
        player_url = urljoin(source_url, row["player"])
        player = urlsplit(player_url)
        if player.hostname != urlsplit(source_url).hostname:
            continue
        clip_id = parse_qs(player.query).get("clip_id", [""])[0]
        title = " ".join(row["Name"].lstrip("* ").split())
        if not clip_id.isascii() or not clip_id.isdecimal() or not title:
            continue
        date_text = " ".join(row["Date"].split()).split(" - ", 1)[0]
        for date_format in ("%B %d, %Y", "%b %d, %Y"):
            try:
                meeting_date = datetime.strptime(date_text.replace(".", ""), date_format).date()
                break
            except ValueError:
                continue
        else:
            continue
        links = {}
        for kind in ("agenda", "minutes", "audio", "video"):
            link = _public_link(source_url, row.get(kind))
            if link:
                links[kind] = link
        meetings.setdefault(clip_id, {
            "external_id": clip_id,
            "title": title,
            "meeting_date": meeting_date.isoformat(),
            "documents": [
                {"kind": kind, "url": links[kind]}
                for kind in ("agenda", "minutes") if kind in links
            ],
            "recordings": [{
                "url": player_url,
                **{f"{kind}_url": links[kind] for kind in ("audio", "video") if kind in links},
            }],
        })
    if not meetings:
        raise ImportInputError("No archived clips were found. Save a ViewPublisher page with meeting videos.")
    return list(meetings.values())


def read_civicplus_events(source_url: str, content: bytes) -> list[dict]:
    payload = read_json(content)
    events = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        raise ImportInputError("Select the saved CivicPlus public Events API response.")
    meetings = []
    for event in events:
        if not isinstance(event, dict) or event.get("isPublished") != "Published" or event.get("isDeleted"):
            continue
        title = event.get("eventName")
        if not isinstance(title, str) or not title.strip():
            continue
        try:
            external_id = str(int(event["id"]))
            start = datetime.fromisoformat(event.get("startDateTime") or event["eventDate"])
        except (KeyError, TypeError, ValueError):
            continue
        documents = []
        files = event.get("publishedFiles")
        for document in files if isinstance(files, list) else ():
            if not isinstance(document, dict):
                continue
            try:
                file_id = int(document["fileId"])
            except (KeyError, TypeError, ValueError):
                continue
            documents.append({
                "external_id": str(file_id),
                "kind": str(document.get("type") or "document"),
                "title": str(document.get("name") or ""),
                "url": urljoin(
                    source_url, f"/v1/Meetings/GetMeetingFileStream(fileId={file_id},plainText=false)"
                ),
            })
        video = _public_link(source_url, event.get("externalMediaUrl"))
        meetings.append({
            "external_id": external_id,
            "title": title.strip(),
            "meeting_date": start.date().isoformat(),
            "source_start": start.isoformat(),
            "documents": documents,
            "recordings": [{"url": video}] if video else [],
        })
    return meetings


class DocumentTable(HTMLParser):
    """Capture the text, date attributes, and links of document table rows."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None
        self.link = None

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "tr":
            self.row = []
        if self.row is None:
            return
        if tag == "td":
            self.cell = {
                "label": fields.get("data-th") or fields.get("headers") or fields.get("data-sortable-type"),
                "text": "", "time": None, "links": [],
            }
            self.row.append(self.cell)
        if self.cell is None:
            return
        if tag == "br":
            self.cell["text"] += "\n"
        if tag == "span" and fields.get("property") == "dc:date":
            self.cell["time"] = fields.get("content")
        if tag == "a" and fields.get("href"):
            self.link = {"url": fields["href"], "title": fields.get("title", ""), "text": ""}
            self.cell["links"].append(self.link)

    def handle_endtag(self, tag):
        if tag in {"a", "td", "tr"}:
            self.link = None
        if tag in {"td", "tr"}:
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data
        if self.link is not None:
            self.link["text"] += data


def _table_rows(content: bytes) -> list:
    parser = DocumentTable()
    parser.feed(content.decode("utf-8", errors="replace"))
    return parser.rows


def read_agenda_center(source_url: str, content: bytes) -> list[dict]:
    file_path = re.compile(r"^/AgendaCenter/ViewFile/([^/]+)/_(\d{8})-(\d+)$", re.I)
    meetings = {}
    for row in _table_rows(content):
        title = None
        identity = None
        documents = {}
        for cell in row:
            for link in cell["links"]:
                absolute = _public_link(source_url, link["url"])
                match = file_path.match(urlsplit(absolute).path) if absolute else None
                if not match:
                    continue
                kind, day, external_id = match.groups()
                kind = kind.lower()
                documents.setdefault(absolute, {"kind": kind, "url": absolute})
                text = " ".join(link["text"].split())
                if kind == "agenda" and text and text.lower() != "agenda" and not title:
                    title = text
                    identity = (day, external_id)
        if not identity:
            continue
        day, external_id = identity
        try:
            meeting_date = datetime.strptime(day, "%m%d%Y").date().isoformat()
        except ValueError:
            continue
        meetings.setdefault(external_id, {
            "external_id": external_id,
            "title": title,
            "meeting_date": meeting_date,
            "documents": list(documents.values()),
        })
    if not meetings:
        raise ImportInputError("No Agenda Center rows were found. Save a page that lists agendas.")
    return list(meetings.values())


def read_municode_meetings(source_url: str, content: bytes) -> list[dict]:
    meetings = {}
    kinds = {"Agenda": "agenda", "Agenda Packet": "packet", "Minutes": "minutes"}
    for row in _table_rows(content):
        cells = {cell["label"]: cell for cell in row}
        time = cells.get("Date", {}).get("time")
        title = " ".join(cells.get("Meeting", {}).get("text", "").split())
        details = cells.get("View", {}).get("links", [])
        link = _public_link(source_url, details[0]["url"]) if details else None
        if not (time and title and link):
            continue
        try:
            start = datetime.fromisoformat(time)
        except ValueError:
            continue
        documents = []
        for label, kind in kinds.items():
            for document in cells.get(label, {}).get("links", []):
                url = _public_link(source_url, document["url"])
                if url:
                    documents.append({"kind": kind, "url": url})
        external_id = urlsplit(link).path
        meetings.setdefault(external_id, {
            "external_id": external_id,
            "title": title,
            "meeting_date": start.date().isoformat(),
            "source_start": start.isoformat(),
            "url": link,
            "documents": documents,
        })
    if not meetings:
        raise ImportInputError("No Municode Meetings rows were found on the selected page.")
    return list(meetings.values())


def read_boardbook(source_url: str, content: bytes) -> list[dict]:
    document_path = re.compile(r"^/Public/(Agenda|Minutes)/\d+$", re.I)
    heading = re.compile(r"^([A-Za-z]+ \d{1,2}, \d{4}).*? - (.+?)(?: Meeting Type:|$)")
    meetings = {}
    for row in _table_rows(content):
        if not row:
            continue
        match = heading.match(" ".join(row[0]["text"].split()))
        if not match:
            continue
        day, title = match.groups()
        try:
            meeting_date = datetime.strptime(day, "%B %d, %Y").date().isoformat()
        except ValueError:
            continue
        for cell in row[1:]:
            for link in cell["links"]:
                url = _public_link(source_url, link["url"])
                if not url:
                    continue
                parsed = urlsplit(url)
                path = document_path.match(parsed.path)
                external_id = parse_qs(parsed.query).get("meeting", [""])[0]
                if not path or not external_id.isascii() or not external_id.isdecimal():
                    continue
                record = meetings.setdefault(external_id, {
                    "external_id": external_id, "title": title, "meeting_date": meeting_date,
                    "documents": [],
                })
                record["documents"].append({"kind": path[1].lower(), "url": url})
    if not meetings:
        raise ImportInputError("No BoardBook agenda or minutes links were found on the selected page.")
    return list(meetings.values())


def read_escribe(source_url: str, content: bytes) -> list[dict]:
    payload = read_json(content)
    rows = payload.get("d") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ImportInputError("Select a saved eSCRIBE calendar meeting response.")
    meetings = []
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(key), str) and row[key].strip()
                                               for key in ("ID", "MeetingName", "StartDate")):
            continue
        try:
            start = datetime.fromisoformat(row["StartDate"].replace("/", "-"))
        except ValueError:
            continue
        documents = []
        links = row.get("MeetingDocumentLink")
        for document in links if isinstance(links, list) else ():
            if not isinstance(document, dict):
                continue
            url = _public_link(source_url, document.get("Url"))
            if url:
                documents.append({
                    "kind": str(document.get("Type") or "document"),
                    "title": str(document.get("Title") or ""),
                    "url": url,
                })
        meetings.append({
            "external_id": row["ID"],
            "title": unescape(row["MeetingName"]).strip(),
            "source_start": start.isoformat(),
            "meeting_date": start.date().isoformat(),
            "url": _public_link(source_url, row.get("Url")),
            "location": str(row.get("Location") or "").strip() or None,
            "documents": documents,
        })
    if rows and not meetings:
        raise ImportInputError("No valid public eSCRIBE meetings were found in the selected response.")
    return meetings


def read_simbli(source_url: str, content: bytes) -> list[dict]:
    page = content.decode("utf-8", errors="replace")
    grid = re.search(r"MeetingGrid_newGrid\.dataBuffer\s*=\s*(\[)", page)
    if not grid:
        raise ImportInputError("Select a saved Simbli public meeting listing.")
    try:
        rows, _ = json.JSONDecoder().raw_decode(page, grid.start(1))
    except ValueError as error:
        raise ImportInputError("The Simbli public meeting listing could not be read.") from error
    meetings = []
    for row in rows:
        if not isinstance(row, dict) or row.get("ACCESS") != "P" or row.get("MM_Status") != "1":
            continue
        title = row.get("MM_MeetingTitle")
        if not isinstance(title, str) or not title.strip():
            continue
        try:
            meeting_id = int(row["Master_MeetingID"])
            district_id = int(row["MM_DistrictID"])
            start = datetime.fromisoformat(row["MM_DateTime"])
        except (KeyError, ValueError, TypeError):
            continue
        url = urljoin(source_url, f"/SB_Meetings/ViewMeeting.aspx?S={district_id}&MID={meeting_id}")
        documents = [{"kind": "agenda", "url": url}]
        if row.get("CanPrintMinutes") == 1 and row.get("MinutesStatus") == "PUBLISHED":
            documents.append({"kind": "minutes", "url": f"{url}&T=1"})
        meetings.append({
            "external_id": str(meeting_id),
            "title": title.strip(),
            "source_start": start.isoformat(),
            "meeting_date": start.date().isoformat(),
            "url": url,
            "documents": documents,
        })
    return meetings


class LinkList(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        fields = dict(attrs)
        self.active = None
        if fields.get("href"):
            self.active = {
                "href": fields["href"], "title": fields.get("title") or fields.get("aria-label") or "", "text": "",
            }
            self.links.append(self.active)

    def handle_data(self, data):
        if self.active is not None:
            self.active["text"] += data

    def handle_endtag(self, tag):
        if tag == "a":
            self.active = None


def read_civicweb(source_url: str, content: bytes) -> list[dict]:
    parser = LinkList()
    parser.feed(content.decode("utf-8", errors="replace"))
    meetings = {}
    for link in parser.links:
        url = _public_link(source_url, link["href"])
        if not url:
            continue
        parsed = urlsplit(url)
        if parsed.path.lower() != "/portal/meetinginformation.aspx":
            continue
        external_id = {key.lower(): value for key, value in parse_qs(parsed.query).items()}.get("id", [""])[0]
        title, separator, day = " ".join(link["text"].split()).rpartition(" - ")
        if not (external_id.isascii() and external_id.isdecimal() and title and separator):
            continue
        try:
            meeting_date = datetime.strptime(day, "%d %b %Y").date().isoformat()
        except ValueError:
            continue
        meetings.setdefault(external_id, {
            "external_id": external_id, "title": title, "meeting_date": meeting_date, "url": url,
        })
    if not meetings:
        raise ImportInputError("No dated CivicWeb meetings were found. Select the meeting-type listing.")
    return list(meetings.values())


def read_iqm2(source_url: str, content: bytes) -> list[dict]:
    page = content.decode("utf-8", errors="replace")
    rows = re.split(r"""<div\s+class=["'][^"']*\bMeetingRow\b[^"']*["']""", page, flags=re.I)[1:]
    meetings = {}
    for row in rows:
        parser = LinkList()
        parser.feed(row.split('class="Row MonthHeader"', 1)[0])
        parent = next((link for link in parser.links if "/detail_meeting.aspx" in link["href"].lower()), None)
        if not parent:
            continue
        url = _public_link(source_url, parent["href"])
        if not url:
            continue
        external_id = parse_qs(urlsplit(url).query).get("ID", [""])[0]
        title_fields = re.findall(r"(?:^|\s)(?:Board|Type):\s*([^\r\n]+)", parent["title"])
        try:
            start = datetime.strptime(" ".join(parent["text"].split()), "%b %d, %Y %I:%M %p")
        except ValueError:
            continue
        if not (external_id.isascii() and external_id.isdecimal() and title_fields):
            continue
        documents = []
        for link in parser.links:
            document_url = _public_link(source_url, link["href"])
            if document_url and urlsplit(document_url).path.lower().endswith("fileopen.aspx"):
                documents.append({"kind": link["text"].strip(), "url": document_url})
        meetings.setdefault(external_id, {
            "external_id": external_id, "title": " - ".join(title_fields),
            "source_start": start.isoformat(), "meeting_date": start.date().isoformat(),
            "url": url, "documents": documents,
        })
    if not meetings:
        raise ImportInputError("No iQM2 rows were found. Select a saved public meeting list.")
    return list(meetings.values())


def read_swagit(source_url: str, content: bytes) -> list[dict]:
    meetings = {}
    for row in _table_rows(content):
        if not row or not row[0]["links"]:
            continue
        link = row[0]["links"][0]
        url = _public_link(source_url, link["url"])
        match = re.fullmatch(r"/videos/(\d+)/?", urlsplit(url).path) if url else None
        if not match:
            continue
        title = " ".join(link["text"].split())
        date_text = " ".join(row[0]["text"].strip().removeprefix(link["text"].strip()).split())
        try:
            day = datetime.strptime(date_text, "%b %d, %Y").date().isoformat()
        except ValueError:
            continue
        if title:
            meetings.setdefault(match[1], {
                "external_id": match[1], "title": title, "meeting_date": day,
                "recordings": [{"url": url}],
            })
    if not meetings:
        raise ImportInputError("No dated Swagit recordings were found. Select a public video archive.")
    return list(meetings.values())


def read_suiteone(source_url: str, content: bytes) -> list[dict]:
    meetings = {}
    document_kinds = {"getagendafile": "agenda", "getagendapacketfile": "packet", "getminutesfile": "minutes"}
    for row in _table_rows(content):
        if len(row) < 2 or not row[0]["links"]:
            continue
        parent = row[0]["links"][0]
        url = _public_link(source_url, parent["url"])
        if not url or urlsplit(url).path.rstrip("/").lower() != "/event":
            continue
        external_id = parse_qs(urlsplit(url).query).get("id", [""])[0]
        title = parent["title"].removeprefix("Navigate to ").strip()
        if not (title and external_id.isascii() and external_id.isdecimal()):
            continue
        try:
            start = datetime.strptime(" ".join(row[1]["text"].split()), "%b %d, %Y | %I:%M %p")
        except ValueError:
            continue
        documents = []
        for cell in row[2:]:
            for link in cell["links"]:
                document_url = _public_link(source_url, link["url"])
                if not document_url:
                    continue
                path = urlsplit(document_url).path.lower().split("/")
                if path[:2] == ["", "event"] and len(path) > 2 and path[2] in document_kinds:
                    documents.append({"kind": document_kinds[path[2]], "url": document_url})
        meetings.setdefault(external_id, {
            "external_id": external_id, "title": title, "meeting_date": start.date().isoformat(),
            "source_start": start.isoformat(), "url": url, "documents": documents,
            "recordings": [{"url": url}] if len(row) >= 6 and any(
                link["url"] == parent["url"] for link in row[-1]["links"]
            ) else [],
        })
    if not meetings:
        raise ImportInputError("No SuiteOne events were found. Select a public meeting archive.")
    return list(meetings.values())


def read_peak(source_url: str, content: bytes) -> list[dict]:
    meetings = {}
    labels = {"AgendaLink": "agenda", "AgendaPacketLink": "packet", "MinutesLink": "minutes"}
    for row in _table_rows(content):
        cells = {cell["label"]: cell for cell in row}
        title = " ".join(cells.get("Name", {}).get("text", "").split())
        date_text = " ".join(cells.get("Date", {}).get("text", "").split()).split(" - ", 1)[0]
        date_text = re.sub(r"^\d{10}\s+", "", date_text)
        documents = []
        external_id = None
        for label, kind in labels.items():
            for link in cells.get(label, {}).get("links", []):
                url = _public_link(source_url, link["url"])
                if url:
                    parsed = urlsplit(url)
                    documents.append({"kind": kind, "url": url})
                    if parsed.hostname == urlsplit(source_url).hostname:
                        event_id = parse_qs(parsed.query).get("event_id", [""])[0]
                        if event_id.isascii() and event_id.isdecimal():
                            external_id = event_id
        if not (title and external_id):
            continue
        for pattern in ("%B %d, %Y", "%b %d, %Y"):
            try:
                day = datetime.strptime(date_text.replace(".", ""), pattern).date().isoformat()
                break
            except ValueError:
                continue
        else:
            continue
        meetings.setdefault(external_id, {
            "external_id": external_id, "title": title, "meeting_date": day, "documents": documents,
        })
    if not meetings:
        raise ImportInputError("No Peak events with published agendas were found.")
    return list(meetings.values())


def read_utah_notice(source_url: str, content: bytes) -> list[dict]:
    identity = re.fullmatch(r"/pmn/sitemap/notice/(\d+)\.html", urlsplit(source_url).path)
    if not identity:
        raise ImportInputError("Enter the original Utah public notice detail URL.")
    page = content.decode("utf-8", errors="replace")
    fields = {
        unescape(key): unescape(value.strip())
        for key, value in re.findall(r"<dt>([^<>]+)</dt>\s*<dd\b[^>]*>(.*?)</dd>", page, re.S)
    }
    title = fields.get("Notice Title")
    try:
        start = datetime.strptime(fields.get("Event Start Date & Time", ""), "%B %d, %Y %I:%M %p")
    except ValueError as error:
        raise ImportInputError("Select a public notice with a dated event.") from error
    if not title:
        raise ImportInputError("Select a public notice with a published title.")
    documents = []
    for row in _table_rows(content):
        if len(row) < 2:
            continue
        for link in row[0]["links"]:
            url = _public_link(source_url, link["url"])
            if not url or not re.fullmatch(r"/pmn/files/\d+\.pdf", urlsplit(url).path):
                continue
            name = " ".join(link["text"].split())
            label = " ".join(row[1]["text"].lower().split())
            if "minutes" in label:
                kind = "minutes"
            elif "packet" in name.lower():
                kind = "packet"
            elif "agenda" in name.lower():
                kind = "agenda"
            else:
                kind = "attachment"
            documents.append({"kind": kind, "url": url, "title": name})
    return [{
        "external_id": identity[1], "title": title, "meeting_date": start.date().isoformat(),
        "source_start": start.isoformat(), "url": source_url, "documents": documents,
        "notice": {"title": title, "text": _visible_text(fields.get("Description/Agenda", ""))},
    }]


def read_destiny(source_url: str, content: bytes) -> list[dict]:
    source = urlsplit(source_url)
    tenant = parse_qs(source.query).get("id", [source.path.lstrip("/").partition("/")[0]])[0]
    if not (tenant.isascii() and tenant.isdecimal()):
        raise ImportInputError("Enter the original AgendaQuick public meeting list URL.")
    base = urljoin(source_url, f"/{tenant}/agenda/")
    page = content.decode("utf-8", errors="replace")
    rows = re.split(r"<h3\b[^>]*>([^<>]+)</h3>", page)[1:]
    meetings = {}
    kinds = {"agenda.cfm": "agenda", "minutes.cfm": "minutes", "packet.cfm": "packet"}
    for heading, body in zip(rows[::2], rows[1::2], strict=True):
        date_text, separator, title = unescape(heading).strip().partition(": ")
        if not (separator and title):
            continue
        try:
            day = datetime.strptime(date_text, "%B %d, %Y").date().isoformat()
        except ValueError:
            continue
        links = LinkList()
        links.feed(body)
        documents = []
        external_id = None
        for link in links.links:
            url = _public_link(base, link["href"])
            if not url:
                continue
            parsed = urlsplit(url)
            kind = kinds.get(parsed.path.rsplit("/", 1)[-1].lower())
            seq = parse_qs(parsed.query).get("seq", [""])[0]
            if parsed.hostname == source.hostname and kind and seq.isascii() and seq.isdecimal():
                external_id = external_id or seq
                if seq == external_id:
                    documents.append({"kind": kind, "url": url})
        if external_id:
            meetings.setdefault(external_id, {
                "external_id": external_id, "title": title, "meeting_date": day, "documents": documents,
            })
    if not meetings:
        raise ImportInputError("No AgendaQuick meetings with published documents were found.")
    return list(meetings.values())


def read_town_hall_streams(source_url: str, content: bytes) -> list[dict]:
    page = content.decode("utf-8", errors="replace")
    archive = page.partition("Previous Events:")[2]
    entries = re.findall(
        r'<a\s+href="([^"]+)"[^>]*>\s*<div class="evbox"[^>]*>'
        r'\s*<h5>([^<>]+)</h5>\s*<p>([^<>]+)</p>', archive,
    )
    meetings = {}
    for href, title, schedule in entries:
        url = _public_link(source_url, unescape(href))
        if not url or urlsplit(url).path != "/stream.php":
            continue
        query = parse_qs(urlsplit(url).query)
        external_id = query.get("id", [""])[0]
        location = query.get("location_id", [""])[0]
        if not all(value.isascii() and value.isdecimal() for value in (external_id, location)):
            continue
        start_text = " ".join(schedule.split()).partition(" to ")[0]
        try:
            start = datetime.strptime(start_text, "%B %d, %Y - %I:%M %p")
        except ValueError:
            continue
        meetings.setdefault(external_id, {
            "external_id": external_id, "title": unescape(title).strip(),
            "meeting_date": start.date().isoformat(), "source_start": start.isoformat(),
            "recordings": [{"url": url}],
        })
    if not meetings:
        raise ImportInputError("No archived Town Hall Streams events were found.")
    return list(meetings.values())


def read_telvue(source_url: str, content: bytes) -> list[dict]:
    page = content.decode("utf-8", errors="replace")
    entries = re.findall(
        r'<a href="([^"]+)">\s*<span class="h4 title block">([^<>]+)</span>', page,
    )
    meetings = {}
    for href, label in entries:
        url = _public_link(source_url, unescape(href))
        path = urlsplit(url).path if url else ""
        match = re.fullmatch(r"/player/[A-Za-z0-9_-]+/(?:playlists/\d+/)?media/(\d+)", path)
        title = unescape(label).strip()
        if not match or not title:
            continue
        row = {"external_id": match[1], "title": title, "recordings": [{"url": url}]}
        date_match = re.search(r"([A-Za-z]+ \d{1,2}, \d{4})$", title)
        if date_match:
            for pattern in ("%B %d, %Y", "%b %d, %Y"):
                try:
                    row["meeting_date"] = datetime.strptime(date_match[1], pattern).date().isoformat()
                    break
                except ValueError:
                    continue
        meetings.setdefault(match[1], row)
    if not meetings:
        raise ImportInputError("No TelVue playlist recordings were found.")
    return list(meetings.values())


def read_champ(source_url: str, content: bytes) -> list[dict]:
    source = urlsplit(source_url)
    identity = re.fullmatch(r"/([a-zA-Z0-9_-]+)/event/(\d+)/?", source.path)
    payload = read_json(content)
    if not isinstance(payload, dict) or not identity:
        raise ImportInputError("Select the public CHAMP event JSON and enter the event URL.")
    customer = payload.get("Customer")
    event = payload.get("Event")
    if not (
        isinstance(customer, dict) and customer.get("CustomerAccessID") == identity[1]
        and isinstance(event, dict) and str(event.get("CustomerEventID")) == identity[2]
        and event.get("EventPublishStatusID") == 2
    ):
        raise ImportInputError("The response does not match a published CHAMP event at this URL.")
    title = event.get("EventTitle")
    if not isinstance(title, str) or not title.strip():
        raise ImportInputError("The CHAMP event has no published title.")
    try:
        local = datetime.fromisoformat(event["EventDateTimeCustomerLocal"])
        utc = datetime.strptime(event["EventDateTimeUTC"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError) as error:
        raise ImportInputError("The CHAMP event has no usable start time.") from error
    url = f"https://play.champds.com/{identity[1]}/event/{identity[2]}"
    board = payload.get("Board")
    agenda = payload.get("Agenda")
    media = payload.get("MediaInfo")
    items = []
    documents = {}

    def collect_attachments(section):
        for attachment in section.get("Attachments") or []:
            if not isinstance(attachment, dict):
                continue
            location = attachment.get("MediaFileLocation", "")
            filename = attachment.get("MediaFileName", "")
            if not isinstance(location, str) or not isinstance(filename, str):
                continue
            if not (re.fullmatch(r"\d{4}-\d{2}", location) and re.fullmatch(r"[\w.-]+", filename)):
                continue
            link = urljoin(url, f"/ATT/{identity[1]}/{location}/{filename}")
            label = unquote(str(attachment.get("MediaNickName") or filename))
            documents.setdefault(link, {"kind": "attachment", "title": label, "url": link})

    if isinstance(agenda, dict):
        collect_attachments(agenda)
        pending = list(reversed(agenda.get("AgendaItems") or []))
        while pending:
            item = pending.pop()
            if not isinstance(item, dict):
                continue
            item_id = item.get("CustomerAgendaItemID")
            label = item.get("Title")
            if isinstance(item_id, int) and isinstance(label, str) and label.strip():
                items.append({"external_id": str(item_id), "title": label.strip()})
                collect_attachments(item)
            pending.extend(reversed(item.get("Children") or []))
    return [{
        "external_id": identity[2], "title": title.strip(), "meeting_date": local.date().isoformat(),
        "scheduled_start": utc.isoformat(), "url": url, "agenda_items": items,
        "board": board.get("BoardName") if isinstance(board, dict) else None,
        "documents": list(documents.values()),
        "recordings": [{"url": url}] if isinstance(media, dict) and media.get("MediaType") == "VOD" else [],
    }]


def read_onbase(source_url: str, content: bytes) -> list[dict]:
    meetings = {}
    kinds = {"1": "agenda", "2": "minutes", "3": "summary", "5": "packet", "6": "attachment"}
    for row in _table_rows(content):
        cells = {cell["label"]: cell for cell in row if cell["label"]}
        title = " ".join(cells.get("mtgType", {}).get("text", "").split())
        time_text = " ".join(cells.get("mtgTime", {}).get("text", "").split())
        if not title or not time_text:
            continue
        try:
            start = datetime.strptime(time_text, "%m/%d/%Y %I:%M:%S %p")
        except ValueError:
            continue
        documents = {}
        recordings = {}
        external_id = None
        for cell in row:
            for link in cell["links"]:
                url = _public_link(source_url, link["url"])
                if not url:
                    continue
                parsed = urlsplit(url)
                query = parse_qs(parsed.query)
                if "/documents/downloadfile/" in parsed.path.lower():
                    kind = kinds.get(query.get("documentType", [""])[0])
                    meeting_id = query.get("meetingId", [""])[0]
                    if kind and meeting_id.isascii() and meeting_id.isdecimal():
                        external_id = external_id or meeting_id
                        if meeting_id == external_id:
                            documents.setdefault(url, {"kind": kind, "url": url})
                elif parsed.path.lower().endswith("/meetings/viewmeeting") and link["text"].strip() == "View Media":
                    recordings.setdefault(url, {"url": url})
        if external_id:
            meetings.setdefault(external_id, {
                "external_id": external_id, "title": title, "meeting_date": start.date().isoformat(),
                "source_start": start.isoformat(), "documents": list(documents.values()),
                "recordings": list(recordings.values()),
            })
    if not meetings:
        raise ImportInputError("No OnBase Agenda Online meeting rows with published documents were found.")
    return list(meetings.values())


def read_laserfiche(source_url: str, content: bytes) -> list[dict]:
    links = LinkList()
    links.feed(content.decode("utf-8", errors="replace"))
    meetings = {}
    for link in links.links:
        url = _public_link(source_url, link["href"])
        match = re.search(r"/edoc/(\d+)/([^/]+\.pdf)$", urlsplit(url).path, re.I) if url else None
        if not match:
            continue
        title = unquote(match[2][:-4]).strip()
        date_match = re.search(r"\b(\d{4})[.-](\d{2})[.-](\d{2})\b", title)
        if not date_match:
            continue
        try:
            day = datetime(*(int(value) for value in date_match.groups())).date().isoformat()
        except ValueError:
            continue
        label = title.lower()
        if "minutes" in label:
            kind = "minutes"
        elif "packet" in label:
            kind = "packet"
        elif "agenda" in label:
            kind = "agenda"
        else:
            continue
        meetings.setdefault(match[1], {
            "external_id": match[1], "title": title, "meeting_date": day,
            "documents": [{"kind": kind, "title": title, "url": url}],
        })
    if not meetings:
        raise ImportInputError("No dated agenda, packet or minutes PDFs were found in this WebLink folder.")
    return list(meetings.values())


def read_towncloud(source_url: str, content: bytes) -> list[dict]:
    payload = read_json(content)
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ImportInputError("Select the TownCloud public meeting table JSON response.")
    meetings = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("DT_RowData"), dict):
            continue
        url = _public_link(source_url, row["DT_RowData"].get("link"))
        identity = re.fullmatch(r"/go/[\w-]+/agendas/(\d+)/?", urlsplit(url).path) if url else None
        title = row.get("name")
        if not identity or not isinstance(title, str) or not title.strip():
            continue
        date_text = row.get("meeting_date")
        if not isinstance(date_text, str):
            continue
        try:
            start = datetime.strptime(date_text, "%B %d, %Y at %I:%M%p")
        except ValueError:
            continue
        documents = []
        for field, kind in (("agenda_pdf", "agenda"), ("minutes_pdf", "minutes"), ("agenda_packets", "packet")):
            links = LinkList()
            if not isinstance(row.get(field), str):
                continue
            links.feed(row[field])
            for link in links.links:
                address = _public_link(source_url, link["href"])
                if address:
                    documents.append({"kind": kind, "url": address})
        meetings.setdefault(identity[1], {
            "external_id": identity[1], "title": title.strip(), "meeting_date": start.date().isoformat(),
            "source_start": start.isoformat(), "url": url, "documents": documents,
        })
    if rows and not meetings:
        raise ImportInputError("No dated TownCloud agenda rows were found.")
    return list(meetings.values())


def read_towncloud_agenda(source_url: str, content: bytes) -> list[dict]:
    identity = re.fullmatch(r"/go/[\w-]+/agendas/(\d+)/?", urlsplit(source_url).path)
    page = content.decode("utf-8", errors="replace")
    heading = re.search(
        r'<div class="agenda-view-header">.*?<h3>([^<>]+)</h3>\s*<div>\s*<strong>([^<>]+)</strong>',
        page, re.S,
    )
    if not identity or not heading:
        raise ImportInputError("Enter the TownCloud public agenda detail URL and its HTML.")
    date_text = unescape(heading[2]).partition(", ")[2]
    try:
        start = datetime.strptime(date_text, "%B %d, %Y at %I:%M %p")
    except ValueError as error:
        raise ImportInputError("The TownCloud agenda has no usable meeting time.") from error
    links = LinkList()
    links.feed(page)
    kinds = {"agenda pdf": "agenda", "agenda pdf packet": "packet"}
    documents = []
    for link in links.links:
        url = _public_link(source_url, link["href"])
        kind = kinds.get(link["title"].lower())
        if url and kind and urlsplit(url).path.endswith("/get_agenda_document_link"):
            documents.append({"kind": kind, "url": url})
    items = []
    for label in re.findall(r'<li class="(?:item(?: has-sub-items)?|sub-item)">\s*<h[56]>([^<>]+)</h[56]>', page):
        title = unescape(label).strip()
        if title:
            items.append({"external_id": str(len(items) + 1), "title": title})
    return [{
        "external_id": identity[1], "title": unescape(heading[1]).strip(),
        "meeting_date": start.date().isoformat(), "source_start": start.isoformat(),
        "url": source_url, "documents": documents, "agenda_items": items,
    }]


def read_digital_towpath(source_url: str, content: bytes) -> list[dict]:
    identity = re.fullmatch(r"/meetings/detail/(\d+)/?", urlsplit(source_url).path)
    page = content.decode("utf-8", errors="replace")
    heading = re.search(r'<h3 class="dtp-meeting-title">([^<>]+)</h3>.*?<time datetime="([^"]+)"[^>]*>([^<>]+)</time>', page, re.S)
    if not identity or not heading:
        raise ImportInputError("Enter the Digital Towpath meeting detail URL and its HTML.")
    try:
        day = datetime.fromisoformat(heading[2]).date().isoformat()
    except ValueError as error:
        raise ImportInputError("The Digital Towpath meeting has no usable date.") from error
    links = LinkList()
    links.feed(page)
    documents = []
    for link in links.links:
        label = link["title"].lower()
        if label not in {"download the agenda", "download the minutes"}:
            continue
        url = _public_link(source_url, link["href"])
        if url:
            documents.append({"kind": label.rsplit(" ", 1)[-1], "title": link["text"].strip(), "url": url})
    return [{
        "external_id": identity[1], "title": unescape(heading[1]).strip(),
        "meeting_date": day, "url": source_url, "documents": documents,
    }]


def _visible_text(markup: str) -> str:
    return " ".join(unescape(re.sub(r"<!--.*?-->|<[^>]*>", "", markup, flags=re.S)).split())


def read_clerkbase(source_url: str, content: bytes) -> list[dict]:
    path = urlsplit(source_url).path
    if not re.fullmatch(r"/Content/[^/]+/.+\.html?", path, flags=re.I):
        raise ImportInputError("Enter a ClerkBase published meeting document URL.")
    page = content.decode("utf-8", errors="replace")
    body = re.search(r"<body\b[^>]*>(.*?)</body>", page, re.I | re.S)
    heading = body[1].split("<h2", 1)[0] if body else ""
    paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", heading, re.I | re.S)
    lines = [_visible_text(paragraph) for paragraph in paragraphs[:12]]
    date_index = next((index for index, line in enumerate(lines)
                       if re.fullmatch(r"[A-Za-z]+ \d{1,2}, \d{4}", line)), None)
    title = next((line for line in lines if re.search(r"\bmeeting$", line, re.I)), "")
    if date_index is None or not title:
        raise ImportInputError("No titled, dated ClerkBase meeting was found in the document.")
    try:
        day = datetime.strptime(lines[date_index], "%B %d, %Y").date().isoformat()
    except ValueError as error:
        raise ImportInputError("The ClerkBase meeting has no usable date.") from error
    links = LinkList()
    links.feed(body[1])
    player = None
    for link in links.links:
        address = _public_link(source_url, link["href"])
        if address:
            parsed = urlsplit(address)
            if parsed.hostname == "vid.opengovideo.com" and "iCurrentPosition" not in parse_qs(parsed.query):
                player = address
                break
    return [{
        "external_id": path.lower(), "title": title, "meeting_date": day, "url": source_url,
        "documents": [{"kind": "document", "url": source_url, "title": "Published meeting document"}],
        "recordings": [{"url": player}] if player else [],
    }]


def read_public_calendar(source_url: str, content: bytes) -> list[dict]:
    calendar = re.sub(r"\r?\n[ \t]", "", content.decode("utf-8-sig", errors="replace"))
    if not calendar.startswith("BEGIN:VCALENDAR"):
        raise ImportInputError("Select a municipality's public iCalendar meeting feed.")
    meetings = []
    for block in re.findall(r"^BEGIN:VEVENT\r?\n(.*?)^END:VEVENT", calendar, re.M | re.S):
        fields = {}
        for line in block.splitlines():
            key, separator, value = line.partition(":")
            if separator:
                fields.setdefault(key.partition(";")[0], value)
        uid = fields.get("UID")
        title = re.sub(r"\\([,;\\])", r"\1", fields.get("SUMMARY", "")).strip()
        start = fields.get("DTSTART", "")
        if not uid or not title or fields.get("STATUS") == "CANCELLED":
            continue
        try:
            day = datetime.strptime(start[:8], "%Y%m%d").date().isoformat()
            value = (datetime.strptime(start.rstrip("Z"), "%Y%m%dT%H%M%S")
                     if re.fullmatch(r"\d{8}T\d{6}Z?", start) else None)
        except ValueError:
            continue
        meeting = {
            "external_id": uid + ("#" + fields["RECURRENCE-ID"] if "RECURRENCE-ID" in fields else ""),
            "title": title, "meeting_date": day,
            "url": _public_link(source_url, fields.get("URL")) or source_url,
        }
        if value:
            meeting["source_start"] = value.isoformat() + ("Z" if start.endswith("Z") else "")
        if fields.get("LOCATION"):
            meeting["location"] = re.sub(r"\\([,;\\])", r"\1", fields["LOCATION"])
        meetings.append(meeting)
    return meetings


def read_wistia(source_url: str, content: bytes) -> list[dict]:
    payload = read_json(content)
    media = payload.get("media") if isinstance(payload, dict) else None
    if not isinstance(media, dict) or media.get("protected"):
        raise ImportInputError("Select an unprotected Wistia public media JSON response.")
    identity = media.get("hashedId")
    title = media.get("name")
    if not isinstance(identity, str) or not re.fullmatch(r"[a-z0-9]{10}", identity) or not isinstance(title, str) or not title.strip():
        raise ImportInputError("The Wistia response has no public video ID or title.")
    assets = media.get("assets") or []
    video = next((_public_link(source_url, asset.get("url")) for asset in assets
                  if isinstance(asset, dict) and asset.get("status") == 2
                  and asset.get("type") in {"hd_mp4_video", "md_mp4_video"} and asset.get("url")), None)
    player = f"https://fast.wistia.net/embed/iframe/{identity}"
    recording = {"url": player}
    if video:
        recording["video_url"] = video
    if isinstance(media.get("captions"), list):
        recording["captions"] = [
            {"language": caption["language"], "text": caption["text"]}
            for caption in media["captions"] if isinstance(caption, dict)
            and isinstance(caption.get("language"), str) and isinstance(caption.get("text"), str)
        ]
    return [{"external_id": identity, "title": title.strip(), "url": player, "recordings": [recording]}]


def read_boardable(source_url: str, content: bytes) -> list[dict]:
    match = re.fullmatch(r"/[\w-]+/meetings/([\w-]+)/?", urlsplit(source_url).path)
    page = content.decode("utf-8", errors="replace")
    embedded = re.search(r'<script\b[^>]*\bid="__NUXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not match or not embedded:
        raise ImportInputError("Enter a Boardable Public Site meeting detail URL and its HTML.")
    table = read_json(embedded[1].encode())
    if not isinstance(table, list):
        raise ImportInputError("The Boardable page has no meeting data.")

    def value(index):
        return table[index] if type(index) is int and 0 <= index < len(table) else None

    detail = next((value(row.get("meeting")) for row in table if isinstance(row, dict)
                   and "agendaListFormat" in row), None)
    if not isinstance(detail, dict) or value(detail.get("slug")) != match[1]:
        raise ImportInputError("The Boardable response does not match this meeting URL.")
    title = value(detail.get("title"))
    identity = value(detail.get("id"))
    date = value(detail.get("date"))
    date_match = re.search(r"[A-Za-z]{3} \d{1,2}, \d{4}", date or "") if isinstance(date, str) else None
    if not isinstance(title, str) or not title.strip() or type(identity) is not int or not date_match:
        raise ImportInputError("No titled, dated Boardable meeting was found.")
    try:
        day = datetime.strptime(date_match[0], "%b %d, %Y").date().isoformat()
    except ValueError as error:
        raise ImportInputError("The Boardable meeting has no usable date.") from error
    links = LinkList()
    links.feed(page)
    documents = []
    for link in links.links:
        url = _public_link(source_url, link["href"])
        if not url:
            continue
        parsed = urlsplit(url)
        if parsed.hostname != "app.boardable.com" or f"/public-site-data/meetings/{match[1]}/documents/" not in parsed.path:
            continue
        label = " ".join(link["text"].split())
        kind = next((kind for kind in ("minutes", "packet", "agenda") if kind in label.lower()), "attachment")
        documents.append({"kind": kind, "title": label, "url": url})
    return [{
        "external_id": str(identity), "title": title.strip(), "meeting_date": day,
        "location": value(detail.get("location")), "url": source_url, "documents": documents,
    }]


def read_gworks(source_url: str, content: bytes) -> list[dict]:
    source = urlsplit(source_url)
    city = re.fullmatch(r"/city/(\d+)/cms/data\.json", source.path)
    payload = read_json(content)
    rows = payload.get("meetings") if isinstance(payload, dict) else None
    if source.hostname != "files.frontdeskgworks.com" or not city or not isinstance(rows, list):
        raise ImportInputError("Enter the gWorks FrontDesk published city meetings JSON URL.")
    meetings = []
    for row in rows:
        if not isinstance(row, dict) or type(row.get("id")) is not int:
            continue
        identity = row["id"]
        title = row.get("title")
        timestamp = row.get("meeting_ts")
        if not isinstance(title, str) or not title.strip() or not isinstance(timestamp, str):
            continue
        try:
            start = datetime.fromisoformat(timestamp)
        except ValueError:
            continue
        documents = [
            {"kind": kind, "url": f"https://api.gworks.cloud/cms/public/city/{city[1]}/{kind}/pdf/{identity}/"}
            for kind in ("agenda", "minutes") if row.get(f"{kind}_fl") is True
        ]
        meetings.append({
            "external_id": str(identity), "title": title.strip(), "scheduled_start": start.isoformat(),
            "location": row.get("location") if isinstance(row.get("location"), str) else None,
            "url": source_url, "documents": documents,
        })
    return meetings


def read_boarddocs(source_url: str, content: bytes) -> list[dict]:
    import pdfplumber
    from pdfplumber.utils.exceptions import PdfminerException

    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            if not 1 <= len(pdf.pages) <= 50:
                raise ImportInputError("Choose an unencrypted BoardDocs print agenda of up to 50 pages.")
            if "BoardDocs" not in str(pdf.metadata.get("Title", "")):
                raise ImportInputError("Choose an agenda printed to PDF by BoardDocs.")
            lines = [line.strip() for page in pdf.pages for line in page.extract_text().splitlines() if line.strip()]
    except (PdfminerException, ValueError, OSError, RecursionError) as error:
        if isinstance(error, ImportInputError):
            raise
        raise ImportInputError("Could not read the BoardDocs PDF.") from error
    date_line = next((index for index, line in enumerate(lines[:12])
                      if re.fullmatch(r"[A-Za-z]+, [A-Za-z]+ \d{1,2}, \d{4}", line)), None)
    if date_line is None or date_line + 1 >= len(lines):
        raise ImportInputError("The BoardDocs print agenda has no recognizable meeting title and date.")
    try:
        day = datetime.strptime(lines[date_line], "%A, %B %d, %Y").date().isoformat()
    except ValueError as error:
        raise ImportInputError("The BoardDocs print agenda has no usable date.") from error
    title = lines[date_line + 1]
    items = {}
    for line in lines[date_line + 2:]:
        item = re.fullmatch(r"(\d+\.\d{2})\s+(.+)", line)
        if item:
            items.setdefault(item[1], {"external_id": item[1], "title": item[2]})
    if not items:
        raise ImportInputError("The BoardDocs print agenda contains no recognizable numbered items.")
    return [{
        "external_id": urlsplit(source_url).path, "title": title, "meeting_date": day, "url": source_url,
        "agenda_items": list(items.values()),
        "documents": [{"kind": "agenda", "title": title, "url": source_url}],
    }]


def read_tyler_meeting_manager(source_url: str, content: bytes) -> list[dict]:
    source = urlsplit(source_url)
    if not source.hostname or not source.hostname.endswith(".meetingmanager.tylerapp.com"):
        raise ImportInputError("Enter the municipality's Tyler Meeting Manager public calendar URL.")
    rows = read_json(content)
    if not isinstance(rows, list):
        raise ImportInputError("Select a saved Tyler public calendar response.")
    meetings = []
    for row in rows:
        if not isinstance(row, dict) or row.get("isPublicVisibility") != 1:
            continue
        identity = row.get("id")
        title = row.get("meetingTitle")
        source_date = row.get("startDateTime")
        if not all(isinstance(value, str) and value.strip() for value in (identity, title, source_date)):
            continue
        if row.get("canceled") or row.get("adjourned") or re.match(r"cancell?ed\b", title, re.I):
            continue
        try:
            start = datetime.strptime(f"{source_date[:10]} {row.get('startTime')}", "%Y-%m-%d %I:%M %p")
        except ValueError:
            continue
        items = []
        labels = row.get("agendaItemTitles")
        if row.get("agendaStatus") == 5 and isinstance(labels, list):
            for index, label in enumerate(labels):
                if isinstance(label, str) and (name := _visible_text(label)):
                    items.append({"external_id": str(index + 1), "title": name})
        meetings.append({
            "external_id": identity, "title": title.strip(), "meeting_date": start.date().isoformat(),
            "source_start": start.isoformat(),
            "location": row.get("location") if isinstance(row.get("location"), str) else None,
            "url": source_url, "agenda_items": items,
        })
    return meetings


PORTAL_READERS = {
    ("granicus", "viewpublisher-html"): read_viewpublisher,
    ("primegov", "primegov-portal-json"): read_primegov_portal,
    ("civicplus-select", "civicplus-events-json"): read_civicplus_events,
    ("civicplus-agenda-center", "agenda-center-html"): read_agenda_center,
    ("municode-meetings", "municode-meetings-html"): read_municode_meetings,
    ("boardbook", "boardbook-html"): read_boardbook,
    ("escribe", "escribe-calendar-json"): read_escribe,
    ("simbli", "simbli-html"): read_simbli,
    ("civicweb", "civicweb-html"): read_civicweb,
    ("iqm2", "iqm2-html"): read_iqm2,
    ("swagit", "swagit-archive-html"): read_swagit,
    ("suiteone-media", "suiteone-archive-html"): read_suiteone,
    ("peak", "peak-viewpublisher-html"): read_peak,
    ("utah-public-notice", "utah-notice-html"): read_utah_notice,
    ("destiny-agendaquick", "agendaquick-html"): read_destiny,
    ("town-hall-streams", "town-hall-streams-html"): read_town_hall_streams,
    ("telvue", "telvue-playlist-html"): read_telvue,
    ("champ", "champ-event-json"): read_champ,
    ("onbase", "onbase-agenda-online-html"): read_onbase,
    ("laserfiche-weblink", "laserfiche-folder-html"): read_laserfiche,
    ("towncloud", "towncloud-table-json"): read_towncloud,
    ("towncloud", "towncloud-agenda-html"): read_towncloud_agenda,
    ("digital-towpath", "digital-towpath-detail-html"): read_digital_towpath,
    ("clerkbase", "clerkbase-document-html"): read_clerkbase,
    ("first-party", "public-meeting-ics"): read_public_calendar,
    ("wistia", "wistia-media-json"): read_wistia,
    ("boardable", "boardable-public-meeting-html"): read_boardable,
    ("gworks", "gworks-frontdesk-json"): read_gworks,
    ("boarddocs", "boarddocs-print-pdf"): read_boarddocs,
    ("tyler-meeting-manager", "tyler-public-calendar-json"): read_tyler_meeting_manager,
}

SOURCE_FORMATS = (
    ("legistar", "meeting-export", "Legistar JSON export"),
    ("primegov", "meeting-export", "PrimeGov JSON export"),
    ("granicus", "meeting-export", "Granicus JSON export"),
    ("novusagenda", "meeting-export", "NovusAGENDA JSON export"),
    ("granicus", "viewpublisher-html", "Granicus ViewPublisher HTML"),
    ("primegov", "primegov-portal-json", "PrimeGov portal meeting list JSON"),
    ("civicplus-select", "civicplus-events-json", "CivicPlus Agenda and Meeting Management Select Events JSON"),
    ("civicplus-agenda-center", "agenda-center-html", "CivicPlus Agenda Center HTML"),
    ("municode-meetings", "municode-meetings-html", "Municode Meetings HTML"),
    ("boardbook", "boardbook-html", "BoardBook public organization HTML"),
    ("escribe", "escribe-calendar-json", "eSCRIBE public calendar JSON"),
    ("simbli", "simbli-html", "Simbli public meeting listing HTML"),
    ("civicweb", "civicweb-html", "iCompass CivicWeb meeting-type listing HTML"),
    ("iqm2", "iqm2-html", "iQM2 public meeting list HTML"),
    ("swagit", "swagit-archive-html", "Granicus Swagit public video archive HTML"),
    ("suiteone-media", "suiteone-archive-html", "SuiteOne Media public meeting archive HTML"),
    ("peak", "peak-viewpublisher-html", "Granicus Peak public agenda center HTML"),
    ("utah-public-notice", "utah-notice-html", "Utah Public Notice Website notice detail HTML"),
    ("destiny-agendaquick", "agendaquick-html", "Destiny AgendaQuick public meeting list HTML"),
    ("town-hall-streams", "town-hall-streams-html", "Town Hall Streams public archive HTML"),
    ("telvue", "telvue-playlist-html", "TelVue public playlist HTML"),
    ("champ", "champ-event-json", "CHAMP public event JSON"),
    ("onbase", "onbase-agenda-online-html", "Hyland OnBase Agenda Online HTML"),
    ("laserfiche-weblink", "laserfiche-folder-html", "Laserfiche WebLink dated document folder HTML"),
    ("towncloud", "towncloud-table-json", "TownCloud public agenda table JSON"),
    ("towncloud", "towncloud-agenda-html", "TownCloud public agenda detail HTML"),
    ("digital-towpath", "digital-towpath-detail-html", "Digital Towpath public meeting detail HTML"),
    ("clerkbase", "clerkbase-document-html", "ClerkBase public meeting document HTML"),
    ("first-party", "public-meeting-ics", "Municipality-published iCalendar meeting feed"),
    ("wistia", "wistia-media-json", "Wistia public media JSON"),
    ("boardable", "boardable-public-meeting-html", "Boardable Public Site meeting detail HTML"),
    ("gworks", "gworks-frontdesk-json", "gWorks FrontDesk city meetings JSON"),
    ("boarddocs", "boarddocs-print-pdf", "Diligent BoardDocs printed agenda PDF"),
    ("tyler-meeting-manager", "tyler-public-calendar-json", "Tyler Meeting Manager saved public calendar JSON"),
)


def source_formats() -> list[dict]:
    return [
        {"connector": connector, "input_format": input_format, "label": label}
        for connector, input_format, label in SOURCE_FORMATS
    ]


def source_namespace(connector: str, source) -> str:
    """Keep the tenant identity stable across pages of the same public source."""
    site = f"//{source.netloc.lower()}"
    query = parse_qs(source.query)
    if connector == "boardbook":
        return site + source.path.rstrip("/")
    if connector == "destiny-agendaquick":
        return site + "/" + query.get("id", [source.path.lstrip("/").partition("/")[0]])[0]
    if connector == "town-hall-streams":
        location = query.get("location_id") or query.get("id", [""])
        return "//townhallstreams.com?" + urlencode({"location_id": location[0]})
    if connector == "telvue":
        return "//telvue.com/" + "/".join(source.path.strip("/").split("/")[:2])
    if connector == "champ":
        return "//champds.com/" + source.path.lstrip("/").partition("/")[0]
    if connector == "onbase":
        return site + "/" + source.path.lstrip("/").partition("/")[0].lower()
    if connector == "laserfiche-weblink":
        if source.hostname == "api.laserfiche.com":
            match = re.match(r"/repository/v2/Repositories/([A-Za-z0-9_-]+)(?:/|$)", source.path)
            if match:
                return site + "/repository/v2/Repositories/" + match[1]
        path = re.split(r"/(?:\d+/fol|browse\.aspx)", source.path, maxsplit=1, flags=re.I)[0]
        return site + path.rstrip("/").lower()
    if connector == "towncloud":
        return site + "/" + "/".join(source.path.strip("/").split("/")[:2])
    if connector == "boardable":
        return site + "/" + source.path.lstrip("/").partition("/")[0]
    if connector in {"first-party", "gworks"}:
        return site + source.path.rstrip("/")
    if connector == "simbli":
        district = query.get("S", [""])[0]
        return site + "?" + urlencode({"S": district}) if district else site + source.path
    if connector == "legistar" and source.hostname == "webapi.legistar.com":
        return site + "/" + "/".join(source.path.strip("/").split("/")[:2])
    return site


def preview_export(
    connector: str, source_url: str, content: bytes, *, input_format: str = "meeting-export"
) -> dict:
    """Normalize a saved source response without opening any URLs."""
    try:
        source = urlsplit(source_url)
        valid_source = (
            source.scheme in {"http", "https"} and source.hostname and source.username is None
        )
    except ValueError:
        valid_source = False
    if not valid_source:
        raise ImportInputError("Enter the original meeting or publishing-site URL.")
    if len(content) > MAX_INPUT_BYTES:
        raise ImportInputError("The export is too large. Select a smaller export and retry.")
    connector = connector.strip().lower()
    if input_format == "meeting-export":
        meetings = read_meeting_export(connector, content)
    else:
        reader = PORTAL_READERS.get((connector, input_format))
        if reader is None:
            raise ImportInputError("Select a supported input format for this source.")
        meetings = reader(source_url, content)
    return {
        "version": CONTRACT_VERSION,
        "source": {
            "connector": connector,
            "url": source_url,
            "namespace": source_namespace(connector, source),
            "format": input_format,
            "sha256": hashlib.sha256(content).hexdigest(),
        },
        "meetings": meetings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize a local meeting export as JSON.")
    parser.add_argument("connector")
    parser.add_argument("source_url")
    parser.add_argument("export", nargs="?", default="-", help="Path to a saved source response, or - for standard input")
    parser.add_argument("--format", default="meeting-export", dest="input_format")
    parser.add_argument("--fetch", action="store_true", help="Read the specified public URL")
    options = parser.parse_args()
    try:
        source_url = options.source_url
        if options.fetch:
            from civic_data_connectors.fetch import fetch_public
            from civic_data_connectors.compat import ImportInputError as FetchInputError

            try:
                source_url, content, _ = fetch_public(source_url, byte_limit=MAX_INPUT_BYTES)
            except FetchInputError as error:
                raise ImportInputError(str(error)) from error
        elif options.export == "-":
            content = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with Path(options.export).open("rb") as stream:
                content = stream.read(MAX_INPUT_BYTES + 1)
        result = preview_export(
            options.connector, source_url, content, input_format=options.input_format
        )
    except (ImportInputError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
