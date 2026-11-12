# Write adapter contract, draft

Schema 2.0.0. Observation date: 2026-11-11. This run uses synthetic data only.
There is no live mutation transport. A mock receipt never establishes vendor acceptance.

## Public operations

`writes.register(engine, adapters=None)` registers `plan_write`, `commit_write`, and
`receipt`. An adapter maps a documented native request and validates fields. The
write coordinator owns authorization, immutable plans, atomic execution intents,
conflicts, partial batches, reconciliation, and scoped durable receipts.

Planning request:

```json
{
  "source": {
    "provider": "legistar",
    "url": "https://webapi.legistar.com/v1/mock-city/events",
    "namespace": "mock-city"
  },
  "changes": [{
    "key": "meeting-1",
    "entity": "event",
    "operation": "create",
    "fields": {"EventDate": "2026-11-11T00:00:00", "EventBodyId": 4}
  }],
  "bounds": {}
}
```

Native field names are intentional. A neutral record is not automatically a
vendor request. `resource_id`, `parent_id`, and `expected_version` are explicit
change members when applicable. Unknown members and unsupported fields fail.
No delete, arbitrary URL, vendor administration, or implicit publishing is exposed.

Planning requires trusted `OperationContext.authorization` capability
`write:plan`; committing requires `write:commit` under an authenticated,
server-saved policy and the explicit exact plan ID/hash in the commit request.
That exact commit is the per-plan approval, not a general implicit mutation.
The service/application supplies the trusted context after its own
principal/client/tenant authentication and approval workflow. Request JSON
cannot grant capabilities or identity. Credentials remain exclusively in the
private context. Consumers may configure a stricter server-side approval callback.

Commit accepts only `{"plan_id":"...", "plan_hash":"..."}`. Receipt accepts only
`{"plan_id":"..."}`. Actor, client, tenant, source origin/namespace, entity,
operation, resource/parent identity, fields, native request, before/after state,
expected version, and mock mode are bound to a canonical SHA256 plan digest.
Plans are immutable and stored with `create_only=True`. Their digest is checked
again on commit; stored plans or client-returned plans are never accepted as an
editable patch. Mutable caller objects cannot change a stored plan.

## Adapter boundary

Typed declarations live in `write_adapters.py`, not the discovery-owned
`providers/` directory:

- `WriteChange`: explicit key, entity, operation, fields, parent/resource IDs and
  expected version.
- `NativeRequest`: method, fixed official origin/path, documented content type,
  safe non-secret headers, native body and file-part declarations.
- `WriteAdapter`: capability lookup, source validation, field validation and
  native mapping, synthetic readback, synthetic apply, uncertain-intent reconcile.
- `MockWriteAdapter`: documents its synthetic state and never opens a network
  connection. Server-side fixture configuration can deny permission, fail before
  send, return a conflict, lose a response after applying, or leave an unknown
  outcome. These controls are not public request members.

The server checks both local authorization and configured provider permission at
plan and commit time. Unsupported or wrong-type fields are rejected before
mutation. Caller-provided expected versions must match actual synthetic provider
revision. A local state fingerprint is labeled as a local precondition, never as
a provider revision or proof of remote compare-and-swap.

## State and retry safety

Use the shared `Storage.put/get/list` protocol. Storage is optional for read-only
engine use, but writes require an explicit store with atomic create/CAS semantics.
Collections: `write_plans`, `receipts`, and synthetic provider state.

Persist per-item execution intent before applying even a mock mutation. Receipts
hold each change's state, resource ID, mock provider revision, readback, and errors.
Concurrent commits must atomically claim a receipt before sending. Duplicate
commits return the same durable result. A crashed processing intent is uncertain,
not a safe-to-repeat create. Retry reconciles the original intended identity and
state before it does anything else. If readback cannot identify exactly one
matching effect, the receipt stays uncertain and requires review.

Allowed item states are `planned`, `sending`, `succeeded`, `failed`, `conflict`,
`uncertain`, and `cancelled`. Receipt state may also be `partial`. These are data
states, not additions to `OperationResult.status`. Standard envelope statuses
remain `completed|partial|cancelled|failed|unsupported`. Successful siblings survive
partial batches. No automatic deletion or rollback occurs. A cancelled batch does
not begin remaining items; previously applied items remain in its receipt.

## Verified native mappings to implement

Mappings are additive as official evidence resolves. The initial inventory is
not yet a complete outbound backlog and unresolved entries remain incomplete.

| Family | Entity / operation | Official request and response |
|---|---|---|
| Legistar | Event create/update | POST `/v1/{Client}/Events`; PUT `/v1/{Client}/Events/{EventId}`; JSON GranicusEvent, required EventDate, update requires matching EventId. JSON object response; only `Accept: text/plain` returns ID string. |
| Legistar | Event item create/update | POST `/v1/{Client}/Events/{EventId}/EventItems`; PUT `/v1/{Client}/Events/{EventId}/EventItems/{EventItemId}`; JSON GranicusEventItem. |
| Legistar | Matter-linked meeting document upload/update | POST `/v1/{Client}/Matters/{MatterId}/Attachments`; PUT same path plus `/{MatterAttachmentId}`; JSON GranicusMatterAttachment. Required MatterAttachmentName; create must not set auto-generated MatterAttachmentSort. Binary is base64 in JSON, not invented multipart. |
| Laserfiche WebLink family | Linked meeting document create/upload/update | Repository API v2 POST `Repositories/{repositoryId}/Entries/{parentEntryId}/Folder/Import`; PATCH `Repositories/{repositoryId}/Entries/{entryId}/Document`; multipart `request` JSON, optional `file`, optional `imageFiles`. Import returns 201 entry and Location; PATCH additive metadata/image append and replaces edoc only when supplied. |
| Laserfiche WebLink family | Large linked meeting document upload/update | CreateMultipartUploadUrls returns uploadId/urls; chunk PUT returns ETags; ImportUploadedParts returns taskId; UpdateUploadedParts returns 202 taskId. Task success requires polling and entry readback, not merely accepting taskId. |
| Wistia | Recording/media upload | POST `https://upload.wistia.com/`; multipart file or form URL; name/project_id/description/contact_id; Bearer authentication preferred, never serialize legacy access_token. Returns 200 Media with hashed_id. |
| Wistia | Recording/media metadata update | PUT `https://api.wistia.com/modern/medias/{mediaHashedId}`; JSON name/new_still_media_id/description/tags/custom_metadata; version header `X-Wistia-API-Version: 2026-09`; returns 200 Media. Tags replace, custom_metadata null clears that key and omitted keys remain. |
| Wistia | Supplied caption create/update | POST modern `/medias/{mediaHashedId}/captions`, PUT same plus `/{languageCode}`; JSON caption_file text or multipart file, create optional language. ISO 639-2 update code `^[a-z]{3}$`. Success 200 with no invented response object. |
| Wistia | Recording/media URL import | POST modern `/medias/import_url`; JSON url/folder_id; returns 201 background_job_status, not Media. URL must be publicly retrievable; some source domains are prohibited by vendor. |
| Wistia | Supplied caption targeted update | POST modern `/medias/{mediaHashedId}/captions/{languageCode}/edits`; JSON expected_version plus edits[1..20] target_text/replacement_text and optional paired inclusive start_ms/end_ms. Atomic vendor version check; 409 stale_version/diverged, 422 unresolved edit writes nothing. |
| Wistia | Recording/media additive tags | POST modern `/taggings/bulk_create`; JSON hashed_ids/tag_names. Adds tags, does not replace. Returns background_job_status; authorizations-based expiring tokens are explicitly disallowed. |

Legistar JSON field schemas come from the official per-operation resource tables,
not the older MeetingId/MeetingName/MeetingDate reader. Read token examples do not
prove write permission. Its live write authentication/conflict behavior remains
access-blocked and must not be invented.

Laserfiche repository documents are relevant only when explicitly associated with
meeting records. Generic repository administration, folders, access control,
deletion and lifecycle administration are not accepted as arbitrary writes.
Wistia generated translation/transcription purchases are not supplied captions
and are outside this release's no-new-OCR/ASR boundary.

## Official evidence

- https://webapi.legistar.com/Help
- https://webapi.legistar.com/Help/Api/POST-v1-Client-Events
- https://webapi.legistar.com/Help/Api/PUT-v1-Client-Events-EventId
- https://webapi.legistar.com/Help/Api/POST-v1-Client-Events-EventId-EventItems
- https://webapi.legistar.com/Help/Api/PUT-v1-Client-Events-EventId-EventItems-EventItemId
- https://webapi.legistar.com/Help/Api/POST-v1-Client-Matters-MatterId-Attachments
- https://webapi.legistar.com/Help/Api/PUT-v1-Client-Matters-MatterId-Attachments-MatterAttachmentId
- https://developer.laserfiche.com/docs/guides/documents-and-folders/guide_importing-documents/
- https://developer.laserfiche.com/docs/guides/documents-and-folders/guide_updating-documents/
- https://docs.wistia.com/reference/post_.md
- https://docs.wistia.com/reference/put_medias-mediahashedid.md
- https://docs.wistia.com/reference/post_medias-mediahashedid-captions.md
- https://docs.wistia.com/reference/put_medias-mediahashedid-captions-languagecode.md
- https://docs.wistia.com/reference/post_medias-import-url.md
- https://docs.wistia.com/reference/post_medias-mediahashedid-captions-languagecode-edits.md
- https://docs.wistia.com/reference/post_taggings-bulk-create.md

Remaining acceptance: exact field-level implementation ledger and deterministic
tests for every implemented adapter; independent lifecycle, transport parity and
restart checks. All live write acceptance remains NOT_RUN under mock-only policy.
