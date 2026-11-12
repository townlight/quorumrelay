"""Bounded transport upload sessions; final opaque inputs use the core input helpers."""

from __future__ import annotations

import base64
import tempfile
import time
from threading import Lock
from uuid import uuid4

CHUNK_BYTES = 256 * 1024
FILE_OPERATIONS = frozenset({"normalize", "discover", "fetch", "import_preview", "import_bundle", "plan_write", "export"})


def allowed(context):
    return any(context.allows(operation) for operation in FILE_OPERATIONS)


class InputUploads:
    """No public path, append-only bytes, retry-safe offsets, scoped TTL and bounded disk usage."""

    def __init__(self, engine, *, max_bytes=200 * 1024 * 1024):
        self.engine, self.max_bytes = engine, max_bytes
        self.values, self.lock = {}, Lock()

    def _prune(self):
        for key, item in list(self.values.items()):
            if item["expires_at"] <= time.time():
                item["stream"].close()
                del self.values[key]

    def begin(self, *, filename, content_type, byte_length, context):
        if not allowed(context):
            raise ValueError("Caller policy does not permit file input.")
        if type(byte_length) is not int or not 0 <= byte_length <= self.max_bytes:
            raise ValueError("Upload byte length exceeds the configured transfer limit.")
        if (not isinstance(filename, str) or not filename or len(filename) > 255 or "\0" in filename
                or not isinstance(content_type, str) or len(content_type) > 255
                or any(c in content_type for c in "\r\n")):
            raise ValueError("Invalid upload filename or content type metadata.")
        with self.lock:
            self._prune()
            if len(self.values) >= 16 or sum(x["byte_length"] for x in self.values.values()) + byte_length > 1024**3:
                raise ValueError("Too many pending uploads; finish or abort an existing upload.")
            identifier = uuid4().hex + uuid4().hex
            self.values[(context.scope, identifier)] = {
                "stream": tempfile.TemporaryFile(), "filename": filename, "content_type": content_type,
                "byte_length": byte_length, "offset": 0, "expires_at": time.time() + 900,
            }
            return {"upload_id": identifier, "byte_length": byte_length, "max_chunk_bytes": CHUNK_BYTES}

    def _get(self, identifier, context):
        if not allowed(context):
            raise ValueError("Caller policy no longer permits file input.")
        self._prune()
        item = self.values.get((context.scope, identifier))
        if item is None:
            raise ValueError("The upload is unavailable or expired in this caller scope.")
        return item

    def chunk(self, identifier, *, offset, content_base64, context):
        if not isinstance(content_base64, str) or len(content_base64) > 4 * ((CHUNK_BYTES + 2) // 3):
            raise ValueError("Upload chunk exceeds 256 KiB.")
        content = base64.b64decode(content_base64, validate=True)
        if len(content) > CHUNK_BYTES or type(offset) is not int or offset < 0:
            raise ValueError("Invalid chunk or offset.")
        with self.lock:
            item = self._get(identifier, context)
            if offset < item["offset"] and offset + len(content) <= item["offset"]:
                item["stream"].seek(offset)
                if item["stream"].read(len(content)) != content:
                    raise ValueError("A retried chunk differs from its previously accepted bytes.")
                return {"upload_id": identifier, "offset": item["offset"]}
            if offset != item["offset"] or offset + len(content) > item["byte_length"]:
                raise ValueError("Chunk offset or total byte length does not match the upload.")
            item["stream"].seek(offset)
            item["stream"].write(content)
            item["offset"] += len(content)
            return {"upload_id": identifier, "offset": item["offset"]}

    def finish(self, identifier, *, context):
        from ..interchange import stage_input
        with self.lock:
            item = self._get(identifier, context)
            if item["offset"] != item["byte_length"]:
                raise ValueError("The upload is incomplete.")
            item["stream"].seek(0)
            result = stage_input(self.engine, identifier, item["stream"], filename=item["filename"],
                                 content_type=item["content_type"], context=context, max_bytes=self.max_bytes)
            item["stream"].close()
            del self.values[(context.scope, identifier)]
            return result

    def abort(self, identifier, *, context):
        with self.lock:
            item = self._get(identifier, context)
            item["stream"].close()
            del self.values[(context.scope, identifier)]
        return {"upload_id": identifier, "aborted": True}

    def close(self):
        with self.lock:
            for item in self.values.values():
                item["stream"].close()
            self.values.clear()
