"""Current public ClerkBase tree controls; supplied document links only."""
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

from .clerkbase_search import listing_rows, mark_supplied_url_identities, _site_source, _AgendaTree
from .contracts import _origin
from .identification import validate_url
from .native import make_bundle

FORMAT = "clerkbase-public-tree-html"


def controls(source, content):
    site = _site_source(source)
    found = []

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            value = d.get("data-toc-url")
            if tag != "a" or "js-doc-view" not in d.get("class", "").split() or not value:
                return
            target = urljoin(_origin(source.url) + "/", value)
            validate_url(target)
            parts = urlsplit(target)
            query = parse_qs(parts.query, keep_blank_values=True)
            if (_origin(target) != _origin(source.url) or parts.path != "/toc/" + site
                    or parts.fragment or set(query) != {"path"} or len(query["path"]) != 1
                    or query["path"][0] != d.get("data-path")
                    or not query["path"][0].endswith(",")):
                raise ValueError("The supplied ClerkBase tree control left its public site.")
            if {"url": target} not in found:
                found.append({"url": target})

    Links(convert_charrefs=True).feed(content.decode("utf-8-sig"))
    return found


def listing_bundle(source, namespace, content):
    # A root containing advertised controls is a valid zero-document capture.
    # Tree responses must actually supply documents; blank/error HTML is not empty success.
    advertised = controls(source, content)
    links = _AgendaTree()
    links.feed(content.decode("utf-8-sig"))
    if advertised and not any(link["attrs"].get("href") for link in links.links):
        rows = []
    else:
        rows = listing_rows(source, content)
    return mark_supplied_url_identities(make_bundle(source, namespace, content, FORMAT, rows))
