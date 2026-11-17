"""Resolve the exact public Boardable document viewer's declared download route."""

import base64
import hashlib
import json
import re
from time import monotonic
from urllib.parse import urlsplit

from .contracts import _origin


def resolve_document(source, url, transport, bounds, context, deadline):
    source_path = urlsplit(source.url)
    source_match = re.fullmatch(r"/([\w-]+)/meetings/([\w-]+)/?", source_path.path)
    target = urlsplit(url)
    match = re.fullmatch(r"/([\w-]+)/public-site-data/meetings/([\w-]+)/documents/([\w-]+)/view", target.path)
    if (source_path.scheme != "https" or source_path.hostname != "site.boardable.com"
            or source_match is None or target.scheme != "https" or target.hostname != "app.boardable.com"
            or target.port not in {None, 443} or target.query or target.fragment or match is None
            or match.group(1, 2) != source_match.group(1, 2)):
        raise ValueError("Boardable documents must belong to the exact captured organization and meeting.")
    if context.check_cancelled() or monotonic() >= deadline:
        raise ValueError("The public document resolution was cancelled or expired.")
    response = transport.request(url, byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes),
        deadline_seconds=max(0.001, deadline - monotonic()), allowed_origins=(_origin(url),),
        allow_redirects=False)
    if (response.status != 200 or response.url != url
            or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)
            or monotonic() >= deadline):
        raise ValueError("The exact public document viewer was not returned within its bounds.")
    page = response.content.decode("utf-8-sig", errors="strict")
    # Decode only bounded JSON-compatible literals. Never evaluate page scripts.
    roots = re.findall(r"\breturn_url:\s*'([^'\r\n]{1,2048})'", page)
    attachments = re.findall(r"\battachment:\s*JSON\.parse\('([^'\r\n]+)'\)", page)
    if len(roots) != 1 or len(attachments) != 1:
        raise ValueError("The public viewer's declared document identity is unavailable or ambiguous.")
    root = json.loads('"' + roots[0].replace('"', '\\"') + '"')
    attachment = json.loads(json.loads('"' + attachments[0].replace('"', '\\"') + '"'))
    if (root != url.removesuffix("/view") or not isinstance(attachment, dict)
            or attachment.get("attachable_id") is None):
        raise ValueError("The public viewer does not identify the exact supplied document.")
    upload_type = attachment.get("attached_type")
    if upload_type != "computer" and not (upload_type == "document"
            and isinstance(attachment.get("document"), dict)
            and attachment["document"].get("upload_type") == "computer"):
        raise ValueError("No supported original-file download is declared for this document.")
    if not re.search(r"downloadUrl\s*\(\)\s*\{\s*return this\.return_url \+ '/download';\s*\}", page):
        raise ValueError("The public viewer's download mapping changed.")
    metadata = {"kind": "boardable_public_viewer_download", "viewer_capture": {
        "citation_url": url, "content_type": response.content_type,
        "byte_length": len(response.content), "sha256": hashlib.sha256(response.content).hexdigest(),
        "content_base64": base64.b64encode(response.content).decode("ascii")}}
    return root + "/download", metadata
