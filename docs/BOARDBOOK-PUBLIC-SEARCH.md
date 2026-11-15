# BoardBook public search

The integrated source supports anonymous BoardBook search for an explicitly configured public organization, such as `https://meetings.boardbook.org/Public/Organization/3307`. No account, browser execution or staff operation is involved.

```python
from quorumrelay import create_engine

result = create_engine().execute("search", {
    "native": True,
    "source": {
        "provider": "boardbook",
        "url": "https://meetings.boardbook.org/Public/Organization/3307",
    },
    "query": {"terms": ["budget"], "limit": 20},
    "bounds": {"max_records": 20},
})
```

The saved baseline organization links to `/Search/Index/3307`. Its current anonymous page declares a GET form with `q`; the deployed `Search.6.js` serializes that form. The exact GET with `q=budget` returned 42 rendered entries. The [pinned source assessment](capabilities/evidence/boardbook-public-search/source.json) identifies the exact bytes, URLs and hashes.

Each normalized record has type `search_result`. Its identity is the supplied search index plus native locator ID, for example `sparqmeetingsagendaitemtexts:3628623`. The observed indexes distinguish agenda items, item text, item actions and documents. These identifiers are not promoted to canonical meeting/item/document identities or inferred parent relationships. Displayed meeting/item labels remain part of the title/excerpt, without inferring IDs, dates, vote tallies or a time zone. Canonical parent identity remains unavailable.

The citation preserves the exact index and organization in the supplied `GoToResult` route. Navigation `returnUrl` is removed from the durable citation and is never followed. A search locator is not a downloaded attachment or meeting-detail capture. Original rendered entries, exact HTML, capture hashes and supplied excerpt text remain portable through storage and JSON/JSONL/ZIP export. Excerpts are explicitly partial and cite the native locator with capture-hash provenance.

The provider receives the first supplied term or phrase. All terms/phrases are then matched locally against obtained fields and excerpts. The captured response has 42 provider candidates and 37 exact local `budget` hits: five document candidates omit the term from their rendered fields. Their unread document bytes are not claimed as searched. Full-document search semantics and complete provider coverage are unverified.

One GET runs per call. `max_records` and query limit bound the candidate slice. The checkpoint resumes a local offset in the exact same hash-bound response and is tied to source, query and caller scope. A changed response fails continuation and requires an explicit restart. There is no inferred server pagination or exhaustion; every native search result remains partial, even after the local slice is exhausted. Empty/unrecognized containers fail rather than establish an empty complete catalog.

Only `search_result` record-type filtering is accepted for this path. Body and date filters are rejected because canonical body/date semantics have not been established for all four indexes. Transfer/parser byte limits, cancellation and deadline checks apply before retrieval, after transport, after mapping and after local search. Cross-organization, duplicate-parameter and unknown-index locators fail. Saved responses use explicit input format `boardbook-public-search-html` with the same configured organization source.

This adds no vendor write, upload, remote import, account requirement or release claim. Existing BoardBook organization/agenda/minutes readers remain separate.
