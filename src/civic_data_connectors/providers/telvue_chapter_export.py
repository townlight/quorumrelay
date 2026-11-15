"""Local chapter CSV preparation for the documented CloudCast 4.1 intake."""
import base64
import csv
from hashlib import sha256
import io
import re
import secrets
from time import monotonic

from ..models import Bounds, Error, OperationResult
from ..storage import operation_cancelled
from .identification import configured_source, validate_source

FORMAT = "telvue-cloudcast-4.1-chapters-csv"
DOCUMENTATION = "https://telvue.com/wp-content/uploads/2014/06/CloudCastUserManual_v4_1.pdf"


def export_chapters(owner, request, content, context):
    from ..interchange import _save_artifact

    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if source.provider != "telvue" or request.get("format") != FORMAT or content is not None:
        raise ValueError("Select the explicit historical CloudCast 4.1 chapter CSV format.")
    if not context.allows("export", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Export namespace is not authorized."),))
    bounds = Bounds(**request.get("bounds", {}))
    chapters = request.get("chapters")
    if (bounds.checkpoint or bounds.date_from or bounds.date_to
            or not isinstance(chapters, list) or not chapters or len(chapters) > bounds.max_records):
        raise ValueError("Supply explicit chapters within max_records; dates and continuation are not supported.")
    if "stream" in request and type(request["stream"]) is not bool:
        raise ValueError("stream must be a boolean.")
    deadline = monotonic() + bounds.deadline_seconds
    limit = min(bounds.parser_bytes, bounds.transfer_bytes)

    def stopped():
        if operation_cancelled(owner.storage, context):
            raise InterruptedError
        if monotonic() >= deadline:
            raise ValueError("Chapter preparation exceeded its deadline.")

    def text(value, required=False):
        if (not isinstance(value, str) or len(value) > limit or (required and not value.strip())
                or any(ord(c) < 32 and c not in "\n\r\t" for c in value) or "\x7f" in value):
            raise ValueError("Chapter fields require bounded plain text without control characters.")
        return value

    def timecode(value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{2}:[0-5][0-9]:[0-5][0-9]", value):
            raise ValueError("Supply explicit HH:MM:SS chapter times with two-digit hours.")
        hours, minutes, seconds = map(int, value.split(":"))
        return hours * 3600 + minutes * 60 + seconds

    try:
        stopped()
        payload = bytearray()
        for chapter in chapters:
            stopped()
            if not isinstance(chapter, dict) or set(chapter) - {"start", "end", "title", "summary", "description"}:
                raise ValueError("Use only documented chapter CSV fields.")
            start, end = chapter.get("start"), chapter.get("end")
            if timecode(end) < timecode(start):
                raise ValueError("A chapter end cannot precede its start.")
            stream = io.StringIO(newline="")
            csv.writer(stream, lineterminator="\r\n").writerow([
                start, end, text(chapter.get("title"), True),
                text(chapter.get("summary", "")), text(chapter.get("description", ""))])
            row = stream.getvalue().encode("utf-8")
            if len(payload) + len(row) > limit:
                raise ValueError("Chapter CSV exceeds the configured byte bound.")
            payload.extend(row)
        stopped()
        manifest = {"format": FORMAT, "provider": "telvue", "product": "CloudCast",
            "documented_version": "4.1.0 / June 2014", "namespace": namespace,
            "filename": "chapters.csv", "content_type": "text/csv; charset=utf-8",
            "byte_length": len(payload), "sha256": sha256(payload).hexdigest(),
            "chapter_count": len(chapters), "documentation": DOCUMENTATION,
            "vendor_transfer_performed": False, "vendor_import_accepted": False,
            "projection_losses": [
                "Headerless Start, End, Title, Summary, Description only; no IDs, relationships, provenance or files.",
                "Explicit chapter times only; no timestamps inferred from meeting dates or agenda ordering.",
                "Historical CloudCast 4.1 format; current Connect/CloudCast applicability is unverified.",
                "UTF-8 output is a local encoding choice; the historical manual does not specify an encoding.",
                "No remote upload, chapter creation, recording or meeting association is performed."]}
        data = {"format": FORMAT, "manifest": manifest}
        if request.get("stream"):
            artifact_id = secrets.token_hex(24)
            metadata = _save_artifact(owner, "artifacts", artifact_id, io.BytesIO(payload),
                {"artifact_id": artifact_id, "format": FORMAT, "manifest": manifest,
                 "namespaces": [namespace]}, context=context, max_bytes=limit)
            data.update(artifact_id=artifact_id, storage_reference=metadata.get("storage_reference",
                {"kind": "civic_export_artifact", "artifact_id": artifact_id}))
        else:
            data["content_base64"] = base64.b64encode(payload).decode()
        return OperationResult("completed", data, coverage={"scope": "local historical CloudCast chapter CSV preparation",
            "source_complete": False, "vendor_import_accepted": False,
            "projection_losses": manifest["projection_losses"]}, operation_id=context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", operation_id=context.operation_id)
