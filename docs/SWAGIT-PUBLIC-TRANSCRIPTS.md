# Swagit supplied transcripts and captions

The `swagit` reader also retains configured archive/listing reads and bounded
native search. `swagit-listing-html` maps recognized dated `/videos/{nativeID}`
rows, their supplied same-video agenda links and Sound Search timestamp URLs.
Timestamp URLs remain links; no transcript is inferred from them. The original
saved compatibility listing format remains supported.

Native search requires `native: true`, an HTTPS `tenant.new.swagit.com/views/{id}/`
source and a nonempty term or phrase. It submits the first expression to the
observed public `/videos/search` GET form, follows validated supplied `rel=next`
links and applies exact local title/date matching to the candidates. It rejects
unverified body filters. Checkpoints bind caller scope, current grant, query and
mid-page capture hash. Provider query semantics and full-catalog coverage remain
unverified. The [retained two-page receipt](verification/swagit-native-search-page2-2026-11-12.json)
records ten distinct native-ID rows per page; no subsequent page was fetched.

Configure an exact supplied HTTPS `tenant[.new].swagit.com/videos/{nativeID}` URL. `swagit-public-player-html` maps the observed player; omit the input format for configured fetch/discovery. Keep the original provider-derived namespace so listing and selected player retain the same native meeting identity.

The existing Princeton search capture supplies video405841. [Pinned observations](capabilities/evidence/swagit-public-player/source.json) record one exact public player GET and its literal caption URL GET. The player supplies62736characters of rendered transcript text. No JavaScript runs; no video or HLS segments are fetched. The single literal HLS source is metadata, not playable-media acceptance.

The reader verifies a unique heading/player/transcript panel and a Download Transcript link for the exact same native video. It preserves title/date, source heading and the rendered transcript-fragments text as a capture-bound searchable TextSegment. Text retains supplied bracketed timestamps; no cues, timing, speakers, votes, attendance or agenda items are inferred. Unrecognized structures fail closed; empty supplied text stays explicitly empty.

Use `engine.fetch_captions(source, native_id)` for the first supplied track, or `language="en"` to match the explicit source language label. Labels do not verify content language. Set `source.options.download_origins` to the exact caption origin for cross-origin transfer (observed: `https://swagit-video.granicus.com`). At least two pages are needed: player then one declared track. No automatic traversal or polling occurs.

Both requests prohibit redirects, require exact URLs and share aggregate transfer/deadline/cancellation bounds. Per-response parser limits also apply. Caption MIME accepts text/vtt or the actually observed application/octet-stream, always with strict UTF8 decoding and recognizable WEBVTT header. Full cue validation/interpretation is not performed. Caption failure preserves independently retrieved player text with a partial error. Raw player/caption bytes and hashes, source text, identities and relationships survive SQLite/reopen, local search and exact neutral ZIP round trips.

[Executed scope and limitations](verification/swagit-public-player-2026-11-15.json) distinguish observed public research requests from injected engine network tests. No full-catalog, staff API, transcription generation, language/timing correctness or playback claim. Original Sound Search timestamp links stay links; this supplied text is a separate source.

Generic `fetch_attachment` can select a supplied document or recording locator
from its original capture or scoped stored record. Shared transfer and configured
download-origin safeguards apply. A returned page or HLS manifest does not prove
binary agenda retrieval or playable media; those are outside the current accepted
read claims.

Administrative create/update/upload operations are deferred per market demand
until a usable product-matched machine contract is available. No built-in Swagit
write adapter is registered; existing implementation and capability statuses are
preserved. No upstream mutation is implied by local bundle import/export.

On November 16, 2026 the unchanged Swagit implementation passed 32 focused tests
covering listing, native search, selected player/caption reads and configured
saved-response fetch, including the existing persistence/reopen/search/ZIP and
boundary cases. Durable outputs are `work/batch2-swagit.log` and
`work/batch2-swagit.xml`. This focused check used injected transports, made no live
vendor requests and adds no installed or hosted-CI certification.
