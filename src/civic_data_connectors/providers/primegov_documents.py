"""Resolve selected PrimeGov public search document routes without executing client code."""
import base64
import hashlib
import json
import math
from datetime import datetime, timezone
from time import monotonic
from urllib.parse import urlencode, urljoin

from .contracts import _origin
from .identification import validate_url


def _positive(value):
    return type(value) is int and 0 < value <= 9999999999999999999


def declared_document(source, raw, citation):
    identity, meeting, kind = raw.get("id"), raw.get("meetingId"), raw.get("type")
    if raw.get("info") != "Attachment" or not _positive(identity) or not _positive(meeting) or type(kind) is not int:
        return None
    if kind == 1:
        path = "/api/systemitemattachment/GetPublicPdfDownloadUrl/" + str(identity)
        label = "system_item_attachment"
    elif kind == 2:
        path = "/api/portal/DownloadSystemItemAttachedDocToBrowser/" + str(identity)
        label = "system_document"
    elif kind == 3:
        path = "/api/meetingSectionAttachment/DownloadPublicPdf?" + urlencode({"id": identity, "meetingId": meeting})
        label = "section_attachment"
    elif (kind == 4 and type(raw.get("compileOutputType")) in {int, float}
          and (type(raw["compileOutputType"]) is int or math.isfinite(raw["compileOutputType"]))
          and raw["compileOutputType"] != 3):
        path = "/api/Meeting/getcompiledfiledownloadurl?" + urlencode({"compiledFileId": identity})
        label = "compiled_document"
    else:
        return None
    return {"kind": label, "external_id": str(identity), "title": raw.get("title"),
        "url": _origin(source.url) + path, "citation_url": citation,
        "availability": "vendor_client_locator_not_fetched"}


def resolve_document(source, url, record, document, bounds, context, transport, deadline, allowed_origins, captures):
    raw, identity = record.get("original") or {}, record.get("identity") or {}
    parent = identity.get("parent") or {}
    meeting, item = raw.get("meetingId"), raw.get("id")
    citation = _origin(source.url) + "/Portal/Meeting?" + urlencode({"meetingId": meeting})
    expected = declared_document(source, raw, citation)
    legacy = dict(expected or {})
    if raw.get("type") == 2:
        legacy.pop("citation_url", None)
    external_id = str(item) if raw.get("type") == 2 else f"type:{raw.get('type')}:{item}"
    if (expected is None or document not in (expected, legacy) or url != expected["url"]
            or identity.get("record_type") != "document" or identity.get("external_id") != external_id
            or parent != {"provider": identity.get("provider"), "namespace": identity.get("namespace"),
                          "record_type": "meeting", "external_id": str(meeting)}
            or record.get("normalized", {}).get("url") != citation):
        raise ValueError("The selected document does not match its captured native meeting and type.")
    kind = raw["type"]
    resolver = kind in {1, 4}
    if bounds.max_pages < (2 if resolver else 1):
        raise ValueError("The selected document exceeds its request budget.")
    remaining = bounds.transfer_bytes

    def read(target, limit):
        if context.check_cancelled():
            raise InterruptedError()
        seconds = deadline - monotonic()
        if seconds <= 0 or limit <= 0:
            raise ValueError("The document exhausted its byte/deadline bounds.")
        allowed = allowed_origins(source, target)
        response = transport.request(target, byte_limit=limit, deadline_seconds=seconds,
                                     allowed_origins=allowed, allow_redirects=False)
        if (response.status != 200 or response.url != target or len(response.content) > limit
                or monotonic() >= deadline):
            raise ValueError("The selected document response did not match its bounded route.")
        return response

    if resolver:
        response = read(url, min(remaining, bounds.parser_bytes))
        remaining -= len(response.content)
        captures.append({"source_url": source.url, "retrieval_url": url,
            "input_format": "primegov-document-resolver-json", "captured_at": datetime.now(timezone.utc).isoformat(),
            "sha256": hashlib.sha256(response.content).hexdigest(), "byte_length": len(response.content),
            "content_type": response.content_type, "content_base64": base64.b64encode(response.content).decode("ascii")})
        target = json.loads(response.content)
        if not isinstance(target, str) or not target:
            raise ValueError("The vendor resolver did not return a URL string.")
        target = urljoin(source.url, target)
        validate_url(target)
        allowed_origins(source, target)
    else:
        target = url
    if context.check_cancelled():
        raise InterruptedError()
    response = read(target, remaining)
    if context.check_cancelled():
        raise InterruptedError()
    if kind == 4 and (response.content_type.split(";", 1)[0].strip().lower() in
                      {"text/html", "application/xhtml+xml"} or
                      response.content.lstrip().lower().startswith((b"<!doctype html", b"<html"))):
        raise ValueError("The compiled file route returned an HTML page, not a file.")
    if kind in {1, 3} and not response.content.startswith(b"%PDF-"):
        raise ValueError("The selected PDF route did not return PDF bytes.")
    return response, {"kind": "primegov_public_search_document", "document_type": kind,
                      "requests": 2 if resolver else 1, "catalog_complete": False}
