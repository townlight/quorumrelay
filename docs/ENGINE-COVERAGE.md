# QuorumRelay core coverage and remaining gaps

Current source candidate: `0.1.0.dev3`, schema `2.0.0`. This is a source-path and acceptance map, not a completion or independent-review claim. It preserves all 31 families, 34 baseline inputs and every supported outbound obligation. The capability inventory remains the per-operation research authority; this map describes the current engine and gaps revealed by inspecting its actual paths.

## Shared implemented behavior

All 34 pinned baseline captures retain the original compatibility-reader contract, IDs/namespaces and capture hashes. All 31 imported provider families have deterministic metadata/supplied-text search checks. Neutral JSON/JSONL/ZIP round trips, hash manifests, CSV/iCalendar projection losses, optional scoped SQLite/state extensions, import preview/idempotence, text extraction and exact-plan write coordination are implemented. These generic checks do not prove complete live source text or every vendor operation.

Runtime `providers` reports seven additive parser hooks separately from the 34 baseline formats. Identity, capture hash, normalized hash, source revision and consumer destination identity remain distinct. Configured attachment downloads use captured relationships, current policy, exact origins and separate transfer limits.

## Roster map

Every row supports baseline parsing, local search over actual captured fields, and neutral export. “Configured capture GET” means only the configured page/feed/response is retrieved; it does not establish automatic source catalog discovery, full pagination or all detail retrieval. “Not implemented” below is an engine status, not a declaration that the vendor lacks a feature.

| Provider | Baseline inputs | Automatic/current read path | Native search | Native writes | Remaining limit |
|---|---:|---|---|---|---|
| legistar | 1 | Date-bounded Events keyset listing; one Event expansion/detail | EventBodyName only | 8 entities /16 create-update routes | Representative public listing/detail/body-query checked; per-item Votes/RollCalls GET is not a general read adapter; live writes blocked. |
| primegov | 2 | Upcoming + yearly archive portal listing | Not implemented | Research/access unresolved | Listing mechanics reused; per-tenant paging/filter completeness and standalone detail paths remain unresolved. |
| granicus | 2 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| novusagenda | 1 | Saved meeting export fallback | Not implemented | Research/access unresolved | No verified automatic listing/detail mapping implemented. |
| civicplus-select | 1 | Tenant Events collection with guarded nextLink | Not implemented | Research/access unresolved | Observed native listing; account/tenant differences, broader text search and outbound contract remain unresolved. |
| civicplus-agenda-center | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| municode-meetings | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| boardbook | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| escribe | 1 | Explicit date-range Calendar POST | Not implemented | Research/access unresolved | Existing Brief mechanics reused; additional paging/detail contracts and account outbound access unresolved. |
| simbli | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| civicweb | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| iqm2 | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| swagit | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| suiteone-media | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| peak | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| utah-public-notice | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| destiny-agendaquick | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| town-hall-streams | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| telvue | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| champ | 1 | Fixed public tenant event JSON endpoint, same legacy identity | Not implemented | Research/access unresolved | Two public details checked; no event catalog/listing or complete paging claim. |
| onbase | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| laserfiche-weblink | 1 | Dated-folder traversal with injected guarded BrowserSession; configured capture fallback | Not implemented | Repository document/media operations | No concrete safe browser/session installed. Repository API child listing has no engine discovery mapping. API OAuth access and WebLink-to-repository authorization mapping unresolved. |
| towncloud | 2 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| digital-towpath | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| clerkbase | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| first-party | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| wistia | 1 | Authenticated media offset listing, Media detail, supplied caption list/language reads | Documented account /modern/search, bounded media/excerpts | Media metadata/upload/import, captions/edits, tags | Read/search/write tests use official shapes and synthetic transports; authorized account credentials and live acceptance missing. No generated diarization/transcription requested. |
| boardable | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| gworks | 1 | Configured capture GET using its existing parser | Not implemented | Research/access unresolved | Complete catalog/pagination, provider detail/search and outbound contracts/tenant access remain unverified. |
| boarddocs | 1 | Saved numbered agenda PDF; configured direct public PDF retrieval | Not implemented | Research/access unresolved | Encrypted/interactive portal/listing path not implemented; no false unsupported-vendor claim. |
| tyler-meeting-manager | 1 | Explicit same-host calendar_api_base, fixed date-range POST; saved fallback | Not implemented | Research/access unresolved | Live Ector response empty; nonempty API rows/paging/full coverage not established. Configured API base is tenant evidence, never guessed. |

## Known executable gaps with a documented route

- **Legistar related reads:** General fetch exposes one Event with expanded items/notes/attachment metadata. Separate public Votes/RollCalls GET routes are documented and used by write readback/reconciliation, but there is no standalone normalized read adapter for their collection/detail records. The existing event item preserves supplied action/tally fields; it does not claim a complete per-person vote dataset.
- **Laserfiche Repository discovery:** Official account API entry-child listing is distinct from observed public WebLink folder traversal. No Repository discovery adapter with its complete field/paging/checkpoint mapping is implemented. This is an implementation gap as well as an OAuth/account acceptance dependency. A write adapter or injected WebLink fixture does not close it.
- **Provider-specific file exports:** No built-in provider-file export adapter is registered. The engine rejects `provider_specific=true` when no connector hook supplies it; it cannot silently substitute a neutral bundle. An explicitly documented usable vendor input format still needs its exact mapping and acceptance; a vendor offering only file download does not establish an import contract.

## Research and environment dependencies

- Generic configured-page paths still need per-provider complete listing/detail/paging evidence, not more repetitions of the same baseline parser test. NovusAGENDA and the BoardDocs interactive portal remain unresolved automatic routes; Tyler has an observed explicit calendar POST but no nonempty live response/paging proof.
- Native search is implemented for Legistar body metadata and Wistia media/transcript excerpts only. Other verified usable provider search contracts require investigation and implementation; unknown routes cannot be relabeled unsupported merely to close the roster.
- Every implemented remote write still needs authorized test credentials/permissions, any tenant-specific required enum values, actual readback and a receipt. No public municipality was mutated. Official docs and synthetic wire/lifecycle checks do not establish those outcomes.
- No concrete live BrowserSession satisfies the required DNS/socket/redirect/subresource safeguards for WebLink. An ordinary browser or a mock declaring guarded=True is insufficient. Saved WebLink captures and fixture traversal remain usable without claiming live full discovery.
- Wistia authenticated reads/search/captions need an account test token. Caption-only access may produce an empty visible track list under limited delegation; that is reported as partial visibility, not proof the media has no captions.
- Reference-product persistence, roles, large document jobs, migrations, actual Windows installed workflows, signed installers where delivered, published packages/docs and post-delivery checks are owning integration/delivery outcomes. Passing core tests or a private source commit does not close them.

## Evidence boundaries

`tests/test_baseline.py`, `test_baseline_search.py`, provider/discovery/detail/native-search tests, storage/import/interchange/write tests and the original matrix cover deterministic behavior. `docs/verification/legistar-detail-2026-11-11.json`, `champ-detail-2026-11-11.json` and `native-search-tyler-2026-11-11.json` preserve bounded public-read outcomes. Historical development wheels and their receipts remain immutable snapshots; a coherent dev3 artifact requires a fresh root-owned build after source readiness.
