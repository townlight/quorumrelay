"""Supplied labeled fields in an existing Utah public notice detail capture."""

import base64
from copy import deepcopy
from hashlib import sha256
import re
from urllib.parse import urljoin, urlsplit

from ..engine import canonical_hash
from .escribe_detail import Node, Page


def _text(node):
    if node.tag in {"script", "style", "noscript"} or "hidden" in node.attrs:
        return ""
    return " ".join(" ".join(_text(c) if isinstance(c, Node) else c
                             for c in node.children).split())



def supplied_assets(page, url, notice_id):
    """Keep literal public notice asset locators; never infer a recording date."""
    origin = urlsplit(url)
    calendar, recordings = [], []

    def target(href, path):
        address = urljoin(url, href)
        parsed = urlsplit(address)
        return address if (parsed.scheme == origin.scheme == "https"
            and parsed.netloc == origin.netloc and not parsed.username
            and not parsed.query and not parsed.fragment
            and re.fullmatch(path, parsed.path)) else None

    def visible(node):
        while node is not None:
            if "hidden" in node.attrs or node.attrs.get("aria-hidden") == "true":
                return False
            node = node.parent
        return True

    for node in page.root.walk():
        if (node.tag == "a" and visible(node) and _text(node) == "Add Notice to Calendar"
                and node.parent is not None and "message" in node.parent.classes()):
            address = target(node.attrs.get("href", ""),
                rf"/pmn/sitemap/noticeical/{re.escape(notice_id)}\.ics")
            if address:
                value = {"kind": "calendar", "url": address, "title": _text(node)}
                if value not in calendar:
                    calendar.append(value)
        if node.tag != "table" or not visible(node):
            continue
        if not any(n.tag == "caption" and _text(n) == "Download Attachments" for n in node.children if isinstance(n, Node)):
            continue
        for row in node.walk():
            if row.tag != "tr" or not visible(row):
                continue
            cells = [n for n in row.children if isinstance(n, Node) and n.tag == "td"]
            if len(cells) != 3 or _text(cells[1]) != "Audio Recording":
                continue
            for link in cells[0].walk():
                if link.tag != "a" or not visible(link):
                    continue
                address = target(link.attrs.get("href", ""), r"/pmn/files/[0-9]+\.mp3")
                if address:
                    value = {"kind": "audio", "url": address, "title": _text(link),
                             "source_category": _text(cells[1])}
                    if value not in recordings:
                        recordings.append(value)
    return calendar, recordings


def enrich_bundle(bundle):
    result = deepcopy(bundle)
    capture = result["capture"]
    if capture["input_format"] != "utah-notice-html":
        return result
    url = capture["source_url"]
    origin = urlsplit(url)
    notice = re.fullmatch(r"/pmn/sitemap/notice/(\d+)\.html", origin.path)
    if not notice:
        return result
    content = base64.b64decode(capture["content_base64"], validate=True)
    digest = sha256(content).hexdigest()
    if digest != capture["sha256"]:
        raise ValueError("Utah notice capture hash mismatch.")
    page = Page()
    page.feed(content.decode("utf-8", errors="replace"))
    calendars, recordings = supplied_assets(page, url, notice[1])
    fields, nodes = {}, {}
    for node in page.root.walk():
        if node.tag != "dt" or not node.parent:
            continue
        siblings = node.parent.children
        following = next((n for n in siblings[siblings.index(node) + 1:]
                          if isinstance(n, Node)), None)
        if following is None or following.tag != "dd":
            continue
        label = _text(node)
        if label in fields:
            raise ValueError("Utah notice has ambiguous labeled fields.")
        nodes[label] = following
        fields[label] = {"text": _text(following), "attributes": dict(following.attrs),
                         "links": [dict(n.attrs) for n in following.walk()
                                   if n.tag == "a" and n.attrs.get("href")]}
    body = fields.get("Public Body", {})
    public_body = None
    links = body.get("links", [])
    if len(links) == 1:
        supplied = urljoin(url, links[0]["href"])
        parsed = urlsplit(supplied)
        match = re.fullmatch(r"/pmn/sitemap/publicbody/(\d+)\.html", parsed.path)
        if (match and parsed.scheme == origin.scheme == "https" and parsed.netloc == origin.netloc
                and not parsed.query and not parsed.fragment and not parsed.username):
            public_body = {"external_id": match[1], "url": supplied, "title": body["text"]}
    for record in result["records"]:
        if (record["identity"]["external_id"] != notice[1] or record["source_url"] != url
                or record["capture_sha256"] != digest):
            raise ValueError("Utah notice disagrees with its capture identity.")
        normalized = record["normalized"]
        normalized["supplied_notice_fields"] = deepcopy(fields)
        for calendar in calendars:
            if calendar not in normalized["documents"]:
                normalized["documents"].append(deepcopy(calendar))
        normalized["recordings"] = deepcopy(recordings)
        normalized["time_zone_status"] = "unknown"
        for label, key in (("Public Body", "body"), ("Entity", "entity"),
                           ("Government Type", "government_type"),
                           ("Notice Type(s)", "source_notice_types"),
                           ("Notice Posted On", "source_posted_on"),
                           ("Notice Last Edited On", "source_last_edited_on")):
            if label in fields:
                normalized[key] = fields[label]["text"]
        # Map only address prose, not map-link button labels.
        location = nodes.get("Meeting Location")
        if location is not None:
            normalized["location"] = " ".join(" ".join(
                _text(n) if isinstance(n, Node) and n.tag != "a" else n if isinstance(n, str) else ""
                for n in location.children).split())
        if public_body:
            normalized["public_body"] = deepcopy(public_body)
            relation = {"relation": "public_body", "value": deepcopy(public_body)}
            if relation not in record["relationships"]:
                record["relationships"].append(relation)
        record["normalized_sha256"] = canonical_hash(normalized)
    return result
