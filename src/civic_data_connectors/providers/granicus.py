"""Observed ViewPublisher listing mapping, including meetings without attachments."""

from datetime import datetime
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from .. import compat
from ..engine import canonical_hash


def listing_rows(source, content):
    parser = compat.ViewPublisherRows()
    parser.feed(content.decode("utf-8", errors="replace"))
    rows = []
    seen = set()
    for raw in parser.rows:
        title = " ".join(raw.get("Name", "").lstrip("* ").split())
        value = " ".join(raw.get("Date", "").split()).split(" - ", 1)[0]
        # The public template includes a hidden numeric sort timestamp before
        # its visible date. The exact captured bytes remain the capture.
        value = re.sub(r"^\d+(?=[A-Za-z])", "", value).replace(".", "")
        if not title or not value:
            continue
        day = None
        for pattern in ("%B %d, %Y", "%b %d, %Y"):
            try:
                day = datetime.strptime(value, pattern).date().isoformat()
                break
            except ValueError:
                pass
        if day is None:
            continue
        player = urljoin(source.url, raw["player"]) if raw.get("player") else None
        if player and urlsplit(player).hostname != urlsplit(source.url).hostname:
            player = None
        identity = None
        for link in [player, raw.get("agenda"), raw.get("minutes")]:
            if link:
                candidate = parse_qs(urlsplit(link).query).get("clip_id", [""])[0]
                if candidate.isascii() and candidate.isdecimal():
                    identity = candidate
                    break
        if identity is None:
            identity = "derived:" + canonical_hash([source.url, day, title])[:32]
        if identity in seen:
            continue
        seen.add(identity)
        documents = [{"kind": kind, "url": urljoin(source.url, raw[kind])}
                     for kind in ("agenda", "minutes") if raw.get(kind)]
        recordings = [{"url": player}] if player else []
        if recordings:
            recordings[0].update({f"{kind}_url": urljoin(source.url, raw[kind])
                                  for kind in ("audio", "video") if raw.get(kind)})
        rows.append(({"external_id": identity, "title": title, "meeting_date": day,
                      "url": player or source.url, "documents": documents,
                      "recordings": recordings, "time_zone_status": "unknown",
                      "agenda_items_availability": "absent"}, raw, "meeting"))
    if not rows:
        raise ValueError("The configured ViewPublisher listing has no recognizable dated meeting rows.")
    return rows
