"""Rich associations from the existing captured TownCloud agenda format."""

import base64
from copy import deepcopy
from hashlib import sha256
import re
from urllib.parse import urlsplit

from ..engine import canonical_hash
from .escribe_detail import Node, Page
from .identification import validate_url


def _owner(node):
    while node is not None:
        if node.tag == "li" and node.classes() & {"item", "sub-item"}:
            return node
        node = node.parent
    return None


def _own_text(node, owner):
    if _owner(node) is not owner:
        return ""
    return " ".join(" ".join(_own_text(c, owner) if isinstance(c, Node) else c
                              for c in node.children).split())


def enrich_bundle(bundle):
    result = deepcopy(bundle)
    capture = result.get("capture", {})
    if capture.get("input_format") != "towncloud-agenda-html":
        return result
    content = base64.b64decode(capture["content_base64"], validate=True)
    digest = sha256(content).hexdigest()
    if digest != capture["sha256"] or len(content) != capture["byte_length"]:
        raise ValueError("The TownCloud agenda capture does not match its digest/size.")
    source = urlsplit(capture["source_url"])
    match = re.fullmatch(r"/go/([A-Za-z0-9_-]+)/agendas/([1-9][0-9]*)/?", source.path)
    if (source.scheme != "https" or source.hostname != "towncloud.io" or source.port not in {None, 443}
            or source.username or source.password or source.query or source.fragment or match is None):
        raise ValueError("The TownCloud agenda source does not bind a tenant and meeting.")
    tenant, meeting = match.groups()
    page = Page()
    page.feed(content.decode("utf-8-sig", errors="strict"))
    nodes = [n for n in page.root.walk() if n.tag == "li" and n.classes() & {"item", "sub-item"}]
    identities = {id(n): "capture:" + digest + ":item:" + str(i) for i, n in enumerate(nodes, 1)}
    items, documents, text = [], [], []
    known_documents = {}
    for position, node in enumerate(nodes, 1):
        title = next((n for n in node.children if isinstance(n, Node) and n.tag in {"h5", "h6"}), None)
        parent = _owner(node.parent)
        if title is None or not title.text() or ("sub-item" in node.classes() and parent is None):
            raise ValueError("The rendered TownCloud item title/hierarchy is ambiguous.")
        identity = identities[id(node)]
        item_documents = []
        for link in node.walk():
            if link.tag != "a" or _owner(link) is not node or not link.attrs.get("href"):
                continue
            url = link.attrs["href"]
            try:
                validate_url(url)
            except ValueError:
                continue
            target = urlsplit(url)
            doc = re.fullmatch(rf"/uploads/{re.escape(tenant)}/meetings/item_attachment/attachment/([1-9][0-9]*)/[^/]+", target.path)
            if (target.scheme != "https" or target.hostname != "towncloud-core-prod.s3.us-west-2.amazonaws.com"
                    or target.port not in {None, 443} or target.query or target.fragment or doc is None):
                continue
            if doc[1] in known_documents and known_documents[doc[1]] != url:
                raise ValueError("One TownCloud attachment ID has conflicting supplied URLs.")
            known_documents[doc[1]] = url
            value = {"kind": "supporting_document", "external_id": doc[1], "title": link.text(),
                     "url": url, "agenda_item_external_id": identity, "meeting_external_id": meeting,
                     "availability": "supplied_locator_not_fetched"}
            if value not in item_documents:
                item_documents.append(value)
                documents.append(value)
        contents = [n for n in node.children if isinstance(n, Node) and "item-contents-wrap" in n.classes()]
        description = " ".join(filter(None, (_own_text(n, node) for n in contents)))
        item = {"external_id": identity, "native_item_id": None, "meeting_external_id": meeting,
                "parent_item_external_id": identities[id(parent)] if parent else None,
                "title": title.text(), "sequence": position - 1, "source_display_position": position,
                "identity_derivation": "capture_local_display_position", "identity_stability": "one_exact_capture_only_not_native_item_id",
                "url": capture["source_url"], "description": description, "documents": item_documents,
                "source_attributes": node.attrs}
        items.append(item)
        if description:
            text.append({"field": "agenda_items." + identity + ".description", "text": description,
                         "citation_url": capture["source_url"], "completeness": "complete",
                         "provenance": {"method": "towncloud_rendered_item_content", "scope": "selected_rendered_item",
                                        "capture_sha256": digest}})
    for record in result["records"]:
        if record["identity"]["record_type"] != "meeting" or record["identity"]["external_id"] != meeting:
            raise ValueError("The rendered TownCloud agenda does not match its normalized meeting.")
        normalized = record["normalized"]
        normalized.update(agenda_items=items, agenda_items_availability="capture_local_rendered_positions",
                          time_zone_status="unknown")
        normalized["documents"] = [d for d in normalized.get("documents", []) if "agenda_item_external_id" not in d] + documents
        record["relationships"] = [r for r in record.get("relationships", []) if r.get("relation") not in {"agenda_item", "document"}]
        record["relationships"].extend({"relation": "agenda_item", "value": deepcopy(item)} for item in items)
        record["relationships"].extend({"relation": "document", "value": deepcopy(doc)} for doc in normalized["documents"])
        record["text"] = [s for s in record.get("text", []) if s.get("provenance", {}).get("method") != "towncloud_rendered_item_content"] + text
        record["normalized_sha256"] = canonical_hash(normalized)
    return result
