"""Resolve an observed public Agenda/Minutes page's supplied download link."""
from __future__ import annotations

import hashlib
import re
from time import monotonic
from urllib.parse import parse_qs, urljoin, urlsplit

from ..compat import LinkList
from .contracts import _origin


def resolve_document(url, transport, bounds, context, deadline):
    parts = urlsplit(url)
    match = re.fullmatch(r"/Public/(Agenda|Minutes)/([0-9]+)", parts.path, re.I)
    query = parse_qs(parts.query, keep_blank_values=True)
    if (parts.scheme != "https" or parts.hostname != "meetings.boardbook.org" or match is None
            or set(query) != {"meeting"} or len(query["meeting"]) != 1
            or re.fullmatch(r"[0-9]+", query["meeting"][0]) is None):
        return url, None
    if context.check_cancelled():
        raise ValueError("Document resolution was cancelled.")
    response = transport.request(url, byte_limit=bounds.parser_bytes,
        deadline_seconds=max(.001, deadline - monotonic()), allowed_origins=(_origin(url),),
        allow_redirects=False)
    if (response.status != 200 or response.url != url or len(response.content) > bounds.parser_bytes
            or monotonic() >= deadline):
        raise ValueError("The supplied BoardBook document page exceeded its verified route/bounds.")
    if response.content_type.split(";", 1)[0].lower() != "text/html":
        raise ValueError("The public BoardBook document page is not the observed HTML format.")
    parser = LinkList()
    parser.feed(response.content.decode("utf-8-sig"))
    targets = set()
    for link in parser.links:
        candidate = urljoin(url, link["href"])
        target = urlsplit(candidate)
        if (_origin(candidate) == _origin(url) and not target.fragment and not target.username
                and target.path.lower() == f"/public/download{match[1]}/{match[2]}".lower()
                and parse_qs(target.query, keep_blank_values=True) == query):
            targets.add(candidate)
    if len(targets) != 1:
        raise ValueError("The public BoardBook page did not supply one matching download link.")
    return targets.pop(), {"kind": "supplied_public_download_link", "page_sha256": hashlib.sha256(response.content).hexdigest(),
        "page_byte_length": len(response.content)}
