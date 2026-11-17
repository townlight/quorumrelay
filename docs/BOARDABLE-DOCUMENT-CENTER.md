# Boardable root Document Center writes

`BoardableDocumentCenterWriteAdapter` implements the captured general Document
Center root upload and existing-title edit. Meeting supporting documents use a
separate adapter. The native browser capture is under
[`capabilities/evidence/boardable-document-center`](capabilities/evidence/boardable-document-center/source.json).

Select `current_document_center: true` in private Boardable credentials. Other
agenda/meeting/document modes must be absent or false. Bind the exact tenant,
organization root URL (`org_url`), numeric `organization_id` and `owner_id`,
allowed namespaces, private `session_cookie` and `xsrf_token`, and permissions.
Existing edits also require a string `document_ids` allowlist and exact
`document_urls` map to the native short-slug URLs. The dispatcher checks this
mode before the meeting/agenda modes; file binding stays scoped to each call.

Both operations use `entity: document` and `fields: {title: 'Document title'}`.
They have no meeting, parent, language or page IDs. The source is the exact
organization root without options, body or input-format overrides.

- `operation: upload` requires `document:upload`, no resource ID and exactly one
  ordinary immutable shared file input named `file`.
- `operation: update` requires `document:update`, the exact allowlisted native
  resource ID, and no files. The title is the only changed field.

## Upload and independent original-byte verification

The native multipart POST to `/{org}/documents` contains `file`, `title`, empty
`body`, `disable_downloads=false` and `folder=0`. A201 response must identify a
native document belonging to the configured organization/owner, with the
captured Document UUID type and canonical short-slug URL. The new native ID and
URL are persisted before independent GET `documents/{slug}/data` and original
download. Filename, MIME type, empty body, root state, native identity, original
length and SHA256 must match the approved immutable file. PDF preview conversion
is independent of original-file success.

If a response is lost before its native identity is available, the receipt stays
uncertain. Recovery never replays the upload or guesses an ID from a title,
filename or catalog search. After a returned ID is persisted, recovery performs
only canonical native reads and original-byte verification.

## Existing-title edits

Planning reads the exact native data URL and original file. The normalized full
business state and original SHA256 bind approval; apply repeats the reads and
checks for a conflict before any POST. The JSON POST to the numeric document
endpoint contains only `title`. Independent data and original download must
confirm the requested title while preserving every other normalized field and
the original bytes. Preview/activity timestamps and other explicitly derived
display data are excluded from business comparison. Captured root
`attachable=false` is a native empty-association marker; an actual association
object is rejected. A matching title is an explicit no-send operation.

These comparisons are preflight conflict detection, not atomic upstream CAS.
An error after send remains uncertain; metadata recovery reads the exact
allowlisted document without another POST. A durable mutation attempt is
required before readback can confirm an uncertain intent.

## Bounds, policy and remaining work

Every request rechecks tenant/namespace/provider grants. POST rechecks the current
application commit grant. Cancellation, deadlines, request counts and cumulative
request/response bytes apply. JSON is finite, depth/list bounded and rejects
duplicate keys. Canonical download URLs stay on the configured organization;
redirects and foreign identity/owner/organization responses are rejected. Session
and XSRF values and reflected cookie components cannot enter plans or receipts.

The implementation covers ordinary computer files in root folder0 with downloads
enabled and no notifications. Folder-specific creation, access/sharing changes,
invitations, signatures, replacement and deletion are not mapped. The captured
replacement workflow warned of irreversible annotation loss and was cancelled;
no replacement was executed. API-key entitlement, broader recurrence and
publication/import gaps remain separate unfinished Boardable work.

The native captures record authorized browser actions. Adapter acceptance uses
synthetic transports with the real Engine/SQLite coordinator and captured
responses/bytes; it does not claim exported browser credentials or live adapter
execution.
