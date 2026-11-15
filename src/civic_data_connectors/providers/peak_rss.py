"""Selected Peak document-publication feeds, separate from meeting identities/dates."""
from email.utils import parsedate_to_datetime
import re
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID
import xml.etree.ElementTree as ET

from .contracts import _origin
from .identification import validate_url
from .native import make_bundle

FORMAT = "peak-publication-rss-xml"
SUPPLEMENT = "{https://www.granicus.com/schema/rss-supplements}"


def source_context(source):
    validate_url(source.url)
    parsed = urlsplit(source.url)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    values = dict(pairs)
    if (source.provider != "peak" or parsed.scheme != "https"
            or not (parsed.hostname or "").endswith(".granicus.com") or parsed.port not in {None, 443}
            or parsed.path != "/ViewPublisherRSS.php" or parsed.fragment or len(pairs) != 2
            or set(values) != {"view_id", "mode"} or values["mode"] not in {"agendas", "minutes"}
            or re.fullmatch(r"[1-9][0-9]{0,18}", values["view_id"]) is None):
        raise ValueError("Use the exact supplied Peak agenda/minutes feed and positive view ID.")
    return values


def parse_bundle(source, namespace, content):
    context = source_context(source)
    text = content.decode("utf-8-sig", errors="strict")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)\b", text, re.I):
        raise ValueError("Feed document/entity declarations are prohibited.")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise ValueError("The publication feed is not well-formed XML.") from None
    stack, count = [(root, 0)], 0
    while stack:
        element, depth = stack.pop()
        count += 1
        if depth > 64 or count > 100000:
            raise ValueError("The feed exceeds defensive structural bounds.")
        stack.extend((child, depth+1) for child in element)
    if root.tag != "rss" or root.get("version") != "2.0" or len(root.findall("channel")) != 1:
        raise ValueError("Expected one RSS2.0 publication channel.")
    channel = root.find("channel")

    def one(parent, name, *, optional=False):
        matches = parent.findall(name)
        if not matches and optional:
            return None
        if len(matches) != 1:
            raise ValueError("Publication identity and source fields must be unique.")
        return matches[0]

    if one(channel, SUPPLEMENT+"sourceURL").text != source.url:
        raise ValueError("The feed does not declare the exact configured source.")
    channel_title = one(channel, "title").text
    if not channel_title:
        raise ValueError("The publication channel title is missing.")
    listing = one(channel, "link").text
    parsed = urlsplit(listing or "")
    if (_origin(listing or "") != _origin(source.url) or parsed.path != "/ViewPublisher.php"
            or parsed.fragment or parse_qsl(parsed.query, keep_blank_values=True) != [("view_id", context["view_id"])]):
        raise ValueError("The feed channel left its configured publisher view.")
    rows, seen = [], set()
    for item in channel.findall("item"):
        # Only the empty Minutes response is observed; do not invent its item schema.
        if context["mode"] != "agendas":
            raise ValueError("Nonempty Minutes item binding is not established by the saved source.")
        guid = one(item, "guid")
        identity = guid.text
        if (not identity or guid.get("isPermaLink") != "false" or str(UUID(identity)) != identity
                or identity in seen):
            raise ValueError("Publication GUIDs must be native, unique and non-permalink identifiers.")
        seen.add(identity)
        link, title = one(item, "link").text, one(item, "title").text
        validate_url(link)
        parsed = urlsplit(link)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        values = dict(pairs)
        if (not title or _origin(link) != _origin(source.url) or parsed.fragment
                or parsed.path != "/AgendaViewer.php" or len(pairs) != 2
                or set(values) != {"view_id", "event_id"} or values["view_id"] != context["view_id"]
                or re.fullmatch(r"[1-9][0-9]{0,18}", values["event_id"]) is None):
            raise ValueError("The agenda publication locator left its native view/event binding.")
        published = one(item, "pubDate").text
        if parsedate_to_datetime(published).utcoffset() is None:
            raise ValueError("Publication time requires its supplied offset; it is not a meeting date.")
        parts = one(item, SUPPLEMENT+"pubDateParts", optional=True)
        description = one(item, "description", optional=True)
        normalized = {"external_id": identity, "title": title, "url": link,
            "source_published": published, "source_publication_parts": dict(parts.attrib) if parts is not None else None,
            "source_notice_html": description.text if description is not None else None,
            "source_view_id": context["view_id"], "source_event_id": values["event_id"],
            "document_publication_mode": context["mode"], "meeting_identity": "not_established",
            "meeting_date_availability": "not_mapped_from_publication_time_or_title",
            "time_zone_status": "unknown", "documents": [{"kind": "agenda", "url": link,
                "availability": "supplied_viewer_not_binary"}]}
        rows.append((normalized, {"item_xml": ET.tostring(item, encoding="unicode"),
            "channel_title": channel_title, "channel_link": listing}, "document_publication"))
    return make_bundle(source, namespace, content, FORMAT, rows)
