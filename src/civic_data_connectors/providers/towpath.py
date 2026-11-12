"""Digital Towpath's supplied dated meeting links and Other Years links."""

from datetime import datetime
from html.parser import HTMLParser
import re
from urllib.parse import quote, urljoin, urlsplit

from ..compat import LinkList
from .contracts import _origin
from .identification import validate_url
from .native import make_bundle

FORMAT = "digital-towpath-listing-html"


def controls(content):
    class Years(HTMLParser):
        values = []

        def handle_starttag(self, tag, attrs):
            fields = dict(attrs)
            if tag == "a" and "dtp-meeting-year" in fields.get("class", "").split() and fields.get("href"):
                url = quote(fields["href"], safe="/:?=&%")
                parts = urlsplit(url)
                match = re.fullmatch(r"/meetings/meetings/[^/]+/(20[0-9]{2})", parts.path)
                if match and not parts.query:
                    validate_url(url)
                    value = {"url": url, "year": match[1]}
                    if value not in self.values:
                        self.values.append(value)

    parser = Years()
    parser.values = []
    parser.feed(content.decode("utf-8", errors="replace"))
    if len(parser.values) > 1000:
        raise ValueError("Too many supplied Digital Towpath year links.")
    return parser.values


def listing_bundle(source, namespace, content):
    page = content.decode("utf-8", errors="replace")
    if "dtp-meetings-list" not in page:
        raise ValueError("The Digital Towpath public meeting listing is unavailable.")
    links = LinkList()
    links.feed(page)
    rows = []
    seen = set()
    for link in links.links:
        if link["title"] != "Link to meeting details page":
            continue
        url = urljoin(source.url, link["href"])
        validate_url(url)
        parts = urlsplit(url)
        if (
            _origin(url) != _origin(source.url)
            or parts.query
            or parts.fragment
            or not re.fullmatch(r"/meetings/(?:detail/[0-9]+|[A-Za-z0-9_-]+)", parts.path)
        ):
            continue
        text = " ".join(link["text"].split())
        date, separator, title = text.partition(": ")
        if not separator or not title:
            continue
        try:
            day = datetime.strptime(date, "%B %d, %Y").date().isoformat()
        except ValueError:
            continue
        native = re.fullmatch(r"/meetings/detail/([0-9]+)", parts.path)
        identity = native[1] if native else "url:" + url
        if identity in seen:
            continue
        seen.add(identity)
        normalized = {
            "external_id": identity,
            "title": title,
            "meeting_date": day,
            "url": url,
            "documents": [],
            "recordings": [],
            "time_zone_status": "unknown",
            "agenda_items_availability": "unverified",
            "documents_availability": "detail_not_fetched",
        }
        rows.append((normalized, dict(link), "meeting"))
    bundle = make_bundle(source, namespace, content, FORMAT, rows)
    for record in bundle["records"]:
        if record["identity"]["external_id"].startswith("url:"):
            record["identity"].update(
                derivation="supplied_detail_url",
                stability="Public detail URL identity; no numeric meeting ID supplied; changes if that URL changes.",
            )
    return bundle
