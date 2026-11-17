"""Map the supplied Town Hall Streams event page and declared HLS locator."""

from datetime import datetime
import json
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from .escribe_detail import Page
from .native import make_bundle

FORMAT = "town-hall-streams-event-html"


def parse_bundle(source, namespace, content):
    url = urlsplit(source.url)
    query = parse_qs(url.query)
    if (url.scheme != "https" or url.hostname not in {"townhallstreams.com", "www.townhallstreams.com"}
            or url.port not in {None, 443} or url.path != "/stream.php"
            or set(query) != {"location_id", "id"}
            or any(len(query[key]) != 1 or not re.fullmatch(r"[1-9][0-9]*", query[key][0])
                   for key in query)):
        raise ValueError("Use the supplied public Town Hall Streams location/event URL.")
    location, event = query["location_id"][0], query["id"][0]
    html = content.decode("utf-8-sig", errors="strict")
    if set(re.findall(r"location_id=([0-9]+)&id=([0-9]+)", html)) != {(location, event)}:
        raise ValueError("The player page does not identify the exact requested location/event.")
    page = Page()
    page.feed(html)
    headings = []
    for node in page.root.walk():
        if node.tag != "p":
            continue
        links = [urlsplit(urljoin(source.url, n.attrs["href"])) for n in node.walk()
                 if n.tag == "a" and n.attrs.get("href")]
        if not any(n.scheme == "https" and n.netloc == url.netloc and n.path == "/town.php"
                   and parse_qs(n.query) == {"id": [location]} for n in links):
            continue
        spans = [n.text() for n in node.walk() if n.tag == "span"]
        title = " ".join(" ".join(c for c in node.children if isinstance(c, str)).split()).strip(" |")
        if len(spans) == 1 and title:
            headings.append((title, spans[0]))
    if len(headings) != 1:
        raise ValueError("The event page does not supply one location-bound title/date header.")
    title, time_text = headings[0]
    start_text, _, end_text = time_text.partition(" - ")
    start = datetime.strptime(start_text, "%b, %d %Y %I:%M %p")
    # Decode a JSON string literal only; no page JavaScript is evaluated.
    declarations = re.findall(r'\bvar\s+originalFile\s*=\s*("(?:[^"\\]|\\.)*")\s*;', html)
    playback = None
    if len(declarations) == 1 and re.search(
            r'\bthsPlayableHlsUrl\(originalFile\)', html) and re.search(
            r'\bjwplayer\("myElement"\)\.setup\(\{\s*file:\s*file\s*,', html):
        value = json.loads(declarations[0])
        media = urlsplit(value)
        if (media.scheme == "https" and media.netloc == "cdn.townhallstreams.com"
                and not media.query and not media.fragment and media.path.startswith("/vod/")
                and media.path.endswith("/playlist.m3u8")):
            playback = value
    recording = {"url": source.url, "kind": "public_event_player",
                 "media_availability": "declared_hls_locator" if playback else "no_verified_locator",
                 "captions_availability": "not_fetched_or_parsed"}
    if playback:
        recording.update(playback_url=playback, playback_type="application/vnd.apple.mpegurl",
                         playback_provenance="captured_player_originalFile_declaration",
                         media_bytes_verified=False)
    normalized = {"external_id": event, "title": title, "url": source.url,
        "meeting_date": start.date().isoformat(), "scheduled_start": start.isoformat(),
        "time_zone_status": "unknown", "source_time": time_text,
        "source_end_time": end_text or None, "location_id": location,
        "recordings": [recording], "documents": []}
    return make_bundle(source, namespace, content, FORMAT,
        [(normalized, {"html": html, "event_id": event, "location_id": location}, "meeting")])
