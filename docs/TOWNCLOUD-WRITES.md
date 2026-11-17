# Existing TownCloud item draft text

The public TownCloud application client declares `POST /go/{site}/drafts` and `GET /go/{site}/drafts?agenda_id={meeting_id}`. QuorumRelay maps one existing, explicitly unexpired draft field for a native agenda item or section. The result means **saved unpublished draft**. It does not save the item form or publish the agenda.

Use `plan_write` with a source such as:

```json
{"provider":"towncloud","url":"https://towncloud.io/go/example","namespace":"//towncloud.io/go/example"}
```

An example change is:

```json
{"key":"draft-1","entity":"item_draft","operation":"update","meeting_id":"7","resource_id":"3","fields":{"content_type":"Meetings::Item","field_name":"text","draft_content":"Proposed agenda text"}}
```

Item fields are `heading`, `subheading`, `text`, and `minutes`. Section fields are `heading` and `text`, with `content_type` set to `Meetings::SectionHeader`. Empty text is supported. New/expired drafts, new items, uploads, publication and arbitrary fields fail before mutation. Rendered public agenda positions are capture-local and cannot be used as native editor IDs.

The application owns session credentials and authorization. Supply these through trusted `OperationContext.credentials["towncloud"]`, never through untrusted requests:

```python
{
    "tenant": "city",
    "site_url": "https://towncloud.io/go/example",
    "allowed_namespaces": ["//towncloud.io/go/example"],
    "permissions": ["item_draft:update"],
    "content_bindings": {"7": {"Meetings::Item": ["3"]}},
    "session_cookie": "application-owned-session-cookie",
    "csrf_token": "application-owned-csrf-token",
}
```

The cookie must use normal `name=value` syntax. The context tenant and namespace policy must match. `content_bindings` is application policy binding known native content to its agenda; the API adapter does not obtain credentials or infer that binding from a public display position.

Planning reads the returned draft snapshot and validates a unique content-type/content-ID/field tuple. Commit rereads it and rejects changes since planning. This preflight comparison is not atomic upstream compare-and-swap. The adapter persists intent before the single POST, then checks exact returned readback; only the selected draft's `updated_at` may vary. Unknown fields and other returned drafts must remain unchanged. A timeout or uncertain response is reconciled through GET after restart, without replaying the POST. No paging or complete account-wide snapshot is inferred from the client.

The source extract/provenance is under `docs/capabilities/evidence/towncloud-client-drafts`. Thirty synthetic coordinator cases cover every declared field, request encoding, identity/tenant permissions, conflict, unknown fields, ignored/collateral changes, cancellation and durable restart recovery. The related write suite passed 105 tests. No live vendor write was performed. The anonymous editor GET redirected to the site home without a form; that observation does not establish that all remaining contracts require private access.

Response retrieval uses the smaller of the approved parser and transfer byte
limits, including injected transports that fail to enforce the requested cap.
An oversized preflight fails before approval. An oversized response after a
sent mutation leaves an uncertain receipt; a subsequent commit reconciles by
readback after reopening without sending a second mutation. The
[executed boundary regressions](verification/write-response-bounds-2026-11-15.json)
preserve existing target binding and request payload contracts.

## Presigned upload contract recovered from public client

The 2026-11-16 public bundle is byte-identical to the pinned application. Its
[single- and multi-file source](capabilities/evidence/towncloud-client-drafts/upload-source.json)
exposes a two-stage storage upload and parent item save. The runtime DOM element
`s3-upload-config` supplies `presigned_post.url` and `presigned_post.fields`. The
client sends those fields, substitutes `${filename}` in the storage key, appends
the file, and requires HTTP201. PDFs then require JSON `success` from the
configured validation URL or `/go/{site}/pdf_validations`, with `s3_key`,
`file_name`, and `content_type=application/pdf`.

The final item form includes indexed `item[item_attachments_attributes]` values:
`name`, `s3_key`, `private_doc` (1/0), `rank` (0), and `original_filename` in the
multi-file branch. The current public page lacks the runtime upload config and
full item form. The created attachment response/native ID, original download
locator, and recovery lookup are still missing. These extracted fields are
pinned for the remaining implementation; no partial storage upload is executed.

All39 current TownCloud draft/public/detail tests passed on2026-11-16. The trial
request was subsequently submitted successfully, with a confirmation that someone
will be in touch. No application dashboard was available. Scott ended further
TownCloud pursuit; do not repeat signup or contact the vendor. Existing
unpublished-draft writes remain the implemented outbound scope.
