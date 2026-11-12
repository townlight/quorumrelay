"""Versioned neutral interchange and explicitly lossy CSV/iCalendar projections.

ZIP copies attachments from authorized caller-owned streams, never source paths or
URLs. SDK streams are the large-file boundary; engine JSON responses are bounded
small-file convenience calls. The module never performs a remote write.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import secrets
import stat
import tempfile
import threading
import time
import zipfile
from copy import deepcopy
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import PurePosixPath
from typing import BinaryIO
from urllib.parse import urlsplit

from .engine import source_identity_key
from .models import Bounds, Error, OperationResult, SCHEMA_VERSION
from .storage import operation_cancelled, tracked_handler

INTERCHANGE_VERSION = "1.0"
_ENCODER = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
_ARTIFACT_LOCK = threading.RLock()


def _json(value) -> bytes:
    return _ENCODER.encode(value).encode("utf-8")


def _strict_json(data):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate JSON object keys are not allowed.")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Non-finite JSON numbers are not supported.")
    value = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError("An interchange entry must be a JSON object.")
    return value


def _hash_json(value):
    digest, size = hashlib.sha256(), 0
    for token in _ENCODER.iterencode(value):
        chunk = token.encode("utf-8")
        digest.update(chunk)
        size += len(chunk)
    return {"sha256": digest.hexdigest(), "byte_length": size}


@dataclass
class Attachment:
    identifier: str
    stream: BinaryIO
    filename: str
    citation_url: str
    sha256: str | None = None


class _ArtifactManager:
    """Bounded, engine-lifetime temporary storage when no durable store is selected."""

    def __init__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="civic-connector-artifacts-", ignore_cleanup_errors=True)
        self.values = {}
        self.size = 0

    def prune(self):
        with _ARTIFACT_LOCK:
            for key, (metadata, path) in list(self.values.items()):
                if metadata["expires_at"] <= time.time():
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        continue  # A Windows download handle may still own the file.
                    self.size -= metadata["byte_length"]
                    del self.values[key]

    def save(self, collection, key, source, metadata, *, scope, limit, context=None):
        from pathlib import Path
        from .extensions import StorageConflict

        with _ARTIFACT_LOCK:
            self.prune()
            if (scope, collection, key) in self.values:
                raise StorageConflict("The scoped artifact identifier already exists.")
            if len(self.values) >= 64:
                raise ValueError("Temporary artifact count limit reached; configure durable storage.")
            identifier = secrets.token_hex(24)
            path = Path(self.directory.name) / identifier
            try:
                with path.open("xb") as target:
                    info = _copy(source, target, min(limit, 1024 * 1024 * 1024 - self.size), context)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
            value = {**deepcopy(metadata), **info}
            self.values[(scope, collection, key)] = (value, path)
            self.size += info["byte_length"]
            return value

    def open(self, collection, key, *, context):
        with _ARTIFACT_LOCK:
            self.prune()
            item = self.values.get((context.scope, collection, key))
            if item is None:
                raise ValueError("The artifact is unavailable in the caller's scope.")
            metadata, path = item
            _authorize_artifact(metadata, context)
            return deepcopy(metadata), path.open("rb")


def _artifact_manager(engine):
    with _ARTIFACT_LOCK:
        manager = getattr(engine, "_civic_artifacts", None)
        if manager is None:
            manager = _ArtifactManager()
            engine._civic_artifacts = manager
        return manager


def _save_artifact(engine, collection, key, source, metadata, *, context, max_bytes):
    metadata = {**metadata, "created_at": time.time(), "expires_at": time.time() + 3600}
    store = engine.storage
    if (store is not None and callable(getattr(store, "save_capture", None))
            and callable(getattr(store, "open_capture", None))):
        class CancellableReader:
            def read(self, size):
                if operation_cancelled(store, context):
                    raise InterruptedError("Export cancelled; no artifact was published.")
                return source.read(size)
        reference = store.save_capture(CancellableReader(), scope=context.scope, max_bytes=max_bytes)
        if operation_cancelled(store, context):
            raise InterruptedError("Export cancelled; no artifact was published.")
        value = {**deepcopy(metadata), "storage_reference": reference,
                 "sha256": reference["sha256"], "byte_length": reference["byte_length"]}
        store.put(collection, key, value, scope=context.scope, create_only=True)
        return value
    return _artifact_manager(engine).save(
        collection, key, source, metadata, scope=context.scope, limit=max_bytes, context=context,
    )


def _open_artifact(engine, collection, key, *, context):
    store = engine.storage
    if store is not None and callable(getattr(store, "open_capture", None)):
        item = store.get(collection, key, scope=context.scope)
        if item is not None:
            _authorize_artifact(item.value, context)
            return item.value, store.open_capture(item.value["storage_reference"], scope=context.scope)
    manager = getattr(engine, "_civic_artifacts", None)
    if manager is None:
        raise ValueError("The artifact is unavailable in the caller's scope.")
    return manager.open(collection, key, context=context)


def _authorize_artifact(metadata, context):
    if metadata.get("purpose") == "input":
        consumers = {"normalize", "import_preview", "import_bundle", "extract_text", "plan_write", "commit_write"}
        if (metadata.get("expires_at", 0) <= time.time()
                or (context.allowed_operations is not None and not context.allowed_operations & consumers)):
            raise ValueError("The input handle expired or file-input authorization was revoked.")
        return
    namespaces = metadata.get("namespaces", [metadata.get("namespace")])
    if (metadata.get("expires_at", 0) <= time.time() or not context.allows("export")
            or (metadata.get("requires_attachment_grant") and "export_attachments" not in context.authorization)
            or any(namespace is None or not context.allows("export", namespace) for namespace in namespaces)):
        raise ValueError("The artifact expired or its operation/source authorization was revoked.")


def cleanup_artifacts(engine) -> None:
    """Release engine-created temporary files after closing download handles.

    Durable storage retention belongs to its owner and is not deleted here.
    """
    with _ARTIFACT_LOCK:
        manager = getattr(engine, "_civic_artifacts", None)
        if manager is not None:
            manager.directory.cleanup()
            manager.values.clear()
            manager.size = 0
            delattr(engine, "_civic_artifacts")


def stage_attachment(engine, identifier: str, source: BinaryIO, *, filename: str,
                     citation_url: str, namespace: str, context, max_bytes=200 * 1024 * 1024) -> dict:
    """Trusted input-handle hook, not an unrestricted file/URL-read operation.

    Transports resolve authorized uploads or scoped handles before calling this.
    Staging is not permission to export; export also requires export_attachments.
    """
    if not isinstance(identifier, str) or not identifier or not context.allows("export", namespace):
        raise ValueError("The attachment identifier or source namespace is not authorized.")
    parsed = urlsplit(citation_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None:
        raise ValueError("An attachment requires a durable HTTP(S) citation without credentials.")
    return _save_artifact(
        engine, "attachments", identifier, source,
        {"id": identifier, "filename": filename, "citation_url": citation_url, "namespace": namespace},
        context=context, max_bytes=max_bytes,
    )


def stage_input(engine, identifier: str, source: BinaryIO, *, filename: str,
                content_type: str, context, max_bytes=200 * 1024 * 1024) -> dict:
    """Stage a trusted upload/SDK handle without granting any provider write.

    Metadata and original bytes are immutable and scoped. Identifiers are logical
    caller-owned IDs, never paths. Normalization/import needs no export grant.
    """
    if (not isinstance(identifier, str) or not identifier
            or not isinstance(filename, str) or not isinstance(content_type, str)
            or type(max_bytes) is not int or max_bytes <= 0):
        raise ValueError("Input staging requires an identifier, filename, MIME type and positive byte limit.")
    if (len(identifier) > 128 or "/" in identifier or "\\" in identifier
            or any(ord(char) < 32 for char in identifier)):
        raise ValueError("An input identifier must be a bounded opaque ID, never a path.")
    handle = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    metadata = {"purpose": "input", "file_handle": handle, "filename": filename,
                "content_type": content_type, "max_bytes": max_bytes}
    # Check current read-input operation policy before consuming a caller stream.
    _authorize_artifact({**metadata, "expires_at": time.time() + 3600}, context)
    value = _save_artifact(engine, "service_files", handle, source, metadata,
                           context=context, max_bytes=max_bytes)
    return {key: value[key] for key in ("file_handle", "filename", "content_type", "byte_length", "sha256")}


def open_input(engine, handle: str, *, context, expected_sha256=None,
               expected_byte_length=None):
    """Reopen and verify an immutable scoped input. Caller closes the stream."""
    if not isinstance(handle, str) or re.fullmatch("[0-9a-f]{64}", handle) is None:
        raise ValueError("Invalid input file handle.")
    metadata, stream = _open_artifact(engine, "service_files", handle, context=context)
    try:
        if metadata.get("purpose") != "input":
            raise ValueError("The handle is not an immutable generic input.")
        if ((expected_sha256 is not None and metadata["sha256"] != expected_sha256)
                or (expected_byte_length is not None and metadata["byte_length"] != expected_byte_length)):
            raise ValueError("The input handle does not match its bound hash/length.")
        actual = _copy(stream, _Discard(), metadata["max_bytes"])
        if actual["sha256"] != metadata["sha256"] or actual["byte_length"] != metadata["byte_length"]:
            raise ValueError("The input bytes changed or exceed their original transfer bound.")
        stream.seek(0)
        public = {key: metadata[key] for key in
                  ("file_handle", "filename", "content_type", "byte_length", "sha256")}
        return public, stream
    except BaseException:
        stream.close()
        raise


def open_artifact(engine, artifact_id: str, *, context):
    """Authorized download hook shared by CLI/HTTP/MCP. Returns metadata, stream.

    The caller must close the stream. No caller-controlled path is ever opened.
    Durable stores retain artifacts across engine restarts; temporary artifacts
    exist only for this engine's lifetime and have explicit count/byte bounds.
    """
    metadata, stream = _open_artifact(engine, "artifacts", artifact_id, context=context)
    if not context.allows("export") or any(
        not context.allows("export", namespace) for namespace in metadata["namespaces"]
    ):
        stream.close()
        raise ValueError("The artifact source namespace is no longer authorized.")
    public = {key: deepcopy(value) for key, value in metadata.items() if key != "storage_reference"}
    return public, stream


class _LimitWriter:
    def __init__(self, stream, limit, deadline_seconds):
        self.stream, self.limit, self.size = stream, limit, 0
        self.deadline = time.monotonic() + deadline_seconds
        self.digest = hashlib.sha256()

    def write(self, data):
        if time.monotonic() > self.deadline:
            raise ValueError("The export deadline was exceeded.")
        if self.size + len(data) > self.limit:
            raise ValueError("The export exceeds the configured transfer byte limit.")
        written = self.stream.write(data)
        if written != len(data):
            raise ValueError("The output stream did not accept all bytes.")
        self.digest.update(data)
        self.size += len(data)
        return written

    def tell(self):
        return self.size

    def flush(self):
        return self.stream.flush()


def _copy(source, target, limit, context=None):
    digest, size = hashlib.sha256(), 0
    while True:
        if context is not None and context.check_cancelled():
            raise InterruptedError("Export cancelled; discard the incomplete output.")
        chunk = source.read(min(1024 * 1024, limit - size + 1))
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise ValueError("A payload exceeds the configured transfer byte limit.")
        target.write(chunk)
        digest.update(chunk)
    return {"sha256": digest.hexdigest(), "byte_length": size}


def _safe_member(name):
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or "\x00" in name or name.startswith("/") or name.endswith("/")
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("Unsafe archive member name.")
    if PurePosixPath(name).is_absolute():
        raise ValueError("Absolute archive member names are not allowed.")


def _capture_locations(value, path=(), *, include_empty=False):
    """Only declared capture locations, never similarly named unknown fields."""
    if not isinstance(value, dict):
        return
    capture = value.get("capture")
    if isinstance(capture, dict) and ("content_base64" in capture or "storage_reference" in capture
                                     or (include_empty and "sha256" in capture)):
        yield (*path, "capture"), capture
    for index, capture in enumerate(value.get("captures", [])):
        if isinstance(capture, dict) and ("content_base64" in capture or "storage_reference" in capture
                                         or (include_empty and "sha256" in capture)):
            yield (*path, "captures", index), capture
    for index, bundle in enumerate(value.get("bundles", [])):
        yield from _capture_locations(bundle, (*path, "bundles", index), include_empty=include_empty)


def _hash_original_archive_bundle(bundle, manifest, archive):
    """Hash original JSON logically, streaming ZIP blobs as base64 JSON strings.

    This runs before capture-storage substitution or any attachment callback.
    It uses canonical JSON syntax identical to _hash_json, including unknown data.
    """
    replacements = {}
    valid = {path for path, capture in _capture_locations(bundle, include_empty=True)}
    locations = manifest.get("capture_locations", [])
    seen = set()
    for location in locations:
        path = tuple(location["path"])
        if path not in valid or path in seen:
            raise ValueError("Invalid or duplicate capture restoration location.")
        seen.add(path)
        capture = _at(bundle, path)
        if location["sha256"] != capture.get("sha256"):
            raise ValueError("Capture restoration hash does not match.")
        if location["inline"]:
            replacements[(*path, "content_base64")] = "captures/" + location["sha256"]
    digest, size = hashlib.sha256(), 0
    def emit(data):
        nonlocal size
        digest.update(data)
        size += len(data)
    def walk(value, path=()):
        if isinstance(value, dict):
            emit(b"{")
            keys = set(value)
            if (*path, "content_base64") in replacements:
                keys.add("content_base64")
            for index, key in enumerate(sorted(keys)):
                if index:
                    emit(b",")
                emit(_json(key))
                emit(b":")
                child_path = (*path, key)
                if child_path in replacements:
                    emit(b'"')
                    with archive.open(replacements[child_path]) as member:
                        while chunk := member.read(3 * 256 * 1024):
                            emit(base64.b64encode(chunk))
                    emit(b'"')
                else:
                    walk(value[key], child_path)
            emit(b"}")
        elif isinstance(value, (list, tuple)):
            emit(b"[")
            for index, child in enumerate(value):
                if index:
                    emit(b",")
                walk(child, (*path, index))
            emit(b"]")
        else:
            emit(_json(value))
    walk(bundle)
    return {"sha256": digest.hexdigest(), "byte_length": size}


def _at(value, path):
    for part in path:
        value = value[part]
    return value


def _capture_stream(capture, storage, scope):
    if "content_base64" in capture:
        # Decode chunks to disk; never make a second transfer-sized bytes object.
        stream = tempfile.TemporaryFile()
        encoded = capture["content_base64"]
        if not isinstance(encoded, str):
            stream.close()
            raise ValueError("A capture content_base64 value must be a string.")
        try:
            for offset in range(0, len(encoded), 1024 * 1024):
                stream.write(base64.b64decode(encoded[offset:offset + 1024 * 1024], validate=True))
            stream.seek(0)
            return stream
        except BaseException:
            stream.close()
            raise
    if storage is None or not callable(getattr(storage, "open_capture", None)):
        raise ValueError("The original capture requires its scoped streaming storage adapter.")
    return storage.open_capture(capture["storage_reference"], scope=scope)


def write_bundle(bundle: dict, destination: BinaryIO, *, format="zip", bounds=None,
                 attachments=(), authorized_attachments=frozenset(), storage=None,
                 scope="local", context=None) -> dict:
    """Write to a caller-owned binary stream. Caller discards output on any error.

    JSON/JSONL retain the whole envelope. ZIP splits record lines and original
    capture blobs, so a transfer-sized PDF does not become a parser-sized input.
    Output size and expanded payload sizes are bounded independently of parser input.
    """
    bounds = bounds or Bounds()
    if not isinstance(bundle, dict) or not isinstance(bundle.get("records"), (list, tuple)):
        raise ValueError("Export requires a bundle with records.")
    if format in {"json", "jsonl"}:
        # Portable text formats carry the original bytes inline. Local storage
        # references alone are neither portable nor a reason to reject small captures.
        bundle = deepcopy(bundle)
        materialized = 0
        for _, capture in _capture_locations(bundle):
            if "storage_reference" not in capture or "content_base64" in capture:
                continue
            with _capture_stream(capture, storage, scope) as original:
                raw = original.read(bounds.parser_bytes + 1)
            if len(raw) > bounds.parser_bytes:
                raise ValueError("Original capture exceeds the text-format parser limit; use ZIP export.")
            if len(raw) != capture["byte_length"] or hashlib.sha256(raw).hexdigest() != capture["sha256"]:
                raise ValueError("Stored original capture does not match its hash/length.")
            materialized += 4 * ((len(raw) + 2) // 3)
            if materialized > bounds.parser_bytes:
                raise ValueError("Original captures exceed the text-format parser limit; use ZIP export.")
            capture["content_base64"] = base64.b64encode(raw).decode("ascii")
    sink = _LimitWriter(destination, bounds.transfer_bytes, bounds.deadline_seconds)
    manifest = {"interchange_version": INTERCHANGE_VERSION, "schema_version": SCHEMA_VERSION,
                "format": format, "entries": [], "attachments": [], "not_included": [],
                "projection_losses": [], "bundle": _hash_json(bundle)}
    capture_hashes = {capture["sha256"] for _, capture in _capture_locations(bundle)}
    for record in bundle["records"]:
        if record.get("capture_sha256") and record["capture_sha256"] not in capture_hashes:
            manifest["not_included"].append({"capture_sha256": record["capture_sha256"],
                                            "reason": "original_capture_not_supplied"})
    if format in {"json", "jsonl"}:
        if attachments:
            raise ValueError("Attachments require ZIP interchange, not JSON/JSONL.")
        if format == "json":
            emitted = 0
            for token in _ENCODER.iterencode({"interchange_version": INTERCHANGE_VERSION,
                                              "bundle": bundle, "manifest": manifest}):
                encoded = token.encode("utf-8")
                emitted += len(encoded)
                if emitted > bounds.parser_bytes:
                    raise ValueError("JSON export exceeds its parser limit; use ZIP export.")
                sink.write(encoded)
        else:
            metadata = {key: value for key, value in bundle.items() if key != "records"}
            header = _json({"type": "header", "interchange_version": INTERCHANGE_VERSION,
                            "bundle": metadata}) + b"\n"
            if len(header) > bounds.parser_bytes:
                raise ValueError("JSONL header exceeds its parser limit; use ZIP export.")
            sink.write(header)
            for record in bundle["records"]:
                if context is not None and context.check_cancelled():
                    raise InterruptedError("Export cancelled.")
                line = _json({"type": "record", "record": record}) + b"\n"
                if len(line) > bounds.parser_bytes:
                    raise ValueError("JSONL record exceeds its parser limit; use ZIP export.")
                sink.write(line)
            sink.write(_json({"type": "manifest", "manifest": manifest}) + b"\n")
    elif format == "zip":
        metadata = deepcopy({key: value for key, value in bundle.items() if key != "records"})
        locations, captures = [], {}
        for path, capture in _capture_locations(metadata):
            sha = capture.get("sha256")
            if not isinstance(sha, str) or re.fullmatch("[0-9a-f]{64}", sha) is None:
                raise ValueError("A capture requires a SHA-256 hash.")
            locations.append({"path": list(path), "sha256": sha,
                              "inline": "content_base64" in capture})
            captures.setdefault(sha, deepcopy(capture))
            capture.pop("content_base64", None)
        manifest["capture_locations"] = locations
        with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            def put_json(name, value):
                digest, size = hashlib.sha256(), 0
                with archive.open(name, "w", force_zip64=True) as member:
                    for token in _ENCODER.iterencode(value):
                        data = token.encode("utf-8")
                        size += len(data)
                        if size > bounds.parser_bytes:
                            raise ValueError("Archive metadata exceeds the parser input limit.")
                        digest.update(data)
                        member.write(data)
                manifest["entries"].append({"path": name, "sha256": digest.hexdigest(), "byte_length": size})
            put_json("bundle.json", metadata)
            digest, size = hashlib.sha256(), 0
            with archive.open("records.jsonl", "w", force_zip64=True) as member:
                for record in bundle["records"]:
                    line = _json(record) + b"\n"
                    if len(line) > bounds.parser_bytes:
                        raise ValueError("A record exceeds the parser input limit.")
                    if context is not None and context.check_cancelled():
                        raise InterruptedError("Export cancelled.")
                    size += len(line)
                    if size > bounds.transfer_bytes:
                        raise ValueError("Record payload exceeds the transfer limit.")
                    digest.update(line)
                    member.write(line)
            manifest["entries"].append({"path": "records.jsonl", "sha256": digest.hexdigest(), "byte_length": size})
            for sha, capture in captures.items():
                name = "captures/" + sha
                with _capture_stream(capture, storage, scope) as source:
                    with archive.open(name, "w", force_zip64=True) as target:
                        info = _copy(source, target, bounds.transfer_bytes, context)
                if info["sha256"] != sha or info["byte_length"] != capture.get("byte_length"):
                    raise ValueError("Original capture hash/length does not match.")
                manifest["entries"].append({"path": name, **info})
            seen_attachments = set()
            for attachment in attachments:
                if attachment.identifier in seen_attachments:
                    raise ValueError("Attachment identifiers must be unique.")
                seen_attachments.add(attachment.identifier)
                if attachment.identifier not in authorized_attachments:
                    manifest["not_included"].append({"id": attachment.identifier, "reason": "not_authorized"})
                    continue
                name = "attachments/" + hashlib.sha256(attachment.identifier.encode()).hexdigest()
                with archive.open(name, "w", force_zip64=True) as target:
                    info = _copy(attachment.stream, target, bounds.transfer_bytes, context)
                if attachment.sha256 is not None and info["sha256"] != attachment.sha256:
                    raise ValueError("Attachment hash does not match.")
                entry = {"path": name, **info}
                manifest["entries"].append(entry)
                manifest["attachments"].append({
                    **entry, "id": attachment.identifier, "filename": attachment.filename,
                    "citation_url": attachment.citation_url,
                })
            # Linked documents never imply permission or successful inclusion.
            for record in bundle["records"]:
                for relation in record.get("relationships", []):
                    if relation.get("relation") in {"document", "recording"}:
                        value = relation.get("value") or {}
                        if not any(a["citation_url"] == (value.get("citation_url") or value.get("url"))
                                   for a in manifest["attachments"]):
                            manifest["not_included"].append({
                                "citation_url": value.get("citation_url") or value.get("url"),
                                "reason": "linked_payload_not_authorized_or_not_supplied",
                            })
            raw_manifest = _json(manifest)
            if len(raw_manifest) > bounds.parser_bytes:
                raise ValueError("Manifest exceeds the parser limit.")
            if sum(entry["byte_length"] for entry in manifest["entries"]) + len(raw_manifest) > bounds.transfer_bytes:
                raise ValueError("Expanded export exceeds the transfer byte limit.")
            archive.writestr("manifest.json", raw_manifest)
    else:
        raise ValueError("Neutral format must be json, jsonl or zip.")
    return {**manifest, "output": {"sha256": sink.digest.hexdigest(), "byte_length": sink.size}}


def _bounded_read(stream, limit):
    data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Input exceeds the parser input limit.")
    return data


def read_bundle(source, *, format="zip", bounds=None, attachment_sink=None,
                capture_storage=None, scope="local") -> dict:
    """Verify before returning. Never extract an archive to a source-named path.

    attachment_sink(metadata, stream) receives verified content only. A configured
    capture_storage saves large original bytes as lossless scoped references.
    """
    bounds = bounds or Bounds()
    verified_logical = False
    stream = io.BytesIO(source) if isinstance(source, bytes) else source
    if format == "json":
        payload = _strict_json(_bounded_read(stream, bounds.parser_bytes))
        if payload.get("interchange_version") != INTERCHANGE_VERSION:
            raise ValueError("Unsupported interchange version.")
        bundle, manifest = payload["bundle"], payload["manifest"]
    elif format == "jsonl":
        header_line = stream.readline(bounds.parser_bytes + 1)
        if len(header_line) > bounds.parser_bytes:
            raise ValueError("JSONL header exceeds the parser input limit.")
        header = _strict_json(header_line)
        if header.get("type") != "header" or header.get("interchange_version") != INTERCHANGE_VERSION:
            raise ValueError("JSONL interchange requires a supported header.")
        bundle = header["bundle"]
        bundle["records"] = []
        consumed, manifest = len(header_line), None
        for line in iter(lambda: stream.readline(bounds.parser_bytes + 1), b""):
            consumed += len(line)
            if len(line) > bounds.parser_bytes or consumed > bounds.transfer_bytes:
                raise ValueError("JSONL input exceeds its parser/transfer limit.")
            item = _strict_json(line)
            if manifest is not None:
                raise ValueError("The JSONL manifest must be the final line.")
            if item.get("type") == "record":
                if len(bundle["records"]) >= bounds.max_records:
                    raise ValueError("The import exceeds max_records; nothing was returned.")
                bundle["records"].append(item["record"])
            elif item.get("type") == "manifest":
                manifest = item["manifest"]
            else:
                raise ValueError("Unknown JSONL entry type.")
        if manifest is None:
            raise ValueError("JSONL requires its integrity manifest.")
    elif format == "zip":
        # Archive central directory needs seekable input. Stage a non-seekable
        # caller stream to bounded disk rather than buffering it in memory.
        with tempfile.TemporaryFile() as staged:
            _copy(stream, staged, bounds.transfer_bytes)
            staged.seek(0)
            try:
                with zipfile.ZipFile(staged) as archive:
                    entries = archive.infolist()
                    if len(entries) > max(128, bounds.max_records * 8):
                        raise ValueError("Too many archive entries.")
                    names = set()
                    expanded = 0
                    for entry in entries:
                        _safe_member(entry.filename)
                        if entry.filename in names:
                            raise ValueError("Duplicate archive member.")
                        names.add(entry.filename)
                        if (entry.filename not in {"manifest.json", "bundle.json", "records.jsonl"}
                                and re.fullmatch(r"(?:captures|attachments)/[0-9a-f]{64}", entry.filename) is None):
                            raise ValueError("Unexpected archive member.")
                        mode = entry.external_attr >> 16
                        if stat.S_ISLNK(mode) or entry.flag_bits & 1:
                            raise ValueError("Links and encrypted members are not supported.")
                        expanded += entry.file_size
                        if expanded > bounds.transfer_bytes:
                            raise ValueError("Expanded archive exceeds the transfer byte limit.")
                    with archive.open("manifest.json") as member:
                        manifest = _strict_json(_bounded_read(member, bounds.parser_bytes))
                    if manifest.get("interchange_version") != INTERCHANGE_VERSION:
                        raise ValueError("Unsupported interchange manifest version.")
                    declared = manifest.get("entries")
                    if not isinstance(declared, list):
                        raise ValueError("Manifest entries must be an array.")
                    paths = [item["path"] for item in declared]
                    if len(paths) != len(set(paths)) or set(paths) | {"manifest.json"} != names:
                        raise ValueError("The archive and its manifest members do not match.")
                    # Verify every payload before parsing, callbacks or persistence.
                    for item in declared:
                        with archive.open(item["path"]) as member:
                            info = _copy(member, _Discard(), bounds.transfer_bytes)
                        if any(info[k] != item.get(k) for k in ("sha256", "byte_length")):
                            raise ValueError("Archive payload hash/length does not match.")
                    with archive.open("bundle.json") as member:
                        bundle = _strict_json(_bounded_read(member, bounds.parser_bytes))
                    bundle["records"] = []
                    with archive.open("records.jsonl") as member:
                        while line := member.readline(bounds.parser_bytes + 1):
                            if len(line) > bounds.parser_bytes or len(bundle["records"]) >= bounds.max_records:
                                raise ValueError("Record parser/count limit exceeded.")
                            bundle["records"].append(_strict_json(line))
                    if _hash_original_archive_bundle(bundle, manifest, archive) != manifest.get("bundle"):
                        raise ValueError("The original bundle hash does not match its manifest.")
                    verified_logical = True
                    for location in manifest.get("capture_locations", []):
                        capture = _at(bundle, location["path"])
                        sha = location["sha256"]
                        if sha != capture.get("sha256") or "captures/" + sha not in names:
                            raise ValueError("A capture reference does not match the archive.")
                        with archive.open("captures/" + sha) as member:
                            if capture_storage is not None:
                                reference = capture_storage.save_capture(
                                    member, scope=scope, max_bytes=bounds.transfer_bytes,
                                )
                                capture["storage_reference"] = reference
                            elif location["inline"]:
                                # The dictionary-returning convenience path needs an inline
                                # string. For large originals, supply capture_storage instead.
                                chunks = []
                                while chunk := member.read(3 * 256 * 1024):
                                    chunks.append(base64.b64encode(chunk).decode("ascii"))
                                capture["content_base64"] = "".join(chunks)
                            else:
                                raise ValueError("Importing a stored capture requires capture_storage.")
                    if attachment_sink is not None:
                        for item in manifest.get("attachments", []):
                            if not item["path"].startswith("attachments/") or not any(
                                entry == {key: item[key] for key in ("path", "sha256", "byte_length")}
                                for entry in declared
                            ):
                                raise ValueError("Attachment declaration does not match a verified payload.")
                            with archive.open(item["path"]) as member:
                                attachment_sink(deepcopy(item), member)
            except (zipfile.BadZipFile, KeyError) as error:
                raise ValueError("Invalid or incomplete neutral ZIP bundle.") from error
    else:
        raise ValueError("Neutral format must be json, jsonl or zip.")
    if manifest.get("interchange_version") != INTERCHANGE_VERSION:
        raise ValueError("Unsupported interchange manifest version.")
    if not verified_logical and _hash_json(bundle) != manifest.get("bundle"):
        raise ValueError("The bundle hash does not match its manifest.")
    if len(bundle.get("records", [])) > bounds.max_records:
        raise ValueError("The import exceeds max_records.")
    return bundle


class _Discard:
    def write(self, data):
        return len(data)


def _leaves(value, prefix=""):
    if isinstance(value, dict) and value:
        return {path for key, child in value.items()
                for path in _leaves(child, f"{prefix}.{key}" if prefix else str(key))}
    if isinstance(value, (list, tuple)) and value:
        return {path for index, child in enumerate(value) for path in _leaves(child, f"{prefix}[{index}]")}
    return {prefix}


def _csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        value = _json(value).decode()
    value = str(value)
    return "'" + value if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) else value


def csv_projection(records, *, kind="meetings"):
    """RFC 4180 CSV with a separate, machine-readable omission ledger."""
    output = io.StringIO(newline="")
    losses = []
    if kind == "meetings":
        columns = ["identity_key", "provider", "namespace", "external_id", "title", "scheduled_start",
                   "meeting_date", "body", "source_url", "capture_sha256", "source_revision"]
    elif kind == "items":
        columns = ["meeting_identity_key", "item_external_id", "title", "department", "source_url"]
    else:
        raise ValueError("CSV projection must be meetings or items.")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\r\n")
    writer.writeheader()
    for record in records:
        identity, normalized = record["identity"], record.get("normalized", {})
        key = source_identity_key(identity)
        included = {"source_url"}
        if kind == "meetings":
            if identity["record_type"] not in {"meeting", "event"}:
                losses.append({"identity_key": key, "reason": "non_meeting_record_omitted",
                               "omitted_fields": sorted(_leaves(record))})
                continue
            row = {"identity_key": key, **{k: identity[k] for k in ("provider", "namespace", "external_id")},
                   **{k: normalized.get(k) for k in ("title", "scheduled_start", "meeting_date", "body")},
                   **{k: record.get(k) for k in ("source_url", "capture_sha256", "source_revision")}}
            writer.writerow({k: _csv_cell(v) for k, v in row.items()})
            included |= {"identity.provider", "identity.namespace", "identity.external_id", "capture_sha256"}
            included |= {p for p in _leaves(record) if p.startswith("source_revision.")}
            included |= {f"normalized.{k}" for k in ("title", "scheduled_start", "meeting_date", "body")}
        else:
            for index, item in enumerate(normalized.get("agenda_items", [])):
                writer.writerow({k: _csv_cell(v) for k, v in {
                    "meeting_identity_key": key, "item_external_id": item.get("external_id"),
                    "title": item.get("title"), "department": item.get("department"),
                    "source_url": record.get("source_url"),
                }.items()})
                included |= {f"normalized.agenda_items[{index}].{field}"
                             for field in ("external_id", "title", "department")}
        losses.append({"identity_key": key, "omitted_fields": sorted(_leaves(record) - included)})
    return output.getvalue().encode("utf-8"), {
        "projection": kind, "lossless": False, "records": losses,
        "representation_changes": ["null/absent become empty cells",
                                   "formula-like cells are prefixed with apostrophe",
                                   "nested source_revision uses JSON; other nested fields are omitted"],
        "specification": "https://www.rfc-editor.org/rfc/rfc4180",
    }


def _ical_text(value):
    value = str(value).replace("\r\n", "\n").replace("\r", "\n")
    if re.search(r"[\x00-\x08\x0b-\x1f\x7f]", value):
        raise ValueError("Calendar text contains an unsupported control character.")
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold_line(line):
    lines, current, size = [], "", 0
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > 75:
            lines.append(current)
            current, size = " ", 1
        current += char
        size += width
    return "\r\n".join([*lines, current])


def icalendar_projection(records):
    """RFC 5545 VEVENT: stable UID, UTC offsets or explicitly floating time."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Civic Data Connectors//Neutral Export 1.0//EN"]
    losses = []
    for record in records:
        key = source_identity_key(record["identity"])
        normalized = record.get("normalized", {})
        loss = {"identity_key": key, "omitted_fields": sorted(_leaves(record)),
                "limitations": ["No recurrence, attendees, votes, documents, media or custom fields projected."]}
        losses.append(loss)
        if record["identity"]["record_type"] not in {"meeting", "event"}:
            loss["reason"] = "non_event_record_omitted"
            continue
        start = normalized.get("scheduled_start") or normalized.get("meeting_date")
        if not start:
            loss["reason"] = "missing_start_event_omitted"
            continue
        if len(start) == 10:
            dtstart = "DTSTART;VALUE=DATE:" + date.fromisoformat(start).strftime("%Y%m%d")
        else:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if dt.utcoffset() is None:
                dtstart = "DTSTART:" + dt.strftime("%Y%m%dT%H%M%S")
                loss["limitations"].append("Unknown source zone exported as floating time; no zone invented.")
            else:
                dtstart = "DTSTART:" + dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                loss["limitations"].append("Known offset represented as UTC; original offset remains in neutral bundle.")
        stamp = datetime.fromisoformat(record["captured_at"].replace("Z", "+00:00"))
        if stamp.utcoffset() is None:
            raise ValueError("Calendar DTSTAMP requires a known captured_at offset.")
        lines += ["BEGIN:VEVENT", f"UID:{key}@civic-data-connectors.invalid",
                  "DTSTAMP:" + stamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                  dtstart, "SUMMARY:" + _ical_text(normalized.get("title", ""))]
        included = {"normalized.title", "normalized.scheduled_start", "normalized.meeting_date", "captured_at"}
        location = normalized.get("location")
        if isinstance(location, str):
            lines.append("LOCATION:" + _ical_text(location))
            included.add("normalized.location")
        citation = next(iter(record.get("citation_urls", [])), record.get("source_url", ""))
        parsed = urlsplit(citation)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not re.search(r"[\x00-\x20\x7f]", citation):
            lines.append("URL:" + citation)
            included.add("citation_urls[0]" if record.get("citation_urls") else "source_url")
        source_status = normalized.get("source_status")
        if source_status == "CANCELLED" or (isinstance(source_status, dict) and source_status.get("canceled")):
            lines.append("STATUS:CANCELLED")
            included |= {p for p in _leaves(record) if p.startswith("normalized.source_status")}
        lines.append("END:VEVENT")
        loss["omitted_fields"] = sorted(_leaves(record) - included)
    lines.append("END:VCALENDAR")
    return ("\r\n".join(_fold_line(line) for line in lines) + "\r\n").encode("utf-8"), {
        "projection": "icalendar", "lossless": False, "records": losses,
        "specification": "https://www.rfc-editor.org/rfc/rfc5545",
    }


def register(engine) -> None:
    def export(owner, request, content, context):
        request = dict(request)
        if request.get("provider_specific"):
            return OperationResult.unsupported("export", reason=(
                "A provider-specific export mapping is not implemented for this configured source. "
                "This does not establish that the provider lacks an import format. "
                "Select a neutral format explicitly or configure an evidenced connector extension."))
        upstream_errors = ()
        if "result" in request:
            upstream = request["result"]
            if not isinstance(upstream, dict):
                raise ValueError("result must be a complete operation result object.")
            if not isinstance(upstream.get("data"), dict):
                return OperationResult.from_dict(upstream)
            request["bundle"] = upstream["data"].get("bundle", upstream["data"])
            request["coverage"] = {**upstream.get("coverage", {}), "input_status": upstream["status"]}
            upstream_errors = tuple(Error(**error) for error in upstream.get("errors", []))
        bounds = Bounds(**request.get("bounds", {}))
        if "stream" in request and type(request["stream"]) is not bool:
            raise ValueError("stream must be a JSON boolean.")
        delivery = request.get("delivery", "storage" if request.get("stream") else "inline")
        if delivery not in {"inline", "storage"}:
            raise ValueError("delivery must be inline or storage.")
        bundle = request.get("bundle")
        if "bundle_key" in request:
            if any(key in request for key in ("bundle", "records", "result")):
                raise ValueError("bundle_key cannot be combined with an inline bundle, records or result.")
            key = request["bundle_key"]
            if not isinstance(key, str) or re.fullmatch("[0-9a-f]{64}", key) is None:
                raise ValueError("bundle_key must be a stored bundle's SHA-256 key.")
            stored = owner.storage.get("bundles", key, scope=context.scope) if owner.storage else None
            if stored is None:
                return OperationResult("failed", errors=(Error("not_found",
                    "The saved bundle is unavailable in the caller's scope."),),
                    operation_id=context.operation_id)
            bundle = stored.value
        if bundle is None:
            records = request.get("records")
            if records is None and owner.storage is not None:
                records = [item.value for item in owner.storage.list("records", scope=context.scope)]
            if records is None:
                raise ValueError("Export requires a bundle, records or configured storage.")
            captures = []
            for digest in dict.fromkeys(record.get("capture_sha256") for record in records):
                stored = owner.storage.get("captures", digest, scope=context.scope) if owner.storage and digest else None
                if stored:
                    captures.append(stored.value)
            bundle = {"schema_version": SCHEMA_VERSION, "records": records, "capture": {}, "captures": captures,
                      "extensions": {"coverage": deepcopy(request.get("coverage", {}))}}
        if any(not context.allows("export", record["identity"]["namespace"]) for record in bundle["records"]):
            return OperationResult("failed", errors=(Error("permission_denied",
                "Export includes a source outside the caller's namespace policy."),),
                operation_id=context.operation_id)
        # When exporting a saved search/result selection, resolve original captures
        # without replacing or discarding any existing bundle/unknown data.
        if owner.storage is not None:
            available = {capture["sha256"] for _, capture in _capture_locations(bundle)}
            extra = []
            for digest in dict.fromkeys(r.get("capture_sha256") for r in bundle["records"]):
                if digest and digest not in available:
                    captured = owner.storage.get("captures", digest, scope=context.scope)
                    if captured is not None:
                        extra.append(captured.value)
                        available.add(digest)
            if extra:
                bundle = {**bundle, "captures": [*bundle.get("captures", []), *extra]}
        format = request.get("format", "zip")
        if operation_cancelled(owner.storage, context):
            return OperationResult("cancelled", operation_id=context.operation_id)
        if format in {"csv", "csv-meetings", "csv-items", "icalendar", "ics"}:
            if format.startswith("csv"):
                payload, losses = csv_projection(bundle["records"], kind="items" if format == "csv-items" else "meetings")
            else:
                payload, losses = icalendar_projection(bundle["records"])
            if len(payload) > bounds.transfer_bytes:
                raise ValueError("Projection exceeds the transfer byte limit.")
            if delivery == "inline" and len(payload) > bounds.parser_bytes:
                raise ValueError("Use the streaming SDK for exports above the JSON response limit.")
            manifest = {"projection_losses": losses, "sha256": hashlib.sha256(payload).hexdigest(),
                        "byte_length": len(payload)}
            if delivery == "storage":
                artifact_id = secrets.token_hex(24)
                metadata = _save_artifact(owner, "artifacts", artifact_id, io.BytesIO(payload),
                    {"artifact_id": artifact_id, "format": format, "manifest": manifest,
                     "namespaces": sorted({r["identity"]["namespace"] for r in bundle["records"]})},
                    context=context, max_bytes=bounds.transfer_bytes)
                data = {"format": format, "artifact_id": artifact_id, "manifest": manifest,
                        "storage_reference": metadata.get("storage_reference",
                            {"kind": "civic_export_artifact", "artifact_id": artifact_id})}
            else:
                data = {"format": format, "content_base64": base64.b64encode(payload).decode(), "manifest": manifest}
            coverage = deepcopy(request.get("coverage", {}))
            status = "partial" if (coverage.get("failures") or coverage.get("truncated")
                                    or coverage.get("input_status") in {"partial", "failed", "cancelled"}
                                    or upstream_errors) else "completed"
            return OperationResult(status, data=data,
                                   errors=upstream_errors, coverage=coverage, operation_id=context.operation_id)
        attachment_ids = request.get("attachment_ids", [])
        if not isinstance(attachment_ids, list) or any(not isinstance(i, str) or not i for i in attachment_ids):
            raise ValueError("attachment_ids must be an array of nonempty identifiers.")
        if len(attachment_ids) != len(set(attachment_ids)):
            raise ValueError("attachment_ids must be unique.")
        if attachment_ids and "export_attachments" not in context.authorization:
            return OperationResult("failed", errors=(Error("permission_denied",
                "The caller is not authorized to export attachments."),), operation_id=context.operation_id)
        with ExitStack() as stack:
            attachments = []
            namespaces = {record["identity"]["namespace"] for record in bundle["records"]}
            for identifier in attachment_ids:
                item, stream = _open_artifact(owner, "attachments", identifier, context=context)
                stack.enter_context(stream)
                if item["namespace"] not in namespaces or not context.allows("export", item["namespace"]):
                    raise ValueError("The attachment does not belong to an authorized exported source.")
                attachments.append(Attachment(identifier, stream, item["filename"],
                                              item["citation_url"], item["sha256"]))
            output = stack.enter_context(tempfile.TemporaryFile())
            try:
                manifest = write_bundle(bundle, output, format=format, bounds=bounds, storage=owner.storage,
                                        scope=context.scope, context=context, attachments=attachments,
                                        authorized_attachments=frozenset(attachment_ids))
            except InterruptedError:
                return OperationResult("cancelled", coverage={"truncated": True}, operation_id=context.operation_id)
            if delivery == "storage":
                output.seek(0)
                artifact_id = secrets.token_hex(24)
                metadata = _save_artifact(owner, "artifacts", artifact_id, output,
                    {"artifact_id": artifact_id, "format": format, "manifest": manifest,
                     "requires_attachment_grant": bool(attachment_ids),
                     "namespaces": sorted(namespaces)}, context=context, max_bytes=bounds.transfer_bytes)
                data = {"format": format, "artifact_id": artifact_id, "manifest": manifest,
                        "storage_reference": metadata.get("storage_reference",
                            {"kind": "civic_export_artifact", "artifact_id": artifact_id})}
            else:
                if output.tell() > bounds.parser_bytes:
                    raise ValueError("Use delivery=storage for exports above the JSON response limit.")
                output.seek(0)
                data = {"format": format, "content_base64": base64.b64encode(output.read()).decode("ascii"),
                        "manifest": manifest}
        coverage = deepcopy(request.get("coverage", {}))
        status = "partial" if (coverage.get("failures") or coverage.get("truncated") or upstream_errors
                                or coverage.get("input_status") in {"partial", "failed", "cancelled"}
                                or any(item.get("reason") == "original_capture_not_supplied"
                                       for item in manifest["not_included"])) else "completed"
        return OperationResult(status, data=data,
                               errors=upstream_errors, coverage=coverage, operation_id=context.operation_id)
    def safe_export(owner, request, content, context):
        try:
            return export(owner, request, content, context)
        except InterruptedError:
            return OperationResult("cancelled", coverage={"truncated": True}, operation_id=context.operation_id)
    engine.register_operation("export", tracked_handler("export", safe_export))
