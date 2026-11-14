# CivicClerk Select selected detail, files and section writes

These mappings apply to **CivicPlus Select / CivicClerk**, separately from Essential / Municode. The public Fishers tenant exposes [official OpenAPI](https://fishersin.api.civicclerk.com/swagger/v1/swagger.json) and [OData metadata](https://fishersin.api.civicclerk.com/v1/$metadata). The pinned copies are in `docs/capabilities/evidence/civicclerk-openapi/`. Public metadata establishes publication values NotPublished=0, Published=1 and PublishedOnDate=2; it does not establish every Event write/readback date transformation.

## Selected published meeting and file reads

Configure the exact tenant's `https://{tenant}.api.civicclerk.com/v1/Events` URL or its matching portal URL. Discover and persist a published Event with the same caller context before calling `fetch_record(source, event_id)`. The stored Event's `agendaId`, rather than its Event ID, selects `/v1/Meetings/{agendaId}`. The returned native Meeting ID must match. Repeated detail reads retain the original Event identity and raw Event/Meeting fields.

Supplied `items` retain native IDs, parent IDs and metadata; their fields are not silently treated as rendered document text. `publishedFiles[].fileId` on either an Event or its selected Meeting supplies the exact file-stream locator `/v1/Meetings/GetMeetingFileStream(fileId={id},plainText=false)` on the tenant API host. Event-supplied files do not require a separate Meeting lookup or a positive `agendaId`. Discovery corrects the historical portal-host locator in the richer record while leaving the baseline compatibility output unchanged. An explicit `fetch_attachment` validates the stored published Event identity, exact configured source and supplied file metadata; selected Meeting files additionally validate the agenda relationship. Exact legacy portal locators can be resolved to the API at fetch time without rewriting storage. Unrelated URLs or file IDs are rejected. These operations enforce byte/deadline/cancellation bounds, exact response URLs and no redirects. Detail remains partial: it does not establish a complete catalog, rendering or playback.

## Section create and update

The existing `plan_write` → exact `plan_id`/`plan_hash` approval → `commit_write` → `receipt` flow now supports only `entity="agenda_section"`, with `operation="create"` or `"update"`. A change supplies:

- `key`, `meeting_id`, and `parent_id` (the native agenda ID).
- `fields.sectionName` and optional nullable `fields.sectionText`. Create requires a nonempty name; update may supply either field.
- `resource_id` for update, optionally `expected_version` equal to the current readback's canonical hash. Create supplies neither.

Use the exact API Events source without options and its derived namespace, for example `//fishersin.api.civicclerk.com`. The trusted application context requires `write:plan` and `write:commit`, a tenant, allowed operations/namespaces, and private `credentials["civicplus-select"]` containing a token plus:

```python
{
    "tenant": "your-application-tenant",
    "origin": "https://fishersin.api.civicclerk.com",
    "allowed_namespaces": ["//fishersin.api.civicclerk.com"],
    "permissions": ["agenda_section:create", "agenda_section:update"],
    "parent_ids": ["91"],
    "meeting_ids": ["7"],
    "resource_ids": ["41"],  # Required target allowlist for updates.
    # "token": supplied privately by the trusted application.
}
```

The example IDs are synthetic, not instructions to modify a public city's data. Both meeting and agenda allowlists remain required. The adapter also reads the exact `/v1/Events/{meeting_id}` and checks its native `id` and `agendaId` during planning, immediately before a write, and during reconciliation. A mismatched relationship prevents the write; a changed relationship after creation leaves the receipt uncertain. Credentials remain private and are redacted from plans/receipts.

Create sends only documented `agendaId`, `sectionName` and optional `sectionText`. Update reads the selected section and checks its agenda parent, preserves omitted fields, then compares the prepared readback immediately before PUT. This is a preflight comparison, not an atomic provider-side lock. A 204 PUT is followed by GET. Success requires exact identity, parent and approved fields. An ambiguous create/readback remains uncertain; replay never resends its POST. No parent move, DELETE, Event write, item write or document upload is mapped here.

## Evidence and remaining scope

The [initial scoped receipt](verification/public-contract-leads-2026-11-13.json), [relationship/status follow-up](verification/provider-fidelity-2026-11-14.json), and [Event-file correction](verification/select-event-files-2026-11-14.json) distinguish actual synthetic execution from live acceptance. Tests cover persistence/reopen/export, source/parent/permission denial, conflicts and uncertain replay. Existing public grouped Search remains unchanged. Event create/update models are documented, but date/time/template readback equivalence still needs an exact mapping. In the pinned spec, create constrains `eventStartTime` to `HH:MM`; update declares a free-form string with a `12:00:00 AM` default, while readback exposes `eventDate` and `startDateTime`. The [official create](https://www.civicplus.help/meetings-select/docs/create-a-one-time-event), [edit](https://www.civicclerk8.civicplus.help/hc/en-us/articles/360035623054-Edit-an-Event-Summary) and [recurrence](https://www.civicplus.help/meetings-select/docs/create-a-recurring-event) guides describe product workflows, not an exact API timestamp conversion. No conversion or recurring-template side effect is inferred here.
