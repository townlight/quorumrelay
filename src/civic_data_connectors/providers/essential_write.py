"""Documented Essential multimedia replacement with exact before/readback checks."""

from copy import deepcopy
from dataclasses import asdict
from time import monotonic
import json

from ..engine import canonical_hash
from ..write_adapters import NativeRequest, WriteAdapter, WriteChange, WriteFailure
from .account_api import ORIGINS, account_namespace, credentials, reject_credential_echo
from .account_reads import guid


class EssentialWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__("municode-meetings", transport)

    def credentials(self, source, context):
        try:
            return credentials(source, context)
        except ValueError:
            raise WriteFailure("permission_denied", "Trusted Essential origin, tenant and namespace binding is required.") from None

    def validate_source(self, source, context):
        if source.provider != self.provider or source.options:
            raise ValueError("Essential writes require the exact configured dev API source without options.")
        account_namespace(source)
        self.credentials(source, context)

    def authorize(self, source, change, context):
        self.validate_source(source, context)
        config = self.credentials(source, context)
        if change.entity != "meeting_multimedia" or change.operation != "update" or change.files:
            raise WriteFailure("mapping_unverified", "Only the documented full meeting_multimedia update is mapped.")
        identity = guid(change.resource_id)
        if change.meeting_id != identity:
            raise ValueError("The explicit meeting_id must equal the multimedia resource_id.")
        if ("meeting_multimedia:update" not in config.get("permissions", ())
                or identity not in config.get("meeting_ids", ())):
            raise WriteFailure("permission_denied", "This meeting multimedia update is outside server policy.")

    def _read(self, source, identity, context, bounds, deadline):
        url = ORIGINS[self.provider] + "/PublicApi/meeting/multimedia/" + guid(identity)
        value = self._call(source, context, NativeRequest("GET", url, "", {}, {}), bounds, deadline,
                           private_response=True)
        reject_credential_echo(json.dumps(value, ensure_ascii=False).encode(), self.credentials(source, context))
        structure = value.get("meetingStructure") if isinstance(value, dict) else None
        if (not isinstance(structure, dict) or structure.get("MeetingId") != identity):
            raise ValueError("The multimedia readback did not identify the exact meeting.")
        validate_structure(structure, identity)
        return structure

    def prepare(self, source, change, context, bounds, deadline):
        self.authorize(source, change, context)
        if not isinstance(change.key, str) or not change.key or len(change.key) > 200:
            raise ValueError("Each change requires a bounded key.")
        before = self._read(source, change.resource_id, context, bounds, deadline)
        if change.expected_version is not None and change.expected_version != canonical_hash(before):
            raise WriteFailure("conflict", "The expected full-structure hash differs from the current readback.")
        # Only documented update targets are patched; every other/unknown field is retained.
        if (not isinstance(change.fields, dict) or not change.fields
                or set(change.fields) - {"Id", "MeetingId", "PublishState", "AudioVideoDetails", "MultimediaItems"}):
            raise ValueError("Patch only documented MeetingStructure fields.")
        after = deepcopy(before)
        for key in ("Id", "MeetingId"):
            if key in change.fields and change.fields[key] != before[key]:
                raise ValueError("The full-model Id and MeetingId identities cannot be retargeted by a patch.")
        if "PublishState" in change.fields:
            after["PublishState"] = change.fields["PublishState"]
        if "AudioVideoDetails" in change.fields:
            patch = change.fields["AudioVideoDetails"]
            if not isinstance(patch, dict) or not patch or set(patch) - {"AudioVideoUrl", "AudioVideoProviderType"}:
                raise ValueError("AudioVideoDetails patch requires documented URL/provider type fields.")
            after["AudioVideoDetails"].update(deepcopy(patch))
        if "MultimediaItems" in change.fields:
            patches = change.fields["MultimediaItems"]
            if not isinstance(patches, list) or not patches:
                raise ValueError("MultimediaItems patches must be a nonempty list keyed by EntityId.")
            seen = set()
            for patch in patches:
                if (not isinstance(patch, dict) or "EntityId" not in patch or len(patch) < 2
                        or set(patch) - {"EntityId", "EntityName", "EntityTypeName", "TimeStamp",
                                        "MultimediaDisplayOptions", "CustomDisplay", "IncludeNumbering",
                                        "UseDefaultMultimediaSettings", "MultimediaBaseUrl"}):
                    raise ValueError("Patch documented multimedia item fields by existing EntityId.")
                identity = guid(patch["EntityId"])
                matches = [item for item in after["MultimediaItems"] if item["EntityId"] == identity]
                if identity in seen or len(matches) != 1:
                    raise ValueError("Each patch must identify one distinct existing multimedia item.")
                seen.add(identity)
                matches[0].update(deepcopy(patch))
        validate_structure(after, change.resource_id)
        if len(json.dumps(after, allow_nan=False).encode()) > min(bounds.parser_bytes, bounds.transfer_bytes):
            raise ValueError("The full update model exceeds configured byte bounds.")
        native = NativeRequest("POST", ORIGINS[self.provider] + "/PublicApi/meeting/multimedia/update/"
                               + change.resource_id, "application/json", after, {})
        return {"change": asdict(change), "native": native.public_dict(), "before": before, "after": after,
                "before_fingerprint": canonical_hash(before), "expected_version": canonical_hash(before),
                "identity_field": "MeetingId", "revision_field": None,
                "read_url": ORIGINS[self.provider] + "/PublicApi/meeting/multimedia/" + change.resource_id,
                "reconcile": None, "conflict_semantics": "preflight_read_compare_not_atomic_upstream_cas"}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        now = self._read(source, change.resource_id, context, bounds, deadline)
        if canonical_hash(now) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "Provider state changed after the exact plan was prepared.")
        if monotonic() >= deadline:
            raise WriteFailure("deadline_exceeded", "Deadline expired before mutation.")
        if persist:
            persist({"resource_id": change.resource_id, "read_url": prepared["read_url"]})
        # Update response schema is unspecified. Do not assume JSON or an ID receipt.
        self._call(source, context, NativeRequest(**prepared["native"]), bounds, deadline, raw=True)
        return self.reconcile(source, prepared, {}, context, bounds, deadline)

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        value = self._read(source, change.resource_id, context, bounds, deadline)
        if canonical_hash(value) != canonical_hash(prepared["after"]):
            return {"state": "uncertain", "resource_id": change.resource_id,
                    "readback": value, "reason": "Exact full structure readback differs; no mutation replay."}
        return {"state": "succeeded", "resource_id": change.resource_id, "readback": value,
                "reconciled": True, "provider_revision": None}


def validate_structure(value, meeting_id):
    guid(value.get("Id"))
    if value.get("MeetingId") != meeting_id or type(value.get("PublishState")) is not int:
        raise ValueError("The full structure requires the exact meeting and integer PublishState.")
    details = value.get("AudioVideoDetails")
    if (not isinstance(details, dict) or type(details.get("AudioVideoProviderType")) is not int
            or not isinstance(details.get("AudioVideoUrl"), str)):
        raise ValueError("The full AudioVideoDetails model is required.")
    items = value.get("MultimediaItems")
    if not isinstance(items, list):
        raise ValueError("MultimediaItems must be a list.")
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each multimedia item must be an object.")
        identity = guid(item.get("EntityId"))
        if identity in seen:
            raise ValueError("Multimedia item EntityId values must be unique.")
        seen.add(identity)
        for key in ("EntityName", "EntityTypeName", "CustomDisplay", "MultimediaBaseUrl"):
            if not isinstance(item.get(key), str):
                raise ValueError("The full documented multimedia item model is required.")
        for key in ("TimeStamp", "MultimediaDisplayOptions"):
            if type(item.get(key)) is not int:
                raise ValueError("Multimedia timestamp/display options must remain documented integers.")
        for key in ("IncludeNumbering", "UseDefaultMultimediaSettings"):
            if type(item.get(key)) is not bool:
                raise ValueError("Multimedia flags must be booleans.")
