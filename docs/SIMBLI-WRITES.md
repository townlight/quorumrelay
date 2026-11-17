# Simbli existing agenda-item title updates

The native adapter updates the title of one existing, editable, nondeleted,
no-workflow agenda item. It uses the recovered Simbli Angular client contract
and the shared exact-plan/commit coordinator. Public listing and reading remain
separate operations. Meeting creation, item creation, supporting-file uploads,
minutes and publication are still unfinished.

The native source contract is preserved in
[the selected-item capture](investigations/2026-11-16-paused/simbli-selected-item-contract.json).
The archived failed draft remains historical evidence; the registered source is
`src/civic_data_connectors/providers/simbli_write.py`.

## Configuration and operation

Use the canonical HTTPS public meeting URL
`https://simbli.eboardsolutions.com/SB_Meetings/ViewMeeting.aspx?S=42&MID=123`
and its exact canonical Simbli namespace. Source options, body and input-format
overrides are rejected. Private `OperationContext.credentials['simbli']` contains
the exact tenant, `site_url`, `site_id`, `meeting_id`, `allowed_namespaces`,
`item_ids`, `permissions`, `encrypted_user_id`, `lock_user_id`, `session_cookie`
and bearer `token`. The required provider permission is `agenda_item:update`.
Application plan/commit grants and namespace policy also apply.

The change has `entity: agenda_item`, `operation: update`, the numeric native
meeting/item IDs as strings, and `fields: {title: 'Updated title'}`. Files,
parent/language/page overrides and other changed fields are rejected. Approval
binds the complete plan hash. Optional `expected_version` binds the normalized
before-state fingerprint.

## Native sequence and preservation

Planning performs only GETs: the fresh authenticated meeting page, the native
item tree, and selected item details. It verifies HTTP status before parsing,
native identities, current editability and the complete bounded DTO. Anonymous
public item captures have `IsEditable=false` and cannot authorize a write.

Commit repeats those reads, compares the approved snapshot, rechecks current
grants, then acquires the exact item lock through JSON at
`https://app2.eboardsolutions.com/api/Workflow/GetItemEditAccess/`. It reads the
tree/details again under the lock, checks identity and conflict state, rechecks
grants and sends `SaveAgendaItem` with the fresh full item/content DTOs. Only
the requested title and native editor `IsEdit` markers are changed. Independent
tree/details readback must confirm the title and preserve unrelated fields,
including comments, children, order, visibility and attachments. The native
editing lock and preflight comparisons are not an atomic upstream CAS.

The session cookie goes only to the Simbli origin. Both origins receive the
native bearer header; the app2 origin never receives the Simbli cookie. Exact
item release uses the native form-encoded `ReleaseItemEditing` route, including
lowercase boolean and empty null encoding. No release-all or heartbeat request
is sent. Cleanup reserves request/byte/time headroom within the original bounds
and remains permitted after cancellation or grant revocation.

## Durable state and uncertain outcomes

Plans and receipts contain stable native identity references rather than page
controls. Known attachment `SecurityToken` values are represented by references
bound to the attachment ID and exact DTO path. Fresh tokens are rebound from
fresh authenticated reads when building the native save; actual tokens are
never persisted. Token rotation does not mask attachment or business changes.
Empty credential-like fields retain their structural presence under escaped
snapshot keys. Unsupported nonempty credential fields and reserved-key
collisions fail closed. Unknown business fields remain in the native DTO and
conflict/readback comparisons.

The coordinator durably records the resource ID and mutation attempt before
save. Errors after send remain uncertain. Restart recovery reads only; it never
reacquires a lock, releases a lock or sends another save. A desired title without
a durable attempt/no-send marker cannot confirm an intent. A successful save
with failed release retains success plus an explicit durable cleanup error.
No-op title changes send no mutation or lock request.

Acceptance is synthetic engine/SQLite execution against the pinned native
contract. An authorized derivative of the sanitized public DTO is explicitly
synthetic; the original captured editability is retained unchanged. No staff
mutation or live adapter execution is claimed.
