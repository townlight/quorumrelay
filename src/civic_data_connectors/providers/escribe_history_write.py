"""Create one explicitly identified item-history step; never publish history."""
from copy import deepcopy
from dataclasses import asdict
import json
from xml.etree import ElementTree as ET

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteCancelled, WriteChange, WriteFailure
from .escribe_publishing import contract, request_xml
from .escribe_history import bind_history

ENTITY = "agenda_item_history_step"
METHOD = "AgendaItemHistoryCreate"
VIEW = "AgendaItemItemHistoryView"


def key(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def policy(adapter, source, change, context):
    adapter.validate_source(source, context)
    config = adapter.credentials(source, context)
    if (change.entity != ENTITY or change.operation != "create" or change.resource_id is not None
            or change.files or change.language is not None or change.page_number is not None
            or change.expected_version is not None):
        raise ValueError("Only a new explicit native history step is mapped.")
    if (ENTITY + ":create" not in config.get("permissions", ())
            or change.meeting_id not in config.get("meeting_ids", ())
            or not isinstance(change.parent_id, str) or not change.parent_id.isascii()
            or not change.parent_id.isdecimal() or not 0 < int(change.parent_id) < 2**31
            or str(int(change.parent_id)) != change.parent_id
            or change.parent_id not in config.get("agenda_item_ids", ())):
        raise WriteFailure("permission_denied", "The exact history meeting and agenda item must be authorized.")
    model = contract()["operations"][METHOD]["request"][0]["type"]
    names = {f["name"] for f in contract()["types"][model]["fields"]}
    if not isinstance(change.fields, dict) or set(change.fields) != names:
        raise ValueError("Every native history-step field must be explicit, including nulls.")
    value, identity = change.fields, change.fields.get("Id")
    if (not isinstance(identity, dict) or set(identity) != {"AgendaItemHistoryId", "Id", "PortalId"}
            or type(identity["Id"]) is not int or not 0 < identity["Id"] < 2**31
            or type(identity["AgendaItemHistoryId"]) is not int or not 0 < identity["AgendaItemHistoryId"] < 2**31
            or identity["PortalId"] not in config.get("portal_ids", ())
            or value["MeetingId"] != change.meeting_id or type(value["AgendaItemId"]) is not int
            or value["AgendaItemId"] != int(change.parent_id)):
        raise WriteFailure("permission_denied", "The full native history identity must bind the authorized parent.")
    request_xml(METHOD, {"history": value}, source.url)


def read(session, change):
    parameters = {"MeetingId": change.meeting_id, "AgendaItemId": int(change.parent_id)}
    value, _ = session.call(VIEW, parameters)
    if not isinstance(value, dict):
        raise ValueError("The exact existing item history must be available.")
    bind_history(parameters, {"records": [{"original": value}]})
    return value


def steps(value):
    wrapper = value.get("Steps")
    if wrapper is None:
        return []
    if not isinstance(wrapper, dict) or set(wrapper) != {"AgendaItemHistoryStep"}:
        raise ValueError("Ambiguous native step collection.")
    rows = wrapper["AgendaItemHistoryStep"]
    if not isinstance(rows, list) or any(not isinstance(r, dict) or not isinstance(r.get("Id"), dict) for r in rows):
        raise ValueError("Every existing step must have its native identifier.")
    if len({key(r["Id"]) for r in rows}) != len(rows):
        raise ValueError("Duplicate existing native history-step identities.")
    return rows


def bind_parent(value, intended):
    history = value.get("History")
    identity = history.get("Id") if isinstance(history, dict) else None
    if (not isinstance(identity, dict) or identity != {
            "Id": intended["Id"]["AgendaItemHistoryId"], "PortalId": intended["Id"]["PortalId"]}):
        raise WriteFailure("conflict", "The selected item history differs from the planned native history parent.")


def prepare(adapter, source, change, context, bounds, deadline):
    policy(adapter, source, change, context)
    if bounds.max_pages < 3:
        raise ValueError("History commit requires preflight, creation and readback call capacity.")
    before = read(adapter._session(source, context, bounds, deadline), change)
    bind_parent(before, change.fields)
    rows = steps(before)
    if len(rows) + 1 > bounds.max_records:
        raise ValueError("The history step collection exceeds max_records.")
    payload = {k: v for k, v in change.fields.items() if k != "Id"}
    if any(r["Id"] == change.fields["Id"] or {k: v for k, v in r.items() if k != "Id"} == payload for r in rows):
        raise WriteFailure("conflict", "The planned step identity/content already exists; do not duplicate it.")
    body = {"history": deepcopy(change.fields)}
    encoded, _ = request_xml(METHOD, body, source.url)
    if len(encoded) > min(bounds.parser_bytes, bounds.transfer_bytes):
        raise ValueError("The history request exceeds byte bounds.")
    return {"change": asdict(change), "before": before, "after": deepcopy(change.fields),
            "before_fingerprint": canonical_hash(before), "resource_id": deepcopy(change.fields["Id"]),
            "native": {"method": "POST", "url": source.url, "soap_method": METHOD, "body": body,
                       "content_type": "application/soap+xml", "headers": {}, "files": []},
            "conflict_semantics": "preflight_full_history_compare_not_atomic_provider_cas",
            "contract_sha256": contract()["metadata_sha256"]["publishing.wsdl"]}


def outcome(adapter, source, prepared, identity, context, bounds, deadline, session=None):
    change = WriteChange.from_dict(prepared["change"])
    if (not isinstance(identity, dict) or set(identity) != set(prepared["resource_id"])
            or any(identity[k] != prepared["resource_id"][k] for k in ("PortalId", "AgendaItemHistoryId"))
            or type(identity["Id"]) is not int or not 0 < identity["Id"] < 2**31):
        raise ValueError("Returned step identity escaped the planned history parent.")
    actual = read(session or adapter._session(source, context, bounds, deadline), change)
    bind_parent(actual, prepared["after"])
    expected = deepcopy(prepared["after"])
    expected["Id"] = identity
    prior = steps(prepared["before"])
    old, new = {key(r["Id"]): r for r in prior}, {key(r["Id"]): r for r in steps(actual)}
    exact = (key(identity) not in old and new == {**old, key(identity): expected}
             and {k: v for k, v in actual.items() if k != "Steps"}
             == {k: v for k, v in prepared["before"].items() if k != "Steps"})
    return {"state": "succeeded" if exact else "uncertain", "resource_id": key(identity),
            "readback": actual, "reconciled": True,
            **({} if exact else {"reason": "Full history/step readback differs; no automatic replay."})}


def apply(adapter, source, prepared, context, bounds, deadline, *, persist=None):
    change = WriteChange.from_dict(prepared["change"])
    policy(adapter, source, change, context)
    session = adapter._session(source, context, bounds, deadline)
    if canonical_hash(read(session, change)) != prepared["before_fingerprint"]:
        raise WriteFailure("conflict", "The complete item history changed after planning.")
    if persist and persist({"resource_id": None}):
        raise WriteCancelled()
    try:
        identity, _ = session.call(METHOD, prepared["native"]["body"])
        if persist:
            persist({"resource_id": key(identity)})
        return outcome(adapter, source, prepared, identity, context, bounds, deadline, session=session)
    except (ValueError, TypeError, KeyError, OSError, TimeoutError, ET.ParseError):
        raise AmbiguousWrite() from None


def reconcile(adapter, source, prepared, item, context, bounds, deadline):
    policy(adapter, source, WriteChange.from_dict(prepared["change"]), context)
    if item.get("resource_id") is None:
        return {"state": "uncertain", "reason": "Returned step ID was lost; no unique lookup or replay is inferred."}
    return outcome(adapter, source, prepared, json.loads(item["resource_id"]), context, bounds, deadline)
