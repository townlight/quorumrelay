# SuiteOne supplied event transcripts

The additive `suiteone-public-event-html` reader accepts one configured HTTPS native `/event/?id=` URL. It binds that event to the page's explicit share-event ID and supplied caption declaration, preserving the unique event title, selected player transcript table and literal MP4 metadata. It does not execute scripts, fetch video or infer a meeting date/body/timezone. The stable meeting key matches the original archive record; source derivation descriptions differ by format.

The original archive supplies event2165. Its actual player has959transcript rows and46,059characters of source prose, plus a second display copy that is not combined. Source text, data-time, data-time_end and displayed timestamp strings are retained. These values are not interpreted as verified timing, speakers, motions, votes or attendance. The page supplies no meeting date in this mapping; none is invented from transcript/title text.

Use a configured event URL with `fetch` to preserve the HTML and rendered text without captions. Use `fetch_captions(source, "2165")` for the player and first declared WebVTT. `language="English"` selects the exact source display label; `"en"` is not inferred. Two pages/no checkpoint, exact no-redirect URL/MIME/UTF8/WebVTT framing, per-response parser bytes, aggregate transfer bytes, deadline and cooperative cancellation are enforced. Caption failure retains independent rendered transcript text.

The declared caption returned HTTP200text/vtt104,409bytes. Raw WebVTT/source text and exact capture bytes/hash, citation/provenance and recording relationship survive idempotent import, SQLite reopen, local search and JSON/JSONL/ZIP. Content-language/accuracy, playback and cue interpretation remain unverified. Downloading existing text is not a generation request.

This rendered event is separate from Liberty's unresolved timed *_content.HTML import schema. It supplies no staff upload/create/update/publication contract. See [source manifest](capabilities/evidence/suiteone-public-event/source.json), [245 affected execution checks](verification/suiteone-public-event-2026-11-15.json) and `tests/test_suiteone_player.py`.
