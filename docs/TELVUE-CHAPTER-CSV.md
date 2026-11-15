# Historical CloudCast chapter CSV preparation

The official CloudCast 4.1.0 manual (June 2014), printed page 14/PDF page 15, defines a headerless chapter CSV with five columns: Start, End, Title, Summary, Description. Start and End use HH:MM:SS; Summary and Description may be empty. Commas require CSV quoting. This is a local preparation contract for that historical product, distinct from Connect recording upload and current deployment qualification.

```python
from quorumrelay import create_engine

result = create_engine().execute("export", {
    "provider_specific": True,
    "source": {"provider": "telvue", "url": "https://connect.telvue.com/",
               "namespace": "telvue:my-organization"},
    "format": "telvue-cloudcast-4.1-chapters-csv",
    "chapters": [{"start": "00:00:20", "end": "00:00:30",
                  "title": "Public comment", "summary": "", "description": ""}],
})
```

The source binds the application's authorized namespace; preparation makes no network request. Provide two-digit hours (00–99), explicit start/end and a nonempty title. No times are derived from meeting dates or item order. The exporter retains explicit row order and CSV-quotes text, including commas, quotes and newlines. It rejects unknown fields, invalid times, reversed ranges, control characters, exceeded record/byte bounds, dates and continuation. Output uses UTF-8 and CRLF rows; the manual does not specify an encoding, so that choice is disclosed rather than asserted as vendor acceptance.

The result provides inline base64 bytes and a SHA-256/length manifest, or a scoped persistent artifact with `stream=True`. Artifact retrieval rechecks caller scope after reopening. Cancellation returns no completed file. IDs, relationships, captures, provenance and attachments belong in neutral interchange bundles; this CSV projects only the five chapter fields.

No upload, recording creation, chapter creation, thumbnail generation, processing or meeting association is performed. Current Connect/CloudCast compatibility remains unverified. The historical UI imports this file through Bulk Add Chapters for a selected existing video; remote acceptance is separate from local preparation. Exact source hash and contract assessment: [source pin](capabilities/evidence/telvue-chapter-csv/source.json). [Official manual](https://telvue.com/wp-content/uploads/2014/06/CloudCastUserManual_v4_1.pdf).

## Connect/CloudCast December 2022 bulk input

`format="telvue-connect-chapters-csv"` additionally accepts nonnegative integer seconds (up to 359999) for start/end, and a missing or empty-string end. The published Add Chapters screenshot explicitly permits seconds or HH:MM:SS, requires start and title, and requires blank positions for all omitted optional fields. Every row still has five fields. Integer and formatted times can be mixed; the exporter preserves their explicit representations without assigning a recording or deriving timestamps. Boolean, fractional, negative and over-bound second values are rejected.

The five-column headerless layout follows the matching explicit 2014 manual contract. The 2022 screenshot names the columns but does not separately state header handling; this derivation is disclosed in the manifest and [source assessment](capabilities/evidence/telvue-chapter-csv/connect-2022-source.json). Current deployment qualification, UTF-8 support and remote acceptance remain unverified. The historical `telvue-cloudcast-4.1-chapters-csv` option continues requiring both formatted times. The scope, bounds, hash manifest, cancellation and persistent artifact behavior above apply to both options.
