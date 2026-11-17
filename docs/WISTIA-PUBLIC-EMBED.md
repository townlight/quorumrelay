# Public Wistia metadata and supplied captions

Use an explicit source with provider `wistia`, format
`wistia-public-embed-html` and an exact HTTPS URL such as
`https://fast.wistia.net/embed/iframe/ylfk2zpd7f`. The same iframe path on
fast.wistia.com is accepted. Queries, alternate player paths and source options
are outside this selected mapping. Existing authenticated account API reads and
writes are separate.

```python
from quorumrelay import Source, create_engine

source = Source("wistia", "https://fast.wistia.net/embed/iframe/ylfk2zpd7f",
                input_format="wistia-public-embed-html")
result = create_engine().fetch(source)
```

The source-declared player supplies one literal JSON argument to `W.iframeInit`.
The parser reads that JSON without executing JavaScript or fetching player assets.
It requires the native hashedId to match the exact configured iframe. Dynamic
expressions, duplicate initializers/keys, mismatched identity and ambiguous
caption languages fail instead of producing an empty successful result.

Results retain the original media fields, asset references and source HTML bytes.
Each supplied captions entry becomes a `transcript` record linked to the native
recording, with a stable composite of media ID and literal language key. Text is
searchable and cited to the iframe/capture hash. The source language key is not
silently replaced by another language-code system. Embedded plain text does not
supply cue timings, so no timestamps are invented. Missing, explicitly empty and
nonempty captions remain distinguishable in media metadata.

`fetch` returns a partial selected-source result, with no catalog, meeting date,
playback or binary download claim. It requires the complete media/caption set to
fit record and parser/transfer limits. Date/body/checkpoint selectors are rejected
for this detail path. An optional external_id must equal the iframe's media ID;
caption_language may be absent or `*` for all supplied tracks. No account token is
sent. The exact URL is fetched without redirects and checked again after response
and parsing for cancellation/deadline completion.

Explicit `discover` can traverse this one static source and continue within its
record/caption set using the shared bounded checkpoint contract. Finishing with a
null checkpoint still reports partial coverage because a single iframe cannot
establish the upstream catalog. Saved normalization and JSON/JSONL/ZIP preserve
captured bytes, unknown native fields, identities, relationships and supplied text.
The shared embed-origin namespace is not equated to an authenticated account's
identity.

The actual captured layout came from the official gWorks builder page's declared
Wistia iframe: 11,499 bytes, native media ylfk2zpd7f, one eng caption containing
1,366 characters. The vendor's demonstration describes staff save/publish steps;
it does not supply a gWorks API or file-import contract. Its separately declared
PDF is a raster screenshot of the published UI. Those research findings remain
separate from this Wistia read implementation. See the source records in
`capabilities/evidence/gworks-current-builder/source.json` and the execution
receipt `verification/wistia-public-embed-2026-11-15.json`.
