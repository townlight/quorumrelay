"""Generated minutes are an approved upstream creation, never an implicit read."""

from copy import deepcopy
from dataclasses import asdict
import uuid

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteChange, WriteFailure
from .granicus_platform import numeric_id
from .granicus_soap import contract, request_xml

METHOD = "CreateClipGeneratedMinutesDocument"


def authorize(adapter, source, change, context):
    config = adapter.credentials(source, context)
    fields = change.fields
    if (change.operation != "create" or change.files or set(fields) != set(contract()["operations"][METHOD]["request"])
            or type(fields.get("isPublished")) is not bool or type(fields.get("isDefault")) is not bool
            or not isinstance(fields.get("name"), str) or not fields["name"].strip()):
        raise ValueError("Generated minutes require all documented arguments, explicit publication/default booleans and a supplied name.")
    for key in ("clipUid", "templateUid"):
        if not isinstance(fields[key], str) or str(uuid.UUID(fields[key])).lower() != fields[key].lower():
            raise ValueError("Generated minutes require supplied canonical clip/template GUIDs.")
    if ("generated_minutes:create" not in config.get("permissions", ())
            or str(numeric_id(change.resource_id)) not in config.get("resource_ids", ())
            or not change.meeting_id or str(change.meeting_id) not in config.get("meeting_ids", ())):
        raise WriteFailure("permission_denied", "Generated minutes require exact clip, meeting and creation authority.")


def _read(session, change):
    values, _ = session.call("GetClip", {"ClipID": numeric_id(change.resource_id)})
    clip = values.get("clip")
    if (not isinstance(clip, dict) or str(clip.get("ID")) != str(change.resource_id)
            or str(clip.get("UID", "")).lower() != change.fields["clipUid"].lower()):
        raise ValueError("The supplied numeric clip and GUID must independently resolve to the same resource.")
    values, _ = session.call("GetClipMinutesDocuments", {"ClipID": numeric_id(change.resource_id)})
    docs = values.get("MinutesDocuments")
    if (not isinstance(docs, list) or any(not isinstance(doc, dict) or not doc.get("UID") for doc in docs)
            or len({doc["UID"] for doc in docs}) != len(docs)):
        raise ValueError("Minutes readback requires unique supplied document UIDs.")
    return {"clip": clip, "documents": docs}


def prepare(adapter, source, change, context, bounds, deadline):
    request_xml(METHOD, change.fields, byte_limit=bounds.transfer_bytes)
    session = adapter._session(source, context, bounds, deadline)
    try:
        before = _read(session, change)
    finally:
        adapter._close_document_session(session)
    if any(doc.get("Name") == change.fields["name"] for doc in before["documents"]):
        raise WriteFailure("conflict", "A minutes document already uses the approved name.")
    fingerprint = canonical_hash(before)
    if change.expected_version is not None and change.expected_version != fingerprint:
        raise WriteFailure("conflict", "The clip/minutes baseline changed.")
    return {"change": asdict(change), "native": {"method": "POST", "url": session.url,
        "content_type": "text/xml", "headers": {}, "files": [], "soap_method": METHOD,
        "body": deepcopy(change.fields)}, "before": before, "before_fingerprint": fingerprint,
        "expected_version": fingerprint, "contract_revision": contract()["source_revision"],
        "publication_requested": change.fields["isPublished"], "default_requested": change.fields["isDefault"],
        "conflict_semantics": "preflight_clip_minutes_compare_not_atomic_provider_cas"}


def _outcome(session, prepared):
    change = WriteChange.from_dict(prepared["change"])
    actual = _read(session, change)
    prior = {doc["UID"]: doc for doc in prepared["before"]["documents"]}
    new = [doc for doc in actual["documents"] if doc["UID"] not in prior]
    matching = [doc for doc in new if doc.get("Name") == change.fields["name"]
                and doc.get("Published") is change.fields["isPublished"]
                and doc.get("Default") is change.fields["isDefault"]]
    # Do not infer undocumented changes to other documents, even default flags.
    by_uid = {doc["UID"]: doc for doc in actual["documents"]}
    verified = len(matching) == 1 and all(uid in by_uid and canonical_hash(by_uid[uid]) == canonical_hash(doc) for uid, doc in prior.items())
    return {"state": "succeeded" if verified else "uncertain", "resource_id": change.resource_id,
        "document_uid": matching[0]["UID"] if len(matching) == 1 else None,
        "readback": actual["documents"], "reconciled": True,
        "publication_requested": change.fields["isPublished"], "default_requested": change.fields["isDefault"],
        "readback_verified_fields": ["clipUid", "name", "isPublished", "isDefault"] if verified else ["clipUid"],
        "submitted_only_fields": ["templateUid"], "document_bytes_verified": False,
        "verification_scope": "Unique new minutes UID/name/publication/default metadata under verified clip; template selection and generated file bytes have no independent readback in this method.",
        **({} if verified else {"reason": "Generated minutes metadata is not uniquely verified; no creation replay."})}


def apply(adapter, source, prepared, context, bounds, deadline, *, persist):
    change = WriteChange.from_dict(prepared["change"])
    session = adapter._session(source, context, bounds, deadline)
    try:
        if canonical_hash(_read(session, change)) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "The clip/minutes changed after approval.")
        if persist:
            persist({"resource_id": change.resource_id})
        try:
            session.call(METHOD, prepared["native"]["body"])
        except ValueError:
            raise AmbiguousWrite() from None
        return _outcome(session, prepared)
    finally:
        adapter._close_document_session(session)


def reconcile(adapter, source, prepared, item, context, bounds, deadline):
    session = adapter._session(source, context, bounds, deadline)
    try:
        return _outcome(session, prepared)
    finally:
        adapter._close_document_session(session)
