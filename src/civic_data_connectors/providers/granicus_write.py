"""Exact-plan Granicus SOAP model writes through the existing coordinator."""

from copy import deepcopy
from dataclasses import asdict
import base64
import hashlib
import json
import uuid
from time import monotonic
from urllib.parse import urlsplit

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteChange, WriteFailure
from .contracts import Response
from .granicus_platform import numeric_id
from .granicus_soap import Session, contract, request_xml

MODELS = {
    "event": ("EventData", "GetEvent", "EventID", "UpdateEvent", "event"),
    "recording": ("ClipData", "GetClip", "ClipID", "UpdateClip", "clip"),
    "agenda_item": ("MetaDataData", "GetMetaData", "MetaDataID", "UpdateMetaData", "MetaData"),
}
# SDK EventData properties explicitly described as system-assigned/ignored.
EVENT_SERVER_FIELDS = {"Status", "AgendaRolloverID", "MeetingTime", "AgendaPostedDate", "NextStartDate"}


class _Bridge:
    def __init__(self, transport):
        self.transport = transport

    def request(self, url, **kwargs):
        if kwargs["allow_redirects"] is not False:
            raise ValueError("SOAP sessions cannot follow redirects.")
        response = self.transport.send(url, method=kwargs["method"], body=kwargs["body"],
            headers=kwargs["headers"], byte_limit=kwargs["byte_limit"], deadline_seconds=kwargs["deadline_seconds"])
        return Response(url, response.content, "text/xml", response.status, response.headers,
                        response.set_cookie_headers)


class GranicusWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__("granicus", transport)

    def _session(self, source, context, bounds, deadline):
        return Session(source, context, bounds, _Bridge(self.transport), deadline=deadline)

    def credentials(self, source, context):
        self.validate_source(source, context)
        return context.credentials["granicus"]

    def validate_source(self, source, context):
        from ..models import Bounds
        if source.options or source.input_format not in {None, "granicus-platform-soap-xml"}:
            raise ValueError("Granicus writes require an explicit SOAP source without options.")
        Session(source, context, Bounds(), _Bridge(self.transport))

    def authorize(self, source, change, context):
        config = self.credentials(source, context)
        if change.entity == "chunked_recording":
            from .granicus_media import authorize
            authorize(self, source, change, context)
            return
        if change.entity == "generated_minutes":
            from .granicus_minutes import authorize
            authorize(self, source, change, context)
            return
        if change.entity == "agenda_tree":
            from .granicus_metadata import authorize
            authorize(self, source, change, context)
            return
        if change.entity == "recording_publication":
            self._publication_policy(source, change, context)
            return
        if change.entity == "recording" and change.operation == "upload":
            self._media_policy(source, change, context)
            return
        if change.entity == "document":
            self._document_policy(source, change, context)
            return
        create = change.entity == "event" and change.operation == "create"
        if change.entity not in MODELS or (change.operation != "update" and not create) or change.files:
            raise WriteFailure("mapping_unverified", "This adapter currently maps documented full-model event/recording/agenda_item updates.")
        if create:
            if (change.resource_id is not None or "event:create" not in config.get("permissions", ())
                    or not isinstance(change.fields, dict)
                    or str(change.fields.get("ForeignID")) not in config.get("foreign_ids", ())):
                raise WriteFailure("permission_denied", "Creation requires an explicitly authorized source ForeignID.")
            numeric_id(change.fields["ForeignID"])
            return
        identity = str(numeric_id(change.resource_id))
        if (f"{change.entity}:update" not in config.get("permissions", ())
                or identity not in config.get("resource_ids", ())):
            raise WriteFailure("permission_denied", "The exact SOAP resource/operation is outside server policy.")
        if change.entity != "event" and (not change.meeting_id
                or str(change.meeting_id) not in config.get("meeting_ids", ())):
            raise WriteFailure("permission_denied", "Related media/items require an explicitly authorized meeting relationship.")

    @staticmethod
    def _read(session, change):
        _, method, key, _, _ = MODELS[change.entity]
        value, _ = session.call(method, {key: numeric_id(change.resource_id)})
        result = next(iter(value.values()))
        if not isinstance(result, dict) or str(result.get("ID")) != str(change.resource_id):
            raise ValueError("SOAP readback differs from the exact resource identity.")
        return result

    def prepare(self, source, change, context, bounds, deadline):
        self.authorize(source, change, context)
        if change.entity == "chunked_recording":
            from .granicus_media import prepare
            return prepare(self, source, change, context, bounds, deadline)
        if change.entity == "generated_minutes":
            from .granicus_minutes import prepare
            return prepare(self, source, change, context, bounds, deadline)
        if change.entity == "agenda_tree":
            from .granicus_metadata import prepare
            return prepare(self, source, change, context, bounds, deadline)
        if change.entity == "recording_publication":
            return self._prepare_publication(source, change, context, bounds, deadline)
        if change.entity == "recording" and change.operation == "upload":
            return self._prepare_media(source, change, context, bounds, deadline)
        if change.entity == "document":
            return self._prepare_document(source, change, context, bounds, deadline)
        create = change.operation == "create"
        read_only = {"ID", "UID", "LastModified"}
        if change.entity == "event":
            read_only |= EVENT_SERVER_FIELDS
        if not isinstance(change.fields, dict) or not change.fields or (not create and set(change.fields) & read_only):
            raise ValueError("Supply a nonempty documented patch without changing provider identity or server-owned fields.")
        model, _, _, operation, parameter = MODELS[change.entity]
        fields = contract()["types"][model]["fields"]
        if set(change.fields) - set(fields):
            raise ValueError("The patch contains fields absent from the pinned vendor model.")
        session = self._session(source, context, bounds, deadline)
        try:
            if create:
                if set(change.fields) != set(fields) or change.fields["ID"] != 0 or change.fields["UID"] != "":
                    raise ValueError("Creation requires the full documented EventData model with unassigned ID0/empty UID.")
                found, _ = session.call("GetEventsByForeignID", {"ForeignID": change.fields["ForeignID"]})
                if found.get("events") != []:
                    raise WriteFailure("conflict", "The source ForeignID already exists or cannot be verified absent.")
                before = None
            else:
                before = self._read(session, change)
        finally:
            session.close()
        # Full-model replacements cannot silently drop or invent unknown fields.
        if not create and set(before) != set(fields):
            raise ValueError("A full documented SOAP model is required; missing/unknown fields remain unmapped.")
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected full-model hash differs from current provider state.")
        after = deepcopy(change.fields) if create else {**deepcopy(before), **deepcopy(change.fields)}
        if create:
            operation, parameter = "CreateEvent", "EventData"
        request_xml(operation, {parameter: after}, byte_limit=bounds.transfer_bytes)
        return {"change": asdict(change), "native": {"method": "POST", "url": session.url,
                "content_type": "text/xml", "body": {parameter: after}, "headers": {}, "files": [],
                "soap_method": operation}, "before": before, "after": after,
                "before_fingerprint": fingerprint, "expected_version": fingerprint,
                "read_url": session.url, "identity_field": "ID", "revision_field": "LastModified",
                "contract_revision": contract()["source_revision"],
                "conflict_semantics": "preflight_full_model_compare_not_atomic_provider_cas"}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        if change.entity == "chunked_recording":
            from .granicus_media import apply
            return apply(self, source, prepared, context, bounds, deadline, persist=persist)
        if change.entity == "generated_minutes":
            from .granicus_minutes import apply
            return apply(self, source, prepared, context, bounds, deadline, persist=persist)
        if change.entity == "agenda_tree":
            from .granicus_metadata import apply
            return apply(self, source, prepared, context, bounds, deadline, persist=persist)
        if change.entity == "recording_publication":
            return self._apply_publication(source, prepared, context, bounds, deadline, persist=persist)
        if change.entity == "recording" and change.operation == "upload":
            return self._apply_media(source, prepared, context, bounds, deadline, persist=persist)
        if change.entity == "document":
            return self._apply_document(source, prepared, context, bounds, deadline, persist=persist)
        session = self._session(source, context, bounds, deadline)
        try:
            if change.operation == "create":
                found, _ = session.call("GetEventsByForeignID", {"ForeignID": change.fields["ForeignID"]})
                if found.get("events") != []:
                    raise WriteFailure("conflict", "The source ForeignID changed after creation was planned.")
            elif canonical_hash(self._read(session, change)) != prepared["before_fingerprint"]:
                raise WriteFailure("conflict", "SOAP resource changed after plan preparation.")
            if persist:
                persist({"resource_id": change.resource_id, "read_url": session.url})
            try:
                returned, _ = session.call(prepared["native"]["soap_method"], prepared["native"]["body"])
            except ValueError:
                raise AmbiguousWrite() from None
            if change.operation == "create":
                identity = numeric_id(returned.get("EventID"))
                if persist:
                    persist({"resource_id": identity})
                from dataclasses import replace
                read_change = replace(change, resource_id=identity)
            else:
                read_change = change
            return self._outcome(prepared, self._read(session, read_change))
        finally:
            try:
                session.close()
            except ValueError:
                pass  # Logout does not change a verified mutation/readback outcome.

    @staticmethod
    def _outcome(prepared, actual):
        # Providers may update LastModified; require every planned patch value,
        # retain full readback and never pretend a server CAS was performed.
        ignored = {"LastModified", "ID", "UID"} if prepared["change"]["operation"] == "create" else {"LastModified"}
        if prepared["change"]["entity"] == "event":
            ignored |= EVENT_SERVER_FIELDS
        matches = all(actual.get(key) == value for key, value in prepared["after"].items() if key not in ignored)
        return {"state": "succeeded" if matches else "uncertain", "resource_id": actual.get("ID"),
                "readback": actual, "reconciled": True,
                "provider_revision": actual.get("LastModified"),
                **({} if matches else {"reason": "SOAP readback differs from the intended patch; no mutation replay."})}

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        if change.entity == "chunked_recording":
            from .granicus_media import reconcile
            return reconcile(self, source, prepared, item, context, bounds, deadline)
        if change.entity == "generated_minutes":
            from .granicus_minutes import reconcile
            return reconcile(self, source, prepared, item, context, bounds, deadline)
        if change.entity == "agenda_tree":
            from .granicus_metadata import reconcile
            return reconcile(self, source, prepared, item, context, bounds, deadline)
        if change.entity == "recording_publication":
            session = self._session(source, context, bounds, deadline)
            try:
                return self._publication_outcome(session, prepared, item.get("publication_result"))
            finally:
                self._close_document_session(session)
        if change.entity == "recording" and change.operation == "upload":
            identity = item.get("resource_id")
            if identity is None:
                return {"state": "uncertain", "reason": "MediaVault upload response identity was lost; no documented unique lookup or safe automatic replay."}
            session = self._session(source, context, bounds, deadline)
            try:
                return self._media_outcome(session, prepared, identity)
            finally:
                self._close_document_session(session)
        if change.entity == "document":
            session = self._session(source, context, bounds, deadline)
            try:
                return self._document_outcome(source, prepared, context, bounds, deadline, session)
            finally:
                self._close_document_session(session)
        session = self._session(source, context, bounds, deadline)
        try:
            if change.operation == "create":
                found, _ = session.call("GetEventsByForeignID", {"ForeignID": change.fields["ForeignID"]})
                candidates = found.get("events")
                if not isinstance(candidates, list) or len(candidates) != 1 or not isinstance(candidates[0], dict):
                    return {"state": "uncertain", "reason": "Creation has no unique ForeignID readback; no mutation replay."}
                return self._outcome(prepared, candidates[0])
            return self._outcome(prepared, self._read(session, change))
        finally:
            session.close()


    def _publication_policy(self, source, change, context):
        config = self.credentials(source, context)
        fields = change.fields
        if (change.operation != "update" or change.files
                or set(fields) != set(contract()["types"]["PublishClipData"]["fields"])
                or type(fields.get("Public")) is not bool
                or str(numeric_id(fields.get("ClipID"))) != str(numeric_id(change.resource_id))):
            raise ValueError("Publication requires the full documented PublishClipData and explicit Public boolean for the exact clip.")
        if ("recording_publication:update" not in config.get("permissions", ())
                or str(change.resource_id) not in config.get("resource_ids", ())
                or not change.meeting_id or str(change.meeting_id) not in config.get("meeting_ids", ())):
            raise WriteFailure("permission_denied", "Publication requires explicit resource, meeting and publication grants.")

    @staticmethod
    def _publication_read(session, prepared):
        identity = numeric_id(prepared["change"]["resource_id"])
        values, _ = session.call("GetClip", {"ClipID": identity})
        actual = values.get("clip")
        if not isinstance(actual, dict) or str(actual.get("ID")) != str(identity):
            raise ValueError("Publication readback differs from the exact clip identity.")
        return actual

    def _prepare_publication(self, source, change, context, bounds, deadline):
        fields = deepcopy(change.fields)
        request_xml("PublishClip", {"PublishClipData": fields}, byte_limit=bounds.transfer_bytes)
        prepared = {"change": asdict(change)}
        session = self._session(source, context, bounds, deadline)
        try:
            before = self._publication_read(session, prepared)
        finally:
            self._close_document_session(session)
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "Publication baseline differs from the expected clip state.")
        return {**prepared, "native": {"method": "POST", "url": session.url,
            "soap_method": "PublishClip", "body": {"PublishClipData": fields},
            "content_type": "text/xml", "headers": {}, "files": []},
            "before": before, "before_fingerprint": fingerprint, "expected_version": fingerprint,
            "after": fields, "contract_revision": contract()["source_revision"],
            "publication_effect": "Public visibility requested" if fields["Public"] else "Non-public visibility requested",
            "conflict_semantics": "preflight_clip_compare_not_atomic_provider_cas"}

    def _apply_publication(self, source, prepared, context, bounds, deadline, *, persist):
        session = self._session(source, context, bounds, deadline)
        try:
            if canonical_hash(self._publication_read(session, prepared)) != prepared["before_fingerprint"]:
                raise WriteFailure("conflict", "The clip changed after publication was planned.")
            if persist:
                persist({"resource_id": prepared["change"]["resource_id"]})
            try:
                result, _ = session.call("PublishClip", prepared["native"]["body"])
            except ValueError:
                raise AmbiguousWrite() from None
            acknowledgement = result.get("PublishClipResult")
            if persist:
                persist({"publication_result": acknowledgement})
            return self._publication_outcome(session, prepared, acknowledgement)
        finally:
            self._close_document_session(session)

    def _publication_outcome(self, session, prepared, acknowledgement):
        actual = self._publication_read(session, prepared)
        # Status is the SDK's visibility state, not a media processing guarantee.
        wanted = "Public" if prepared["after"]["Public"] else "Not-Public"
        acknowledged = (isinstance(acknowledgement, dict)
            and str(acknowledgement.get("ClipID")) == str(actual["ID"]))
        matched = actual.get("Status") == wanted
        return {"state": "succeeded" if acknowledged and matched else "uncertain",
            "resource_id": actual["ID"], "readback": actual, "provider_status": actual.get("Status"),
            "publication_result": acknowledgement, "reconciled": True,
            "publication_requested": prepared["after"]["Public"], "playable_media_verified": False,
            "readback_verified_fields": ["ClipID", "Public"] if matched else ["ClipID"],
            "submitted_only_fields": ["Name", "Title", "TextField", "TemplateID", "MetaID"],
            "verification_scope": "PublishClip acknowledgement and independent clip identity/visibility only; other publication fields are submitted exactly but have no documented independent readback mapping.",
            **({} if acknowledged and matched else {"reason": "Publication acknowledgement or requested visibility is unverified; no mutation replay."})}

    def _document_policy(self, source, change, context):
        config = self.credentials(source, context)
        fields = change.fields
        if (change.operation not in {"update", "upload"} or not isinstance(fields, dict)
                or fields.get("ParentType") not in {"event", "clip"}
                or fields.get("Kind") not in {"agenda", "minutes"}
                or (fields["ParentType"] == "event" and fields["Kind"] != "agenda")):
            raise ValueError("Use an event agenda or clip agenda/minutes document operation.")
        if (f"document:{change.operation}" not in config.get("permissions", ())
                or str(numeric_id(change.resource_id)) not in config.get("resource_ids", ())
                or not change.meeting_id or str(change.meeting_id) not in config.get("meeting_ids", ())):
            raise WriteFailure("permission_denied", "Document operation/resource/meeting exceeds exact server policy.")
        if change.operation == "update":
            allowed = {"ParentType", "Kind", "URL"}
            if fields["ParentType"] == "clip" and fields["Kind"] == "minutes" and "Name" in fields:
                allowed.add("Name")
            if set(fields) != allowed or change.files:
                raise ValueError("Document URL updates require only ParentType, Kind and URL, without files.")
            self._document_url(source, fields["URL"], config)
        elif (set(fields) != ({"ParentType", "Kind", "Description", "Name"}
                              if fields["Kind"] == "minutes" else {"ParentType", "Kind", "Description"})
              or len(change.files) != 1 or (fields["ParentType"], fields["Kind"]) == ("clip", "agenda")):
            raise ValueError("UploadEventAgendaDocument or UploadClipMinutesDocument requires explicit description, optional documented minutes Name, and one file.")

    @staticmethod
    def _document_url(source, value, config):
        if not isinstance(value, str):
            raise ValueError("A supplied document HTTPS URL is required.")
        parsed = urlsplit(value)
        origin = f"{parsed.scheme}://{parsed.hostname}"
        allowed = [f"https://{urlsplit(source.url).hostname}", *config.get("document_origins", ())]
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in {None, 443} or parsed.fragment or origin not in allowed
                or any(c in value for c in "\r\n\0")):
            raise ValueError("The document URL is outside the explicit HTTPS origin policy.")
        return value

    @staticmethod
    def _document_read(session, change):
        event = change.fields["ParentType"] == "event"
        value, _ = session.call("GetEvent" if event else "GetClip",
                                {"EventID" if event else "ClipID": numeric_id(change.resource_id)})
        record = next(iter(value.values()))
        if not isinstance(record, dict) or str(record.get("ID")) != str(change.resource_id):
            raise ValueError("Document parent readback has a different identity.")
        return record

    @staticmethod
    def _close_document_session(session):
        try:
            session.close()
        except ValueError:
            pass

    def _document_parameters(self, prepared, bounds, *, data=None, location=""):
        change = WriteChange.from_dict(prepared["change"])
        fields = change.fields
        params = {"EventID" if fields["ParentType"] == "event" else "ClipID": numeric_id(change.resource_id)}
        if change.operation == "update":
            params["URL"] = fields["URL"]
            if "Name" in fields:
                params["Name"] = fields["Name"]
        else:
            part = prepared["native"]["files"][0]
            # Minutes have a documented SDK chunk protocol/1GB ceiling.
            # Agenda is a single SOAP Document; its encoded request remains
            # caller-bounded, without inventing a vendor 7MB restriction.
            maximum = 1_000_000_000 if fields["Kind"] == "minutes" else bounds.transfer_bytes
            if not 0 < part["reference"]["byte_length"] <= min(maximum, bounds.transfer_bytes):
                raise ValueError("The SOAP document exceeds its documented/adapter safe byte ceiling.")
            if data is None:
                chunked = prepared["native"].get("chunked_upload")
                with self._open_file(part) as stream:
                    data = stream.read(7_000_000 if chunked else part["reference"]["byte_length"])
                if chunked:
                    location = json.dumps({"action": "add", "id": chunked["id"]}, separators=(",", ":"))
            params["Document"] = {"Description": fields["Description"], "Location": location,
                                  "FileContents": base64.b64encode(data).decode("ascii"), "FileExtension": part["filename"].rsplit(".", 1)[-1]}
            if fields["Kind"] == "minutes":
                params["Name"] = fields["Name"]
        return params

    def _prepare_document(self, source, change, context, bounds, deadline):
        files = self._files(change, bounds)
        if files and (files[0]["part"] != "Document" or "." not in files[0]["filename"]):
            raise ValueError("The file part must be Document with an explicit filename extension.")
        fields = change.fields
        event = fields["ParentType"] == "event"
        method = ("UploadEventAgendaDocument" if event else "UploadClipMinutesDocument") if change.operation == "upload" else (
            "SetEventAgendaURL" if event else "SetClipAgendaURL" if fields["Kind"] == "agenda" else "SetClipMinutesURL")
        if change.operation == "update" and "Name" in fields:
            method = "SetClipMinutesURLWithName"
        session = self._session(source, context, bounds, deadline)
        try:
            before = self._document_read(session, change)
        finally:
            self._close_document_session(session)
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The document parent differs from its expected state.")
        prepared = {"change": asdict(change), "native": {"method": "POST", "url": session.url,
            "content_type": "text/xml", "headers": {}, "body": deepcopy(fields), "files": list(files),
            "soap_method": method}, "before": before, "before_fingerprint": fingerprint,
            "expected_version": fingerprint, "read_url": session.url,
            "contract_revision": contract()["source_revision"],
            "conflict_semantics": "preflight_full_parent_compare_not_atomic_provider_cas"}
        if files and fields["Kind"] == "minutes" and files[0]["reference"]["byte_length"] > 7_000_000:
            prepared["native"]["chunked_upload"] = {"id": str(uuid.uuid4()), "chunk_bytes": 7_000_000,
                "count": (files[0]["reference"]["byte_length"] + 6_999_999) // 7_000_000}
        request_xml(method, self._document_parameters(prepared, bounds), byte_limit=bounds.transfer_bytes)
        return prepared

    def _apply_document(self, source, prepared, context, bounds, deadline, *, persist):
        change = WriteChange.from_dict(prepared["change"])
        session = self._session(source, context, bounds, deadline)
        try:
            if canonical_hash(self._document_read(session, change)) != prepared["before_fingerprint"]:
                raise WriteFailure("conflict", "The document parent changed after planning.")
            parameters = self._document_parameters(prepared, bounds)
            if persist:
                persist({"resource_id": change.resource_id, "read_url": session.url})
            try:
                chunked = prepared["native"].get("chunked_upload")
                if chunked:
                    # Mirror the pinned SDK: add chunks, finish on the last.
                    # Any uncertain response goes to readback only; never add a
                    # chunk twice or restart a partially received document.
                    with self._open_file(prepared["native"]["files"][0]) as stream:
                        for index in range(chunked["count"]):
                            data = stream.read(chunked["chunk_bytes"])
                            location = json.dumps({"action": "finish" if index == chunked["count"]-1 else "add",
                                                   "id": chunked["id"]}, separators=(",", ":"))
                            parameters = self._document_parameters(prepared, bounds, data=data, location=location)
                            session.call(prepared["native"]["soap_method"], parameters)
                            if persist:
                                persist({"completed_chunks": index+1, "upload_id": chunked["id"]})
                else:
                    session.call(prepared["native"]["soap_method"], parameters)
            except ValueError:
                raise AmbiguousWrite() from None
            return self._document_outcome(source, prepared, context, bounds, deadline, session)
        finally:
            self._close_document_session(session)

    def _document_outcome(self, source, prepared, context, bounds, deadline, session):
        change = WriteChange.from_dict(prepared["change"])
        actual = self._document_read(session, change)
        value = actual.get("AgendaFile" if change.fields["Kind"] == "agenda" else "MinutesFile")
        matches = value == change.fields.get("URL") if change.operation == "update" else False
        digest = None
        if change.operation == "upload":
            try:
                url = self._document_url(source, value, self.credentials(source, context))
                remaining = min(bounds.transfer_bytes - session.transferred,
                                prepared["native"]["files"][0]["reference"]["byte_length"] + 1)
                if context.check_cancelled() or monotonic() >= deadline or remaining <= 0:
                    raise ValueError("Readback bounds exhausted.")
                # Document reads never receive private SOAP cookies or authorization headers.
                response = self.transport.send(url, method="GET", body=None, headers={},
                    byte_limit=remaining, deadline_seconds=max(0.001, deadline-monotonic()))
                content = response.content
                session.transferred += len(content)
                session.requests += 1
                if len(content) > remaining or monotonic() >= deadline:
                    raise ValueError("Document readback exceeded bounds.")
                reference = prepared["native"]["files"][0]["reference"]
                digest = hashlib.sha256(content).hexdigest()
                matches = response.status == 200 and len(content) == reference["byte_length"] and digest == reference["sha256"]

            except Exception:
                matches = False
        if matches and "Name" in change.fields:
            docs, _ = session.call("GetClipMinutesDocuments", {"ClipID": numeric_id(change.resource_id)})
            matches = any(isinstance(item, dict) and item.get("Name") == change.fields["Name"]
                          for item in docs.get("MinutesDocuments", []))
        return {"state": "succeeded" if matches else "uncertain", "resource_id": actual["ID"],
                "readback": actual, "reconciled": True, "document_sha256": digest,
                **({} if matches else {"reason": "The exact planned document could not be independently verified; no upload replay."})}


    def _media_policy(self, source, change, context):
        config = self.credentials(source, context)
        if (change.resource_id is not None or set(change.fields) != {"FolderID", "NewFileName"}
                or "recording:upload" not in config.get("permissions", ())
                or str(numeric_id(change.fields["FolderID"])) not in config.get("folder_ids", ())
                or change.parent_id not in {None, change.fields["FolderID"], str(change.fields["FolderID"])}
                or not change.meeting_id or str(change.meeting_id) not in config.get("meeting_ids", ())):
            raise WriteFailure("permission_denied", "MediaVault upload requires exact folder/meeting policy and documented parameters.")
        if len(change.files) != 1:
            raise ValueError("MediaVault upload requires one explicitly approved media file.")

    @staticmethod
    def _media_folder(session, folder_id):
        values, _ = session.call("GetClips", {"FolderID": numeric_id(folder_id)})
        clips = values.get("clips")
        if not isinstance(clips, list) or any(not isinstance(clip, dict) for clip in clips):
            raise ValueError("The documented folder-clips result could not be verified.")
        ids = [numeric_id(clip.get("ID")) for clip in clips]
        if len(ids) != len(set(ids)):
            raise ValueError("Folder clips repeat a provider identity.")
        return clips

    def _prepare_media(self, source, change, context, bounds, deadline):
        from .granicus_vault import VaultSession, request_xml as vault_xml
        parts = self._files(change, bounds)
        part = parts[0]
        if (part["part"] != "bytes" or part["filename"] != change.fields["NewFileName"]
                or not part["content_type"].startswith(("video/", "audio/"))
                or not part["reference"]["byte_length"]):
            raise ValueError("Approve one nonempty audio/video bytes part with matching NewFileName.")
        session = self._session(source, context, bounds, deadline)
        vault = VaultSession(session, change.fields["FolderID"])
        try:
            before = self._media_folder(session, change.fields["FolderID"])
            if any(clip.get("FileName") == change.fields["NewFileName"] for clip in before):
                raise WriteFailure("conflict", "A folder clip already uses the supplied physical filename.")
            vault._connect()  # Read-only folder interface + private impersonation setup.
            endpoint = vault._url
            # Validate exact literal serialization without persisting its private header.
            vault_xml("UploadFile", {**change.fields, "bytes": self._file_bytes(part)},
                service_host=urlsplit(session.url).hostname, token="", byte_limit=bounds.transfer_bytes)
        finally:
            vault.close()
            self._close_document_session(session)
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "Folder state differs from the expected upload baseline.")
        return {"change": asdict(change), "native": {"method": "POST", "url": endpoint,
            "content_type": "text/xml", "headers": {}, "body": deepcopy(change.fields), "files": list(parts),
            "soap_method": "UploadFile", "publication": "No PublishClip call or inferred public visibility"},
            "before": before, "before_fingerprint": fingerprint, "expected_version": fingerprint,
            "contract_revision": contract()["source_revision"], "read_url": session.url,
            "conflict_semantics": "preflight_folder_compare_not_atomic_provider_cas"}

    def _apply_media(self, source, prepared, context, bounds, deadline, *, persist):
        from .granicus_vault import VaultSession
        change = WriteChange.from_dict(prepared["change"])
        session = self._session(source, context, bounds, deadline)
        vault = VaultSession(session, change.fields["FolderID"])
        try:
            if canonical_hash(self._media_folder(session, change.fields["FolderID"])) != prepared["before_fingerprint"]:
                raise WriteFailure("conflict", "The upload folder changed after planning.")
            vault._connect()
            if vault._url != prepared["native"]["url"]:
                raise WriteFailure("conflict", "The folder's authorized MediaVault endpoint changed.")
            data = self._file_bytes(prepared["native"]["files"][0])
            if persist:
                persist({"target_folder_id": change.fields["FolderID"]})
            try:
                result = vault.call("UploadFile", {**change.fields, "bytes": data})
            except ValueError:
                raise AmbiguousWrite() from None
            identity = numeric_id(result.get("UploadFileResult"))
            if persist:
                persist({"resource_id": identity})
            return self._media_outcome(session, prepared, identity)
        finally:
            vault.close()
            self._close_document_session(session)

    @staticmethod
    def _media_outcome(session, prepared, identity):
        values, _ = session.call("GetClip", {"ClipID": numeric_id(identity)})
        actual = values.get("clip")
        if not isinstance(actual, dict) or str(actual.get("ID")) != str(identity):
            raise ValueError("The uploaded clip identity could not be independently read back.")
        return {"state": "succeeded", "resource_id": identity, "readback": actual, "reconciled": True,
                "submitted_file_sha256": prepared["native"]["files"][0]["reference"]["sha256"],
                "verification_scope": "Documented UploadFile acknowledgement plus independent Clip identity; submitted bytes are plan-verified, not a remote original-byte claim.",
                "provider_status": actual.get("Status"), "playable_media_verified": False,
                "publication_requested": False}
