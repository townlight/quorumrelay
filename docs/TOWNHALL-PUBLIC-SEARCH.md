# Town Hall Streams public keyword search

The integrated source supports the anonymous archive search form for a configured location, for example `https://www.townhallstreams.com/town.php?id=31`.

```python
from quorumrelay import create_engine

result = create_engine().execute("search", {
    "native": True,
    "source": {
        "provider": "town-hall-streams",
        "url": "https://www.townhallstreams.com/town.php?id=31",
    },
    "query": {"terms": ["budget"], "limit": 20},
    "bounds": {"max_records": 20},
})
```

Both the original baseline and current public page declare a POST form to the same location URL with `search` and `searchbtn=Search`. One exact keyword POST returned 39 archived meeting rows. The existing baseline archive mapper reads their literal event IDs, titles, local dates/start strings and stream URLs. This handler checks that each mapped stream locator stays on the configured origin/location and agrees with the event ID. The event stream URL supplies a precise citation. Unknown time zones remain unknown; recording links are not video bytes or captions.

The provider receives the first term/phrase; exact local matching applies all supplied terms/phrases to obtained metadata. Query/bounds dates apply locally to the supplied calendar date. No server date semantics, document/full-text search, canonical body filter or unreturned agenda items are inferred. Only meeting record types are accepted; unsupported body/type requests fail before network access.

One POST executes per call, with no cookies, account or session mutation. Transfer/parser bytes, deadline and cancellation apply before transport, after transport, after mapping and after local search. A local offset checkpoint is tied to source/query/caller scope and the exact response hash. Revised responses fail continuation and require an explicit restart. The provider's archive completeness, ranking and server pagination are unverified; all native results remain partial after local offset exhaustion. Unreadable/empty captures fail rather than establish a complete empty result.

Exact response bytes, capture hash, native IDs, recording relationships, citations and POST request fields survive SQLite persistence/reopening and JSON/JSONL/ZIP exchange. The existing `town-hall-streams-html` saved format and all original compatibility inputs remain supported; this adds a native search handler, not a replacement baseline reader.

Source URLs and immutable hashes are in [the source assessment](capabilities/evidence/townhall-public-search/source.json). Execution scope is recorded in [the receipt](verification/townhall-native-search-2026-11-15.json). No vendor write/import, browser execution or release is involved.
