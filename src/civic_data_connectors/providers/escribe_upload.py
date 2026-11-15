"""Explicit native document chunk with caller-declared whole-content readback hash."""
import base64
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import io
import re

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteCancelled, WriteChange, WriteFailure
from .escribe_publishing import contract, request_xml
from .escribe_write import native_identity


def policy(adapter, source, change, context):
    adapter.validate_source(source, context)
    config = adapter.credentials(source, context)
    identity = native_identity("document", change.resource_id)
    if (change.entity != "document" or change.operation != "upload" or change.parent_id is not None
            or change.meeting_id is not None or change.language is not None or change.page_number is not None
            or "document:upload" not in config.get("permissions", ())
            or str(identity) not in config.get("resource_ids", ())):
        raise WriteFailure("permission_denied", "Upload requires an exact authorized existing document and operation.")
    fields = change.fields
    if (not isinstance(fields, dict) or set(fields) != {"offset", "length", "IsPrivate", "expected_document_sha256"}
            or type(fields["offset"]) is not int or not 0 <= fields["offset"] < 2**31
            or type(fields["length"]) is not int or not 0 < fields["length"] < 2**31
            or type(fields["IsPrivate"]) is not bool
            or not isinstance(fields["expected_document_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", fields["expected_document_sha256"]) is None
            or len(change.files) != 1 or change.files[0].get("part") != "Chunk"):
        raise ValueError("Supply explicit native offset/length/IsPrivate, final document SHA256 and one bound Chunk file.")
    if change.files[0]["reference"]["byte_length"] != fields["length"]:
        raise ValueError("This bounded mapping requires length equal to the supplied chunk byte count.")
    return identity


def snapshot(adapter, session, identity):
    record = adapter._read(session, "document", identity)
    fields = contract()["types"][contract()["operations"]["DocumentCreate"]["request"][0]["type"]]["fields"]
    if set(record) != {field["name"] for field in fields}:
        raise ValueError("The complete current document metadata is required.")
    value, _ = session.call("DocumentGetContent", {"Id": identity})
    content = base64.b64decode(value, validate=True)
    if record["FileSize"] != len(content):
        raise ValueError("The document content and native metadata byte count differ.")
    return {"record": record, "content_sha256": sha256(content).hexdigest(),
            "byte_length": len(content)}, content


def parameters(adapter, change, identity):
    content = adapter._file_bytes(change.files[0])
    if len(content) != change.fields["length"]:
        raise ValueError("The bound chunk byte count changed.")
    return {"Parameters": {"Chunk": base64.b64encode(content).decode("ascii"),
        "DocumentId": identity, "IsPrivate": change.fields["IsPrivate"],
        "length": change.fields["length"], "offset": change.fields["offset"]}}


def prepare(adapter, source, change, context, bounds, deadline):
    identity = policy(adapter, source, change, context)
    if bounds.max_pages < 5:
        raise ValueError("Native upload requires two preflight reads, one send and two readback calls.")
    body = parameters(adapter, change, identity)
    encoded, _ = request_xml("DocumentUpload", body, source.url)
    if len(encoded) > min(bounds.parser_bytes, bounds.transfer_bytes):
        raise ValueError("The single SOAP chunk exceeds configured parser/transfer bounds.")
    session = adapter._session(source, context, bounds, deadline)
    before, content = snapshot(adapter, session, identity)
    if before["record"]["IsPrivate"] != change.fields["IsPrivate"]:
        raise ValueError("This upload preserves the existing explicit IsPrivate field; no visibility change is mapped.")
    if change.expected_version is not None and change.expected_version != canonical_hash(before):
        raise WriteFailure("conflict", "Expected metadata/content fingerprint differs from current document.")
    session.check()
    reference = adapter.file_engine.storage.save_capture(io.BytesIO(content), scope=context.scope,
                                                        max_bytes=bounds.transfer_bytes)
    session.check()
    public_body = deepcopy(body)
    public_body["Parameters"]["Chunk"] = {"file_reference": deepcopy(change.files[0]["reference"])}
    return {"change": asdict(change), "before": before, "before_content_reference": reference,
        "before_fingerprint": canonical_hash(before), "resource_id": identity,
        "after": {"expected_document_sha256": change.fields["expected_document_sha256"],
                  "IsPrivate": change.fields["IsPrivate"]},
        "native": {"method": "POST", "url": source.url, "soap_method": "DocumentUpload",
                   "body": public_body, "content_type": "application/soap+xml", "headers": {},
                   "files": deepcopy(list(change.files))},
        "conflict_semantics": "preflight_metadata_and_content_compare_not_atomic_provider_cas",
        "contract_sha256": contract()["metadata_sha256"]["publishing.wsdl"],
        "limits": ["One explicit chunk; offset is caller supplied and not interpreted as a library splice rule.",
                   "No clear, append, truncate, finalize, processing poll or publication method is inferred.",
                   "Success requires exact caller-declared final whole-document hash and metadata preservation."]}


def outcome(adapter, prepared, session):
    actual, _ = snapshot(adapter, session, prepared["resource_id"])
    expected = {**prepared["before"]["record"], "FileSize": actual["byte_length"],
                "IsPrivate": prepared["after"]["IsPrivate"]}
    matches = (actual["content_sha256"] == prepared["after"]["expected_document_sha256"]
               and actual["record"] == expected)
    return {"state": "succeeded" if matches else "uncertain", "resource_id": str(prepared["resource_id"]),
            "readback": actual, "reconciled": True,
            **({} if matches else {"reason": "Whole-document bytes or preserved metadata differ; no upload replay."})}


def apply(adapter, source, prepared, context, bounds, deadline, *, persist=None):
    change = WriteChange.from_dict(prepared["change"])
    identity = policy(adapter, source, change, context)
    session = adapter._session(source, context, bounds, deadline)
    before, _ = snapshot(adapter, session, identity)
    if canonical_hash(before) != prepared["before_fingerprint"]:
        raise WriteFailure("conflict", "Native document metadata or bytes changed after planning.")
    body = parameters(adapter, change, identity)
    if persist and persist({"resource_id": str(identity)}):
        raise WriteCancelled()
    try:
        session.call("DocumentUpload", body)
        return outcome(adapter, prepared, session)
    except Exception:
        # Once the exact send can have happened, neither retry nor cancellation
        # may turn an unknown byte outcome into a safe-to-repeat write.
        raise AmbiguousWrite() from None


def reconcile(adapter, source, prepared, item, context, bounds, deadline):
    change = WriteChange.from_dict(prepared["change"])
    policy(adapter, source, change, context)
    return outcome(adapter, prepared, adapter._session(source, context, bounds, deadline))
