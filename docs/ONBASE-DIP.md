# OnBase linked-document file preparation

The local source supports `onbase-tagged-dip-files` through the existing `export`
operation. It prepares document bytes plus a configured Normal Tagged DIP index;
it does not run OnBase, create an Agenda meeting, attach a document to an Agenda
item, or claim a completed vendor import. This additive source feature is not in
the frozen dev8 wheel.

Hyland's [Foundation26.1 Tagged DIP example](https://docs.hyland.com/r/OnBase/Document-Import-Processor/Foundation-26.1/Document-Import-Processor/Import-Index-File/Import-Index-Parameters/Examples-of-DIP-Format-Process-Settings-and-Field-Order/Tagged-DIP-Example)
and [field-order rules](https://docs.hyland.com/r/OnBase/Document-Import-Processor/Foundation-26.1/Document-Import-Processor/Configuration/Tagged-DIP-Field-Order-Configuration/Field-Order)
describe the layout. Provenance and a pinned vendor example figure are in
[source.json](capabilities/evidence/onbase-dip/source.json). The local HTTP page
captures are SPA bootstrap shells; they are not represented as contract text.
The rendered official references establish the recorded rules.

Use a destination DIP process configured for **Tagged Fields**, **no field
delimiters**, and **New Line** separation. Supply the exact case-sensitive tag
mapping for every Document Type, including any separator colon. The exporter
requires colon-terminated ASCII tags of at most 20 characters. An exclusive Begin
tag starts each document; configured File Type precedes File Name. File Name
alone is documented to resolve relative to the index directory for a Normal DIP
without FTP. No absolute source path is emitted or read.

```json
{
  "provider_specific": true,
  "format": "onbase-tagged-dip-files",
  "source": {"provider": "onbase", "url": "https://city.example.org/OnBaseAgendaOnline"},
  "tags": {
    "begin": "BEGIN:",
    "document_type": "DocTypeName:",
    "file_type": "FileType:",
    "file_name": "FileName:"
  },
  "index_encoding": "ascii",
  "files": [{"file_type": "document", "content_type": "application/pdf"}],
  "documents": [{
    "file_index": 0,
    "filename": "agenda.pdf",
    "document_type": "Meeting Agenda",
    "file_type_number": 42,
    "keywords": [{"tag": "MeetingID:", "keyword_type": "Meeting ID", "value": "123"}]
  }],
  "stream": true
}
```

All destination names/numbers above are **synthetic examples**: `42` is not a
claimed OnBase PDF file-type number. Replace them with the existing destination
configuration. MIME does not establish a numeric OnBase file type; no conversion
or vendor format-compatibility guarantee is inferred. Keyword values must already
follow any destination masking, date/currency, length and multivalue rules. The
exporter rejects control characters, unsafe/colliding filenames, ambiguous tags
and system-keyword replacement/revision/admin mappings. It never silently
sanitizes a destination identity or substitutes unencodable characters.

Save the example as `request.json`. With a trusted service configuration granting
`export` and `export_attachments` for the source namespace, the existing CLI can
stage the real file and stream the artifact:

```powershell
quorumrelay export --request request.json --export-file 0 agenda.pdf --output prepared.zip
```

Use the CLI's actual global configuration options for your deployment as described
in [the developer guide](DEVELOPER-GUIDE.md). Python `Engine.execute("export", ...)`,
HTTP `POST /v1/operations/export` and MCP `export` use the same request. For HTTP/MCP,
upload each authorized file and replace the metadata-only file entry with its
`file_handle`; small callers can supply `content_base64` instead. Stored output
requires `stream:true` and returns `artifact_id`; output access rechecks current
attachment authorization and source namespace. Input scope/hash/expiry checks are
the existing generic-input contract. Export bounds cover records, index/inline
bytes, transfer bytes, cancellation and deadline.

The ZIP contains `index.txt`, document basenames and `manifest.json`. The index
uses CRLF and the caller-selected `ascii`, `cp1252` or `utf-8` encoding; configure
the destination decoding to match. The manifest records exact file hashes,
destination mappings, required DIP configuration and losses. Unknown document
metadata remains in that manifest, never silently becomes an OnBase keyword.
Extract all files before processing: OnBase DIP does not consume this ZIP wrapper.
Keep the full extracted path within Hyland's documented 260-character limit.

Hyland documents a **Test Only** operation that produces a Verification Report
without creating documents or copying/deleting source files. Preparation here
does not run it, commit a batch, set up a DIP process or modify an installation.
Synthetic checks independently assert the emitted vendor layout and exact bytes;
remote processing remains an optional observation under the owner amendment.
Agenda entity writes and native API contracts remain separate implementation work.
