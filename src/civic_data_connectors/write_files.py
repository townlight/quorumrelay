"""Scoped file staging and immutable digest-bound write references."""

from __future__ import annotations

import base64
import hashlib
import io
import re
import uuid


def stage_write_file(engine, stream, *, context, max_bytes=200 * 1024 * 1024):
    """Stage SDK/CLI input without putting large bytes into request/plan JSON."""
    storage = engine.storage
    if not callable(getattr(storage, "save_capture", None)):
        raise ValueError("Write files require scoped capture storage.")
    reference = storage.save_capture(stream, scope=context.scope, max_bytes=max_bytes)
    handle = uuid.uuid4().hex + uuid.uuid4().hex
    storage.put("service_files", handle, {"reference": reference}, scope=context.scope, create_only=True)
    return handle


def resolve_write_files(engine, files, *, context, bounds):
    """Resolve only caller-scoped handles, never filenames or arbitrary paths."""
    storage = engine.storage
    if files and not (callable(getattr(storage, "save_capture", None))
                      and callable(getattr(storage, "open_capture", None))):
        raise ValueError("Write file parts require scoped capture storage.")
    result, total = [], 0
    for part in files:
        if not isinstance(part, dict):
            raise ValueError("A write file part must be an object.")
        metadata = {"part", "filename", "content_type"}
        if set(part) not in (metadata | {"file_handle"}, metadata | {"content_base64"}):
            raise ValueError("A file requires part, filename, content_type and exactly one file_handle/content_base64.")
        if "file_handle" in part:
            handle = part["file_handle"]
            if not isinstance(handle, str) or not re.fullmatch(r"[0-9a-f]{64}", handle):
                raise ValueError("The file handle is unavailable in this caller scope.")
            item = storage.get("service_files", handle, scope=context.scope)
            if item is None:
                raise ValueError("The file handle is unavailable in this caller scope.")
            reference = item.value["reference"]
        else:
            encoded = part["content_base64"]
            if not isinstance(encoded, str) or len(encoded) > ((bounds.transfer_bytes + 2) // 3) * 4:
                raise ValueError("The file exceeds the transfer byte limit.")
            data = base64.b64decode(encoded, validate=True)
            reference = storage.save_capture(io.BytesIO(data), scope=context.scope,
                                             max_bytes=bounds.transfer_bytes)
        size = reference.get("byte_length")
        digest = reference.get("sha256")
        if (type(size) is not int or size < 0 or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Capture storage must provide exact byte_length and SHA256 for write files.")
        total += size
        if total > bounds.transfer_bytes:
            raise ValueError("The submitted file parts exceed the transfer byte limit.")
        # Check availability/integrity now; commit repeats this using the same reference, not the handle's head.
        with open_write_file(storage, reference, scope=context.scope):
            pass
        result.append({**{k: part[k] for k in metadata}, "reference": reference})
    return result


def open_write_file(storage, reference, *, scope):
    """Verify a bounded snapshot before sending; rewind the same verified stream."""
    stream = storage.open_capture(reference, scope=scope)
    try:
        digest, size, maximum = hashlib.sha256(), 0, reference["byte_length"]
        while chunk := stream.read(min(1024 * 1024, maximum - size + 1)):
            size += len(chunk)
            if size > maximum:
                raise ValueError("The immutable write file no longer matches its planned byte length.")
            digest.update(chunk)
        if size != maximum or digest.hexdigest() != reference["sha256"]:
            raise ValueError("The immutable write file no longer matches its planned digest/size.")
        stream.seek(0)
        return stream
    except BaseException:
        stream.close()
        raise
