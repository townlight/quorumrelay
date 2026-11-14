# Boardable legacy agenda writes

The current local source maps two existing-meeting operations from the vendor's
anonymously served legacy application client. See the [pinned source](capabilities/evidence/boardable-client-write/source.json)
and [executed synthetic receipt](verification/boardable-telvue-writes-2026-11-14.json).
This is observed client compatibility, not a stable public API promise. No live
mutation or login was performed. These changes are later than the preserved dev13 packages.

Use source provider `boardable`, namespace chosen by the application, and the exact
runtime `Boardable.org_url`, for example `https://app.boardable.com/example/`.
Do not derive it from a public site slug. Application-owned
`OperationContext.credentials["boardable"]` must contain `tenant`, matching `org_url`,
`allowed_namespaces`, `legacy_agenda_editor=True`, `session_cookie`, `csrf_token`,
`meeting_ids` (string native IDs), `meeting_urls` (ID to exact native URL), and
`permissions`. A meeting URL must equal the supplied organization URL plus
`meetings/{id}`. Other URL variants fail closed. Live session acquisition belongs
to the calling application and is not a synthetic acceptance requirement.

Use the ordinary `plan_write`, exact `plan_id`/`plan_hash` approval and
`commit_write` lifecycle. For sibling reorder, specify:

```python
change = {
    "key": "agenda-order", "entity": "agenda_order", "operation": "update",
    "meeting_id": "7", "resource_id": "7",
    "fields": {"agenda_item_ids": [4, 1, 3, 2]},
}
```

Require permission `agenda_order:update`. IDs are native positive integers and
must give a complete preorder of the existing nested edit-list. Siblings may
change order; parents, members and every other supplied field remain unchanged.
The adapter sends native `{agenda: [{id, parent_agenda_id}, ...]}` JSON to the
meeting's `/agenda/reorder`, then verifies the entire resulting tree.

For text edits use entity `item`, operation `update`, permission `item:update`,
`meeting_id` of the authorized parent and `resource_id` of an existing item.
Supply `fields={"text": "Budget revised", "description": "Supplied description"}`,
or either field alone. Text must be nonempty. The trusted configuration must
explicitly contain `onedrive_access_token=None`, matching the vendor runtime null
value serialized by FormData as `"null"`. Cloud-import credentials are unsupported.

The adapter verifies membership in that meeting's edit-list, GETs the selected
`agenda_item`, and requires its complete text, description, privacy, duration,
responsible-person and existing-upload snapshots. It sends multipart `/agenda/update`
with the requested text changes and all other editable values and existing
attachment IDs preserved. Full item and tree readback must confirm the exact
result, including unknown fields. Missing, duplicate or mismatched native IDs
fail before mutation. New attachments and changes to assignments, privacy or
duration are not exposed by this mapping.

Both mappings use bounded GETs, tenant/namespace/current-permission checks,
full-snapshot preflight and durable mutation intent. Preflight is not atomic
upstream CAS. A lost response or unconfirmed result is reconciled through GETs
without another POST, including after restart. Cancellation during a planning
read returns cancelled and persists no plan. Plans never call `prepare-draft`.
The vendor client does call that separate mutation before opening its editor;
applications must supply an already readable edit-list state.

The `has_agenda_builder`/`has_approval_workflows` feature flags select a different
`agenda_app_url` editor. It is not covered. Recurring `current_date` variants,
new items, new files, full meeting forms, draft preparation, publication,
deletes and vendor-specific file imports remain unmapped. The visible new-file
FormData branch alone does not establish created attachment identity, stored
bytes, processing or subsequent readback. No such behavior is inferred.
