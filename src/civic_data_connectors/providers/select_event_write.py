"""Exact native Select event update with caller-declared native postconditions."""
import base64
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
import json
import math
from time import monotonic
from uuid import UUID

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, NativeRequest, WriteCancelled, WriteChange, WriteFailure
from .discovery import _api_source

GUARDS = {"isPublished", "publishStart", "startEventAutomatically", "streamId", "externalMediaUrl"}
DIRECT = GUARDS | {"eventName", "eventDescription", "eventCategoryId"}
LOCATION = {"address1", "address2", "city", "state", "zipCode"}
EDITABLE = {"eventName", "eventDescription", "eventDate", "startDateTime", "eventCategoryId", "categoryId",
            "eventCategoryName", "categoryName", "eventLocation", "actualStartTime", "meetingEndTime"}


@lru_cache(maxsize=1)
def contract():
    return json.loads(files("civic_data_connectors.data").joinpath("select_event_update.json").read_bytes())


def validate(value, schema, depth=0):
    if depth > 20:
        raise ValueError("Excessive native event model depth.")
    if value is None and schema.get("nullable"):
        return
    if "$ref" in schema:
        return validate(value, contract()["models"][schema["$ref"].split("/")[-1]], depth + 1)
    kind = schema.get("type")
    matches = {"object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str), "integer": type(value) is int,
        "boolean": type(value) is bool, "number": type(value) in {int, float}}
    if not matches.get(kind, False) or ("enum" in schema and value not in schema["enum"]):
        raise ValueError("The native event field does not match the pinned schema.")
    if kind == "object":
        properties = schema.get("properties", {})
        if set(value) - set(properties) or set(schema.get("required", ())) - set(value):
            raise ValueError("Unknown or missing native event fields.")
        for key, child in value.items():
            validate(child, properties[key], depth + 1)
    elif kind == "array":
        for child in value:
            validate(child, schema["items"], depth + 1)
    elif kind in {"integer", "number"}:
        if not math.isfinite(value):
            raise ValueError("Finite native numbers are required.")
        bits = {"int32": 32, "int64": 64}.get(schema.get("format"))
        if bits and not -(2 ** (bits - 1)) <= value < 2 ** (bits - 1):
            raise ValueError("Native integer exceeds its schema bounds.")
    elif kind == "string":
        if len(value) < schema.get("minLength", 0):
            raise ValueError("A nonempty native event string is required.")
        fmt = schema.get("format")
        if fmt == "date-time":
            if "T" not in value:
                raise ValueError("Use an explicit native date-time literal.")
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif fmt == "uuid":
            UUID(value)
        elif fmt == "byte":
            base64.b64decode(value, validate=True)


def authorize(adapter, source, change, context):
    from .civicclerk_write import _id
    adapter.validate_source(source, context)
    config = adapter.credentials(source, context)
    if (change.operation != "update" or change.files or change.parent_id is not None
            or change.language is not None or change.page_number is not None):
        raise WriteFailure("mapping_unverified", "Only selected native event metadata update is mapped.")
    identity = _id(change.resource_id)
    if (_id(change.meeting_id) != identity or "event:update" not in config.get("permissions", ())
            or str(identity) not in config.get("resource_ids", ())
            or str(identity) not in config.get("meeting_ids", ())):
        raise WriteFailure("permission_denied", "The selected event is outside trusted write policy.")
    return identity


def read(adapter, source, identity, context, bounds, deadline):
    value = adapter.read(source, _api_source(source) + "/" + str(identity), context, bounds, deadline)
    validate(value, contract()["response"])
    if type(value.get("id")) is not int or value["id"] != identity:
        raise ValueError("Exact native event identity readback is required.")
    return value


def prepare(adapter, source, change, context, bounds, deadline):
    identity = authorize(adapter, source, change, context)
    if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
        raise ValueError("Each change requires a bounded key.")
    if not isinstance(change.fields, dict) or set(change.fields) != {"native_request", "expected_readback"}:
        raise ValueError("Supply the complete native request and explicit expected native readback.")
    body, expected = deepcopy(change.fields["native_request"]), deepcopy(change.fields["expected_readback"])
    validate(body, contract()["request"])
    properties = contract()["models"][contract()["request"]["$ref"].split("/")[-1]]["properties"]
    if set(body) != set(properties):
        raise ValueError("Every native update property must be explicit; no vendor defaults are applied.")
    validate(expected, contract()["response"])
    if len(json.dumps(change.fields, allow_nan=False).encode()) > min(bounds.parser_bytes, bounds.transfer_bytes):
        raise ValueError("The native request and expected snapshot exceed configured byte bounds.")
    before = read(adapter, source, identity, context, bounds, deadline)
    if change.expected_version is not None and change.expected_version != canonical_hash(before):
        raise WriteFailure("conflict", "The expected event version differs from current native readback.")
    if (set(expected) != set(before) or any(expected[k] != before[k] for k in before if k not in EDITABLE)
            or any(k not in before or body[k] != before[k] for k in GUARDS)
            or any(k not in expected or body[k] != expected[k] for k in DIRECT)
            or "eventTemplateId" not in before):
        raise ValueError("Publication, media, template and unrelated native fields must be preserved.")
    old_location, new_location = before.get("eventLocation"), expected.get("eventLocation")
    if (not isinstance(old_location, dict) or not isinstance(new_location, dict)
            or set(old_location) != set(new_location)
            or any(old_location[k] != new_location[k] for k in old_location if k not in LOCATION)
            or any(k not in new_location or body[k] != new_location[k] for k in LOCATION)):
        raise ValueError("Exact native location readback and preserved location identity are required.")
    native = NativeRequest("PUT", _api_source(source) + "/" + str(identity), "application/json", body, {})
    return {"change": asdict(change), "native": native.public_dict(), "resource_id": identity,
        "before": before, "before_fingerprint": canonical_hash(before), "expected_readback": expected,
        "conflict_semantics": "preflight_read_compare_not_atomic_upstream_cas",
        "date_time_semantics": "caller_supplied_native_literals_and_postconditions_no_conversion_inferred"}


def apply(adapter, source, prepared, context, bounds, deadline, persist=None):
    identity = authorize(adapter, source, WriteChange.from_dict(prepared["change"]), context)
    before = read(adapter, source, identity, context, bounds, deadline)
    if canonical_hash(before) != prepared["before_fingerprint"]:
        raise WriteFailure("conflict", "Native event changed after planning.")
    if persist and persist({"resource_id": identity}):
        raise WriteCancelled()
    response = adapter._call(source, context, NativeRequest(**prepared["native"]), bounds, deadline, raw=True)
    if response.status not in {200, 204}:
        raise AmbiguousWrite("Event update did not return a documented success status.")
    return reconcile(adapter, source, prepared, {"resource_id": identity}, context, bounds, deadline)


def reconcile(adapter, source, prepared, item, context, bounds, deadline):
    identity = authorize(adapter, source, WriteChange.from_dict(prepared["change"]), context)
    if item.get("resource_id") != identity:
        return {"state": "uncertain", "reason": "Exact persisted event identity is unavailable."}
    try:
        value = read(adapter, source, identity, context, bounds, deadline)
        if context.check_cancelled() or monotonic() >= deadline:
            raise ValueError("Native model validation completed outside active bounds.")
    except (WriteFailure, ValueError, TypeError, KeyError):
        return {"state": "uncertain", "resource_id": identity, "reason": "Exact event readback unavailable."}
    if canonical_hash(value) != canonical_hash(prepared["expected_readback"]):
        return {"state": "uncertain", "resource_id": identity, "readback": value,
                "reason": "Native event differs from the explicit approved postcondition."}
    return {"state": "succeeded", "resource_id": identity, "readback": value, "provider_revision": None}
