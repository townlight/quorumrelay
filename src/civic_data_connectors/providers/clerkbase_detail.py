"""Retain supplied published ClerkBase document text without interpreting minutes."""

import base64
from copy import deepcopy
from hashlib import sha256

from ..engine import canonical_hash
from .escribe_detail import Node, Page

_EXCLUDED = {"script", "style", "nav", "header", "footer", "form", "noscript"}


def _text(node):
    if node.tag in _EXCLUDED or "hidden" in node.attrs:
        return ""
    return " ".join(" ".join(_text(c) if isinstance(c, Node) else c for c in node.children).split())


def _included(node):
    while node is not None:
        if node.tag in _EXCLUDED or "hidden" in node.attrs:
            return False
        node = node.parent
    return True


def enrich_bundle(bundle):
    result = deepcopy(bundle)
    capture = result.get("capture", {})
    if capture.get("input_format") != "clerkbase-document-html":
        return result
    raw = base64.b64decode(capture["content_base64"], validate=True)
    digest = sha256(raw).hexdigest()
    if digest != capture["sha256"]:
        raise ValueError("The ClerkBase capture bytes disagree with their digest.")
    page = Page()
    page.feed(raw.decode("utf-8-sig", errors="replace"))
    bodies = [n for n in page.root.walk() if n.tag == "body"]
    if len(bodies) != 1:
        raise ValueError("The supplied ClerkBase document has no unique body.")
    body = bodies[0]
    paragraphs = [{"text": _text(n), "attributes": deepcopy(n.attrs)}
                  for n in body.walk() if n.tag == "p" and _included(n) and _text(n)]
    text = _text(body)
    for record in result["records"]:
        if record["capture_sha256"] != digest or record["source_url"] != capture["source_url"]:
            raise ValueError("The supplied ClerkBase document disagrees with its capture binding.")
        normalized = record["normalized"]
        normalized.update(document_text=text, document_paragraphs=paragraphs,
                          document_text_scope="supplied_static_html_body_no_script_or_css_execution")
        record["text"] = [s for s in record.get("text", [])
                          if s.get("provenance", {}).get("method") != "clerkbase_document_body"]
        if text:
            record["text"].append({"field": "document_text", "text": text,
                "citation_url": capture["source_url"], "completeness": "supplied_html_body_only",
                "provenance": {"method": "clerkbase_document_body", "capture_sha256": digest,
                               "scope": "body_without_navigation_forms_scripts_styles"}})
        record["normalized_sha256"] = canonical_hash(normalized)
    return result
