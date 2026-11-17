"""Pinned SDK agenda Add/Import mappings; private sessions use the common coordinator."""

from copy import deepcopy
from dataclasses import asdict

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteChange, WriteFailure
from .granicus_platform import numeric_id
from .granicus_soap import contract, request_xml


def _nodes(rows, parent=None, depth=0):
    if not isinstance(rows, list) or depth > 24:
        raise ValueError("Metadata must be an explicitly bounded tree/array.")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each metadata node must be a documented object.")
        result.append((row, parent))
        result.extend(_nodes(row.get("Children", []), row, depth + 1))
        if len(result) > 10000:
            raise ValueError("Metadata node count exceeds the adapter safety limit.")
    return result


def authorize(adapter, source, change, context):
    config = adapter.credentials(source, context)
    fields = change.fields
    allowed = ({"ParentType", "MetaDataData"} if change.operation == "create" else
               {"ParentType", "MetaData", "ClearExisting", "AsTree"})
    if (change.operation not in {"create", "update"} or change.files or set(fields) != allowed
            or fields.get("ParentType") not in {"event", "clip"}):
        raise ValueError("Agenda tree requires an explicit Add or Import model and parent type.")
    if change.operation == "update" and (type(fields["ClearExisting"]) is not bool or type(fields["AsTree"]) is not bool):
        raise ValueError("Import requires explicit ClearExisting and AsTree booleans; no vendor defaults are inferred.")
    if fields.get("ClearExisting") is True:
        raise ValueError("Clearing existing metadata is documented by the vendor but excluded by this project's no-delete scope.")
    identity = str(numeric_id(change.resource_id))
    if (f"agenda_tree:{change.operation}" not in config.get("permissions", ())
            or identity not in config.get("resource_ids", ()) or not change.meeting_id
            or str(change.meeting_id) not in config.get("meeting_ids", ())):
        raise WriteFailure("permission_denied", "Agenda Add/Import requires exact parent and meeting grants.")
    rows = [fields["MetaDataData"]] if change.operation == "create" else fields["MetaData"]
    nodes = _nodes(rows)
    if not nodes:
        raise ValueError("Supply at least one metadata node; empty deletion is not mapped.")
    ids = []
    for row, parent in nodes:
        if set(row) != set(contract()["types"]["MetaDataData"]["fields"]) or row["ID"] != 0 or row["UID"] != "":
            raise ValueError("New nodes require every documented MetaDataData field with unassigned ID0/empty UID.")
        foreign = str(numeric_id(row["ForeignID"]))
        if foreign not in config.get("foreign_ids", ()):
            raise WriteFailure("permission_denied", "Every new metadata ForeignID must be explicitly authorized.")
        ids.append(foreign)
        if parent is not None and (row["ParentID"] != 0 or row["ParentUID"] != ""):
            raise ValueError("Nested creation uses its explicit Children relationship with unassigned parent keys.")
    if len(ids) != len(set(ids)):
        raise ValueError("New metadata ForeignIDs must be unique for exact reconciliation.")


def _parameters(change):
    fields = change.fields
    prefix = "Event" if fields["ParentType"] == "event" else "Clip"
    method = ("Add" if change.operation == "create" else "Import") + prefix + "MetaData"
    body = {prefix + "ID": numeric_id(change.resource_id)}
    body.update({key: deepcopy(value) for key, value in fields.items() if key != "ParentType"})
    return method, body


def _read(session, change):
    prefix = "Event" if change.fields["ParentType"] == "event" else "Clip"
    values, _ = session.call("Get" + prefix + "MetaData", {prefix + "ID": numeric_id(change.resource_id)})
    rows = values.get("metadata")
    nodes = _nodes(rows)
    ids = [numeric_id(row.get("ID")) for row, _ in nodes]
    if len(ids) != len(set(ids)):
        raise ValueError("Metadata readback repeats provider IDs.")
    return rows


def prepare(adapter, source, change, context, bounds, deadline):
    method, body = _parameters(change)
    request_xml(method, body, byte_limit=bounds.transfer_bytes)
    session = adapter._session(source, context, bounds, deadline)
    try:
        before = _read(session, change)
    finally:
        adapter._close_document_session(session)
    rows = [change.fields["MetaDataData"]] if change.operation == "create" else change.fields["MetaData"]
    existing = {row["ID"]: row for row, _ in _nodes(before)}
    existing_foreign = {str(row.get("ForeignID")) for row in existing.values()}
    for row, parent in _nodes(rows):
        if str(row["ForeignID"]) in existing_foreign:
            raise WriteFailure("conflict", "A submitted ForeignID already exists under this parent.")
        if parent is None and row["ParentID"]:
            old = existing.get(row["ParentID"])
            if old is None or (row["ParentUID"] and row["ParentUID"] != old.get("UID")) or change.fields.get("ClearExisting"):
                raise ValueError("The supplied root parent must exist in the retained agenda and match its UID.")
        elif parent is None and row["ParentUID"]:
            raise ValueError("A root ParentUID requires its supplied matching ParentID.")
    fingerprint = canonical_hash(before)
    if change.expected_version is not None and change.expected_version != fingerprint:
        raise WriteFailure("conflict", "Agenda tree differs from the expected baseline.")
    return {"change": asdict(change), "native": {"method": "POST", "url": session.url,
        "content_type": "text/xml", "headers": {}, "files": [], "soap_method": method, "body": body},
        "before": before, "before_fingerprint": fingerprint, "expected_version": fingerprint,
        "agenda_replacement_requested": change.fields.get("ClearExisting", False),
        "contract_revision": contract()["source_revision"],
        "conflict_semantics": "preflight_parent_metadata_compare_not_atomic_provider_cas"}


def _outcome(session, prepared, key_table):
    change = WriteChange.from_dict(prepared["change"])
    actual = _read(session, change)
    flat = [row for row, _ in _nodes(actual)]
    by_foreign = {}
    for row in flat:
        by_foreign.setdefault(str(row.get("ForeignID")), []).append(row)
    intended = [change.fields["MetaDataData"]] if change.operation == "create" else change.fields["MetaData"]
    matched = all(type(row.get("ID")) is int and row["ID"] > 0 for row in flat)
    resolved = {}
    for row, parent in _nodes(intended):
        found = by_foreign.get(str(row["ForeignID"]), [])
        if len(found) != 1:
            matched = False
            continue
        target = found[0]
        resolved[str(row["ForeignID"])] = target["ID"]
        # Creation IDs/UIDs and child parent references are server-assigned.
        fields = {k: v for k, v in row.items()
                  if k not in {"ID", "UID", "Children", "ParentID", "ParentUID"}}
        matched &= all(k in target and canonical_hash(target[k]) == canonical_hash(v)
                       for k, v in fields.items())
        if parent is None:
            matched &= ("ParentID" in target and
                        canonical_hash(target["ParentID"]) == canonical_hash(row["ParentID"]))
            if row["ParentUID"]:
                matched &= target.get("ParentUID") == row["ParentUID"]
        else:
            parents = by_foreign.get(str(parent["ForeignID"]), [])
            matched &= (len(parents) == 1 and "ParentID" in target and "ParentUID" in target
                        and "UID" in parents[0]
                        and canonical_hash(target["ParentID"]) == canonical_hash(parents[0]["ID"])
                        and canonical_hash(target["ParentUID"]) == canonical_hash(parents[0]["UID"]))
    if change.fields.get("ClearExisting"):
        matched &= len(flat) == len(_nodes(intended))
    else:
        by_id = {row["ID"]: row for row in flat}
        matched &= all(row["ID"] in by_id and all(k in by_id[row["ID"]] and canonical_hash(by_id[row["ID"]][k]) == canonical_hash(v) for k, v in row.items()
                         if k != "Children") for row, _ in _nodes(prepared["before"]))
    if key_table is not None:
        matched &= (isinstance(key_table, list) and len(key_table) == len(resolved)
                    and all(isinstance(pair, dict) and type(pair.get("ForeignID")) is int
                            and type(pair.get("GranicusID")) is int and pair["GranicusID"] > 0
                            and resolved.get(str(pair["ForeignID"])) == pair["GranicusID"] for pair in key_table)
                    and len({str(pair.get("ForeignID")) for pair in key_table if isinstance(pair, dict)}) == len(resolved))
    return {"state": "succeeded" if matched else "uncertain", "resource_id": change.resource_id,
        "readback": actual, "key_table": key_table, "resolved_foreign_ids": resolved,
        "reconciled": True, "agenda_replacement_requested": change.fields.get("ClearExisting", False),
        "verification_scope": "Independent parent metadata fields, unique supplied ForeignIDs, provider IDs and parent links; no automatic mutation replay.",
        **({} if matched else {"reason": "Agenda metadata readback or key mapping differs; no mutation replay."})}


def apply(adapter, source, prepared, context, bounds, deadline, *, persist):
    change = WriteChange.from_dict(prepared["change"])
    session = adapter._session(source, context, bounds, deadline)
    try:
        if canonical_hash(_read(session, change)) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "Parent metadata changed after approval.")
        if persist:
            persist({"resource_id": change.resource_id})
        try:
            result, _ = session.call(prepared["native"]["soap_method"], prepared["native"]["body"])
        except ValueError:
            raise AmbiguousWrite() from None
        key_table = result.get("KeyTable")
        if not isinstance(key_table, list):
            raise AmbiguousWrite()
        if persist:
            persist({"metadata_key_table": key_table})
        return _outcome(session, prepared, key_table)
    finally:
        adapter._close_document_session(session)


def reconcile(adapter, source, prepared, item, context, bounds, deadline):
    session = adapter._session(source, context, bounds, deadline)
    try:
        return _outcome(session, prepared, item.get("metadata_key_table"))
    finally:
        adapter._close_document_session(session)
