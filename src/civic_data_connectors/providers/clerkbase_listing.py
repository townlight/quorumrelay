"""Current public ClerkBase tree controls; supplied document links only."""
from copy import deepcopy
from html import escape
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from .clerkbase_search import listing_rows, mark_supplied_url_identities, _site_source, _AgendaTree, _document_url
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


def parent_document(source, content, child_url):
    allowed = controls(source, content)
    if {"url": child_url} not in allowed:
        raise ValueError("The agenda tree is not declared by its parent.")
    links = _AgendaTree()
    links.feed(content.decode("utf-8-sig", errors="strict"))
    values = [_document_url(source, link["attrs"]["href"]) for link in links.links
              if link["attrs"].get("href") and link["attrs"].get("data-toc-url")
              and urljoin(_origin(source.url) + "/", link["attrs"]["data-toc-url"]) == child_url]
    if len(values) != 1:
        raise ValueError("The agenda tree lacks one matching parent document.")
    return values[0]


def listing_bundle(source, namespace, content, *, tree_url=None, expected_document_url=None):
    # A root containing advertised controls is a valid zero-document capture.
    # Tree responses must actually supply documents; blank/error HTML is not empty success.
    advertised = controls(source, content)
    links = _AgendaTree()
    links.feed(content.decode("utf-8-sig"))
    if advertised and not any(link["attrs"].get("href") for link in links.links):
        rows = []
    elif any(urlsplit(link["attrs"].get("href", "")).fragment for link in links.links):
        tree_path = parse_qs(urlsplit(tree_url or "").query, keep_blank_values=True).get("path", [])
        if tree_path != ["SouthKingstown_Docket,AGENDA,"] or expected_document_url is None:
            raise ValueError("The supplied fragment tree is not the evidenced agenda-node branch.")
        rows, seen, document_base = [], set(), None
        for link in links.links:
            attrs = link["attrs"]
            href = attrs.get("href")
            title = " ".join(" ".join(link["text"]).split()) or " ".join((attrs.get("title") or "").split())
            if not href or not title:
                continue
            target = urlsplit(href)
            if not target.fragment:
                markup = "<a " + " ".join(f'{escape(k)}="{escape(v or "", quote=True)}"' for k, v in attrs.items()) + ">" + escape(title) + "</a>"
                rows.extend(listing_rows(source, markup.encode("utf-8")))
                continue
            node = attrs.get("data-node-id", "")
            if (re.fullmatch(r"AGENDA_[1-9][0-9]*", node) is None
                    or attrs.get("data-path") != tree_path[0] + node + ","
                    or re.fullmatch(r"_CPA[1-9][0-9]*", target.fragment) is None):
                raise ValueError("The supplied agenda node does not match the evidenced branch.")
            base = _document_url(source, target._replace(fragment="").geturl())
            if base != expected_document_url or (document_base is not None and base != document_base):
                raise ValueError("The agenda nodes do not identify one supplied document.")
            document_base = base
            url = base + "#" + target.fragment
            if url in seen:
                continue
            seen.add(url)
            rows.append(({"external_id": url, "title": title, "url": url, "documents": [],
                          "recordings": [], "time_zone_status": "unknown",
                          "parent_identity_availability": "not_established"},
                         {"link_attributes": deepcopy(attrs), "link_text": title}, "agenda_item"))
        if not rows and not advertised:
            raise ValueError("The ClerkBase tree has no supplied document or agenda node links.")
    else:
        rows = listing_rows(source, content)
    bundle = mark_supplied_url_identities(make_bundle(source, namespace, content, FORMAT, rows))
    for record in bundle["records"]:
        if record["identity"]["record_type"] == "agenda_item":
            record["identity"]["stability"] = "Uses the exact supplied agenda-anchor URL; no independent native item identity is established."
    return bundle
