# PrimeGov public document links, outlines and tracking search

## Public tracking-number search

The public advanced-search client sends its Tracking Number input as
`TrackingNo` to `POST /api/v2/PublicPortal/search`. Set the existing PrimeGov
source's `options.tracking_number` to the literal number:

```python
from quorumrelay import Source, create_engine

source = Source("primegov", "https://selected-tenant.primegov.com/public/portal",
                options={"tracking_number": "PG-2026/011"})
result = create_engine().execute("search", {
    "native": True, "source": source.public_dict(),
    "query": {"date_from": "2026-11-01", "date_to": "2026-11-30"},
    "bounds": {"max_records": 100, "deadline_seconds": 15},
})
```

This option applies only to native public search. Explicit date bounds remain
required. Optional query terms/phrases retain local AND matching over returned
metadata/excerpts; tracking-only searches send empty `Text`. The number must be
nonempty text without control characters, bounded by1024UTF-8 bytes and the
parser limit. Form encoding preserves the literal value. The filter binds the
checkpoint, so a continuation cannot change or remove it.

Results remain partial. Tracking matching is provider-defined, without locally
verified equality against an invented response field. Full-document content,
server matching rules and catalog completeness remain unverified. The exact
form request is retained in `bundle.extensions.public_search_request` alongside
the original response and native identities through SQLite and JSON/JSONL/ZIP.
The current Reno client returned200 with the previously pinned hash; source
excerpts are in `capabilities/evidence/primegov-tracking-search/source.json`.
This public form does not establish authenticated Meeting/speaker/private
tracking API behavior, writes or vendor-file import.

## Public document links and selected outlines

The Waco public portal's declared `_Upcoming.js` has a `getHref(doc)` contract. Rich records now use the HTML portal route for `compileOutputType=3`; PDF and Word use the compiled-document route. Missing/nonpositive `templateId` selects the native `compiledMeetingDocumentFileId`, rather than inventing a meeting-template ID. An explicit valid source link takes priority. Each descriptor must match its parent meeting ID; malformed/unknown branches are counted in `documents_unmapped_count`. Original document fields remain in source metadata and captures.

The frozen legacy export projection remains unchanged for compatibility. Its historical HTML descriptors can differ from corrected rich-record document locators. Applications should use `records[].normalized.documents` and current relationships for retrieval. No existing imported record is automatically rewritten; reimporting a current normalized capture refreshes its normalized hash.

The public `publicSpeaker.js` separately declares an anonymous GET of `GetSectionsAndItemsForSpeakerRequest?meetingId=...`. This retrieves an outline for the public speaker-request UI; it does not submit a request, search speakers, or expose a complete agenda contract.

```python
from quorumrelay import Bounds, Source, create_engine
from quorumrelay.storage import SQLiteStorage

source = Source("primegov", "https://wacotexas.primegov.com/public/portal",
                input_format="primegov-portal-json")
engine = create_engine(storage=SQLiteStorage("records.sqlite"))
# First import the captured native meeting under this exact source and caller scope.
result = engine.fetch_related(source, "4922", "agenda_section",
                              bounds=Bounds(max_records=20))
```

The selected meeting must already be stored with native ID and `allowPublicSpeaker=true`. Only `agenda_section` or `agenda_item` is mapped. Response sections must assert the selected meeting ID. Section membership follows the native nested response; item parent IDs/system-item IDs/levels are retained without inventing a deeper hierarchy. The handler validates MIME, exact response URL, current scope, cancellation, deadline and byte/record bounds. It never follows redirects or calls registration/submission methods. Date filters and continuation are rejected because this is one selected snapshot, with cap disclosure and exact raw capture.

All results remain partial: the request UI can omit agenda content and does not establish complete history, item documents, supplied text or authenticated Meeting/speaker/tracking API behavior. The live selected response had six sections and zero items. Synthetic cases cover nonempty client-shaped items, vote summaries, raw ZIP roundtrips, repeated imports, search/reopening and guarded failures. Public source pins and actual read hashes are in `docs/capabilities/evidence/primegov-public-outline/source.json`.

Selected public-search Type 4 documents also use the declared `_Search.js` HTML branch for numeric `compileOutputType=3`. `fetch_attachment` retrieves the exact native compiled-file page with one guarded GET, validates HTML MIME and framing, and preserves its bytes and SHA-256. It reports `text_availability=not_extracted`, `content_completeness=unverified`, and no dynamic execution or compilation. This does not extract the agenda or call `CompileAsync`. Unknown or Boolean output types remain unmapped. The page can be staged explicitly as an authorized ZIP attachment; exporting a record alone does not include its bytes. Source pins are in `docs/capabilities/evidence/primegov-search-html/source.json`.
