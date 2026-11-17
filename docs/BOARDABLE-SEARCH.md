# Boardable public search

Current local source maps the GET declared by the vendor public site's search
component and API helper. The [pinned source](capabilities/evidence/boardable-public-search/source.json)
and [synthetic execution](verification/boardable-search-interchange-2026-11-14.json)
separate the request contract from live observations. Both selected anonymous
requests timed out; no live search success or catalog acceptance is claimed.

```python
result = engine.execute("search", {
    "source": {
        "provider": "boardable",
        "url": "https://site.boardable.com/ventura-county-community-college-district/meetings",
    },
    "native": True,
    "query": {"terms": ["budget"], "phrases": ["budget review"]},
})
```

The exact configured public source resolves its SiteId from the matched landing
state. GET `/api/public-sites/search` sends the first expression as `query`,
`type=meetings`, and the vendor-declared `year`/`month` filters when both requested
date bounds fit one year/month. The response supplies candidates; local Unicode
word/phrase matching applies all requested terms and phrases to the title and
provided agenda/minutes/attachment context excerpts. Those excerpts do not
establish full-document coverage. Body filters, other record types and invented
paging/checkpoints are rejected.

Import the discovery listing captures into the same principal/client/tenant scope
before searching if normalized records and ordinary `hits` are needed. Only
SHA-verified original listing bytes from that exact configured source bind a
search result URL/slug to its existing numeric meeting ID. Ambiguous, tampered,
other-source and other-scope captures cannot supply identities. Search uses the
listing's supplied date with explicit capture provenance; it does not infer a
numeric ID or date from the search renderer.

Every selected raw result remains in `data.candidates`. Results without a verified
numeric-ID binding produce an explicit coverage failure and no invented record
or slug identity. `data.bundle` retains the exact search response, unknown fields,
and required listing identity captures; normalized known records retain their
original IDs. Use the complete neutral bundle for persistence/export. A raw search
response alone has no registered parser that guesses missing identity links.

Results remain partial. The vendor client declares no paging, total, terminal,
matching/ranking or full-text completeness contract. Bounds cap received bytes,
selected candidates and time; truncation is explicit and has no fabricated cursor.
Failed HTTP/MIME/origin/shape/timeouts are failed results, never successful empty
search. Cancellation is checked before and after reads. No attachment URL is
fetched by search, and policies/document administration are outside this mapping.

Twenty-four synthetic cases cover the declared fields, exact IDs, missing or
ambiguous identity bindings, failures, bounds, cancellation and SQLite/reopen/ZIP
preservation. The workflow exposed a shared-capture ZIP alias defect: export now
snapshots all original capture locations and inline flags before removing inline
bytes. Logical manifest integrity and single-blob deduplication remain enforced.
These source changes are later than preserved dev13 packages; no package or
release was rebuilt.
