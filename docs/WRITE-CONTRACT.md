# QuorumRelay write adapter contract

Schema 2.0.0. Frozen candidate 0.1.0.dev8; local source includes later mappings identified below. Current status: 2026-11-12. The engine contains real native write mappings and `PublicWriteTransport`; it can change an upstream provider when an authorized caller supplies usable credentials and approves an exact plan. Vendor-documented synthetic execution through these mappings satisfies provider discovery/read/search/import/export/write acceptance for its evidenced operation and field scope. Live provider mutation/readback remains **NOT_RUN** and is optional supporting evidence, not a completion gate. A synthetic receipt must never be represented as an actual remote mutation.

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
    "url": "https://webapi.legistar.com/v1/example-city/events",
    "namespace": "//webapi.legistar.com/v1/example-city"
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
- `WriteAdapter`: exact credential/source authorization, typed field validation, fixed native mapping, actual before/readback checks, apply and uncertain-intent reconciliation.
- `WriteTransport` / `PublicWriteTransport`: bounded outgoing requests with public-network, TLS, origin and credential isolation. Synthetic tests inject the transport protocol; there is no production `MockWriteAdapter` class. The injected transport declares `mock=True`, which is bound to the plan and cannot change at commit.
- `write_files.stage_write_file` and generic `interchange.stage_input`: caller-scoped file staging. `changes[].files[]` accepts `file_handle` or inline `content_base64`. A generic input handle is reopened through current operation-policy and expiry checks, then digest/length verified and bound to an immutable storage reference. The commit verifies the same bytes again, independently of a mutable handle head. Parser metadata and transfer limits remain separate.

The server checks both local authorization and configured provider permission at
plan and commit time. Unsupported or wrong-type fields are rejected before
mutation. Caller-provided expected versions must match actual provider readback. A local state fingerprint is labeled as a local precondition, never as
a provider revision or proof of remote compare-and-swap.

## State and retry safety

Use the shared `Storage.put/get/list` protocol. Storage is optional for read-only
engine use, but writes require an explicit store with atomic create/CAS semantics.
Collections include `write_plans`, `receipts`, scoped operation state, and immutable file captures. No synthetic provider state is stored by the production engine.

Persist per-item execution intent before the first outbound mutation. Receipts
hold each change's state, remote resource ID, provider revision when supplied, readback, and errors.
Concurrent commits must atomically claim a receipt before sending. Duplicate
commits return the same durable result. A crashed processing intent is uncertain,
not a safe-to-repeat create. Retry reconciles the original intended identity and
state before it does anything else. If readback cannot identify exactly one
matching effect, the receipt stays uncertain and requires review.

Allowed item states are `planned`, `sending`, `succeeded`, `failed`, `conflict`,
`uncertain`, `pending` for asynchronous tasks, and `cancelled`. Receipt state may also be `partial`. These are data
states, not additions to `OperationResult.status`. Standard envelope statuses
remain `completed|partial|cancelled|failed|unsupported`. Successful siblings survive
partial batches. No automatic deletion or rollback occurs. A cancelled batch does
not begin remaining items; previously applied items remain in its receipt.

## Implemented native mappings and acceptance limits

Mappings are additive as official evidence resolves. The initial inventory is
not yet a complete outbound backlog and unresolved entries remain incomplete.

| Family | Entity / operation | Official request and response |
|---|---|---|
| Legistar | Event create/update | POST `/v1/{Client}/Events`; PUT `/v1/{Client}/Events/{EventId}`; JSON GranicusEvent, required EventDate, update requires matching EventId. JSON object response; only `Accept: text/plain` returns ID string. |
| Legistar | Event item create/update | POST `/v1/{Client}/Events/{EventId}/EventItems`; PUT `/v1/{Client}/Events/{EventId}/EventItems/{EventItemId}`; JSON GranicusEventItem. |
| Legistar | Matter-linked meeting document upload/update | POST `/v1/{Client}/Matters/{MatterId}/Attachments`; PUT same path plus `/{MatterAttachmentId}`; JSON GranicusMatterAttachment. Required MatterAttachmentName; create must not set auto-generated MatterAttachmentSort. Binary is base64 in JSON, not invented multipart. |
| Legistar | Meeting matter/text/history create/update | JSON POST/PUT under `/Matters`, `/Matters/{MatterId}/Texts` and `/Matters/{MatterId}/Histories`; explicitly authorized meeting relationship required. |
| Legistar | Supplied vote / roll-call create/update | POST/PUT `/v1/{Client}/EventItems/{EventItemId}/Votes[/{VoteId}]` or `/RollCalls[/{RollCallId}]`; required PersonId and ValueId native fields, matching EventItem parent and explicit authorized meeting relationship. |
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
prove write permission. Actual deployment authentication/conflict behavior has
not been observed live and must not be invented; the documented synthetic checks
remain valid evidence for their attributed mapping and safety scope.

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

Remaining acceptance includes unresolved documented provider entities/fields and their synthetic execution/readback/receipt coverage, plus the required consumer workflows and delivery outcomes. Existing synthetic tests cover native wire contracts, duplicate commits, stale data, partial/denied outcomes, response loss/reconciliation, file handles and source isolation. Coverage is attributed per operation and field; shared safety tests do not establish every provider capability. No provider account acquisition or live transaction is required to satisfy the documented synthetic verification basis. Real deployments still require their own trusted credentials, current permissions and exact-plan approval.

## Later local source mappings

TelVue Connect existing-playlist reorder and media membership additions are
mapped from the pinned public vendor client, with documented v2 readback and
synthetic coordinator execution. See [exact fields, credentials and limits](TELVUE-WRITES.md).
This does not establish media upload, processing or vendor meeting association.

The table above records the earlier mapped surface and does not enumerate all
later source additions. Current source additionally includes Granicus Platform
SOAP and MediaVault event/media/metadata/document workflows, explicit publication,
non-clearing metadata imports, generated minutes and meeting-bound attendee/motion
data. See [the coverage map](ENGINE-COVERAGE.md), the pinned
[vendor contract provenance](capabilities/evidence/granicus-platform/source.json)
and the [engine adapter](../src/civic_data_connectors/providers/granicus_platform.py).
Publication is explicit approved input; destructive clearing, deletes and unrelated
platform administration remain excluded. Returned provider IDs/jobs do not imply
independently verified playable bytes.

Other later source additions include [Wistia replacement](WISTIA-SWAP.md),
Laserfiche paired image/text pages (see the pinned contract and tests referenced
in the coverage map), and the [OnBase DIP prepared file export](ONBASE-DIP.md).
These are local source capabilities with scoped evidence; the immutable dev8 wheel
and its existing installed-consumer receipts do not contain or certify later code.


## Source identity and credential routing

For new Legistar sources, use the same stable namespace returned by read validation, such as `//webapi.legistar.com/v1/example-city`. The request Client comes from the validated `/v1/{Client}` URL; it is not extracted by treating the entire stable namespace as a path segment. Historical write-only configurations using the exact Client slug remain accepted. The engine does not rewrite either identity or implicitly grant credentials between them: `allowed_namespaces` and provider credential policy must authorize the exact configured source namespace. A source claiming one Client's namespace while routing to another Client fails before any mutation.

Laserfiche Repository API account/repository identifiers and public WebLink source identities are distinct. A public WebLink source does not establish Repository OAuth access or an authorized repository mapping. Keep that prerequisite explicit rather than assuming that public meeting data authorizes repository mutations.


Laserfiche Repository routing derives its repository ID from the exact API source URL, separately from source identity. Canonical read/write sources use `//api.laserfiche.com/repository/v2/Repositories/{repositoryId}`; explicit historical write-only repository slug identities remain accepted. Current credential and caller namespace policy must match the exact configured identity, so this compatibility does not grant an alias or broaden repository access. WebLink identity derivation is unchanged; no public WebLink-to-account mapping is inferred.


## Essential multimedia update (post-dev3 source)

The built-in `municode-meetings` adapter uses only the documented dev origin `https://meetingsgov.devmunicode.com`. Trusted credentials must bind `origin`, caller `tenant`, exact application namespace, `token`, permission `meeting_multimedia:update`, and explicit `meeting_ids`. It does not issue tokens or infer a production host.

The official-linked production Postman sample records a lower-camel-case update request, but its multimedia GET and POST have no response examples. The linked development article documents a Pascal-case `MeetingStructure` under `meetingStructure` for that development host, without establishing production response casing/wrapper or persistence/readback semantics. Production multimedia updates therefore remain unmapped and are rejected before network; an account is not required to identify this evidence gap. See [the exact saved source and limits](capabilities/evidence/essential-postman/source.json).

A change uses entity `meeting_multimedia`, operation `update`, and equal GUID `resource_id`/`meeting_id`. `fields` can patch documented `PublishState`, `AudioVideoDetails` (`AudioVideoProviderType`, `AudioVideoUrl`), and `MultimediaItems`. Item patches are keyed by distinct existing `EntityId` and may update documented `EntityName`, `EntityTypeName`, `TimeStamp`, `MultimediaDisplayOptions`, `CustomDisplay`, `IncludeNumbering`, `UseDefaultMultimediaSettings`, and `MultimediaBaseUrl` values. Full-model `Id`/`MeetingId`, if supplied, must equal the before identities. The official sample demonstrates URL/timestamp/default/base-URL edits; remaining fields are typed by its full submitted model, with tenant enums and actual mutability still requiring authorized live verification. The adapter GETs the full `meetingStructure`, preserves all other documented and unknown values, validates the full model, and POSTs the full object to `/PublicApi/meeting/multimedia/update/{meetingId}`. It does not create meetings/items or upload media. Publication and other supplied enum integers are preserved as caller-selected model values; no enum meanings are invented.

`expected_version`, when supplied, is the canonical hash of the full before structure, not a fabricated provider revision. Commit rereads and compares the exact before hash. This is a preflight compare, not atomic provider CAS. Update response shape is unspecified, so the adapter accepts bounded successful HTTP status without guessing an ID/JSON response and then requires exact full-structure GET readback. Lost responses remain uncertain until read-only reconciliation; a possibly accepted POST is never resent. Existing durable intent, exact approval, caller policy, cancellation and receipt boundaries apply. Structures containing secret-like unknown keys that cannot safely enter the plan fail rather than silently dropping those fields. Live tenant acceptance remains NOT_RUN.

Fixed account reads and every PublicWriteTransport request disable redirects before a second socket/request can receive credentials. Exact account read routes are also verified on the response. Essential multimedia captures retain the supplied parent meeting relationship; arbitrary EntityTypeName values remain raw rather than inferred agenda relationships.

## Response completion bounds

Shared JSON write adapters recheck cancellation and the total deadline after transport completion and JSON sanitization. An interrupted mutation response remains uncertain because the request may have reached the provider. An interrupted final GET cannot confirm success; the durable intent remains available for read-only reconciliation after restart, without replaying the mutation. Preflight GET interruption retains its cancelled/deadline status and cannot produce an approved plan. Synthetic public-coordinator coverage includes Wistia and Select, raw mutation responses and parsing completion. See `verification/write-response-completion-2026-11-15.json`.

The shared JSON, Essential and Granicus adapters also honor the durable cancellation returned by the coordinator after commit-time preflight and before the native mutation. A stopped item remains durably cancelled even if cancellation is later cleared. Granicus document chunk uploads check this persisted signal after each accepted chunk: interruption leaves the saved upload ID and completed-chunk count uncertain, sends no further chunks and permits read-only reconciliation without resubmitting or finishing the upload. These are cooperative checkpoints, not rollback of accepted remote work.

## Select native event update

Selected `event:update` additionally supports the exact documented18property native PUT plus an explicit complete intended GET snapshot. Publication/media/template and unrelated fields are preserved; native clock/date literals are caller supplied without inferred conversions. Preflight hash, exact readback and durable GET-only reconciliation apply. Event create remains separate. See [native contract and limits](CIVICPLUS-SELECT-EVENT-UPDATES.md).
