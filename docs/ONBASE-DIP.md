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

Hyland separately documents a [Create or Update Agenda Item from Document workflow](https://docs.hyland.com/r/OnBase/Agenda/Foundation-26.1/Agenda/Configuration/System-Interaction/Workflow/General-Workflow-Actions/Create-or-Update-Agenda-Item-From-Document). Its destination meeting/item types and any target meeting must already exist; a target meeting uses the destination numeric ID. Unity-form field mappings, ownership group and supporting-document relationships are destination configuration. A DIP keyword named `MeetingID:` does not by itself establish that workflow or associate an agenda item. The official workflow also warns that using the same Document Type to initialize the workflow and create its agenda item can create an infinite loop. This exporter neither installs nor invokes that workflow. Exact source captures and version limits are in [the contract assessment](capabilities/evidence/contract-followup-2026-11-14/source.json).
# Agenda entity integration is separate from DIP

Hyland's Foundation 25.1 Enterprise Integration Server documentation supplies a
more specific Agenda entity integration lead. The adapter example identifies
`Entity/agendaandminutes/25957/Update`; **25957 is an example configured entity
type, not a universal Agenda type ID**.

| Documented operation | Request outline | Documented response |
| --- | --- | --- |
| `CreateEntityType_<type ID>` | `EntityCreateData` → `Fields` | Created `entityItemID` |
| `ReadEntityType_<type ID>` | `EntityReadData` → `entityItemID` | Configured entity fields and primary key fields, if any |
| `UpdateEntityType_<type ID>` | `EntityUpdateData` → `entityItemID`, `Fields` | Complete response schema not specified on this overview page |

The adapter connects to a configured Application Server/data source using an
OnBase service account, enumerates configured objects and generates the selected
object's WSDL/schema. Canonical schemas instead refer to configured Web Services
Publishing objects. The documentation therefore establishes a **destination
schema dependency for this EIS path**: a shareable generated WSDL/XSD and matching
Agenda field/type mapping, endpoint/binding and readback/error contract are needed
to implement it. No live credentials or mutation is needed for synthetic tests.

The published outlines do not provide XML namespaces, complete typed Agenda
fields, a fixed HTTP SOAP action/envelope or a document-association request.
Generating those from display labels would invent a contract. This mapping
assessment adds no EIS adapter or new export format. It does not establish that
all alternative Agenda APIs are private. Exact public topic captures and scoped
findings are pinned in
[the EIS evidence](capabilities/evidence/onbase-eis-entity/source.json).
