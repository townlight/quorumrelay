"""Exact-plan Granicus SOAP model writes through the existing coordinator."""

from copy import deepcopy
from dataclasses import asdict

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
        create = change.operation == "create"
        if not isinstance(change.fields, dict) or not change.fields or ("ID" in change.fields and not create):
            raise ValueError("Supply a nonempty documented patch without changing provider identity.")
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
        matches = all(actual.get(key) == value for key, value in prepared["after"].items() if key not in ignored)
        return {"state": "succeeded" if matches else "uncertain", "resource_id": actual.get("ID"),
                "readback": actual, "reconciled": True,
                "provider_revision": actual.get("LastModified"),
                **({} if matches else {"reason": "SOAP readback differs from the intended patch; no mutation replay."})}

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
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
