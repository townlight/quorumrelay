# BoardDocs public listing and selected printable agenda

The integrated source has an opt-in, bounded BoardDocs public read. Its route and field mapping comes from the pinned third-party LlamaIndex reader and example notebook, not BoardDocs vendor documentation. The provider's existing saved numbered-agenda PDF reader remains unchanged.

## Configure one public committee

Use the exact public page and an explicit committee ID obtained from the source you intend to read:

```python
from quorumrelay import Bounds, OperationContext, Source, create_engine

source = Source(
    "boarddocs",
    "https://go.boarddocs.com/mi/grand/Board.nsf/Public",
    options={"boarddocs_committee_id": "YOUR_COMMITTEE_ID"},
)
context = OperationContext(
    principal="meeting-reader",
    client_id="your-application",
    allowed_operations=frozenset({"discover", "fetch", "normalize", "import_bundle", "search"}),
    allowed_namespaces=frozenset({"//go.boarddocs.com"}),
)
engine = create_engine()
result = engine.discover(
    source,
    bounds=Bounds(max_pages=10, max_records=25, deadline_seconds=30),
    context=context,
)
```

Without `boarddocs_committee_id`, discovery does not open the BoardDocs route and the prior saved-PDF behavior remains available. The source path must end exactly in `/{site}/Board.nsf/Public` on `go.boarddocs.com` over HTTPS. The reader posts `current_committee_id` to `/BD-GetMeetingsList?open`, then requests `/PRINT-AgendaDetailed` for selected listing meetings with `id` and `current_committee_id`. There is no server-paging route in the pinned reader. `max_pages`, `max_records`, parser/transfer limits, deadline and cancellation bound this work; the result remains partial and does not claim a complete committee archive.

The discovery record preserves the listing's native `unique`, `numberdate`, `unid` and original row. The selected printable page supplies the meeting title/date, partially rendered text and any `public-file` href strings. The mapping does not infer agenda-item hierarchy or fetch linked files. If a request is denied or the response changes, the operation reports that outcome. It does not change user-agent identity or work around a 403, challenge or access denial.

## Selected detail and caller scope

After importing the meeting record with persistence enabled, `fetch_record` can request its printable agenda. The source identity and current caller scope must match the stored meeting; a caller cannot supply an arbitrary meeting ID to open a new detail route.

BoardDocs public reads need no provider credential. The application still controls its own service authentication and must grant only the operations and namespaces its caller may use. The provider-derived namespace is host-wide (`//go.boarddocs.com`); applications that separate committees within that host should also enforce their configured source URL and committee ID in their own source policy. Keep the same principal/client/tenant context when importing and fetching so the stored record remains in scope. `fetch_record` requires the selected meeting bundle to have been imported into scoped storage first; it then revalidates the stored listing identity before requesting its printable agenda.

## Evidence and limits

The [City Bureau archived listing](capabilities/evidence/boarddocs-public/grand-list-source.json)
adds exact-byte compatibility evidence: 331 native meeting rows and one empty
object placeholder. The parser reports that placeholder separately and retains
the entire original capture. A nonempty row without a native ID still fails.
This third-party archive is not a current vendor read or complete catalog proof.

The route and parsing extracts are pinned under [BoardDocs evidence](capabilities/evidence/boarddocs-public/llama-index-source.json) to LlamaIndex commit `26c7dc3e9846045864cf93ab92cb13bc80a3394e`. `tests/test_boarddocs_public_helpers.py` and `tests/test_boarddocs_public_workflow.py` exercise third-party-source-shaped synthetic responses, guarded POSTs, denials, changed listings, bounds, persistence/reopen, search and ZIP export. This is synthetic source execution; no live BoardDocs acceptance is claimed.

The third-party reader returns one rendered meeting document. The current mapping does not claim catalog completeness, server paging, native search, agenda-item structure, attachment bytes, MIME/visibility guarantees, archived-meeting access or vendor approval. See [engine coverage](ENGINE-COVERAGE.md#roster-map) for the broader status.

## Saved public meeting fragments

`boarddocs-public-meeting-html` accepts saved `BD-GetMeeting` fragments using the
same explicit configured source and committee. It maps `meeting-name`,
`meeting-date` and `meeting-description`. The same-site native clipboard
`goto?open&id=...` identifier must agree with the navigation buttons' `base` IDs;
title/date matching never invents an identity. The two pinned Grand Rapids
fragments retain the exact native identities from the archived listing.

The description is locally searchable and preserved through SQLite/import retry,
reopen and neutral ZIP alongside exact original HTML. Time in a title is retained
as text, without a scheduled instant or time zone. Agenda/minutes controls with
`href="#"` supply no download URL. This saved parser does not add live requests,
map an item hierarchy or establish a vendor write/import contract.
[Archived source and exact hashes](capabilities/evidence/boarddocs-public/grand-detail-source.json)
and [executed scope](verification/boarddocs-meeting-fragment-2026-11-14.json)
are separate from official vendor or current live acceptance. Preserved dev13
artifacts predate this source.
