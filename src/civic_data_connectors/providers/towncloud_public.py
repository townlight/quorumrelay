"""Observed TownCloud published-agendas listing, including its SSR embedding."""

from copy import deepcopy
from datetime import datetime
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit

from .identification import validate_url

FORMAT = "towncloud-public-listing-json"
_PUBLISHED = re.compile(r"/go/([A-Za-z0-9_-]+)/published_agendas\.json\Z")


def _tenant(url):
    try:
        validate_url(url)
        parsed = urlsplit(url)
    except (TypeError, ValueError):
        return None
    match = _PUBLISHED.fullmatch(parsed.path)
    if (parsed.scheme != "https" or parsed.hostname != "towncloud.io" or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment or not match):
        return None
    return match.group(1)


class _Embedded(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.url = None
        self.parts = None
        self.results = []

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "script" and fields.get("type") == "application/json":
            url = fields.get("sveltekit:data-url", "")
            if _tenant(url):
                self.url, self.parts = url, []

    def handle_data(self, data):
        if self.parts is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.parts is not None:
            self.results.append((self.url, "".join(self.parts)))
            self.url, self.parts = None, None


def listing_rows(source, content):
    """Return mapped rows and original unknown fields; no paging is inferred."""
    text = content.decode("utf-8-sig")
    tenant = _tenant(source.url)
    if tenant:
        rows = json.loads(text)
    else:
        parser = _Embedded()
        parser.feed(text)
        if len(parser.results) != 1:
            raise ValueError("Expected one supplied TownCloud published-agendas response.")
        url, encoded = parser.results[0]
        tenant = _tenant(url)
        wrapper = json.loads(encoded)
        if not isinstance(wrapper, dict) or wrapper.get("status") != 200 or not isinstance(wrapper.get("body"), str):
            raise ValueError("The supplied TownCloud listing response was not successful.")
        rows = json.loads(wrapper["body"])
    if not isinstance(rows, list):
        raise ValueError("The TownCloud published-agendas response must be an array.")
    result = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        link = raw.get("agendaRead")
        try:
            validate_url(link)
            parsed = urlsplit(link)
        except (TypeError, ValueError):
            continue
        identity = re.fullmatch(rf"/go/{re.escape(tenant)}/agendas/([0-9]+)/?", parsed.path)
        title, day, clock = raw.get("template"), raw.get("date"), raw.get("time")
        if (parsed.scheme != "https" or parsed.hostname != "towncloud.io" or parsed.port not in (None, 443)
                or parsed.query or parsed.fragment or not identity or not isinstance(title, str) or not title.strip()
                or not isinstance(day, str) or not isinstance(clock, str)):
            continue
        try:
            start = datetime.strptime(f"{day} {clock}", "%m/%d/%Y %I:%M %p")
        except ValueError:
            continue
        documents = []
        for field, kind in (("agendaDownload", "agenda"), ("minutesDownload", "minutes"),
                            ("agendaPacketDownload", "packet"), ("agendaPdfPacketDownload", "packet")):
            value = raw.get(field)
            if not isinstance(value, str) or not value:
                continue
            try:
                validate_url(value)
                doc = urlsplit(value)
            except ValueError:
                continue
            if (doc.scheme == "https" and doc.hostname == "towncloud.io" and doc.port in (None, 443)
                    and not doc.query and not doc.fragment
                    and doc.path.startswith(f"/go/{tenant}/agendas/{identity.group(1)}/")
                    and all(part not in {".", ".."} for part in doc.path.split("/"))
                    and "%" not in doc.path):
                documents.append({"kind": kind, "url": value})
        normalized = {"external_id": identity.group(1), "title": title.strip(),
                      "meeting_date": start.date().isoformat(), "source_start": start.isoformat(),
                      "time_zone_status": "unknown", "url": link, "documents": documents,
                      "recordings": [], "agenda_items_availability": "unverified"}
        result.setdefault(identity.group(1), (normalized, deepcopy(raw), "meeting"))
    if rows and not result:
        raise ValueError("No dated TownCloud published agenda rows with valid identities were found.")
    return list(result.values())

