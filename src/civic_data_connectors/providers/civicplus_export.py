"""Prepare named historical import files; never transfer files to a vendor."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import secrets
import tempfile
import zipfile
from contextlib import ExitStack
from datetime import date
from time import monotonic

from ..models import Bounds, Error, OperationResult
from .identification import configured_source, validate_source

FORMAT = "civicplus-historical-files"
DOCUMENTATION = "https://www.civicplus.help/meetings-select/docs/historical-imports"
VERIFIED_TOKENS = {"Agenda", "Agenda Packet", "Minutes"}
UNRESOLVED_TOKENS = {"Packet", "Notice", "Notices", "Other", "Media", "Audio/Video"}


def _component(value):
    if (not isinstance(value, str) or not value or value != value.strip()
            or re.search(r'[<>:"/\\|?*_\x00-\x1f]', value) or value.endswith(".") or value in {".", ".."}):
        raise ValueError("Filename metadata must be nonempty and unambiguous, without path or underscore delimiters.")
    return value


def _validate_pdf(stream):
    import pdfplumber
    if not stream.read(8).startswith(b"%PDF-"):
        raise ValueError("A PDF input must contain PDF bytes, not merely a filename or MIME label.")
    stream.seek(0)
    try:
        with pdfplumber.open(stream) as pdf:
            if not pdf.pages:
                raise ValueError("A historical meeting PDF must contain a readable page tree.")
    except Exception:
        raise ValueError("The historical meeting PDF could not be parsed as a readable document.") from None
    stream.seek(0)


def export_historical(owner, request, content, context):
    """Create a portable ZIP of explicit meeting files and an honest loss manifest."""
    from ..interchange import _save_artifact, open_input
    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if source.provider != "civicplus-select" or request.get("format", FORMAT) != FORMAT:
        raise ValueError("This mapping prepares CivicPlus Select historical files only.")
    if content is not None:
        raise ValueError("Historical export uses explicit scoped file handles or small inline files.")
    if not context.allows("export", namespace) or "export_attachments" not in context.authorization:
        return OperationResult("failed", errors=(Error("permission_denied",
            "Historical file export requires export and export_attachments for the exact source namespace."),),
            operation_id=context.operation_id)
    bounds, meeting = Bounds(**request.get("bounds", {})), request.get("meeting")
    if not isinstance(meeting, dict):
        raise ValueError("Explicit meeting body, meeting_type and meeting_date are required.")
    body, meeting_type = _component(meeting.get("body")), _component(meeting.get("meeting_type"))
    if source.body and body != source.body:
        raise ValueError("Historical export body conflicts with the explicitly configured source body.")
    meeting_day = meeting.get("meeting_date")
    if not isinstance(meeting_day, str) or date.fromisoformat(meeting_day).isoformat() != meeting_day:
        raise ValueError("meeting_date must be an explicit YYYY-MM-DD meeting date.")
    day_token = date.fromisoformat(meeting_day).strftime("%m_%d_%Y")
    if ((bounds.date_from and meeting_day < bounds.date_from)
            or (bounds.date_to and meeting_day > bounds.date_to)):
        raise ValueError("Historical meeting date is outside the caller's date bounds.")
    files = request.get("files")
    if not isinstance(files, list) or not files or len(files) > min(bounds.max_records, 6):
        raise ValueError("One event requires one to six explicit files within max_records.")
    if "stream" in request and type(request["stream"]) is not bool:
        raise ValueError("stream must be a JSON boolean.")
    delivery = "storage" if request.get("stream") else "inline"
    if any(isinstance(part, dict) and part.get("file_type") in UNRESOLVED_TOKENS for part in files):
        return OperationResult("unsupported", errors=(Error("provider_filename_mapping_unverified",
            "The exact historical-import filename token is unverified for this file type. "
            "Known examples map Agenda, Agenda Packet and Minutes. Obtain the exact provider token before preparing other file types.",
            source=source.url),), coverage={"scope": "filename mapping gap; no files exported",
            "vendor_import_accepted": False}, operation_id=context.operation_id)
    deadline, total, pdf_count, media_count = monotonic() + bounds.deadline_seconds, 0, 0, 0
    manifest = {"format": FORMAT, "provider": source.provider, "namespace": namespace,
                "delivery_container": "ZIP wrapper; extract named files before consultant intake; vendor ZIP import is not established",
                "meeting": meeting, "files": [], "documentation": DOCUMENTATION,
                "vendor_transfer_performed": False, "vendor_import_accepted": False,
                "projection_losses": ["Agenda item structure and bookmarks are not imported by this workflow.",
                    "Media timestamps, supplied captions, votes, relationships, revisions and other normalized fields have no filename mapping.",
                    "Meeting metadata beyond body/type/date is retained here only; it is not a vendor input field.",
                    "MP4 filename tokens are not verified; media file preparation remains incomplete.",
                    "Vendor optimization can change PDF bytes after import; local originals remain exact."],
                "local_transfer_limit": bounds.transfer_bytes,
                "vendor_size_limit": "not_documented", "consultant_processing_required": True}
    names, digests, tokens = set(), set(), set()
    try:
        with ExitStack() as stack:
            output = stack.enter_context(tempfile.TemporaryFile())
            archive = stack.enter_context(zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED))
            for part in files:
                if context.check_cancelled():
                    raise InterruptedError
                if monotonic() >= deadline:
                    raise ValueError("Historical export exceeded its deadline.")
                if not isinstance(part, dict) or part.get("file_type") not in VERIFIED_TOKENS:
                    raise ValueError("The supplied FileType has no recorded historical-import contract.")
                token = part["file_type"]
                if token in tokens:
                    raise ValueError("Duplicate per-event FileType would produce an ambiguous import.")
                tokens.add(token)
                if ("file_handle" in part) == ("content_base64" in part):
                    raise ValueError("Each file requires exactly one scoped file_handle or content_base64.")
                if "file_handle" in part:
                    previous = owner.storage.get("service_files", part["file_handle"], scope=context.scope) if owner.storage else None
                    if previous and "reference" in previous.value and previous.value.get("purpose") != "input":
                        raise ValueError("Historical export requires a new generic file upload with MIME and expiry metadata; legacy input handles remain usable by their original operations.")
                    metadata, stream = open_input(owner, part["file_handle"], context=context)
                    stack.enter_context(stream)
                    mime = part.get("content_type", metadata["content_type"])
                    if mime != metadata["content_type"]:
                        raise ValueError("File MIME metadata conflicts with the scoped upload.")
                    length = metadata["byte_length"]
                else:
                    encoded = part["content_base64"]
                    if not isinstance(encoded, str) or len(encoded) > ((bounds.parser_bytes + 2) // 3) * 4:
                        raise ValueError("Inline file exceeds parser bounds; use a scoped upload handle.")
                    payload = base64.b64decode(encoded, validate=True)
                    length, stream, mime = len(payload), io.BytesIO(payload), part.get("content_type")
                total += length
                if total > bounds.transfer_bytes:
                    raise ValueError("Historical files exceed the local transfer bound.")
                if mime == "application/pdf":
                    pdf_count += 1
                    if token in {"Media", "Audio/Video"}:
                        raise ValueError("Media FileType requires MP4 bytes.")
                    _validate_pdf(stream)
                    extension = ".pdf"
                elif mime == "video/mp4":
                    media_count += 1
                    if token not in {"Media", "Audio/Video"}:
                        raise ValueError("The supplied PDF FileType cannot name an MP4 file.")
                    extension = ".mp4"
                else:
                    raise ValueError("Historical files require verified PDF or MP4 content.")
                if pdf_count > 5 or media_count > 1:
                    raise ValueError("One event permits at most five PDFs and one media file.")
                target = f"{body}_{meeting_type}_{token}_{day_token}{extension}"
                name = target
                if len(name.encode("utf-8")) > 240 or name.casefold() in names:
                    raise ValueError("The generated import filename collides or exceeds local portability bounds.")
                names.add(name.casefold())
                digest, copied = hashlib.sha256(), 0
                with archive.open(name, "w") as entry:
                    while chunk := stream.read(min(1024 * 1024, bounds.transfer_bytes - copied + 1)):
                        if context.check_cancelled():
                            raise InterruptedError
                        if monotonic() >= deadline or copied + len(chunk) > length:
                            raise ValueError("Historical file changed or exceeded deadline/transfer bounds.")
                        copied += len(chunk)
                        digest.update(chunk)
                        entry.write(chunk)
                if copied != length or digest.hexdigest() in digests:
                    raise ValueError("Historical file length changed or duplicate bytes were supplied.")
                digests.add(digest.hexdigest())
                manifest["files"].append({"archive_path": name, "target_filename": target,
                    "file_type": token, "content_type": mime, "byte_length": copied, "sha256": digest.hexdigest(),
                    "unmapped_metadata": {key: value for key, value in part.items()
                        if key not in {"file_type", "content_type", "file_handle", "content_base64"}}})
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))
            archive.close()
            if context.check_cancelled():
                raise InterruptedError
            size = output.tell()
            if size > bounds.transfer_bytes:
                raise ValueError("Historical archive plus manifest exceeds the local transfer bound.")
            output.seek(0)
            if delivery == "storage":
                artifact_id = secrets.token_hex(24)
                metadata = _save_artifact(owner, "artifacts", artifact_id, output,
                    {"artifact_id": artifact_id, "format": FORMAT, "manifest": manifest,
                     "requires_attachment_grant": True, "namespaces": [namespace]},
                    context=context, max_bytes=bounds.transfer_bytes)
                data = {"format": FORMAT, "artifact_id": artifact_id, "manifest": manifest,
                        "storage_reference": metadata.get("storage_reference",
                            {"kind": "civic_export_artifact", "artifact_id": artifact_id})}
            else:
                if size > bounds.parser_bytes:
                    raise ValueError("Use stream=true for archives above the parser response bound.")
                data = {"format": FORMAT, "content_base64": base64.b64encode(output.read()).decode(),
                        "manifest": manifest}
        return OperationResult("completed", data,
            coverage={"scope": "explicit files for one historical meeting", "vendor_import_accepted": False,
                      "source_complete": False, "projection_losses": manifest["projection_losses"]},
            operation_id=context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", operation_id=context.operation_id)
