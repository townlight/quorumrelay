"""Prepare explicitly supplied legislative text; never import into Legistar."""
import base64
from hashlib import sha256
import io
import secrets
from time import monotonic

from ..models import Bounds, Error, OperationResult
from ..storage import operation_cancelled
from .identification import configured_source, validate_source

FORMAT = "legistar-legislative-text"
DOCUMENTATION = "https://support.granicus.com/articles/How_To/Drafting-Legislative-Files-Legistar-Text-Editor"


def export_text(owner, request, content, context):
    from ..interchange import _save_artifact

    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if source.provider != "legistar" or request.get("format") != FORMAT or content is not None:
        raise ValueError("Use explicit title/body fields for Legistar legislative text preparation.")
    if not context.allows("export", namespace):
        return OperationResult("failed", errors=(Error("permission_denied", "Export namespace is not authorized."),))
    bounds = Bounds(**request.get("bounds", {}))
    if bounds.checkpoint or bounds.date_from or bounds.date_to:
        raise ValueError("Single-file preparation has no date filter or continuation.")
    if "stream" in request and type(request["stream"]) is not bool:
        raise ValueError("stream requires a boolean.")
    encoding = request.get("text_encoding")
    if encoding not in {"ascii", "cp1252", "utf-8"}:
        raise ValueError("Explicitly select the destination text encoding: ascii, cp1252 or utf-8.")
    deadline = monotonic() + bounds.deadline_seconds
    limit = min(bounds.parser_bytes, bounds.transfer_bytes)

    def stopped():
        if operation_cancelled(owner.storage, context):
            raise InterruptedError
        if monotonic() >= deadline:
            raise ValueError("Legislative text preparation exceeded its deadline.")

    def section(key):
        value = request.get(key)
        if (not isinstance(value, str) or not value.strip() or len(value) > limit
                or any(ord(c) < 32 and c not in "\r\n\t" or ord(c) == 127 for c in value)):
            raise ValueError("Supply bounded nonempty plain-text title and body without control characters.")
        lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if any(line.lstrip().startswith("..") for line in lines):
            raise ValueError("Section-like lines in supplied text are ambiguous; no escaping rule is documented.")
        return "\r\n".join(lines)

    try:
        stopped()
        payload = ("..title\r\n" + section("title") + "\r\n..body\r\n" + section("body") + "\r\n").encode(encoding)
        if len(payload) > limit:
            raise ValueError("Legislative text exceeds configured byte bounds.")
        stopped()
        manifest = {"format": FORMAT, "provider": "legistar", "namespace": namespace,
            "filename": "legislative-text.txt", "content_type": "text/plain", "encoding": encoding,
            "byte_length": len(payload), "sha256": sha256(payload).hexdigest(), "documentation": DOCUMENTATION,
            "vendor_transfer_performed": False, "vendor_import_accepted": False,
            "projection_losses": [
                "Only explicit title and body text; no IDs, parents, dates, status, attachments or provenance embedded.",
                "Line endings normalized to CRLF; section-like input is rejected rather than escaped.",
                "Vendor guide does not specify text encoding; caller selection requires destination compatibility.",
                "Local Text Editor import preparation only; no meeting/media migration, remote import or association."]}
        data = {"format": FORMAT, "manifest": manifest}
        if request.get("stream"):
            artifact_id = secrets.token_hex(24)
            metadata = _save_artifact(owner, "artifacts", artifact_id, io.BytesIO(payload),
                {"artifact_id": artifact_id, "format": FORMAT, "manifest": manifest, "namespaces": [namespace]},
                context=context, max_bytes=limit, check_bounds=stopped)
            data.update(artifact_id=artifact_id, storage_reference=metadata.get("storage_reference",
                {"kind": "civic_export_artifact", "artifact_id": artifact_id}))
        else:
            data["content_base64"] = base64.b64encode(payload).decode()
        stopped()
        return OperationResult("completed", data, coverage={"scope": "local legislative text file preparation",
            "source_complete": False, "vendor_import_accepted": False,
            "projection_losses": manifest["projection_losses"]}, operation_id=context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", operation_id=context.operation_id)
