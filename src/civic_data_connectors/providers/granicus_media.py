"""SDK MediaVault chunk/register/assign workflows with private durable intent state."""

from copy import deepcopy
from dataclasses import asdict
import re
import uuid

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteFailure
from .granicus_platform import numeric_id
from .granicus_soap import contract
from .granicus_vault import VaultSession


def authorize(adapter, source, change, context):
    config = adapter.credentials(source, context)
    fields = change.fields
    wanted = {"FolderID", "Extension", "ChunkBytes", "Name"} if change.operation == "upload" else {"FolderID", "Extension", "ChunkBytes", "ClipUID"}
    if (change.operation not in {"upload", "update"} or set(fields) != wanted or len(change.files) != 1
            or type(fields["ChunkBytes"]) is not int or not 0 < fields["ChunkBytes"] <= 7_000_000
            or not isinstance(fields["Extension"], str) or not re.fullmatch(r"[A-Za-z0-9]{1,12}", fields["Extension"])):
        raise ValueError("Chunk upload needs explicit folder/extension/chunk size and one file; 7MB is an adapter chunk ceiling, not a vendor total-file limit.")
    if (f"chunked_recording:{change.operation}" not in config.get("permissions", ())
            or str(numeric_id(fields["FolderID"])) not in config.get("folder_ids", ())
            or not change.meeting_id or str(change.meeting_id) not in config.get("meeting_ids", ())):
        raise WriteFailure("permission_denied", "Chunk upload requires exact folder, meeting and operation grants.")
    if change.operation == "upload":
        if change.resource_id is not None or not isinstance(fields["Name"], str) or not fields["Name"].strip():
            raise ValueError("New clip registration requires an explicit name without an existing resource identity.")
    elif (str(numeric_id(change.resource_id)) not in config.get("resource_ids", ())
          or not isinstance(fields["ClipUID"], str) or str(uuid.UUID(fields["ClipUID"])).lower() != fields["ClipUID"].lower()):
        raise WriteFailure("permission_denied", "Assignment requires the exact existing clip identity, UID and resource grant.")


def _before(adapter, session, change):
    folder = adapter._media_folder(session, change.fields["FolderID"])
    if change.operation == "upload":
        if any(clip.get("Name") == change.fields["Name"] for clip in folder):
            raise WriteFailure("conflict", "The supplied clip name already exists in the target folder.")
        return {"folder": folder}
    values, _ = session.call("GetClip", {"ClipID": numeric_id(change.resource_id)})
    clip = values.get("clip")
    if (not isinstance(clip, dict) or str(clip.get("ID")) != str(change.resource_id)
            or str(clip.get("UID", "")).lower() != change.fields["ClipUID"].lower()
            or not any(str(row.get("ID")) == str(change.resource_id) for row in folder)):
        raise ValueError("The assignment clip ID/UID must independently match the supplied folder.")
    return {"folder": folder, "clip": clip}


def prepare(adapter, source, change, context, bounds, deadline):
    parts = adapter._files(change, bounds)
    part = parts[0]
    if (part["part"] != "bytes" or not part["content_type"].startswith(("video/", "audio/"))
            or not part["reference"]["byte_length"]):
        raise ValueError("Approve one nonempty audio/video bytes part.")
    session = adapter._session(source, context, bounds, deadline)
    vault = VaultSession(session, change.fields["FolderID"])
    try:
        before = _before(adapter, session, change)
        vault._connect()
        endpoint = vault._url
    finally:
        vault.close()
        adapter._close_document_session(session)
    fingerprint = canonical_hash(before)
    if change.expected_version is not None and change.expected_version != fingerprint:
        raise WriteFailure("conflict", "The upload target differs from the supplied baseline.")
    return {"change": asdict(change), "native": {"method": "POST", "url": endpoint,
        "content_type": "text/xml", "headers": {}, "files": list(parts), "body": deepcopy(change.fields),
        "soap_method": "StartUpload/SendChunk/FinishUpload/" + ("RegisterUploadedFile" if change.operation == "upload" else "AssignUploadedFile")},
        "before": before, "before_fingerprint": fingerprint, "expected_version": fingerprint,
        "upload_intent_id": str(uuid.uuid4()), "contract_revision": contract()["source_revision"],
        "publication_requested": False, "conflict_semantics": "preflight_target_compare_not_atomic_provider_cas"}


def _private_store(adapter, source, prepared, context):
    if adapter.file_engine is None or adapter.file_engine.storage is None:
        raise ValueError("Chunk upload requires private scoped durable storage.")
    storage = adapter.file_engine.storage
    binding = canonical_hash({"prepared": prepared, "source": source.public_dict(), "scope": context.scope})
    key = prepared["upload_intent_id"]
    value = {"binding": binding, "phase": "starting", "completed_bytes": 0}
    version = storage.put("private_provider_uploads", key, value, scope=context.scope, create_only=True)
    def save(**step):
        nonlocal version
        value.update(step)
        version = storage.put("private_provider_uploads", key, value, scope=context.scope, expected_version=version)
    return save


def apply(adapter, source, prepared, context, bounds, deadline, *, persist):
    from ..write_adapters import WriteChange
    change = WriteChange.from_dict(prepared["change"])
    session = adapter._session(source, context, bounds, deadline)
    vault = VaultSession(session, change.fields["FolderID"])
    try:
        if canonical_hash(_before(adapter, session, change)) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "The upload target changed after plan approval.")
        vault._connect()
        if vault._url != prepared["native"]["url"]:
            raise WriteFailure("conflict", "The configured folder upload interface changed.")
        save = _private_store(adapter, source, prepared, context)
        if persist and persist({"upload_stage": "starting"}):
            raise WriteFailure("cancelled", "Cancelled before the MediaVault upload started.")
        try:
            bucket = vault.call("StartUpload", {})["StartUploadResult"]
            if not isinstance(bucket, str) or str(uuid.UUID(bucket)).lower() != bucket.lower():
                raise ValueError("The documented upload GUID was not returned.")
            # Bucket GUID is a private remote control token, never a receipt field.
            save(bucket_guid=bucket, phase="chunking")
            offset = 0
            with adapter._open_file(prepared["native"]["files"][0]) as stream:
                while chunk := stream.read(change.fields["ChunkBytes"]):
                    save(phase="sending_chunk", next_position=offset)
                    vault.call("SendChunk", {"GUID": bucket, "ChunkPosition": offset, "bytes": chunk})
                    offset += len(chunk)
                    save(phase="chunking", completed_bytes=offset)
                    if persist and persist({"upload_stage": "chunking", "completed_bytes": offset}):
                        raise AmbiguousWrite()
            save(phase="sending_finish")
            checksum = vault.call("FinishUpload", {"GUID": bucket})["FinishUploadResult"]
            # Vendor calls this a checksum but does not specify its algorithm.
            save(phase="finished", vendor_checksum=checksum)
            if persist:
                persist({"upload_stage": "registering" if change.operation == "upload" else "assigning",
                         "provider_checksum": checksum, "checksum_algorithm": "vendor_unspecified"})
            save(phase="sending_registration" if change.operation == "upload" else "sending_assignment")
            if change.operation == "upload":
                returned = vault.call("RegisterUploadedFile", {"GUID": bucket, "FolderID": change.fields["FolderID"],
                    "Name": change.fields["Name"], "Extension": change.fields["Extension"]})
                identity = numeric_id(returned["RegisterUploadedFileResult"])
            else:
                vault.call("AssignUploadedFile", {"GUID": bucket, "ClipUID": change.fields["ClipUID"], "Extension": change.fields["Extension"]})
                identity = numeric_id(change.resource_id)
            save(phase="acknowledged", resource_id=identity)
            if persist:
                persist({"upload_stage": "acknowledged", "resource_id": identity, "media_assignment_acknowledged": True})
        except Exception:
            raise AmbiguousWrite() from None
        return outcome(adapter, session, prepared, identity, private_bucket=bucket)
    finally:
        vault.close()
        adapter._close_document_session(session)


def outcome(adapter, session, prepared, identity, *, private_bucket):
    result = adapter._media_outcome(session, prepared, identity)
    if private_bucket and private_bucket in str(result):
        raise ValueError("Private upload control state cannot enter a public readback.")
    if (prepared["change"]["operation"] == "update"
            and str(result["readback"].get("UID", "")).lower() != prepared["change"]["fields"]["ClipUID"].lower()):
        raise ValueError("Assigned clip readback differs from the approved UID.")
    result["verification_scope"] = "Documented chunk/finish/register-or-assign acknowledgement plus independent clip identity; submitted bytes are plan-verified. Vendor checksum algorithm, remote original-byte equality and playable processing are not independently verified."
    return result


def reconcile(adapter, source, prepared, item, context, bounds, deadline):
    stored = adapter.file_engine.storage.get("private_provider_uploads", prepared["upload_intent_id"], scope=context.scope)
    binding = canonical_hash({"prepared": prepared, "source": source.public_dict(), "scope": context.scope})
    if stored is None or stored.value.get("binding") != binding:
        return {"state": "uncertain", "reason": "Private upload state does not match this caller/source/approved plan; no mutation replay."}
    identity = stored.value.get("resource_id")
    if identity is None or stored.value.get("phase") != "acknowledged":
        return {"state": "uncertain", "reason": "A MediaVault stage outcome is unknown; no documented status query or safe automatic chunk/registration/assignment replay."}
    session = adapter._session(source, context, bounds, deadline)
    try:
        return outcome(adapter, session, prepared, identity, private_bucket=stored.value.get("bucket_guid"))
    finally:
        adapter._close_document_session(session)
