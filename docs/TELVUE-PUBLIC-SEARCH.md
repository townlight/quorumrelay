# TelVue public video search

The integrated source supports anonymous player-wide search from an explicitly configured `/player/{key}/videos` source. Playlist sources are rejected for this operation: the public form searches the player, and its results do not establish playlist membership.

```python
from quorumrelay import create_engine

result = create_engine().execute("search", {
    "native": True,
    "source": {
        "provider": "telvue",
        "url": "https://videoplayer.telvue.com/player/4jeRlBTetCoFJdyT5ssIvBrB9VUvRN0M/videos",
    },
    "query": {"terms": ["council"], "limit": 20},
    "bounds": {"max_records": 20},
})
```

The original saved playlist declares a public GET form to the same player's `/videos/search`, with `showtabssearch=true`, `fullscreen=false` and `search`. One exact declared-form GET returned 43 native media candidates with a declared total of 43. The deployed player client confirms that separate per-video metadata requests provide video/caption/chapter match counts; those counts and caption/chapter text are not retrieved by this path. The unrelated Connect CMS client is not its contract.

The mapper returns `recording` records with the literal `data-video-id`, supplied title, rendered summary and duration display. A date at the end of a supplied title is parsed using the original TelVue date convention, explicitly marked `calendar_date_in_supplied_title`. A missing/unreadable date remains unknown; date-filtered local search reports unknown dates. No offset, time zone or scheduled instant is inferred.

Each result locator must match the configured player, native media ID and exact observed search-link fields. During native search, every locator must also echo the exact requested first expression; mismatched cached responses fail before results are published. It remains a public search locator, not video bytes, an inferred canonical media URL or a downloaded caption. The links retain the user's search terms, so they are preserved in record citations and recording relationships, outside searchable normalized metadata. Otherwise the URL itself would falsely make every candidate match its query. Original link fields and exact HTML remain in the capture/original record.

The provider receives the first term/phrase. Exact local matching applies all requested expressions to supplied metadata/summary text. The real capture retains all 43 candidates but produces 22 exact local `council` hits; the other candidates do not supply matching metadata. Search results may have matched unrequested caption/chapter content; that is not converted into a local exact hit. Persisting/reopening retains the same 22-hit behavior.

One GET runs per call. Local offset continuation is bound to source/query/caller scope and the exact response hash; changes fail and require an explicit restart. The capture's declared total and any `provider_remaining_unretrieved` are reported. The generic player client has a load-more implementation using sort selectors and offset; those selectors are absent from this captured search page, so its applicability to search continuation is unverified. No server paging route/ordering or complete provider catalog is inferred. A local checkpoint ending does not establish provider exhaustion, and all native results remain partial. Empty or unrecognized containers fail rather than prove a complete empty catalog.

Bounds cover parser/transfer bytes, cancellation and deadline before transport, after transport/mapping and after local search. Body filtering and meeting/document record-type requests are rejected. Exact capture bytes, IDs, citations, recording relationships, summary provenance and request context survive SQLite retry/reopen and JSON/JSONL/ZIP interchange. Explicit saved format `telvue-public-search-html` uses the same player-wide source. Existing playlist/media/caption readers and original formats remain separate.

See [source URLs and hashes](capabilities/evidence/telvue-public-search/source.json) and the [execution receipt](verification/telvue-native-search-2026-11-15.json). No scripts, account, media generation, upload, write or release are involved.
