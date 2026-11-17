# Peak public archive search

The original Douglas County Peak capture declares a public GET form targeting `ViewSearchResults.php`, with a literal view ID, five record-type checkboxes, keywords and an archive/upcoming scope. QuorumRelay implements the documented **Available Archives** selection and preserves meeting groups and their rendered search excerpts.

```python
result = engine.execute("search", {
    "source": {
        "provider": "peak",
        "url": "https://douglascountynv.granicus.com/ViewPublisher.php?view_id=1",
    },
    "native": True,
    "query": {"terms": ["budget"], "limit": 20},
    "bounds": {"max_records": 20, "max_pages": 1},
})
```

The first term or phrase supplies provider candidates; exact local matching applies all requested expressions to returned metadata and rendered excerpts. Date filters remain local. No full-document search, provider matching semantics, body filter or catalog completeness is inferred. Unsupported body or item-record filters fail before a request.

One provider page is fetched per call. Use `result.coverage["checkpoint"]` in the next call's bounds, keeping the source/query/caller scope unchanged. Within-page continuation verifies the exact captured page hash before advancing. Native clip IDs already seen across pages are excluded. Parser and transfer byte limits, cancellation and deadlines apply through final mapping and search.

The bounded live source observation returned 150 native clip groups on page 1 and declared five pages. The exact page-2 request returned HTTP 200 with an empty result table and no page declaration. **That response is rejected as an unverifiable continuation.** It does not establish that the search or archive is exhausted. All successful search responses remain partial, even at a declared last page. No automatic repeated retry occurs.

Each mapped group requires consistent same-origin/view native clip IDs from supplied agenda/minutes/player locators. IDs match the existing Peak captured-listing namespace; names and dates are not joined to invent identity. Group excerpts stay with the containing meeting. Subitems lacking native item IDs do not become independent agenda-item records. Documents and recordings remain supplied locators; no file bytes or playable media are inferred.

The result bundle retains original HTML bytes/hash, retrieval URL, request context, native identities and original group fields. Import it with `import_bundle` and `persist=true` for application-owned storage. SQLite reopening, local search and JSON/JSONL/ZIP exports retain the captured data. Saved search HTML also has an explicit `peak-public-search-html` normalize parser with a configured ViewPublisher source.

Exact vendor responses and the declared pagination script are pinned under `capabilities/evidence/peak-public-search/`. The source observation and synthetic engine tests are separate evidence; no staff API, write, import or publication support is claimed.
