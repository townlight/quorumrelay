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
