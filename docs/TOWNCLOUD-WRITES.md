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
