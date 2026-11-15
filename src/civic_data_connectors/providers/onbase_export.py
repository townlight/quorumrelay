"""Prepare a configured Normal Tagged DIP file bundle; never run OnBase."""

import base64
import hashlib
import io
import json
import re
import secrets
import tempfile
import zipfile
from contextlib import ExitStack
from time import monotonic

from ..models import Bounds, Error, OperationResult
from .identification import configured_source, validate_source

FORMAT = "onbase-tagged-dip-files"


def _line(value, *, maximum=4096):
    if (not isinstance(value, str) or not value or len(value) > maximum
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError("DIP fields require bounded nonempty single-line strings without control characters.")
    return value


def _tag(value):
    value = _line(value, maximum=20)
    if not value.endswith(":") or not value.isascii() or value.strip() != value:
        raise ValueError("DIP tags require explicit ASCII names including a trailing colon, at most 20 characters.")
    return value


def export_dip(owner, request, content, context):
    from ..interchange import _save_artifact, open_input

    source = configured_source(request["source"])
    namespace = validate_source(source, context)
    if source.provider != "onbase" or request.get("format") != FORMAT or content is not None:
        raise ValueError("Use explicit files and mappings for OnBase tagged DIP preparation.")
    if not context.allows("export", namespace) or "export_attachments" not in context.authorization:
        return OperationResult("failed", errors=(Error("permission_denied",
            "DIP export requires export and export_attachments for the source namespace."),),
            operation_id=context.operation_id)
    bounds = Bounds(**request.get("bounds", {}))
    files, documents = request.get("files"), request.get("documents")
    if (not isinstance(files, list) or not isinstance(documents, list) or not files
            or len(files) != len(documents) or len(files) > bounds.max_records):
        raise ValueError("Supply one explicit document mapping for every file within max_records.")
    if "stream" in request and type(request["stream"]) is not bool:
        raise ValueError("stream requires a boolean.")
    tags = request.get("tags")
    if not isinstance(tags, dict) or set(tags) != {"begin", "document_type", "file_type", "file_name"}:
        raise ValueError("Supply exact configured begin/document_type/file_type/file_name DIP tags.")
    tags = {key: _tag(value) for key, value in tags.items()}
    if len(set(tags.values())) != len(tags) or any(
            a.startswith(b) for a in tags.values() for b in tags.values() if a != b):
        raise ValueError("DIP tags must be distinct and unambiguous.")
    # An explicit Windows codepage matches the destination process's index-file
    # decoding setting; never silently replace characters during encoding.
    encoding = request.get("index_encoding")
    if encoding not in {"ascii", "utf-8", "cp1252"}:
        raise ValueError("Select the destination index encoding: ascii, utf-8 or cp1252.")
    deadline = monotonic() + bounds.deadline_seconds

    def check_output_bounds():
        if context.check_cancelled():
            raise InterruptedError
        if monotonic() >= deadline:
            raise ValueError("File preparation exceeded its deadline.")

    fields = [{"tag": tags[key], "keyword_type": keyword} for key, keyword in (
        ("begin", ">>Begin Document, Exclusive"), ("document_type", ">>Document Type"),
        ("file_type", ">>File Type"), ("file_name", ">>File Name"))]
    manifest = {"format": FORMAT, "namespace": namespace, "process": "Normal Tagged DIP; no FTP or In-Place",
        "configuration": {"field_type": "Tagged Fields", "field_delimiters": "None",
            "separator": "New Line", "index_encoding": encoding, "field_order": fields},
        "files": [], "vendor_transfer_performed": False, "vendor_import_accepted": False,
        "projection_losses": ["No Agenda meeting/item relationship is created by this file format.",
            "Only explicitly mapped Document Type, File Type and keyword values enter the DIP index.",
            "Other supplied metadata stays in the local manifest; revisions, votes and media timecodes are not inferred.",
            "Extract all files before processing; configure the exact case-sensitive tags and destination types.",
            "Actual vendor Test Only/Verification Report and batch commit are separate operations, not performed here."]}
    mappings, names, indices, configured_keywords = [], set(), set(), {}
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("Document mappings must be objects.")
        index = document.get("file_index")
        if type(index) is not int or not 0 <= index < len(files) or index in indices:
            raise ValueError("Document mappings require unique in-range file_index values.")
        indices.add(index)
        name = _line(document.get("filename"), maximum=120)
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. -]*", name) or name.endswith((".", " "))
                or name in {".", ".."} or name.casefold() in {"index.txt", "manifest.json"}
                or name.split(".")[0].rstrip(" .").upper() in {"CON", "PRN", "AUX", "NUL",
                    *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
                or name.casefold() in names):
            raise ValueError("DIP filenames must be unique safe portable basenames; no path sanitization is inferred.")
        names.add(name.casefold())
        document_type = _line(document.get("document_type"))
        file_type = document.get("file_type_number")
        if type(file_type) is not int or file_type <= 0:
            raise ValueError("Supply the destination's configured positive file_type_number; none is guessed from MIME.")
        lines = [tags["begin"], tags["document_type"] + document_type, tags["file_type"] + str(file_type)]
        keywords = document.get("keywords", [])
        if not isinstance(keywords, list):
            raise ValueError("keywords requires explicit tag/keyword_type/value entries.")
        for keyword in keywords:
            if not isinstance(keyword, dict) or set(keyword) != {"tag", "keyword_type", "value"}:
                raise ValueError("Each keyword requires exactly tag, keyword_type and value.")
            tag, kind, value = _tag(keyword["tag"]), _line(keyword["keyword_type"]), _line(keyword["value"])
            if kind.startswith((">>", "<<")) or any(
                    tag.startswith(other) or other.startswith(tag) for other in tags.values()):
                raise ValueError("Only ordinary explicitly configured keywords are supported; no revision/admin system tags.")
            if (tag in configured_keywords and configured_keywords[tag] != kind) or any(
                    tag != other and (tag.startswith(other) or other.startswith(tag)) for other in configured_keywords):
                raise ValueError("Keyword tags must have one unambiguous destination mapping.")
            configured_keywords[tag] = kind
            lines.append(tag + value)
        # Hyland requires File Type before File Name. File Name alone searches
        # the index directory in a Normal DIP without FTP; no absolute path needed.
        lines.append(tags["file_name"] + name)
        mappings.append((index, name, lines, document))
    fields[3:3] = [{"tag": tag, "keyword_type": kind} for tag, kind in configured_keywords.items()]
    index_bytes = ("\r\n".join(line for _, _, lines, _ in mappings for line in lines) + "\r\n").encode(encoding)
    if len(index_bytes) > bounds.parser_bytes:
        raise ValueError("DIP index exceeds parser bounds.")
    total = len(index_bytes)
    try:
        with ExitStack() as stack:
            output = stack.enter_context(tempfile.TemporaryFile())
            archive = stack.enter_context(zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED))
            archive.writestr("index.txt", index_bytes)
            for index, name, _, document in mappings:
                if context.check_cancelled():
                    raise InterruptedError
                if monotonic() >= deadline:
                    raise ValueError("DIP preparation exceeded deadline.")
                part = files[index]
                if not isinstance(part, dict) or ("file_handle" in part) == ("content_base64" in part):
                    raise ValueError("Each file requires exactly one scoped handle or inline base64 content.")
                if "file_handle" in part:
                    metadata, stream = open_input(owner, part["file_handle"], context=context)
                    stack.enter_context(stream)
                    length = metadata["byte_length"]
                    mime = metadata["content_type"]
                    if part.get("content_type", mime) != mime:
                        raise ValueError("MIME metadata conflicts with scoped input.")
                else:
                    encoded = part["content_base64"]
                    if not isinstance(encoded, str) or len(encoded) > ((bounds.parser_bytes + 2) // 3) * 4:
                        raise ValueError("Inline file exceeds parser bound; use a scoped handle.")
                    payload = base64.b64decode(encoded, validate=True)
                    length, stream, mime = len(payload), io.BytesIO(payload), part.get("content_type")
                total += length
                if not length or total > bounds.transfer_bytes:
                    raise ValueError("DIP inputs are empty or exceed transfer bounds.")
                digest, copied = hashlib.sha256(), 0
                with archive.open(name, "w") as entry:
                    while chunk := stream.read(min(1024 * 1024, length - copied + 1)):
                        if context.check_cancelled():
                            raise InterruptedError
                        if monotonic() >= deadline or copied + len(chunk) > length:
                            raise ValueError("DIP input changed or deadline exceeded.")
                        copied += len(chunk)
                        digest.update(chunk)
                        entry.write(chunk)
                if copied != length:
                    raise ValueError("DIP input length changed.")
                manifest["files"].append({"archive_path": name, "byte_length": copied,
                    "sha256": digest.hexdigest(), "content_type": mime, "mapping": document,
                    "file_type_validation": "explicit destination numeric ID; vendor type/format compatibility not inferred"})
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode())
            archive.close()
            if context.check_cancelled():
                raise InterruptedError
            size = output.tell()
            if size > bounds.transfer_bytes:
                raise ValueError("DIP archive exceeds transfer bounds.")
            output.seek(0)
            if request.get("stream"):
                artifact_id = secrets.token_hex(24)
                _save_artifact(owner, "artifacts", artifact_id, output,
                    {"artifact_id": artifact_id, "format": FORMAT, "manifest": manifest,
                     "requires_attachment_grant": True, "namespaces": [namespace]},
                    context=context, max_bytes=bounds.transfer_bytes, check_bounds=check_output_bounds)
                data = {"format": FORMAT, "artifact_id": artifact_id, "manifest": manifest}
            else:
                if size > bounds.parser_bytes:
                    raise ValueError("Use stream=true for an archive above parser response bounds.")
                data = {"format": FORMAT, "content_base64": base64.b64encode(output.read()).decode(), "manifest": manifest}
        check_output_bounds()
        return OperationResult("completed", data, coverage={"scope": "explicit linked document file/index preparation",
            "source_complete": False, "vendor_import_accepted": False,
            "projection_losses": manifest["projection_losses"]}, operation_id=context.operation_id)
    except InterruptedError:
        return OperationResult("cancelled", operation_id=context.operation_id)
