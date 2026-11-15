# Town Hall Streams supplied transcript display

`fetch_captions` can read the transcript display declared in an exact configured
Town Hall Streams event player. It retrieves the player, validates its native
location/event binding and full-transcript GET declaration, then reads that
destination once. Both requests disable redirects and share parser, transfer
and deadline bounds. A fresh in-memory cookie jar carries the anonymous player session to the same-origin transcript GET. Cookie values are not captured or stored. No login, generation request or polling job is started.

```python
from quorumrelay import Source, create_engine

source = Source(
    "town-hall-streams",
    "https://townhallstreams.com/stream.php?location_id=72&id=74003",
    input_format="town-hall-streams-event-html",
)
result = create_engine().fetch_captions(source, "74003")
```

The event ID must match the configured player. Both observed public hostnames,
`townhallstreams.com` and `www.townhallstreams.com`, are supported without changing
the original location/event identity. A location archive URL alone does not
supply the selected player context. Language selection and checkpoints are
rejected; the current contract has neither. The request needs a page budget of
at least two, for the player and transcript display.

The vendor client inserts the response HTML into its transcript display. The
connector retains the exact response capture and extracts static fragment text
for search, excluding scripts, hidden nodes and embedded content. It does not
execute JavaScript or CSS. Full HTML documents, forms and ambiguous sentinel
responses are retained with an explicit failure rather than indexed as
transcripts. Source language, timing and speakers remain unverified; no page or
time anchors are invented. The result stays partial.

For an empty response, the meeting remains available and its transcript status
is `supplied_full_response_empty`. For available static text, the record contains
`transcript_text` and a cited text segment with the separate transcript capture
hash. A failed transcript request retains the successfully retrieved meeting and
reports an error. Cancellation returns cancelled, with no successful transcript
claim. The rich bundle supports ordinary import, local search and neutral ZIP.

Actual checks of existing source events74003 and77576 returned HTTP200 with
empty transcript bodies. Those initial requests were sessionless; a fresh anonymous PHP-session Hollis read also returned an empty body. Nonempty HTML text handling is **synthetic execution**
against the declared display contract. It does not establish nonempty live
transcripts, full-event completeness, diarization, timing accuracy or playback.
The existing HLS playlist path remains separate from this transcript read.

[Source observations and exact hashes](capabilities/evidence/townhall-transcripts/source.json)
and [execution receipt](verification/townhall-supplied-transcripts-2026-11-14.json)
keep those evidence levels separate.
