"""Scoped file staging and immutable digest-bound write references."""

from __future__ import annotations

import base64
import hashlib
import io
import re
import uuid


def stage_write_file(engine, stream, *, context, filename="upload.bin",
                     content_type="application/octet-stream", max_bytes=200 * 1024 * 1024):
    """Stage SDK/CLI input without putting large bytes into request/plan JSON."""
    from .interchange import stage_input
    return stage_input(engine, uuid.uuid4().hex, stream, filename=filename,
                       content_type=content_type, context=context, max_bytes=max_bytes)["file_handle"]


def resolve_write_files(engine, files, *, context, bounds):
    """Resolve only caller-scoped handles, never filenames or arbitrary paths."""
    from .interchange import open_input
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
        else:
            encoded = part["content_base64"]
            if not isinstance(encoded, str) or len(encoded) > ((bounds.transfer_bytes + 2) // 3) * 4:
                raise ValueError("The file exceeds the transfer byte limit.")
            data = base64.b64decode(encoded, validate=True)
            handle = stage_write_file(engine, io.BytesIO(data), context=context,
                                      filename=part["filename"], content_type=part["content_type"],
                                      max_bytes=bounds.transfer_bytes)
        item = storage.get("service_files", handle, scope=context.scope)
        if item is None:
            raise ValueError("The file handle is unavailable in this caller scope.")
        if item is not None and item.value.get("purpose") is None and "reference" in item.value:
            # Published SDK write uploads predate generic input metadata.
            reference = item.value["reference"]
        else:
            _, stream = open_input(engine, handle, context=context)
            stream.close()
            reference = item.value["storage_reference"]
        size, digest = reference.get("byte_length"), reference.get("sha256")
        if (type(size) is not int or size < 0 or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Capture storage must provide exact byte_length and SHA256 for write files.")
        total += size
        if total > bounds.transfer_bytes:
            raise ValueError("The submitted file parts exceed the transfer byte limit.")
        with open_write_file(storage, reference, scope=context.scope):
            pass
        result.append({**{k: part[k] for k in metadata}, "reference": reference})
    return result


def open_write_input(engine, reference, *, context):
    """Open exact plan-bound bytes; upload expiry does not expire a durable plan.

    The coordinator rechecks current write policy. Handle-shaped plans produced
    before durable-reference restoration remain readable only in their saved
    scope and only when both storage metadata and bytes match the bound digest.
    """
    if "file_handle" in reference:
        if reference.get("scope") != context.scope:
            raise ValueError("The immutable write file is outside this caller scope.")
        item = engine.storage.get("service_files", reference["file_handle"], scope=context.scope)
        if item is None or item.value.get("purpose") != "input":
            raise ValueError("The planned file is unavailable in this caller scope.")
        stored = item.value["storage_reference"]
        for key in ("sha256", "byte_length"):
            if item.value.get(key) != reference[key] or stored.get(key) != reference[key]:
                raise ValueError("The planned file no longer matches its bound digest/size.")
        reference = stored
    return open_write_file(engine.storage, reference, scope=context.scope)


def open_write_file(storage, reference, *, scope):
    """Verify a scoped immutable snapshot and rewind the same verified stream."""
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
