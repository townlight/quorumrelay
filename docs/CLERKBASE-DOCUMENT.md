# ClerkBase public reads and supplied document text

Provider `clerkbase` covers the evidenced ClerkBase/ClerksHQ public interfaces
below. It does not cover the separate OnBoardGOV product. Identification of a
ClerkBase host is not proof that every tenant or vendor product uses these routes.

## Supported public scope

| Read path | Implemented behavior and limits |
| --- | --- |
| South Kingstown tree | Configure `https://clerkshq.com/southkingstown-ri` for `discover`. Follow only current supplied `data-toc-url` controls in that site's public content tree, with bounded nested traversal and continuation. |
| South Kingstown native search | `search` with `native=true`, the same source, and a term or phrase submits the observed sidebar form to `/search`. It validates the displayed expression, result counters, exact document links and supplied next-page controls. |
| Saved tree/search | `clerkbase-public-tree-html` and `clerkbase-search-html` normalize the captured South Kingstown layouts. Documents use the exact supplied URL as identity, explicitly labeled `supplied_url`. |
| Selected document HTML | Configure the exact published `/Content/.../*.htm` or `.html` source URL for `discover` or `fetch`, or normalize a saved `clerkbase-document-html` capture. The pinned Richmond document is separately verified below. |
| Local preservation | Import and persist capture bundles, reopen SQLite, search supplied text and export neutral bundles. Nested-tree parent response evidence survives reopen and ZIP roundtrip. |

Tree continuation revalidates the current root and parent chain before following
a child. Transfer accounting includes revalidation. Failed siblings retain
independently retrieved records and retry state; cancellation and deadlines do
not publish unfinished child records. The specifically evidenced
`SouthKingstown_Docket,AGENDA,` branch retains 17 supplied fragment anchors as
`agenda_item` records. Those anchors are URL identities, with no inferred native
item IDs or parent meeting relationship. Other fragment-tree shapes are rejected.

Native search sends the first term using `AllWords`, or the first phrase using
`Phrase`, then applies exact local matching to the returned title, location,
snippets and explicit title date. It does not retrieve full document bodies or
apply a requested governing-body filter; coverage reports that filter as unknown
and unapplied. Search respects per-response parser limits, page/record bounds,
deadline and cancellation. A changed resumed result capture fails instead of
silently continuing from a stale offset. Supported numeric next-page controls
include pages 10, 19 and 100, through the existing maximum display page 10001
(zero-based request page 10000); page 1, leading zeros and larger values fail.

Inspect status, errors and coverage on every result. Discovery and native search
remain partial and do not claim catalog completeness. A supplied document URL
must be selected explicitly for its content read: there is no automatic
search/tree-to-document sweep, generic `fetch_record(external_id)` or
`fetch_related` mapping for this provider. Linked binary downloads, broader
tenant layouts, structured votes/motions and OnBoardGOV reads are outside this
verified scope.

## Supplied document text

The existing `clerkbase-document-html` format accepts a published ClerkBase meeting
document under its supplied `/Content/.../*.htm` or `.html` citation. Saved
normalization and default configured document discovery now retain static document
body text and paragraphs in the rich record. No new format or upstream API is
introduced. Original compatibility output and URL-path meeting identity remain
unchanged.

Rich `normalized.document_text` and `normalized.document_paragraphs` preserve the
supplied text and paragraph attributes. `record.text` identifies the citation and
exact capture SHA-256. The governing `normalized.body` field is not populated from
document prose. Recommendations, votes, attendance and headings in minutes remain
source text; no structured vote, motion or agenda hierarchy is inferred.

Static extraction excludes script/style/navigation/header/footer/form/noscript
elements and nodes bearing `hidden`. It does not execute CSS or scripts and does
not claim browser-rendered accessibility text. Original HTML remains available in
the exact capture. Rich normalized hashes change when retained text changes;
source identity and unchanged compatibility fields remain stable.

Use the existing normalization/discovery, local search and JSON/JSONL/ZIP neutral
export interfaces. [Four scoped synthetic cases](verification/clerkbase-document-text-2026-11-12.json)
use the original pinned Richmond minutes capture and synthetic configured GET.
They check content preservation, local text matching, neutral roundtrip, source
revision hashing, idempotence, exclusion guards and original-output parity. These
checks do not claim a new live download, provider-native phrase semantics, complete
catalog coverage or upstream mutation. This change is local source work and is
not part of frozen dev8.

## Evidence and writes

Earlier live observations are recorded in the
[tree discovery receipt](verification/clerkbase-tree-engine-discovery-2026-11-12.json),
[native search receipt](verification/clerkbase-native-search-engine-read-2026-11-12.json),
[page-two/tree route receipt](verification/clerkbase-page2-tree-route-probes-2026-11-12.json)
and [nested branch source receipt](capabilities/evidence/clerkbase-nested-tree/source.json).
The November 17 batch uses those saved captures and synthetic transports; it does
not claim a fresh live read or complete live paging run.

No ClerkBase write adapter is registered. A version-matched native mutation,
permission and result/readback contract is not supplied. Draft, publication,
upload and other writes remain deferred according to market demand. This is not
a claim that the vendor lacks an API, and another product's route is not a
substitute. Existing write adapters for other providers are unchanged.

Source trace under `src/civic_data_connectors`: `providers/__init__.py` registers
formats and native search; `providers/discovery.py` owns traversal, parent
validation, checkpointing and configured retrieval; `providers/clerkbase_listing.py`
maps controls and the evidenced fragment branch; `providers/clerkbase_search.py`
owns native form search and result mapping. `compat.read_clerkbase`,
`engine.normalize` and `providers/clerkbase_detail.enrich_bundle` retain the
selected document text. `providers/retrieval.py` delegates configured `fetch` to
discovery; `write_adapters.default_adapters` contains no ClerkBase entry.

Focused batch validation is recorded in `work/batch4-clerkbase.log` and
`work/batch4-clerkbase.xml`: 37 passing tests across `test_clerkbase_search.py`,
`test_clerkbase_listing.py`, `test_clerkbase_recursive_discovery.py` and
`test_clerkbase_detail.py`. The paging defect was reproduced before the minimal
numeric-control fix; `work/batch4-clerkbase-repro.log` preserves that result.
