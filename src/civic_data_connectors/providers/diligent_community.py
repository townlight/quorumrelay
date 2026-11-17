"""Public Diligent Community reads. No administrative or write contract is inferred."""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import replace
from datetime import date
import hashlib
from html.parser import HTMLParser
import json
import re
from time import monotonic
from urllib.parse import urlencode, urljoin, urlsplit

from ..engine import canonical_hash, source_identity_key
from ..models import Error, OperationResult
from .contracts import PublicTransport
from .discovery import _checkpoint, _resume
from .identification import validate_url
from .native import make_bundle

PROVIDER = "diligent-community"
MEETINGS = "diligent-community-meetings-json"
DETAIL = "diligent-community-meeting-json"
DOCUMENTS = "diligent-community-documents-json"
FORMATS = (MEETINGS, DETAIL, DOCUMENTS)
SERVICE = "/Services/MeetingsService.svc/meetings"
HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.community\.diligentoneplatform\.com")
ID = re.compile(r"[1-9][0-9]{0,18}")
FILE = re.compile(r"/document/(?:[1-9][0-9]{0,18}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})/?")
# Named by the captured vendor page's packageDocumentTypes configuration.
KINDS = {1: "agenda", 4: "agenda_packet", 9: "minutes", 10: "minutes", 53: "minutes_adopted", 55: "minutes_adopted"}


def origin(source):
    validate_url(source.url)
    parsed = urlsplit(source.url)
    if source.provider != PROVIDER or parsed.scheme != "https" or not HOST.fullmatch(parsed.hostname or ""):
        raise ValueError("Use the configured HTTPS tenant.community.diligentoneplatform.com source.")
    result = "https://" + parsed.hostname
    if source.namespace is not None and source.namespace != "//" + parsed.hostname:
        raise ValueError("Diligent Community namespace does not match the tenant.")
    if source.options or source.input_format not in (None, *FORMATS):
        raise ValueError("Unknown Community options or input format.")
    return result


def number(value):
    if type(value) is not int or not ID.fullmatch(str(value)):
        raise ValueError("A positive native integer ID is required.")
    return str(value)


class PublicHTML(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.links, self.text, self.hidden = base, [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "a" and not self.hidden:
            href = dict(attrs).get("href", "")
            url = urljoin(self.base, href)
            parsed = urlsplit(url)
            if (parsed.scheme + "://" + parsed.netloc == self.base and FILE.fullmatch(parsed.path)
                    and not parsed.query and not parsed.fragment and url not in self.links):
                self.links.append(url)

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, text):
        if not self.hidden and text.strip():
            self.text.append(text.strip())


def bundle(source, content, fmt, expected=None):
    base = origin(source)
    namespace = "//" + urlsplit(base).hostname
    payload = json.loads(content)
    rows = []
    if fmt == MEETINGS:
        if not isinstance(payload, list):
            raise ValueError("Meeting listing must be an array.")
        seen = set()
        for raw in payload:
            if not isinstance(raw, dict):
                raise ValueError("Invalid meeting row.")
            identifier = number(raw.get("Id"))
            day = raw.get("MeetingDate")
            if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
                raise ValueError("Invalid meeting calendar day.")
            if identifier in seen or not isinstance(raw.get("Name"), str) or not raw["Name"].strip():
                raise ValueError("Duplicate meeting identity or missing title.")
            seen.add(identifier)
            if raw.get("Published") is not True:
                continue
            rows.append(({"external_id": identifier, "title": raw["Name"], "meeting_date": day,
                          "body": raw.get("MeetingTypeName"), "meeting_type_id": raw.get("MeetingTypeId"),
                          "body_source": "provider_label; migrated classifications not independently verified",
                          "source_time": raw.get("MeetingTime"), "time_zone_status": "unknown",
                          "location": raw.get("MeetingLocation"),
                          "url": base + "/Portal/MeetingInformation.aspx?Id=" + identifier,
                          "documents": [], "recordings": [], "agenda_items_availability": "not_in_listing"},
                         deepcopy(raw), "meeting"))
    elif fmt == DETAIL:
        if not isinstance(payload, dict):
            raise ValueError("Meeting detail must be an object.")
        identifier = number(payload.get("Id"))
        if (expected is not None and identifier != expected) or not isinstance(payload.get("Name"), str):
            raise ValueError("Meeting detail identity/title mismatch.")
        rows.append(({"external_id": identifier, "title": payload["Name"],
                      "location": payload.get("Location"), "source_time": payload.get("Time"),
                      "time_zone_status": "unknown", "meeting_date": None,
                      "url": base + "/Portal/MeetingInformation.aspx?Id=" + identifier,
                      "documents": [], "recordings": [], "agenda_items_availability": "not_in_detail"},
                     deepcopy(payload), "meeting"))
    elif fmt == DOCUMENTS:
        if not isinstance(payload, dict) or not isinstance(payload.get("Documents"), list):
            raise ValueError("Meeting documents require the Documents array wrapper.")
        seen = set()
        for raw in payload["Documents"]:
            if not isinstance(raw, dict):
                raise ValueError("Invalid document row.")
            identifier, meeting = number(raw.get("Id")), number(raw.get("MeetingId"))
            if expected is not None and meeting != expected:
                raise ValueError("Document belongs to a different meeting.")
            if identifier in seen:
                raise ValueError("Duplicate document identity.")
            seen.add(identifier)
            # Preserve exact response bytes in the capture, but never expose nonpublic bodies as records.
            if raw.get("IsPublic") is not True or type(raw.get("DocumentType")) is not int or raw["DocumentType"] not in KINDS:
                continue
            html = raw.get("Html") or ""
            if not isinstance(html, str):
                raise ValueError("Document HTML must be text.")
            parser = PublicHTML(base)
            parser.feed(html)
            url = base + "/document/" + identifier
            docs = [{"url": url, "kind": KINDS[raw["DocumentType"]], "external_id": identifier}]
            docs.extend({"url": link, "kind": "supporting_document"} for link in parser.links if link != url)
            rows.append(({"external_id": identifier, "title": raw.get("Name"),
                          "meeting_external_id": meeting, "kind": KINDS[raw["DocumentType"]],
                          "url": url, "documents": docs, "description": "\n".join(parser.text),
                          "source_html": html, "source_format": raw.get("Format"),
                          "time_zone_status": "unknown", "is_public": True}, deepcopy(raw), "document"))
    else:
        raise ValueError("Unknown Diligent Community saved format.")
    result = make_bundle(source, namespace, content, fmt, rows)
    for record in result["records"]:
        if fmt == DOCUMENTS:
            parent = {"provider": PROVIDER, "namespace": namespace, "record_type": "meeting",
                      "external_id": record["normalized"]["meeting_external_id"], "parent": None}
            record["identity"]["parent"] = parent
            record["relationships"].append({"relation": "meeting", "identity": parent})
            record["text"] = [{"text": record["normalized"]["description"], "citation_url": record["normalized"]["url"],
                               "kind": "published_document_text"}]
    return result


class DiligentCommunityConnector:
    provider = PROVIDER

    def __init__(self, transport=None, storage=None):
        self.transport, self.storage = transport or PublicTransport(), storage

    def capabilities(self):
        read = {"capability_status": "observed", "implementation_status": "implemented", "acceptance_status": "fixture_passed"}
        deferred = {"capability_status": "unverified", "implementation_status": "not_implemented",
                    "acceptance_status": "not_run", "details": "Write contracts unavailable; deferred per market demand."}
        return {"canonical_id": PROVIDER, "name": "Diligent Community", "aliases": [], "baseline_formats": [],
                "operations": {**{key: dict(read) for key in ("identify", "discover", "fetch", "parse", "local_search", "neutral_export")},
                               **{key: dict(deferred) for key in ("create", "update", "upload", "publish")}},
                "restrictions": ["Public reads only; bounded listing and selected meeting documents.",
                                 "No complete-catalog, native agenda-item, recording or timezone inference."],
                "evidence_note": "Boone County public vendor client and saved responses; docs/DILIGENT-COMMUNITY.md."}

    def identify(self, url):
        from ..models import Source
        try:
            base = origin(Source(PROVIDER, url))
        except ValueError as error:
            return OperationResult("failed", errors=(Error("unrecognized_source", str(error)),))
        return OperationResult("completed", {"provider": PROVIDER, "identified": True, "url": url,
                                             "namespace": "//" + urlsplit(base).hostname})

    def _read(self, url, base, bounds, context, deadline, budget, binary=False):
        if context.check_cancelled():
            raise ValueError("Operation cancelled.")
        remaining = bounds.transfer_bytes - budget["bytes"]
        if budget["pages"] >= bounds.max_pages or remaining <= 0 or monotonic() >= deadline:
            raise ValueError("Read budget exhausted.")
        limit = remaining if binary else min(remaining, bounds.parser_bytes)
        budget["pages"] += 1
        response = self.transport.request(url, byte_limit=limit, deadline_seconds=max(.001, deadline - monotonic()),
                                          allowed_origins=(base,), allow_redirects=False)
        budget["bytes"] += len(response.content)
        if (context.check_cancelled() or monotonic() >= deadline or response.status != 200
                or response.url != url or len(response.content) > limit):
            raise ValueError("Public response failed status, identity, cancellation or bounds checks.")
        return response

    def parse(self, source, content, input_format, bounds, context):
        return OperationResult("partial", bundle(source, content, input_format), coverage={
            "catalog_complete": False, "source_complete": False, "scope": "one saved public response"})

    def discover_content(self, engine, source, request, content, bounds, context):
        from .discovery import discover
        if source.input_format is None:
            request = {**request, "source": {**source.public_dict(), "input_format": MEETINGS}}
        return discover(engine, request, content, context, validated_namespace="//" + urlsplit(origin(source)).hostname)

    def fetch_content(self, engine, source, request, content, bounds, context):
        if any(key in request for key in ("external_id", "parent_id", "record_type")) or request.get("attachment") is not None:
            raise ValueError("Saved input cannot be combined with selected record or attachment retrieval.")
        selected = self.discover_content(engine, source, request, content, bounds, context)
        if selected.data and selected.data["bundles"]:
            return OperationResult(selected.status, selected.data["bundles"][0], selected.errors,
                                   selected.coverage, context.operation_id)
        return selected

    def discover(self, source, bounds, context):
        return self.discover_request(source, {}, bounds, context)

    def discover_request(self, source, request, bounds, context):
        base = origin(source)
        if request.get("record_types") not in (None, [], ["meeting"]):
            raise ValueError("Discovery lists meetings; fetch_related retrieves selected meeting documents.")
        if not bounds.date_from or not bounds.date_to:
            raise ValueError("Supply explicit date_from and date_to.")
        binding = canonical_hash({"source": source.public_dict(), "dates": [bounds.date_from, bounds.date_to], "scope": context.scope})
        offset, expected_hash = 0, None
        if bounds.checkpoint:
            tasks, _ = _resume(bounds.checkpoint, binding)
            if len(tasks) != 1 or set(tasks[0]) != {"offset", "sha256"}:
                raise ValueError("Invalid Community continuation.")
            offset, expected_hash = tasks[0]["offset"], tasks[0]["sha256"]
            if type(offset) is not int or offset < 0 or not isinstance(expected_hash, str):
                raise ValueError("Invalid Community continuation values.")
        deadline, budget = monotonic() + bounds.deadline_seconds, {"pages": 0, "bytes": 0}
        url = base + SERVICE + "?" + urlencode({"from": bounds.date_from, "to": bounds.date_to, "loadall": "false"})
        try:
            response = self._read(url, base, bounds, context, deadline, budget)
            result = bundle(source, response.content, MEETINGS)
            digest = result["capture"]["sha256"]
            if expected_hash is not None and expected_hash != digest:
                raise ValueError("Listing changed; restart without checkpoint.")
            rows = [r for r in result["records"] if bounds.date_from <= r["normalized"]["meeting_date"] <= bounds.date_to
                    and (not source.body or (r["normalized"].get("body") or "").casefold() == source.body.casefold())]
            if offset > len(rows):
                raise ValueError("Continuation is outside this listing.")
            end = min(len(rows), offset + bounds.max_records)
            result["records"] = rows[offset:end]
            result["compatibility"]["meetings"] = [deepcopy(r["normalized"]) for r in result["records"]]
            result["capture"]["retrieval_url"] = url
            if context.check_cancelled() or monotonic() >= deadline:
                raise ValueError("Operation interrupted during parsing.")
            checkpoint = _checkpoint(binding, [{"offset": end, "sha256": digest}], set()) if end < len(rows) else None
            return OperationResult("partial", {"source": source.public_dict(), "records": result["records"],
                "captures": [result["capture"]], "bundles": [result]}, coverage={"catalog_complete": False,
                "source_complete": False, "checkpoint": checkpoint, "truncated": end < len(rows), **budget,
                "scope": "date-bounded public listing; server completeness unverified; hash-bound local continuation"})
        except (ValueError, OSError) as error:
            return self._failed(context, error, budget)

    @staticmethod
    def _failed(context, error, budget):
        return OperationResult("cancelled" if context.check_cancelled() else "failed",
                               errors=(Error("community_read_failed", str(error)),),
                               coverage={"catalog_complete": False, "source_complete": False, **budget},
                               operation_id=context.operation_id)

    def fetch(self, source, request, bounds, context):
        base = origin(source)
        if "caption_language" in request:
            return OperationResult.unsupported("fetch_captions")
        if bounds.checkpoint:
            raise ValueError("Selected detail/file reads do not accept listing continuation.")
        deadline, budget = monotonic() + bounds.deadline_seconds, {"pages": 0, "bytes": 0}
        if request.get("attachment") is not None:
            return self._attachment(source, request["attachment"], bounds, context, deadline, budget)
        identifier = request.get("parent_id", request.get("external_id"))
        if identifier is None:
            return self.discover_request(source, request, bounds, context)
        if not isinstance(identifier, str) or not ID.fullmatch(identifier):
            raise ValueError("Use a positive decimal meeting ID string.")
        related = "parent_id" in request
        if related and request.get("record_type") != "document":
            return OperationResult.unsupported("fetch_related")
        fmt, suffix = (DOCUMENTS, "meetingDocuments") if related else (DETAIL, "meetingData")
        try:
            response = self._read(base + SERVICE + "/" + identifier + "/" + suffix, base, bounds, context, deadline, budget)
            result = bundle(source, response.content, fmt, identifier)
            total = len(result["records"])
            result["records"] = result["records"][:bounds.max_records]
            result["capture"]["retrieval_url"] = response.url
            if context.check_cancelled() or monotonic() >= deadline:
                raise ValueError("Operation interrupted during parsing.")
            return OperationResult("partial", result, coverage={"catalog_complete": False, "source_complete": False,
                "truncated": total > bounds.max_records, "input_records": total, **budget,
                "scope": "one selected public meeting response; no date inferred from title"})
        except (ValueError, OSError) as error:
            return self._failed(context, error, budget)

    def _attachment(self, source, selection, bounds, context, deadline, budget):
        if not isinstance(selection, dict) or self.storage is None:
            raise ValueError("Document download requires a captured record in scoped storage.")
        index = selection.get("index", 0)
        if type(index) is not int or index < 0 or selection.get("kind", "documents") != "documents" or selection.get("url_field", "url") != "url":
            raise ValueError("Select a document index, not arbitrary media or URL fields.")
        key = selection.get("record_key")
        if not isinstance(key, str):
            raise ValueError("Missing captured record key.")
        stored = self.storage.get("records", key, scope=context.scope)
        record = stored.value if stored else None
        if isinstance(record, dict) and "record" in record:
            record = record["record"]
        if not isinstance(record, dict):
            raise ValueError("Captured document not found in this scope.")
        identity = record.get("identity", {})
        base = origin(source)
        if identity.get("provider") != PROVIDER or identity.get("namespace") != "//" + urlsplit(base).hostname:
            raise ValueError("Captured document belongs to another tenant/provider.")
        replay = bundle(source, json.dumps({"Documents": [record.get("original")]}).encode(), DOCUMENTS)
        if not replay["records"] or source_identity_key(replay["records"][0]["identity"]) != key:
            raise ValueError("Document identity no longer matches captured public fields.")
        docs = replay["records"][0]["normalized"]["documents"]
        if docs != record.get("normalized", {}).get("documents") or index >= len(docs):
            raise ValueError("Download does not match captured document membership.")
        url = docs[index]["url"]
        try:
            # Observed public 301 adds only the trailing slash to the same native document ID.
            # Request that canonical route directly; redirects remain disabled.
            response = self._read(url.rstrip("/") + "/", base, bounds, context, deadline, budget, binary=True)
            mime = response.content_type.split(";", 1)[0].lower().strip()
            if not response.content:
                raise ValueError("Empty document response.")
            if mime == "application/pdf" and not response.content.startswith(b"%PDF-"):
                raise ValueError("PDF response lacks PDF bytes.")
            prefix = response.content[:512].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
            if mime in {"text/html", "application/xhtml+xml"} or prefix.startswith((b"<!doctype html", b"<html")):
                # HTML agenda content is already retained from meetingDocuments; avoid treating login/challenge as a file.
                raise ValueError("HTML response is not a verified document download; use retained agenda HTML.")
            data = {"record": record, "attachment": {
                "citation_url": url, "content_type": response.content_type, "byte_length": len(response.content),
                "sha256": hashlib.sha256(response.content).hexdigest(),
                "content_base64": base64.b64encode(response.content).decode(), "text_availability": "not_extracted"}}
            if context.check_cancelled() or monotonic() >= deadline:
                raise ValueError("Operation interrupted while encoding the file.")
            return OperationResult("completed", data,
                coverage={"catalog_complete": False, "source_complete": False, **budget})
        except (ValueError, OSError) as error:
            result = self._failed(context, error, budget)
            return replace(result, data={"record": record, "attachment": None})

    def native_search(self, source, query, bounds, context):
        return OperationResult.unsupported("native_search", reason="Use shared local search over captured materials.")

    def export(self, source, request, context):
        return OperationResult.unsupported("provider_export", reason="Use shared neutral export.")

    def plan_write(self, source, request, context):
        return OperationResult.unsupported("plan_write", reason="Writes deferred per market demand; no usable contract.")

    def commit_write(self, source, request, context):
        return OperationResult.unsupported("commit_write", reason="Writes deferred per market demand; no usable contract.")
