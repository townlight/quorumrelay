"""CloudCast's vendor-documented public MRSS, separate from Connect account APIs."""
from email.utils import parsedate_to_datetime
import re
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

from .identification import validate_url

FORMAT = "telvue-cloudcast-mrss-xml"
MEDIA = "{http://search.yahoo.com/mrss/}"
CLOUD = "{http://cloudcast.telvue.com/mrss_cloudcast/}"


def listing_rows(source, content):
    parsed = urlsplit(source.url)
    match = re.fullmatch(r"/mrss/([A-Za-z0-9_-]+)", parsed.path)
    query = parse_qs(parsed.query, keep_blank_values=True)
    validate_url(source.url)
    if (parsed.scheme != "https" or parsed.hostname != "connect.telvue.com" or not match
            or parsed.port not in (None, 443) or parsed.fragment or set(query) - {"recent"}
            or (query and (len(query["recent"]) != 1 or not query["recent"][0].isdigit()
                          or int(query["recent"][0]) < 1))):
        raise ValueError("CloudCast MRSS requires its explicit HTTPS player feed URL and optional positive recent.")
    text = content.decode("utf-8-sig")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)\b", text, re.I):
        raise ValueError("MRSS document/entity declarations are prohibited.")
    root = ET.fromstring(text)
    stack, count = [(root, 0)], 0
    while stack:
        element, depth = stack.pop()
        count += 1
        if depth > 64 or count > 100000:
            raise ValueError("MRSS exceeds structural bounds.")
        stack.extend((child, depth + 1) for child in element)
    if root.tag != "rss" or root.get("version") != "2.0" or len(root.findall("channel")) != 1:
        raise ValueError("Expected one RSS 2.0 CloudCast channel.")
    rows, seen = [], set()
    for item in root.find("channel").findall("item"):
        identity = item.findtext(CLOUD + "id")
        link = item.findtext("link")
        expected = f"https://videoplayer.telvue.com/player/{match[1]}/media/{identity}"
        if not identity or not identity.isascii() or not identity.isdigit() or link != expected:
            raise ValueError("CloudCast item identity must match the supplied player/media citation.")
        if identity in seen:
            raise ValueError("Duplicate CloudCast media identity in feed.")
        seen.add(identity)
        recordings = []
        for media in item.findall(".//" + MEDIA + "content"):
            url = media.get("url")
            validate_url(url)
            if urlsplit(url).scheme != "https":
                raise ValueError("Supplied CloudCast media must use HTTPS.")
            value = {"url": url}
            for key in ("lang", "type", "medium"):
                if media.get(key) is not None:
                    value[{"lang": "language"}.get(key, key)] = media.get(key)
            if media.get("duration") is not None:
                duration = media.get("duration")
                if not duration.isascii() or not duration.isdigit():
                    raise ValueError("CloudCast duration must be nonnegative integer seconds.")
                value["duration_seconds"] = int(duration)
            recordings.append(value)
        normalized = {"external_id": identity, "url": link, "title": item.findtext("title"),
                      "description": item.findtext(MEDIA + "description"), "recordings": recordings,
                      "program": item.findtext(CLOUD + "program"), "episode": item.findtext(CLOUD + "episode"),
                      "summary": item.findtext(CLOUD + "summary"),
                      "categories": [node.text for node in item.findall(MEDIA + "category")],
                      "source_pub_date": item.findtext("pubDate")}
        if normalized["source_pub_date"]:
            published = parsedate_to_datetime(normalized["source_pub_date"])
            if published.tzinfo is None:
                raise ValueError("CloudCast publication time must supply its offset.")
            normalized["published_at"] = published.isoformat()
        # Publication time and program names do not establish meeting date/body.
        rows.append((normalized, {"item_xml": ET.tostring(item, encoding="unicode")}, "recording"))
    return rows
