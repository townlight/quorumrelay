# Boardable agenda writes

The current local source maps three existing-meeting operations from the vendor's
anonymously served legacy application client. See the [pinned source](capabilities/evidence/boardable-client-write/source.json)
and [executed synthetic receipt](verification/boardable-telvue-writes-2026-11-14.json).
This is observed client compatibility, not a stable public API promise. The legacy evidence involved no live
mutation or login; the current-builder trial below is separate. These changes are later than the preserved dev13 packages.

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
`agenda_app_url` editor. The current-builder mapping below covers selected item
and file operations. Recurring `current_date` variants,
legacy-editor new files, full meeting forms, draft preparation, publication,
deletes and vendor-specific file imports remain unmapped. The visible new-file
FormData branch alone does not establish created attachment identity, stored
bytes, processing or subsequent readback. No such behavior is inferred.

## Create one legacy agenda item

Use entity `item`, operation `create`, an authorized `meeting_id`, explicit integer
`parent_id=0` for a root or an existing native parent whose `agenda` is an array,
and `fields={"text": "Budget public discussion"}`. Omit `resource_id` and files.
Require `item:create`. The client-declared JSON is `{text, parent_id, date: ""}`;
recurring-day variants and other new-item fields are not mapped.

Planning GETs the existing edit-list and binds its full snapshot. Commit checks
that snapshot again, persists mutation intent, sends one POST and persists the
returned native ID. Readback must contain that new ID with exact requested text
and parent; removing it must restore the complete previous tree. Collateral
changes, missing/duplicate IDs and unrequested children leave the result
uncertain. An ambiguous POST without a returned ID is never reconciled by title
or date and is never resent. A confirmed ID can reconcile after restart through
GETs. Post-send cancellation also leaves an uncertain result until readback.

[New source extract](capabilities/evidence/boardable-client-write/create-item-source.json)
and [64-case affected receipt](verification/boardable-item-create-2026-11-14.json)
attribute this scope separately. Created edit-list membership does not establish
publication, delivery, remote attachment bytes or a stable public API promise.

Response retrieval uses the smaller of the approved parser and transfer byte
limits, including injected transports that fail to enforce the requested cap.
An oversized preflight fails before approval. An oversized response after a
sent mutation leaves an uncertain receipt; a subsequent commit reconciles by
readback after reopening without sending a second mutation. The
[executed boundary regressions](verification/write-response-bounds-2026-11-15.json)
preserve existing target binding and request payload contracts.

## Current Agenda Builder items and uploads

The authorized QuorumRelay Evaluation trial exposed the current editor at
`agendas.boardable.com`. Its observed client sends session-authenticated requests
to `https://app.boardable.com/api/agenda-approvals`, with numeric `Organization`
header. [Pinned source and sanitized trial captures](capabilities/evidence/boardable-current-builder/source.json)
record JSON item creation (201), multipart item update/upload (200), exact item
and meeting readback, and a 134-byte original file download matching its SHA256.
The adapter has separate [105-case affected synthetic acceptance](verification/boardable-current-builder-2026-11-16.json);
the browser trial actions and the adapter test execution are distinct evidence.

Use the existing `boardable` provider with the exact app organization root and
trusted credentials containing `current_agenda_builder=True`, `tenant`,
`org_url`, numeric `organization_id`, `allowed_namespaces`, `meeting_ids`,
`permissions`, and `session_cookie`. Optional `csrf_token` supplies the CSRF header.
Create additionally requires explicit `owner_id`. Do not enable
`legacy_agenda_editor` simultaneously. Credentials stay in the application's
trusted context, outside source options and durable plans.

Use the ordinary plan, exact approval, commit and read-only reconciliation
lifecycle. Entity `item` supports `create`/`update` with `text`, `description`,
`duration` and `is_private`, and corresponding `item:create`/`item:update` grants.
Create requires an explicit integer `parent_id` (0 for root); update requires the
existing native `resource_id` and cannot move its parent. Files use the ordinary
durable file-reference path. Text-only creation uses JSON POST; updates use PUT
JSON or multipart POST with `_method=PUT`. New uploads retain existing upload IDs.

Planning and preflight bind the exact meeting/item snapshots. Readback verifies
returned identity, parent, requested fields, owner, presenters, approval tree,
existing uploads and unchanged other agenda nodes. New upload metadata must bind
to that item and organization; its declared original download route must match
the exact approved organization/upload/filename. Bounded original bytes must
match the approved size and SHA256. Preflight is not atomic upstream CAS.
Lost replies retain durable intent and any returned ID; reconciliation never
replays the write or resolves an unknown creation by title.

Recurring/multiday/scheduler meeting operations, draft preparation,
publication, invitations, vendor imports and general Document Center uploads
remain outside this mapping. This is observed current-client compatibility.


## Native single meeting create and update

The authorized evaluation trial supplied exact native JSON contracts in
[the pinned meeting form evidence](capabilities/evidence/boardable-meeting-form/source.json).
Creation sends `POST /{org}/meetings` and requires201 with a raw meeting object.
Update sends `POST /{org}/meetings_v2/{id}` and requires200. Readback uses the exact
returned canonical URL plus `?format=json`, requiring200 with a `meeting` object.
Changing the title changes the canonical URL. A numeric detail URL returned404.

Select `current_meeting_form=True` exclusively of the legacy and current-builder
modes. Trusted credentials require `tenant`, exact `org_url`, numeric
`organization_id`, `allowed_namespaces`, `session_cookie`, `xsrf_token`, and
`meeting:create`/`meeting:update` permissions. Creation requires numeric `owner_id`;
update requires explicit `meeting_ids` and `meeting_urls` mapping each native ID
string to its exact current canonical URL. Keep session secrets outside source
options and durable plans. Windows runtime timezone support uses `tzdata`.

Entity `meeting` supports title, description, location, IANA timezone and one
`dates` entry (`date` MM/DD/YYYY, `from`/`to` such as `10:00 pm`). Creation is
owner-only, private, unpublished and `no_remote`; notifications are disabled.
Update preserves owner, membership/roles, agenda/media and unknown business
fields; supported existing state is private, unpublished, nonrecurring and
without guests or remote video. Unsupported fields are rejected. Date conversion
rejects nonexistent or ambiguous daylight saving times.

Planning binds the exact ID, organization, URL, snapshot and current permissions.
Preflight detects conflicting edits; it is not atomic upstream CAS. The returned
native ID and changed canonical URL are persisted before readback or cancellation.
Recovery reads only that URL, never replays POST or matches titles. Lost creation
responses with no returned URL remain uncertain; lost update replies may leave
an obsolete URL and likewise require an externally supplied exact identity URL.

[The attributed adapter receipt](verification/boardable-meeting-write-2026-11-16.json)
records131 affected synthetic passes and a separate all-fields update check.
The native trial independently created/edited synthetic meetings526572/526577.
Weekly series creation and series metadata updates are covered separately below.
Other recurrence patterns, multi-day, scheduler, draft preparation, publication,
invitations, imports and general Document Center uploads remain open.

## Additional series contract research (2026-11-16)

The authorized evaluation tenant created a private weekly series ending after two
occurrences: series `12615`, meeting `526612` on November 16 and meeting `526613`
on November 23. Independent canonical JSON reads returned HTTP 200 and retained
the common series ID, distinct native meeting IDs, UTC recurrence IDs and local
Eastern dates. Invitations were not sent and neither meeting was published.
Minimized captures and hashes are under
`capabilities/evidence/boardable-meeting-form/recurrence-*.json` and
`followup-2026-11-16.json`.

The series page posts an empty JSON body to
`/{org}/meeting-series/{series_id}/data`; its response contains `can`, `meeting`,
`past`, `today`, `future` and `unpublished`. The observed series list URL redirects
to the native series resource. The `/meeting-series/12615/edit/all` editor uses
the original meeting's `/meetings_v2/526612` action with `editType: Series` and
`series_choice: subsequent`. Its initial `series_from` and `series_to` differed
from the persisted occurrence times, so those editor defaults must not be reused
as a verified update payload. That editor was inspected without saving.

That first create request/response was evicted from the browser network buffer;
its saved `series.data` is persisted readback rather than a captured submission.
The later exact request capture and separate implementation follow below. The
single-meeting mode continues to reject recurrence inputs.

## Weekly series creation and metadata updates

`BoardableSeriesWriteAdapter` uses the captured native meeting form with both
`current_meeting_form: true` and `current_meeting_series: true` in trusted
credentials. These modes remain mutually exclusive with the agenda builders.
The existing organization, tenant, namespace, session and operation grants apply.
Updates additionally require a trusted `series_ids` grant and the original meeting's
ID and exact canonical URL in `meeting_ids` and `meeting_urls`. A series grant
authorizes the complete selected series; individual child IDs are discovered only
through that series' native collection and independently checked canonical reads.

Creation uses an ordinary `meeting/create` change with `title`, optional
`description` and `location`, `timezone`, one initial `dates` entry and:

```json
"recurrence": {
  "repeat_period": "week",
  "weekly_interval": 1,
  "end_date": "12/07/2026"
}
```

Dates use `MM/DD/YYYY` and local `h:mm am/pm` clocks. The end date is inclusive.
The bounded mapping permits two through 52 weekly occurrences, further limited by
the operation's record bounds and a 366-day span. Every occurrence is checked for
ambiguous or nonexistent local DST times. Creation remains owner-only, private,
unpublished, without guests, groups or remote video.

Updates use `meeting/update` with `resource_id` identifying the original meeting
and only `title`, `description` or `location`. The native `series_choice` is
`subsequent`, starting from that original meeting. The adapter verifies every
occurrence's identity, predecessor, date, UTC instants, membership roles and
business state before and after a write. Native schedules cannot be edited through
this series form; changes to dates, timezone or recurrence are rejected.

The create response's original meeting ID, canonical URL and series ID are retained
before readback or cancellation. Recovery reads the exact persisted identity and
the selected series, then every occurrence; it never replays a mutation or searches
by title. Partial generation, missing or extra occurrences, collateral changes,
unexpected publication or stale URLs remain uncertain. Policy is rechecked before
apply, including a narrowed series grant. Preflight comparison is not an atomic
upstream compare-and-swap.

Authorized native fixture series `12616` independently returned create201,
update200 and canonical readback200 for meetings `526618` and `526619`. Both titles
changed while IDs, dates, UTC times and privacy were retained. These exact native
requests and responses are pinned under
`capabilities/evidence/boardable-series-form/`. Local engine/SQLite replay and
adversarial synthetic checks are recorded separately in
`verification/boardable-series-write-2026-11-16.json`; the adapter has not been run
against the vendor with exported browser credentials.



## Supporting meeting-file upload

`BoardableMeetingDocumentsWriteAdapter` maps one root supporting file for an
existing owner-only, private, unpublished, nonseries `no_remote` meeting. Select
both `current_meeting_form: true` and `current_meeting_documents: true` in trusted
credentials. This mode excludes series and both agenda modes. Require the exact
organization and owner IDs, `meeting_ids`, `meeting_urls`, namespace binding and
`meeting_document:upload` permission. Session and XSRF values stay in private
credentials.

The change uses `entity: meeting_document`, `operation: upload`, the native
`meeting_id` string, empty `fields` and one ordinary shared write-file input.
Resource, parent, language and page identifiers are absent. The coordinator
resolves the input into an immutable scoped reference before planning. Existing
draft agenda content is preserved. Unsupported access states fail before upload.

The native multipart route is `/{org}/attachments/upload`, with
`attachments[0][file]`, `attachments[0][type]=upload`, `attachable_type=meeting`,
`attachable_id`, `folder_id=0` and the observed string `original_token=undefined`.
Its normal response is HTTP200 with an empty body. The response contains no new
attachment ID.

Planning reads the exact trusted canonical meeting with `?format=json` and the
read-only `POST /{org}/attachment-list` for `folder: root`. Apply checks the full
normalized snapshot again. After uploading, exactly one new native attachment ID
must appear in both collections. Existing attachment records, folder metadata,
meeting membership and business state must remain unchanged. Existing nested files
are preserved independently of the root collection; duplicate filenames are allowed.

The new ID and safe native UUID detail URL are persisted before independent
verification. Detail must identify the exact meeting, organization, owner, root
folder and computer upload. The adapter downloads the original through its exact
same-origin attachment route without redirects and compares its size and SHA256
to the immutable input. PDF preview conversion may still be pending.

Timeouts, cancellation after send, ambiguous ID deltas, changed records or failed
byte verification remain uncertain. Recovery performs only reads, using the
persisted ID or the complete before/after native ID delta. It never replays the
upload or searches by filename. Preflight comparison is not atomic upstream CAS.

Native trial capture used private meeting526577 and attachments684953/684954;
the second file's141originalbytes match SHA256
`785229e6354d8899d43e6c9bc083204360c51593717c738aca05c00dcc513ab5`.
Captures and bytes are pinned under
`capabilities/evidence/boardable-meeting-documents/`; local acceptance is recorded
in `verification/boardable-meeting-documents-2026-11-16.json`. Native browser
operations and local adapter execution are separate evidence. General Document
Center files, replacements, deletion, publication and invitations are not mapped
by this adapter.
