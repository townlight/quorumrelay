"""Exact-plan PublishingService record writes; no publication or upload inference."""
from copy import deepcopy
from dataclasses import asdict
import json
from xml.etree import ElementTree as ET

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure
from .escribe_publishing import Session, contract, endpoint, request_xml
from .identification import validate_source

MODELS = {"meeting": "Meeting", "agenda": "Agenda", "agenda_item": "AgendaItem",
          "attachment": "Attachment", "document": "Document",
          "package": "Package", "bookmark": "Bookmark", "resolution": "Resolution"}


def native_identity(entity, value):
    if entity in {"agenda", "agenda_item", "attachment", "bookmark", "resolution"}:
        if not isinstance(value, str):
            raise ValueError("Compound resource_id requires the canonical JSON native identifier object.")
        result = json.loads(value)
        if not isinstance(result, dict) or identity_key(result) != value:
            raise ValueError("Compound identity must use canonical sorted JSON without spaces.")
        return result
    if entity in {"document", "package"}:
        if type(value) is int and 0 < value < 2**31:
            return value
        if isinstance(value, str) and value.isascii() and value.isdecimal():
            number = int(value)
            if str(number) == value and 0 < number < 2**31:
                return number
        raise ValueError("Document/package resource_id requires a positive canonical Int32 without coercion.")
    return value


def identity_key(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) if isinstance(value, dict) else str(value)


def verify_identifier(entity, identity):
    fields = contract()["operations"][MODELS[entity] + "GetById"]["request"]
    kind = contract()["types"].get(fields[0]["type"], {}).get("fields")
    if kind is not None and (not isinstance(identity, dict)
            or set(identity) != {field["name"] for field in kind}
            or any(value is None or value == "" for value in identity.values())):
        raise ValueError("Every native compound identifier component is required.")
    request_xml(MODELS[entity] + "GetById", {fields[0]["name"]: identity}, "https://example.org")


class EscribeWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__("escribe", transport)

    def credentials(self, source, context):
        config = context.credentials.get("escribe")
        if (not isinstance(config, dict) or config.get("endpoint") != endpoint(source)
                or not context.tenant or config.get("tenant") != context.tenant
                or source.namespace not in config.get("allowed_namespaces", ())):
            raise WriteFailure("permission_denied", "Exact PublishingService endpoint, namespace and tenant policy are required.")
        # The pinned WSDL declares HTTPS, not a token/authentication exchange.
        # Authentication, if required by a deployment, belongs to the injected transport.
        return config

    def validate_source(self, source, context):
        endpoint(source)
        namespace = validate_source(source, context)
        if not source.namespace or source.namespace != namespace:
            raise ValueError("Writes require the exact provider-derived namespace.")
        self.credentials(source, context)

    def authorize(self, source, change, context):
        if change.entity == "document" and change.operation == "upload":
            from .escribe_upload import policy
            policy(self, source, change, context)
            return
        self.validate_source(source, context)
        config = self.credentials(source, context)
        if (change.entity not in MODELS or change.operation not in {"create", "update"}
                or change.files or change.parent_id is not None or change.language is not None
                or change.page_number is not None):
            raise WriteFailure("mapping_unverified", "Only exact native record create/update is mapped; no file upload/publication actions.")
        if f"{change.entity}:{change.operation}" not in config.get("permissions", ()):
            raise WriteFailure("permission_denied", "The exact native entity operation is not authorized.")
        if change.operation == "update":
            identity = native_identity(change.entity, change.resource_id)
            verify_identifier(change.entity, identity)
            if identity_key(identity) not in config.get("resource_ids", ()):
                raise WriteFailure("permission_denied", "The exact resource identity is not authorized.")
        elif change.resource_id is not None or change.expected_version is not None:
            raise ValueError("Create requires no existing resource/version; supply the complete explicit native model.")
        if change.entity in {"agenda", "agenda_item", "attachment", "bookmark", "package", "resolution"}:
            if not change.meeting_id or change.meeting_id not in config.get("meeting_ids", ()):
                raise WriteFailure("permission_denied", "The exact related meeting must be authorized.")

    def _session(self, source, context, bounds, deadline):
        return Session(source, context, bounds, self.transport,
                       storage=self.file_engine.storage if self.file_engine else None, deadline=deadline)

    @staticmethod
    def _parameter(method, value):
        fields = contract()["operations"][method]["request"]
        if len(fields) != 1:
            raise ValueError("This mapping requires one exact declared method parameter.")
        return {fields[0]["name"]: value}

    def _read(self, session, entity, identity):
        method = MODELS[entity] + "GetById"
        value, _ = session.call(method, self._parameter(method, identity))
        if not isinstance(value, dict) or value.get("Id") != identity:
            raise ValueError("Readback does not identify the exact selected native resource.")
        return value

    def _parent(self, source, change, value, context):
        config = self.credentials(source, context)
        if change.entity == "meeting":
            if value.get("PortalId") not in config.get("portal_ids", ()):
                raise WriteFailure("permission_denied", "The meeting's exact native portal is not authorized.")
        elif change.entity == "package":
            if value.get("MeetingId") != change.meeting_id:
                raise WriteFailure("conflict", "The package does not bind the selected parent meeting.")
            if type(value.get("DocumentId")) is not int or value["DocumentId"] <= 0:
                raise ValueError("An explicit positive existing native DocumentId is required.")
        elif change.entity in {"agenda", "agenda_item", "attachment", "bookmark", "resolution"}:
            if not isinstance(value.get("Id"), dict) or value["Id"].get("MeetingId") != change.meeting_id:
                raise WriteFailure("conflict", "The native model does not bind the selected parent meeting.")

    def prepare(self, source, change, context, bounds, deadline):
        if change.entity == "document" and change.operation == "upload":
            from .escribe_upload import prepare
            return prepare(self, source, change, context, bounds, deadline)
        self.authorize(source, change, context)
        if not isinstance(change.fields, dict) or not change.fields:
            raise ValueError("Supply explicit native fields.")
        model = MODELS[change.entity]
        schema_fields = contract()["types"][contract()["operations"][model + "Create"]["request"][0]["type"]]["fields"]
        names = {field["name"] for field in schema_fields}
        if set(change.fields) - names or (change.operation == "update" and "Id" in change.fields):
            raise ValueError("Unknown native fields and identity patches are not allowed.")
        session = self._session(source, context, bounds, deadline)
        if change.operation == "create":
            if set(change.fields) != names:
                raise ValueError("Create requires every field of the pinned native model, including explicit nulls.")
            before, after = None, deepcopy(change.fields)
            identity = after["Id"]
            verify_identifier(change.entity, identity)
            method = model + "Exists"
            found, _ = session.call(method, self._parameter(method, identity))
            if found is not False:
                raise WriteFailure("conflict", "The proposed native identity is not verified absent.")
        else:
            identity = native_identity(change.entity, change.resource_id)
            before = self._read(session, change.entity, identity)
            if set(before) != names:
                raise ValueError("Full current model is required before replacement; omitted fields cannot be preserved.")
            if change.expected_version is not None and change.expected_version != canonical_hash(before):
                raise WriteFailure("conflict", "The expected model fingerprint does not match current state.")
            self._parent(source, change, before, context)
            after = {**deepcopy(before), **deepcopy(change.fields)}
        self._parent(source, change, after, context)
        method = model + ("Create" if change.operation == "create" else "Update")
        parameters = self._parameter(method, after)
        body, _ = request_xml(method, parameters, source.url)
        if len(body) > min(bounds.parser_bytes, bounds.transfer_bytes):
            raise ValueError("The exact native request exceeds byte bounds.")
        return {"change": asdict(change), "before": before, "after": after,
                "before_fingerprint": canonical_hash(before), "resource_id": identity,
                "native": {"method": "POST", "url": source.url, "soap_method": method,
                           "body": parameters, "content_type": "application/soap+xml", "headers": {}, "files": []},
                "conflict_semantics": "preflight_full_model_compare_not_atomic_provider_cas",
                "contract_sha256": contract()["metadata_sha256"]["publishing.wsdl"]}

    def _outcome(self, source, prepared, identity, context, session):
        change = WriteChange.from_dict(prepared["change"])
        actual = self._read(session, change.entity, identity)
        self._parent(source, change, actual, context)
        expected = deepcopy(prepared["after"])
        # Creation returns the authoritative ID; no response-loss lookup is inferred.
        expected["Id"] = identity
        matches = actual == expected
        return {"state": "succeeded" if matches else "uncertain", "resource_id": identity_key(identity),
                "readback": actual, "reconciled": True,
                **({} if matches else {"reason": "Exact full-model readback differs; no automatic replay."})}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        if change.entity == "document" and change.operation == "upload":
            from .escribe_upload import apply
            return apply(self, source, prepared, context, bounds, deadline, persist=persist)
        self.authorize(source, change, context)
        session = self._session(source, context, bounds, deadline)
        identity = prepared["resource_id"]
        if change.operation == "update":
            current = self._read(session, change.entity, identity)
            if canonical_hash(current) != prepared["before_fingerprint"]:
                raise WriteFailure("conflict", "Native resource changed after the exact plan was prepared.")
        else:
            method = MODELS[change.entity] + "Exists"
            found, _ = session.call(method, self._parameter(method, identity))
            if found is not False:
                raise WriteFailure("conflict", "Creation target is no longer verified absent.")
        if persist and persist({"resource_id": identity_key(identity) if change.operation == "update" else None}):
            raise WriteCancelled()
        try:
            returned, _ = session.call(prepared["native"]["soap_method"], prepared["native"]["body"])
            if change.operation == "create":
                if returned is None:
                    raise ValueError("Creation returned no native identity.")
                identity = returned
                verify_identifier(change.entity, identity)
                if isinstance(identity, dict):
                    assigned = {"Id"} if change.entity in {"agenda_item", "bookmark"} else set()
                    if any(identity[k] != prepared["resource_id"][k] for k in identity if k not in assigned):
                        raise ValueError("Created identifier differs from the planned native parent/key.")
                if persist:
                    persist({"resource_id": identity_key(identity)})
            return self._outcome(source, prepared, identity, context, session)
        except (ValueError, TypeError, KeyError, OSError, TimeoutError, ET.ParseError):
            raise AmbiguousWrite() from None

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        if change.entity == "document" and change.operation == "upload":
            from .escribe_upload import reconcile
            return reconcile(self, source, prepared, item, context, bounds, deadline)
        self.authorize(source, change, context)
        if change.operation == "create" and item.get("resource_id") is None:
            return {"state": "uncertain", "reason": "Create response identity was lost; no unique lookup or mutation replay is inferred."}
        identity = (native_identity(change.entity, item["resource_id"]) if change.operation == "create"
                    else prepared["resource_id"])
        return self._outcome(source, prepared, identity, context,
                             self._session(source, context, bounds, deadline))
