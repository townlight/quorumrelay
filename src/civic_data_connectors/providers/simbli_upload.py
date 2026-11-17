"""Native supporting-file upload followed by the locked full-item save."""

from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import re
from urllib.parse import urlencode
from uuid import uuid4

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteCancelled, WriteChange, WriteFailure
from .simbli import HOST
from .simbli_write import _Requests, _assert_safe, _bounded_json, _comparable, _expect, _find_tree, _good_id

UPLOAD = "/services/api/FileUpload/UploadFile"
RESTRICTED_EXTENSIONS = frozenset(
    "folder;dir;ade;adp;asp;aspx;asx;bas;bat;chm;cmd;com;cpl;crt;exe;hlp;hta;inf;ins;isp;js;jse;lnk;"
    "mda;mdb;mde;mdt;mdw;mdz;msc;msi;msp;mst;ops;pcd;pif;prf;reg;scf;scr;sct;shb;shs;url;vb;vbe;"
    "vbs;wsc;wsf;wsh;htm;html;php".split(";")
)
DESCRIPTOR = (
    "TempFileName", "FileName", "AttachmentID", "SaveFileName", "OrigFileName",
    "IsDeleted", "Operation", "ContentType", "FileExtension", "Title", "OrigTitle", "FileSize",
)
NATIVE = {"upload": UPLOAD, "file_part": "file", "attachmentId": 0, "id": 0,
          "save": "locked_full_item", "files": []}


class _AuthorizedRequests(_Requests):
    def send(self, method, url, **kwargs):
        if not kwargs.get("cleanup"):
            self.guard(method)
        return super().send(method, url, **kwargs)


def _target(change):
    return replace(change, entity="agenda_item", operation="update", resource_id=change.parent_id,
                   parent_id=None, files=())


def _part(part):
    if not isinstance(part, dict) or set(part) != {"part", "filename", "content_type", "reference"}:
        raise ValueError("One immutable file reference is required.")
    name, mime, ref = part["filename"], part["content_type"], part["reference"]
    if (part["part"] != "file" or not isinstance(name, str) or not name or len(name) > 250
            or name in {".", ".."} or any(c in name for c in '/\\\r\n"')
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or not isinstance(mime, str) or not re.fullmatch(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+", mime)
            or not isinstance(ref, dict) or type(ref.get("byte_length")) is not int
            or ref["byte_length"] <= 0 or not re.fullmatch(r"[0-9a-f]{64}", str(ref.get("sha256", "")))):
        raise ValueError("The supporting-file metadata is invalid.")
    if "." in name and name.rsplit(".", 1)[1].lower() in RESTRICTED_EXTENSIONS:
        raise ValueError("The native Simbli uploader rejects this file extension.")


def _field(snapshot, change):
    rows = [f for f in snapshot["item"]["ItemContents"] if f.get("FieldName") == change.fields["field_name"]]
    if len(rows) != 1 or rows[0].get("ControlType") != 9:
        raise ValueError("The exact supporting-document field must exist once.")
    value = rows[0]
    if type(value.get("FieldVisibility")) is not int or value["FieldVisibility"] not in {0, 1, 2}:
        raise ValueError("The existing supporting-field visibility is invalid.")
    attachments = value.get("Attachments")
    if attachments is None:
        attachments = []
    if not isinstance(attachments, list) or any(not isinstance(a, dict) for a in attachments):
        raise ValueError("A native attachment array is required.")
    ids = [a.get("AttachmentID") for a in attachments]
    if any(not _good_id(i) for i in ids) or len(set(map(str, ids))) != len(ids):
        raise ValueError("Existing attachment identities must be unique and positive.")
    if any(type(a.get("Order")) is not int or a["Order"] < 1 for a in attachments):
        raise ValueError("Existing attachments require positive native order values.")
    return value


class SupportingUpload:
    def __init__(self, adapter):
        self.adapter = adapter

    def authorize(self, source, change, context):
        a = self.adapter
        a.validate_source(source, context)
        config = a.credentials(source, context)
        if "agenda_item_attachment:upload" not in config.get("permissions", ()):
            raise WriteFailure("permission_denied", "Supporting-file upload permission is required.")
        if (change.operation != "upload" or change.resource_id is not None
                or not isinstance(change.parent_id, str) or change.parent_id not in config["item_ids"]
                or change.meeting_id != str(config["meeting_id"]) or change.language is not None
                or change.page_number is not None or not isinstance(change.fields, dict)
                or set(change.fields) != {"field_name"}
                or not isinstance(change.fields["field_name"], str)
                or change.fields["field_name"] not in config.get("supporting_fields", ())
                or len(change.files) != 1):
            raise WriteFailure("mapping_unverified", "Select one authorized item supporting field and one new file.")
        _part(change.files[0])
        return config

    def _bytes(self, change):
        part = change.files[0]
        data = self.adapter._file_bytes(part)
        if len(data) != part["reference"]["byte_length"] or hashlib.sha256(data).hexdigest() != part["reference"]["sha256"]:
            raise ValueError("The immutable file bytes changed.")
        return data

    def _session(self, source, change, config, context, bounds, deadline):
        def guard(method):
            self.authorize(source, change, context)
            if method == "POST":
                self.adapter._authorize_commit(source, change, context)
        session = _AuthorizedRequests(self.adapter.transport, config, context, bounds, deadline)
        session.guard = guard
        return session

    def _current(self, session, source, config, change, bounds):
        current = self.adapter._read_current(session, source, config, _target(change), bounds)
        _field(current.snapshot, change)
        if not current.page.get("encrModuleID"):
            raise ValueError("Fresh native module context is required for upload.")
        return current

    def prepare(self, source, change, context, bounds, deadline):
        config = self.authorize(source, change, context)
        self._bytes(change)
        if 2 * change.files[0]["reference"]["byte_length"] + 2048 > bounds.transfer_bytes:
            raise WriteFailure("bounds_exceeded", "The budget cannot cover upload and original-file verification.")
        session = self._session(source, change, config, context, bounds, deadline)
        session.require(3)
        current = self._current(session, source, config, change, bounds)
        before = current.snapshot
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The item differs from the requested baseline.")
        if any(a.get("OrigFileName", a.get("FileName")) == change.files[0]["filename"]
               for a in (_field(before, change)["Attachments"] or [])):
            raise WriteFailure("conflict", "A supporting attachment already uses that original filename.")
        native = deepcopy(NATIVE)
        native["files"] = list(change.files)
        result = {"change": asdict(change), "before": before, "before_fingerprint": fingerprint,
                  "native": native, "conflict_semantics": "preflight_and_native_item_lock_not_atomic_cas"}
        _bounded_json(json.dumps(result, allow_nan=False).encode(), bounds)
        _assert_safe(result, current.page["secrets"])
        return result

    def _prepared(self, source, prepared, context, bounds):
        _bounded_json(json.dumps(prepared, allow_nan=False).encode(), bounds)
        change = WriteChange.from_dict(prepared["change"])
        config = self.authorize(source, change, context)
        native = deepcopy(NATIVE)
        native["files"] = list(change.files)
        if (prepared.get("native") != native or prepared.get("before_fingerprint") != canonical_hash(prepared["before"])):
            raise ValueError("The prepared upload binding changed.")
        if change.expected_version is not None and change.expected_version != prepared["before_fingerprint"]:
            raise ValueError("The expected item version binding changed.")
        _field(prepared["before"], change)
        return change, config

    def _upload(self, session, current, change, bounds, source):
        part = change.files[0]
        data = self._bytes(change)
        boundary = "quorumrelay-" + uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{part["filename"]}"\r\n'
                f'Content-Type: {part["content_type"]}\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
        p = current.page
        url = HOST + UPLOAD + "?" + urlencode({"sct": p["sToken"], "enportaluid": p["enCuUID"],
            "endid": p["enDID"], "enentitytypeid": p["encrModuleID"], "enentityid": p["enMeetingID"],
            "enitemid": current.selected["ID"], "attachmentId": 0, "id": 0})
        self.adapter._authorize_commit(source, change, session.context)
        response = session.send("POST", url, host=HOST, body=body,
                                headers={"Content-Type": "multipart/form-data; boundary=" + boundary}, file_body=True)
        _expect(response, ambiguous=True)
        payload = _bounded_json(response.content, bounds)
        value = payload.get("Data") if isinstance(payload, dict) else None
        if not isinstance(value, dict) or value.get("isSuccess") is not True or not isinstance(value.get("FileDetail"), dict):
            raise AmbiguousWrite("The upload did not return a confirmed native file descriptor.")
        detail = value["FileDetail"]
        if any(k not in detail for k in DESCRIPTOR):
            raise AmbiguousWrite("The native file descriptor is incomplete.")
        result = {k: deepcopy(detail[k]) for k in DESCRIPTOR}
        if (result["IsDeleted"] is not False or type(result["Operation"]) is not int
                or type(result["AttachmentID"]) is not int or result["AttachmentID"] < 0
                or result["FileName"] != part["filename"] or result["OrigFileName"] != part["filename"]
                or not isinstance(result["ContentType"], str)
                or result["ContentType"].lower() != part["content_type"].lower()
                or type(result["FileSize"]) is not int or result["FileSize"] != len(data)
                or any(not isinstance(result[k], str) or len(result[k]) > 4096
                       for k in ("TempFileName", "SaveFileName", "Title", "OrigTitle", "FileExtension"))
                or not result["TempFileName"]):
            raise AmbiguousWrite("The uploaded file metadata does not match the approved input.")
        result["Title"] = result["Title"][:250]
        result.update(Id=len(_field(current.snapshot, change)["Attachments"] or []) + 1, Order=1,
                      VisibilityMode=_field(current.snapshot, change)["FieldVisibility"])
        _assert_safe(result, p["secrets"])
        return result

    def _verify(self, session, source, config, prepared, change, bounds, descriptor):
        current = self._current(session, source, config, change, bounds)
        before = prepared["before"]
        old = _field(before, change)["Attachments"] or []
        actual = _field(current.snapshot, change)["Attachments"] or []
        old_ids = {str(a["AttachmentID"]) for a in old}
        added = [a for a in actual if str(a["AttachmentID"]) not in old_ids]
        if len(added) != 1 or len(actual) != len(old) + 1 or actual[0] is not added[0]:
            raise AmbiguousWrite("The saved attachment is not uniquely identified in the selected field.")
        new = added[0]
        if new.get("IsDeleted") is not False or new.get("Order") != 1:
            raise AmbiguousWrite("The new attachment is deleted or not first in native order.")
        part = change.files[0]
        expected = deepcopy(before)
        field = _field(expected, change)
        if field["Attachments"] is None:
            field["Attachments"] = []
        for i, attachment in enumerate(field["Attachments"]):
            attachment["Order"] = i + 2
            token = attachment.get("$simbli_field:SecurityToken")
            if isinstance(token, dict) and "$simbli_attachment_token" in token:
                token["$simbli_attachment_token"]["path"][-1] = i + 1
        field["Attachments"].insert(0, deepcopy(new))
        field["HasData"] = True
        _find_tree(expected["tree"], int(change.parent_id))["HasAttachment"] = True
        target = _target(change)
        if (_find_tree(before["tree"], int(change.parent_id))["Title"] !=
                _find_tree(current.snapshot["tree"], int(change.parent_id))["Title"]
                or canonical_hash(_comparable(expected, target)) != canonical_hash(_comparable(current.snapshot, target))):
            raise AmbiguousWrite("The attachment save changed unrelated item state.")
        if descriptor is None:
            raise AmbiguousWrite("No durable native upload descriptor is available.")
        if descriptor.get("AttachmentID", 0) > 0 and str(descriptor["AttachmentID"]) != str(new["AttachmentID"]):
            raise AmbiguousWrite("The assigned attachment identity changed after upload.")
        for key in ("FileName", "OrigFileName", "ContentType", "Title", "OrigTitle", "FileExtension", "VisibilityMode"):
            if new.get(key) != descriptor[key]:
                raise AmbiguousWrite("The saved attachment differs from the returned upload descriptor.")
        if (str(new.get("SchoolID")) != str(config["site_id"])
                or str(new.get("EnitityID")) != str(config["meeting_id"])):
            raise AmbiguousWrite("The saved attachment belongs to a different site or meeting.")
        url = HOST + "/Meetings/Attachment.aspx?" + urlencode({"S": config["site_id"],
            "AID": new["AttachmentID"], "MID": config["meeting_id"]})
        response = session.send("GET", url, host=HOST, headers={"Accept": part["content_type"]}, binary=True)
        _expect(response, ambiguous=True)
        mime = next((v for k, v in response.headers.items() if k.lower() == "content-type"), "").split(";")[0].lower()
        if (mime != part["content_type"].lower() or len(response.content) != part["reference"]["byte_length"]
                or hashlib.sha256(response.content).hexdigest() != part["reference"]["sha256"]):
            raise AmbiguousWrite("Independent attachment bytes do not match the approved original.")
        return {"state": "succeeded", "resource_id": str(new["AttachmentID"]), "item_id": change.parent_id,
                "original_sha256": part["reference"]["sha256"], "original_bytes_verified": True,
                "readback": current.snapshot, "reconciled": True}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change, config = self._prepared(source, prepared, context, bounds)
        a = self.adapter
        session = self._session(source, change, config, context, bounds, deadline)
        session.require(3)
        current = self._current(session, source, config, change, bounds)
        if canonical_hash(current.snapshot) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "The item changed after upload planning.")
        self._bytes(change)
        if session.transfer + 2 * change.files[0]["reference"]["byte_length"] + 2048 > bounds.transfer_bytes:
            raise WriteFailure("bounds_exceeded", "Insufficient remaining upload/readback transfer budget.")
        session.require(10)  # lock, two preflight reads, upload, save, four readbacks, release
        a._authorize_commit(source, change, context)
        item_id, lock = current.selected["ID"], current.page["lock_dto"]
        attempted = False
        lock_attempted = False
        result = None
        try:
            if persist and persist({"item_id": change.parent_id, "lock_attempted": True}):
                raise WriteCancelled()
            a._authorize_commit(source, change, context)
            session.reserve_cleanup = True
            lock_attempted = True
            a._lock(session, current.page, item_id, lock, bounds)
            locked = a._read_tree_details(session, current.page, _target(change), bounds)
            if locked.selected["ID"] != item_id or canonical_hash(locked.snapshot) != prepared["before_fingerprint"]:
                raise WriteFailure("conflict", "The item changed while acquiring its editing lock.")
            a._authorize_commit(source, change, context)
            if context.check_cancelled():
                raise WriteCancelled()
            if persist and persist({"item_id": change.parent_id, "upload_attempted": True}):
                raise WriteCancelled()
            attempted = True
            descriptor = self._upload(session, current, change, bounds, source)
            if persist and persist({"uploaded_descriptor": descriptor}):
                raise WriteCancelled()
            a._authorize_commit(source, change, context)
            contents = deepcopy(locked.details["ItemContents"])
            selected = next(f for f in contents if f.get("FieldName") == change.fields["field_name"])
            if selected["Attachments"] is None:
                selected["Attachments"] = []
            for i, attachment in enumerate(selected["Attachments"]):
                attachment["Order"] = i + 2
            selected["Attachments"].insert(0, descriptor)
            for field in contents:
                field["IsEdit"] = True
            body = {"EncrID": item_id, "itemDetailsDTO": deepcopy(locked.details["ItemDetails"]), "itemContentDTO": contents}
            if persist and persist({"mutation_attempted": True}):
                raise WriteCancelled()
            a._authorize_commit(source, change, context)
            a._save(session, current.page, item_id, body)
            result = self._verify(session, source, config, prepared, change, bounds, descriptor)
        except (WriteFailure, ValueError, TypeError, KeyError):
            if not attempted:
                raise
            result = {"state": "uncertain", "item_id": change.parent_id,
                      "reason": "Upload or item save may have succeeded; recovery reads only, without replay."}
        finally:
            if lock_attempted:
                try:
                    a._release(session, current.page, item_id, lock)
                    if persist:
                        persist({"lock_release_confirmed": True})
                except Exception:
                    if persist:
                        persist({"lock_release_error": True})
                    if result is not None:
                        result["lock_release_error"] = True
        return result

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change, config = self._prepared(source, prepared, context, bounds)
        if not item.get("mutation_attempted") or not isinstance(item.get("uploaded_descriptor"), dict):
            return {"state": "uncertain", "item_id": change.parent_id,
                    "reason": "The upload has no durable item-save attempt and descriptor; no write replay."}
        session = self._session(source, change, config, context, bounds, deadline)
        return self._verify(session, source, config, prepared, change, bounds, item["uploaded_descriptor"])
