# CivicPlus Agenda Center supported reader

This provider is `civicplus-agenda-center`, distinct from Select/CivicClerk.
Its supported reads retain the existing configured listing and captured public
controls. Administrative writes and external imports are deferred per market
demand until a product-matched machine contract is available.

## Supported operations

- Normalize saved `agenda-center-html` listing responses, preserving captured
  HTML and native meeting IDs. The parser maps titled agenda links with a supplied
  `ViewFile/{kind}/_MMddyyyy-ID` path, calendar dates and document URLs in the
  same table row. It does not synthesize agenda items or infer a meeting body.
- Fetch a configured listing, or discover a configured HTTPS `/AgendaCenter`
  root and the year/category controls actually published there. Discovery applies
  date bounds, limits and resumable checkpoints. Resumed controls are checked
  against the current root; caller-invented categories are rejected.
- Search the public year/category keyword route using `native: true`, a nonempty
  explicit date range and at least one term or phrase. The adapter sends the
  first expression to the published `UpdateCategoryList` read form and applies
  exact local matching to mapped meeting title/date metadata. Further expressions
  are local filters. Unknown requested meeting bodies are explicitly retained.
- Fetch a document URL selected from its original capture or scoped stored
  record through `fetch_attachment`. The generic transfer retains exact returned
  bytes, content type and SHA-256, with `text_availability: not_extracted`.
  Download origins remain subject to the shared configured-origin policy.
- Use the existing shared local import, persistence, search and export operations
  for the resulting bundles. This does not add native upstream write support.

For example, bounded native search uses:

```json
{
  "source": {
    "provider": "civicplus-agenda-center",
    "url": "https://www.effinghamcounty.org/AgendaCenter"
  },
  "native": true,
  "query": {"terms": ["Commission"]},
  "bounds": {
    "date_from": "2025-01-01",
    "date_to": "2025-12-31",
    "max_pages": 1,
    "max_records": 3
  }
}
```

Return the response's `coverage.checkpoint` in the next request's bounds while
retaining its source, query and caller scope. Search continuation binds mapped
provider values rather than generated DOM row IDs. A changed mapped result set
requires restarting; harmless DOM noise retains the original capture separately.

## Evidence and limits

The retained [2024 year/category receipt](verification/civicplus-agenda-center-year-2024-2026-11-12.json)
records 35 Effingham rows. The [native-search receipt](verification/civicplus-agenda-center-native-search-2026-11-12.json)
records two bounded pages of three hits each. The [ViewFile receipt](verification/agendacenter-viewfile-html-2026-11-12.json)
records an HTML response of 2,481 bytes; that result establishes HTML retrieval,
not PDF or binary-document acceptance.

Discovery and native search remain partial: no complete catalog, universal tenant
coverage, PreviousVersions traversal or full-document text search is claimed.
Missing rows or the observed HTTP-200 application-error page fail explicitly;
an error is not a verified empty search result. The historic Chino extraction
failure and other unresolved layout/tenant coverage remain limitations.

On November 16, the unchanged registered implementation passed nine focused
tests: configured saved-response fetch, public year traversal/date filtering,
forged-control rejection, scoped native search, application-error handling,
small continuation pages, changed-row rejection and harmless-DOM continuation.
Logs and JUnit XML are in `work/batch2-agendacenter.log` and
`work/batch2-agendacenter.xml`. Existing broader unchanged-reader evidence is
reused; this check made no live vendor requests and provides no installed or
hosted-CI certification.

The built-in write registry contains no Agenda Center adapter. A local authorized
`plan_write` probe with durable storage returns `failed` with error code
`mapping_unverified` before any adapter execution. This describes the current
runtime response precisely; it does not establish that CivicPlus itself cannot
write. No remote writes, account creation or vendor contact occurred.
