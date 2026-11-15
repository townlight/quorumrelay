# iQM2 selected public player

For a supplied native URL such as `https://kentwa.iqm2.com/Citizens/SplitView.aspx?Mode=Video&MeetingID=6049&Format=Agenda`, the default configured discover/fetch path now reads one bounded HTML page. The explicit format `iqm2-public-player-html` also normalizes a saved capture. This supplements the existing meeting-detail and native-search mappings; it does not replace the frozen baseline.

The page must bind the selected meeting through its unique `OutlinePanelInner` control and its same-origin meeting detail URL. The parser decodes only the observed literal JSON argument to `SetupJWPlayer`; it never evaluates JavaScript. Computed calls, additional calls and escaped outer-literal variants are rejected. The native meeting ID is preserved. The title is explicitly an ID label, and no meeting date or time zone is inferred from this shell.

The [declared vendor client](https://kentwa.iqm2.com/Scripts/player.js) uses the first source, derives its MIME from the file extension, and activates only the first subtitle track when that source is MP4 and `hasTranscript` is true. The observed [meeting6049 player](https://kentwa.iqm2.com/Citizens/SplitView.aspx?Mode=Video&MeetingID=6049&Format=Agenda) points at an HLS playlist containing an MP4 path component; it is accurately labeled HLS. Its track list is empty. A synthetic MP4/track case exercises the separately attributed client logic. The client's hardcoded `en` is labeled as player configuration, not verified subtitle language.

All media and subtitle values are metadata locators. Discovery performs no media/track request, manifest traversal or playback. Export preserves the capture, identities, raw source metadata and limits. Local parser bounds of64 sources and64 tracks are defensive limits, not vendor maxima. Shared parser/transfer/deadline/cancellation, URL validation and caller authorization apply. No recording upload, meeting association, staff SOAP operation or complete archive is established.

Exact source hashes and attribution are in [source.json](capabilities/evidence/iqm2-public-player/source.json), with the captured public page under `tests/fixtures/iqm2-player-6049.capture.json` and affected execution in `tests/test_iqm2_player.py`.

## Explicit supplied-caption retrieval

`engine.fetch_captions(source, "6049")` reads the exact configured Video/Agenda player and, when its declared MP4/hasTranscript branch activates a first track, that exact HTTPS URL. Cross-origin tracks require explicit `source.options["download_origins"]`. Requests reject redirects and enforce aggregate transfer, per-response parser, deadline and cancellation bounds. A checkpoint is unsupported; allow two request pages. No track means one request and an explicit partial result without a guessed endpoint.

Only a response labeled `text/vtt` with a recognizable UTF8 WebVTT header is retained. This is supplied source text, not validation/interpretation of all cue syntax: no timing, speakers, translation or content-language inference. The exact original file bytes, including a possible BOM, survive as a separate hashed capture. Source text is searchable after SQLite reopening and retained with both captures in neutral ZIP. The player client's hardcoded `en` still does not establish the content language; named-language selection is unsupported. No media bytes or transcription service is requested.

The active-track network branch is tested synthetically from the pinned vendor client; the actual6049 capture has no supplied track. This extends the earlier metadata-only scope, with execution in `tests/test_iqm2_captions.py` and receipt `docs/verification/iqm2-supplied-captions-2026-11-14.json`.
