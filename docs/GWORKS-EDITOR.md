# gWorks editor meeting detail

The `gworks-editor-meeting-json` format reads one meeting from the vendor's publicly available development-editor contract. It preserves flattened meeting fields, ordered agenda sections/items, supplied minutes text, file descriptors and unknown original fields. The same records support local search, persistence and neutral JSON/JSONL/ZIP export.

```python
from quorumrelay import Source, create_engine

source = Source(
    "gworks",
    "https://api.dev.gworks.cloud/cms/secure/city/meeting/5017",
    input_format="gworks-editor-meeting-json",
    options={"gworks_city_id": "1311"},
)
# saved_bytes is a captured JSON response, not the JavaScript source.
result = create_engine().normalize(source, saved_bytes,
                                   input_format="gworks-editor-meeting-json")
```

For an authorized fetch, supply `OperationContext` credentials under `gworks`: `token`, matching `tenant`, `city_id`, `origin="https://api.dev.gworks.cloud"`, and `allowed_namespaces=["//api.dev.gworks.cloud/city/1311/cms"]`. Call `engine.fetch(source, context=context)`. These values belong in trusted caller configuration. No enrollment or credential acquisition is performed by the library.

The development namespace is deliberately separate from production city JSON identities. Native meeting ID must match the selected URL. Section/item identities are capture-local positions because the client supplies no native item IDs. File descriptors, including staff-only indicators, are retained as metadata; no file URL is invented. Supplied ISO offsets are retained, numeric timestamp units remain uninterpreted. Discovery without saved input is rejected because this is a single-meeting endpoint.

Source manifest: `docs/capabilities/evidence/gworks-development-editor/source.json`. The editor declares GET/POST/PUT routes, direct flattened readback, nested array structures, JSON-string serialization for save fields and explicit publication controls. Detail reads, normalization and the bounded writes below are implemented.

Verification: `tests/test_gworks_editor.py` plus existing gWorks regression tests. Synthetic transport exercises the actual fetch handler, tenant/origin isolation, malformed responses, cancellation, bounds, SQLite reopen/search and lossless export. No live account calls, package build or release.


## Meeting writes

The built-in gWorks write adapter now supports:
- `meeting:create`: explicit draft or published-agenda creation.
- `meeting:update`: title, location, category and scheduled time; editing agenda/minutes text; appending sections/items.
- Explicit agenda or minutes publication, with separate publication permissions and a caller-selected publication date.

Existing sections/items cannot be removed through this mapping. Existing attachments, staff-only file descriptors and unknown fields are preserved. New file upload, archive, unpublish and delete operations are outside this mapping.

Use the write source URL `https://api.dev.gworks.cloud/cms/secure/city/meeting/`, namespace `//api.dev.gworks.cloud/city/1311/cms`, and option `gworks_city_id="1311"`. It uses the same trusted tenant/city/origin/token binding as reads. Add `permissions` containing the authorized operations and `meeting_ids` containing permitted existing meeting IDs as strings. Publishing also requires `meeting:publish_agenda` or `meeting:publish_minutes`. The shared coordinator requires `write:plan` and `write:commit`, durable storage and exact plan-hash approval.

Example change for a plan:

```json
{
  "key": "new-council",
  "entity": "meeting",
  "operation": "create",
  "fields": {
    "title": "Council hearing",
    "location": "City chambers",
    "scheduled_start": "2026-11-17T18:30:00-07:00",
    "category_ref_type_id": "2",
    "sections": [
      {"title": "Public business", "items": [{"value": "Bridge repair", "minute": ""}]}
    ],
    "publication": "draft"
  }
}
```

For update, use `operation="update"` and `resource_id` as the native meeting ID. Omit unchanged fields. If supplying `sections`, provide the complete ordered set of section titles and item value/minute pairs; the adapter overlays them onto the snapshot to preserve file references and unknown properties. Appended entries start with empty file lists. Supplied meeting timestamps require explicit offsets and minute precision.

To publish, set `publication="agenda"` or `"minutes"` and `published_on="YYYY-MM-DD"`. Minutes publication requires an already published agenda. Ordinary updates preserve existing publication flags; editing already published content may change what readers see. Creation sends explicit unpublished flags for drafts, instead of relying on server publication defaults.

Planning performs no mutation. Update commit re-reads the full original snapshot and rejects changes since planning. The outgoing request follows the editor's form field serialization: category as a string, section/file arrays as JSON strings inside the JSON body, and explicit publication fields when selected. Save response identity is persisted before readback. Success requires requested values and preserved before-state to match the detail GET; only the server modification timestamp is allowed to change freely. This is a preflight comparison, not an atomic server compare-and-swap.

A timeout, lost ID, cancellation after send, denied readback or unexpected result leaves an uncertain receipt. Retrying the same plan reconciles by confirmed ID and never repeats POST/PUT. There is no title-based create matching. The adapter is bound to the captured development deployment; production routing is not silently substituted.

Write verification: `tests/test_gworks_write.py` exercises the real adapter through the coordinator with a synthetic transport. Shared approval, durable-intent, cancellation and readback checks are included in `docs/verification/gworks-writes-2026-11-16.json`.



## Development media upload and association

The `media` entity with operation `upload` accepts one SDK staged file (`content_base64` or `file_handle` at the public boundary). Preparation validates its immutable byte identity and bounded media-library pages without allocating a remote file. Use the existing development meeting source and private tenant/city/token binding. Private configuration additionally supplies explicit `city_code` for the file-server route and `media:upload`; association requires `meeting:update` and the selected meeting-ID allowlist. Approved signed-storage origins can be set with `media_storage_origins`; the default is `https://files.dev.gworks.cloud`. API Bearer credentials are never sent to storage.

For upload-and-attach, supply fields `meeting_id` and `target` (`meeting` or `agenda_item`). Agenda items additionally require explicit `section_index`, `item_index` and `usetype` (`official` or `public`). The plan binds the selected item to its original snapshot; those indexes are not native IDs. Omitting association fields requests upload only. Existing-file association is a separate explicit update/associate operation using exact `media_id` and selected meeting target.

The upload performs metadata allocation, one signed PUT, bounded library readback, exact new native-ID verification and a file-byte hash check before association. Existing duplicate filenames are rejected. The meeting save preserves unknown fields and existing attachments and verifies the exact resulting state. Durable progress is recorded before each mutation. An uncertain allocation, PUT or meeting save is never automatically replayed; receipt reconciliation only reads. An upload may be confirmed while its association remains uncertain.

Supported extensions follow the captured client: gif, jpg, jpeg, png, pdf, doc, docx, ppt, pptx, xls and xlsx. The vendor UI threshold is 30000KB; SDK byte/deadline limits also apply. Publication is not implicit in attachment upload. This maps the development client; production applicability remains separate.

Integrated verification: 97 affected cases passed, including 15 media cases, existing meeting writes/editor reads and shared coordinator checks. Exact bindings: `docs/verification/gworks-media-writes-2026-11-16.json`. No live vendor calls or uploads were performed.
