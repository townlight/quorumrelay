"""Captured root Document Center uploads and title edits; original-byte readback."""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import re
from time import monotonic
from urllib.parse import quote

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure, sanitize
from ..write_transport import WriteResponse
from .boardable_builder_write import BoardableBuilderWriteAdapter, _safe_header_value
from .boardable_meeting_write import _source_org, _native_id, _check_json_bounds, _check_prepared_size

_TYPE = "App\\Boardable\\Documents\\Document"
_VOLATILE = {
    "activity",
    "breadcrumbs",
    "pdf",
    "attachable",
    "owner",
    "created_at",
    "updated_at",
    "iconUrl",
    "bareIconUrl",
    "thumbnailUrl",
    "thumb",
    "filesize_label",
}


class _Session:
    def __init__(self, adapter, source, change, context, bounds, deadline):
        self.adapter, self.source, self.change, self.context = adapter, source, change, context
        self.bounds, self.deadline = bounds, deadline
        self.pages = self.transferred = 0
        self.attempted = False

    def request(self, method, url, body=None, content_type=None, *, binary=False):
        config = self.adapter.authorize(self.source, self.change, self.context)
        if method == "POST" and (
            "write:commit" not in self.context.authorization
            or not self.context.allows("commit_write", self.source.namespace)
        ):
            raise WriteFailure("permission_denied", "The current Document Center commit grant was revoked.")
        if self.context.check_cancelled():
            raise WriteCancelled()
        if not url.startswith(self.source.url + "documents/") and url != self.source.url + "documents":
            raise ValueError("The Document Center request left its fixed organization.")
        remaining = self.deadline - monotonic()
        limit = self.bounds.transfer_bytes - self.transferred - len(body or b"")
        if self.pages >= self.bounds.max_pages or limit <= 0 or remaining <= 0:
            raise WriteFailure("bounds_exceeded", "Document Center request bounds exhausted.")
        limit = min(limit, self.bounds.parser_bytes) if not binary else limit
        headers = {
            "Accept": "application/json",
            "Cookie": config["session_cookie"],
            "X-XSRF-TOKEN": config["xsrf_token"],
            "X-Requested-With": "XMLHttpRequest",
        }
        if content_type:
            headers["Content-Type"] = content_type
        self.pages += 1
        self.transferred += len(body or b"")
        try:
            response = self.adapter.transport.send(
                url, method=method, body=body, headers=headers, byte_limit=limit, deadline_seconds=remaining
            )
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite("Document Center transport did not confirm its response.") from None
        if not isinstance(response, WriteResponse) or len(response.content) > limit:
            raise ValueError("Document Center returned an invalid or oversized response.")
        self.transferred += len(response.content)
        if not 200 <= response.status < 300:
            raise WriteFailure("provider_rejected", "Document Center rejected the request.")
        if method == "GET" and self.context.check_cancelled():
            raise WriteCancelled()
        if method == "GET" and monotonic() >= self.deadline:
            raise WriteFailure("deadline_exceeded", "Document Center exceeded its deadline.")
        return response

    def read(self, url):
        response = self.request("GET", url)
        if response.status != 200:
            raise ValueError("Document Center returned an unexpected read status.")
        return self.decode(response)

    def decode(self, response):
        try:

            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate native JSON key.")
                    result[key] = value
                return result

            value = json.loads(response.content, object_pairs_hook=unique)
            _check_json_bounds(value, self.bounds)
            canonical_hash(value)
            return value
        except (ValueError, TypeError, RecursionError):
            raise ValueError("Document Center did not return bounded finite JSON.") from None


class BoardableDocumentCenterWriteAdapter(WriteAdapter):
    _validate_part = BoardableBuilderWriteAdapter._validate_part
    _read_part = BoardableBuilderWriteAdapter._read_part
    _multipart_body = BoardableBuilderWriteAdapter._multipart_body

    def __init__(self, transport=None):
        super().__init__("boardable", transport)

    def credentials(self, source, context):
        config = context.credentials.get(self.provider)
        _source_org(source.url)
        if (
            not isinstance(config, dict)
            or config.get("current_document_center") is not True
            or not context.tenant
            or config.get("tenant") != context.tenant
            or config.get("org_url") != source.url
        ):
            raise WriteFailure(
                "permission_denied", "An exact Document Center organization binding is required."
            )
        if any(
            config.get(flag) is True
            for flag in (
                "current_agenda_builder",
                "legacy_agenda_editor",
                "current_meeting_form",
                "current_meeting_series",
                "current_meeting_documents",
            )
        ):
            raise WriteFailure("permission_denied", "Document Center mode must be selected independently.")
        if (
            not source.namespace
            or source.namespace not in config.get("allowed_namespaces", ())
            or not context.allows("commit_write", source.namespace)
            or (context.allowed_namespaces is not None and source.namespace not in context.allowed_namespaces)
        ):
            raise WriteFailure("permission_denied", "The Document Center namespace is not authorized.")
        _native_id(config.get("organization_id"))
        _native_id(config.get("owner_id"))
        cookie = config.get("session_cookie")
        if (
            not _safe_header_value(cookie)
            or re.fullmatch(r"[A-Za-z0-9_-]+=[^;,\s]+(?:; [A-Za-z0-9_-]+=[^;,\s]+)*", cookie) is None
            or not _safe_header_value(config.get("xsrf_token"))
        ):
            raise WriteFailure(
                "credentials_required", "Safe private session and XSRF credentials are required."
            )
        return config

    def validate_source(self, source, context):
        if (
            source.provider != self.provider
            or source.options
            or source.body is not None
            or source.input_format is not None
        ):
            raise ValueError("Use only the exact Document Center organization source.")
        self.credentials(source, context)

    def authorize(self, source, change, context):
        self.validate_source(source, context)
        config = self.credentials(source, context)
        if (
            change.entity != "document"
            or change.operation not in {"upload", "update"}
            or any(
                v is not None
                for v in (change.meeting_id, change.parent_id, change.language, change.page_number)
            )
            or set(change.fields) != {"title"}
            or not isinstance(change.fields["title"], str)
            or not 0 < len(change.fields["title"]) <= 1000
            or change.fields["title"] != change.fields["title"].strip()
            or any(ord(c) < 32 for c in change.fields["title"])
        ):
            raise WriteFailure(
                "mapping_unverified", "Only root Document Center upload and title edits are mapped."
            )
        if "document:" + change.operation not in config.get("permissions", ()):
            raise WriteFailure(
                "permission_denied", "The current Document Center operation is not authorized."
            )
        if change.operation == "upload":
            if change.resource_id is not None or len(change.files) != 1:
                raise ValueError("A root upload requires exactly one file and no existing resource ID.")
            self._validate_part(change.files[0])
        else:
            if (
                change.files
                or not isinstance(change.resource_id, str)
                or re.fullmatch(r"[1-9][0-9]{0,18}", change.resource_id) is None
                or change.resource_id not in config.get("document_ids", ())
            ):
                raise WriteFailure("permission_denied", "The document is outside the exact ID allowlist.")
            self._document_url(source, config, change.resource_id)
        self._safe(change.fields, config)
        return config

    def _document_url(self, source, config, identity):
        url = config.get("document_urls", {}).get(identity)
        prefix = source.url + "documents/"
        if (
            not isinstance(url, str)
            or not url.startswith(prefix)
            or re.fullmatch(r"[a-f0-9]{8}", url[len(prefix) :]) is None
        ):
            raise WriteFailure("permission_denied", "An exact native document URL is required.")
        return url

    def _safe(self, value, config):
        if canonical_hash(sanitize(value, config)) != canonical_hash(value):
            raise ValueError("Credential-bearing Document Center data cannot be persisted.")
        text = json.dumps(value, ensure_ascii=False)
        secrets = [config["session_cookie"], config["xsrf_token"]]
        secrets.extend(part.partition("=")[2] for part in config["session_cookie"].split("; "))
        if any(secret in text or quote(secret, safe="") in text for secret in secrets if secret):
            raise ValueError("Reflected Document Center credentials cannot be persisted.")
        return value

    def _normalize(self, raw, source, config, *, expected_id=None, expected_url=None):
        if not isinstance(raw, dict):
            raise ValueError("The native document is not an object.")
        identity = _native_id(raw.get("id"))
        if expected_id is not None and identity != expected_id:
            raise ValueError("The native document ID changed.")
        _native_id(raw.get("organization_id"))
        _native_id(raw.get("owner_id"))
        if (
            raw.get("organization_id") != config["organization_id"]
            or raw.get("owner_id") != config["owner_id"]
        ):
            raise ValueError("The native document belongs to a different organization or owner.")
        uuid = raw.get("uuid")
        if (
            not isinstance(uuid, dict)
            or uuid.get("uuidable_id") != identity
            or uuid.get("uuidable_type") != _TYPE
            or not isinstance(uuid.get("short_slug"), str)
            or re.fullmatch(r"[a-f0-9]{8}", uuid["short_slug"]) is None
        ):
            raise ValueError("The native document UUID binding is invalid.")
        url = source.url + "documents/" + uuid["short_slug"]
        if raw.get("url") != url or (expected_url is not None and url != expected_url):
            raise ValueError("The native document URL changed or left its organization.")
        filename = raw.get("filename")
        if (
            not isinstance(filename, str)
            or not filename
            or filename in {".", ".."}
            or any(c in filename for c in "\r\n/\\")
            or len(filename) > 255
        ):
            raise ValueError("The native document filename is unsafe.")
        download = source.url + "documents/download/" + uuid["short_slug"] + "/" + quote(filename, safe="")
        if raw.get("downloadUrl") != download or raw.get("disable_downloads") is not False:
            raise ValueError("The native original download is unavailable or noncanonical.")
        if (
            type(raw.get("folder_id")) not in (int, str)
            or raw.get("folder_id") not in (0, "0")
            or raw.get("folder") is not None
            or raw.get("upload_type") != "computer"
            or raw.get("documentable_id", 0) != 0
            or raw.get("documentable_type", "") != ""
            or raw.get("notify", []) != []
            or (raw.get("attachable") is not None and raw.get("attachable") is not False)
            or raw.get("deleted_at") is not None
            or raw.get("token_id") is not None
        ):
            raise ValueError("Only an ordinary undeleted root computer document is mapped.")
        if type(raw.get("file_size")) is not int or raw["file_size"] < 0:
            raise ValueError("The native document file length is invalid.")
        result = {key: deepcopy(value) for key, value in raw.items() if key not in _VOLATILE}
        result["folder_id"] = 0
        result["uuid"] = {k: v for k, v in uuid.items() if k not in {"created_at", "updated_at"}}
        return self._safe(result, config)

    def _snapshot(self, session, url, identity):
        config = self.credentials(session.source, session.context)
        raw = session.read(url + "/data")
        norm = self._normalize(raw, session.source, config, expected_id=identity, expected_url=url)
        response = session.request("GET", norm["downloadUrl"], binary=True)
        if response.status != 200 or len(response.content) != norm["file_size"]:
            raise ValueError("Original download does not match the native document length.")
        return {"document": norm, "original_sha256": hashlib.sha256(response.content).hexdigest()}

    def prepare(self, source, change, context, bounds, deadline):
        config = self.authorize(source, change, context)
        if context.check_cancelled():
            raise WriteCancelled()
        session = _Session(self, source, change, context, bounds, deadline)
        before = None
        if change.operation == "update":
            url = self._document_url(source, config, change.resource_id)
            before = self._snapshot(session, url, int(change.resource_id))
        else:
            if change.files[0]["reference"]["byte_length"] > bounds.transfer_bytes:
                raise ValueError("The Document Center file exceeds transfer bounds.")
            self._read_part(change.files[0])
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The approved Document Center version changed.")
        prepared = {
            "document_center_mode": True,
            "change": asdict(change),
            "before": before,
            "before_fingerprint": fingerprint,
            "native": {
                "method": "POST",
                "url": source.url + "documents" + ("/" + change.resource_id if change.resource_id else ""),
            },
        }
        _check_prepared_size(prepared, bounds)
        self._safe(prepared, config)
        return prepared

    def _prepared(self, source, prepared, context, bounds):
        _check_prepared_size(prepared, bounds)
        change = WriteChange.from_dict(prepared["change"])
        config = self.authorize(source, change, context)
        expected = source.url + "documents" + ("/" + change.resource_id if change.resource_id else "")
        if (
            prepared.get("document_center_mode") is not True
            or prepared.get("native") != {"method": "POST", "url": expected}
            or prepared.get("before_fingerprint") != canonical_hash(prepared.get("before"))
        ):
            raise ValueError("The immutable Document Center plan was altered.")
        self._safe(prepared, config)
        return change, config

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change, config = self._prepared(source, prepared, context, bounds)
        session = _Session(self, source, change, context, bounds, deadline)
        if "write:commit" not in context.authorization:
            raise WriteFailure("permission_denied", "The current client commit grant was revoked.")
        if change.operation == "update":
            url = self._document_url(source, config, change.resource_id)
            try:
                current = self._snapshot(session, url, int(change.resource_id))
            except (WriteFailure, ValueError, TypeError):
                raise WriteFailure(
                    "conflict", "The current Document Center file no longer matches the approved target."
                ) from None
            if canonical_hash(current) != prepared["before_fingerprint"]:
                raise WriteFailure("conflict", "The Document Center file changed after approval.")
            if current["document"]["title"] == change.fields["title"]:
                return {
                    "state": "succeeded",
                    "resource_id": change.resource_id,
                    "no_send": True,
                    "readback": current,
                }
            body = json.dumps(change.fields, separators=(",", ":")).encode()
            content_type = "application/json"
        else:
            part = change.files[0]
            parts = [{"kind": "file", "name": "file", "part": part}]
            parts.extend(
                {"kind": "field", "name": key, "value": value}
                for key, value in [
                    ("title", change.fields["title"]),
                    ("body", ""),
                    ("disable_downloads", "false"),
                    ("folder", "0"),
                ]
            )
            body, content_type = self._multipart_body(parts, bounds)
        self.authorize(source, change, context)
        if "write:commit" not in context.authorization or not context.allows(
            "commit_write", source.namespace
        ):
            raise WriteFailure("permission_denied", "The current Document Center commit policy was revoked.")
        if persist and persist({"resource_id": change.resource_id, "mutation_attempted": True}):
            raise WriteCancelled()
        try:
            response = session.request("POST", prepared["native"]["url"], body, content_type)
            if response.status != (201 if change.operation == "upload" else 200):
                raise ValueError("Unexpected native save status.")
            native = session.decode(response)
            identity = _native_id(native.get("id"))
            normalized = self._normalize(
                native, source, config, expected_id=int(change.resource_id) if change.resource_id else None
            )
            url = normalized["url"]
            if persist and persist({"resource_id": str(identity), "document_url": url}):
                raise WriteCancelled()
            item = {"resource_id": str(identity), "document_url": url, "mutation_attempted": True}
            return self._verify(session, prepared, item)
        except (WriteFailure, ValueError, TypeError, KeyError, RecursionError):
            raise AmbiguousWrite("The Document Center save was sent; use read-only recovery.") from None

    def _verify(self, session, prepared, item):
        change = session.change
        identity = item.get("resource_id")
        url = item.get("document_url")
        if change.operation == "update":
            identity = change.resource_id
            url = self._document_url(
                session.source, self.credentials(session.source, session.context), identity
            )
        if (
            not item.get("mutation_attempted")
            or not isinstance(identity, str)
            or re.fullmatch(r"[1-9][0-9]{0,18}", identity) is None
            or not isinstance(url, str)
            or not url.startswith(session.source.url + "documents/")
            or re.fullmatch(r"[a-f0-9]{8}", url.removeprefix(session.source.url + "documents/")) is None
        ):
            return {
                "state": "uncertain",
                "resource_id": identity,
                "reason": "No durable native document identity/attempt is available.",
            }
        snapshot = self._snapshot(session, url, int(identity))
        document = snapshot["document"]
        matched = document.get("title") == change.fields["title"]
        if change.operation == "upload":
            part = change.files[0]
            matched = (
                matched
                and document["filename"] == part["filename"]
                and document["mime_type"] == part["content_type"]
                and document["body"] == ""
                and snapshot["original_sha256"] == part["reference"]["sha256"]
                and document["file_size"] == part["reference"]["byte_length"]
            )
        else:
            expected = deepcopy(prepared["before"])
            expected["document"]["title"] = change.fields["title"]
            matched = matched and canonical_hash(snapshot) == canonical_hash(expected)
        return {
            "state": "succeeded" if matched else "uncertain",
            "resource_id": identity,
            "document_url": url,
            "readback": snapshot,
            "reconciled": True,
        }

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change, config = self._prepared(source, prepared, context, bounds)
        return self._verify(_Session(self, source, change, context, bounds, deadline), prepared, item)
