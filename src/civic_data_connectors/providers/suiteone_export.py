"""Prepare an ordinary HTML document for SuiteOne's manual bookmarking intake."""

import base64
from hashlib import sha256
from html import escape
import io
import secrets
from time import monotonic

from ..models import Bounds, Error, OperationResult
from ..storage import operation_cancelled
from .identification import configured_source, validate_source

FORMAT = "suiteone-bookmark-document"
DOCUMENTATION = "https://getsuiteone.com/wp-content/uploads/2021/08/S1_BookmarksUpdate_2021.pdf"


def export_document(owner, request, content, context):
    from ..interchange import _save_artifact

    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if source.provider != "suiteone-media" or request.get("format") != FORMAT or content is not None:
        raise ValueError("Use explicit plain text for SuiteOne HTML document preparation.")
    if not context.allows("export", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Export namespace is not authorized."),))
    bounds = Bounds(**request.get("bounds", {}))
    if bounds.checkpoint or bounds.date_from or bounds.date_to:
        raise ValueError("This explicit document has no dates or continuation; select its text before exporting.")
    if "stream" in request and type(request["stream"]) is not bool:
        raise ValueError("stream must be a boolean.")
    title, paragraphs = request.get("title"), request.get("paragraphs")
    if (not isinstance(title, str) or not title.strip() or len(title) > 1024
            or not isinstance(paragraphs, list) or not paragraphs or len(paragraphs) > bounds.max_records):
        raise ValueError("Supply a bounded title and nonempty plain-text paragraphs within max_records.")
    deadline = monotonic() + bounds.deadline_seconds

    def stopped():
        if operation_cancelled(owner.storage, context):
            raise InterruptedError
        if monotonic() >= deadline:
            raise ValueError("Document preparation exceeded its deadline.")

    def checked(value):
        if (not isinstance(value, str) or not value.strip() or len(value) > bounds.parser_bytes
                or any(ord(c) < 32 and c not in "\n\r\t" for c in value) or "\x7f" in value):
            raise ValueError("Document fields require nonempty bounded plain text without control characters.")
        return escape(value, quote=True)

    try:
        stopped()
        safe_title = checked(title)
        chunks = ['<!doctype html>\n<html><head><meta charset="utf-8"><title>', safe_title,
                  '</title></head><body><h1>', safe_title, '</h1>\n']
        size = sum(len(c.encode("utf-8")) for c in chunks)
        # Bound escaped output as it is produced, including the closing tags.
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        for paragraph in paragraphs:
            stopped()
            chunk = '<p>' + checked(paragraph).replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br>') + '</p>\n'
            size += len(chunk.encode("utf-8"))
            if size + len('</body></html>\n') > limit:
                raise ValueError("Escaped HTML exceeds the local output byte bound.")
            chunks.append(chunk)
        chunks.append('</body></html>\n')
        payload = ''.join(chunks).encode("utf-8")
        stopped()
        manifest = {"format": FORMAT, "provider": source.provider, "namespace": namespace,
            "filename": "bookmark-document.html", "content_type": "text/html; charset=utf-8",
            "byte_length": len(payload), "sha256": sha256(payload).hexdigest(),
            "documentation": DOCUMENTATION, "vendor_transfer_performed": False,
            "vendor_import_accepted": False, "automatic_bookmarks_created": False,
            "projection_losses": [
                "Plain document text only; native IDs, relationships, attachments and provenance are not an interchange bundle.",
                "No Liberty exported format, timestamps, speakers or recording association is generated.",
                "Upload as an ordinary HTML document; add bookmarks and set play times manually in SuiteOne.",
                "Do not select Liberty Exported Format or Replace Existing Bookmarks for this document."]}
        data = {"format": FORMAT, "manifest": manifest}
        if request.get("stream"):
            artifact_id = secrets.token_hex(24)
            metadata = _save_artifact(owner, "artifacts", artifact_id, io.BytesIO(payload),
                {"artifact_id": artifact_id, "format": FORMAT, "manifest": manifest,
                 "namespaces": [namespace]}, context=context, max_bytes=limit, check_bounds=stopped)
            data.update(artifact_id=artifact_id, storage_reference=metadata.get("storage_reference",
                {"kind": "civic_export_artifact", "artifact_id": artifact_id}))
        else:
            data["content_base64"] = base64.b64encode(payload).decode()
        return OperationResult("completed", data, coverage={"scope": "local ordinary HTML document preparation",
            "source_complete": False, "vendor_import_accepted": False,
            "projection_losses": manifest["projection_losses"]}, operation_id=context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", operation_id=context.operation_id)
