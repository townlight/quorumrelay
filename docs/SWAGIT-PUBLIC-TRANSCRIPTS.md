# Swagit supplied transcripts and captions

Configure an exact supplied HTTPS `tenant[.new].swagit.com/videos/{nativeID}` URL. `swagit-public-player-html` maps the observed player; omit the input format for configured fetch/discovery. Keep the original provider-derived namespace so listing and selected player retain the same native meeting identity.

The existing Princeton search capture supplies video405841. [Pinned observations](capabilities/evidence/swagit-public-player/source.json) record one exact public player GET and its literal caption URL GET. The player supplies62736characters of rendered transcript text. No JavaScript runs; no video or HLS segments are fetched. The single literal HLS source is metadata, not playable-media acceptance.

The reader verifies a unique heading/player/transcript panel and a Download Transcript link for the exact same native video. It preserves title/date, source heading and the rendered transcript-fragments text as a capture-bound searchable TextSegment. Text retains supplied bracketed timestamps; no cues, timing, speakers, votes, attendance or agenda items are inferred. Unrecognized structures fail closed; empty supplied text stays explicitly empty.

Use `engine.fetch_captions(source, native_id)` for the first supplied track, or `language="en"` to match the explicit source language label. Labels do not verify content language. Set `source.options.download_origins` to the exact caption origin for cross-origin transfer (observed: `https://swagit-video.granicus.com`). At least two pages are needed: player then one declared track. No automatic traversal or polling occurs.

Both requests prohibit redirects, require exact URLs and share aggregate transfer/deadline/cancellation bounds. Per-response parser limits also apply. Caption MIME accepts text/vtt or the actually observed application/octet-stream, always with strict UTF8 decoding and recognizable WEBVTT header. Full cue validation/interpretation is not performed. Caption failure preserves independently retrieved player text with a partial error. Raw player/caption bytes and hashes, source text, identities and relationships survive SQLite/reopen, local search and exact neutral ZIP round trips.

[Executed scope and limitations](verification/swagit-public-player-2026-11-15.json) distinguish observed public research requests from injected engine network tests. No full-catalog, staff API, transcription generation, language/timing correctness or playback claim. Original Sound Search timestamp links stay links; this supplied text is a separate source.
