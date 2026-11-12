# Select historical named-file import

Provider: F05 `civicplus-select`, baseline B07 `civicplus-events-json`.
Evidence observed 2026-11-11; handoff reconciled 2026-11-12 against QuorumRelay
`0.1.0.dev8`, inventory `researched-pass-7`. This is **file preparation for
consultant-mediated import**, not a remote write API or provider acceptance.

## Official contract

Source: [Historical Imports](https://www.civicplus.help/meetings-select/docs/historical-imports)
(article updated 2026-10-29; inventory evidence `select-import`).

- Historical intake accepts **PDF and MP4 only**.
- Each event has at most **five PDFs and one audio/video file**. The article
  names Agenda, Packet, Minutes, Notices and Other in its summary, and Agenda,
  Agenda Packet, Minutes, Notice, Other and Media in its instructions.
- Required filename stem: `MeetingBody_MeetingType_FileType_MM_DD_YYYY`.
  Literal successful examples in the article:
  - `City Council_Regular Meeting_Agenda_12_18_2020`
  - `City Council_Regular Meeting_Agenda Packet_12_18_2020`
  - `City Council_Regular Meeting_Minutes_12_18_2020`
- The article does not specify filename escaping, file-extension rules,
  timezone rules or a historical-FTP file-size ceiling.
- Packets remain single PDFs, **not separate agenda items**.
- MP4 import loses existing bookmarks/timestamps; manual bookmarking is separate.

The article embeds the
[Filename Tester](https://civicplus-lruiz.github.io/Historical-Import-Tester/Tester.html).
Its v3.5.9 source and isolated classifier cases are preserved in:

- `evidence/civicplus-official-filename-tester-v3.5.9.html`, SHA256
  `9f056bcd6fbcd4002c18b302a57b8155acbaa81517f78d82e2a4d209fa4c5c0f`.
- `evidence/civicplus-official-filename-tester-v3.5.9-cases.json`, SHA256
  `e5b1a9c9b8ba1bb10bca63c0d37ff79f5d04dde8b8eab297f2f99676b4d42e07`.

Those paths are relative to this directory. Classifier results are **not**
consultant/vendor acceptance. The classifier uses the full filename, so words
in the body or meeting type can override the intended file type.

## FTP host conflict and access blocker

The same official article names both:

- `ftp://imports.civicclerk.com` in its credentials section.
- `ftp://important.civicclerk.com` in its FileZilla instructions.

The correct host is unresolved. Credentials must come from the customer's
project lead. Files belong in the FTP **main folder**, not meeting/date
subfolders. No connection, probe or transfer was performed or is authorized.
Do not select a host by guessing.

After upload, the customer notifies the Implementation Consultant. The
consultant processes and spot-checks the import, releases it, and helps resolve
errors. The customer then reviews the imported files. No machine endpoint,
task identifier, polling contract or automatic receipt is documented.

## Current local implementation, separate from vendor intake

`src/civic_data_connectors/providers/civicplus_export.py` prepares files through
the shared `export` entry point, format `civicplus-historical-files`. It uses
canonical local tokens `Agenda`, `Agenda Packet`, `Minutes`, `Notice`, `Other`
and `Media`. Ambiguous aliases `Packet`, `Notices` and `Audio/Video` are rejected;
they must not be advertised as accepted exporter inputs.

Tests in `tests/test_civicplus_export.py` exercise named-file preparation,
full-filename classifier conflicts, PDF validation, bounded MP4 box framing,
exact bytes/hashes, duplicate slots, caller bounds, scope and loss reporting.
MP4 framing does not prove codec/playback validity. The ZIP is a **local
QuorumRelay wrapper**, not a documented vendor ZIP importer.

Export preparation does not itemize packets, generate bookmarks, transfer
files, notify a consultant, or prove import/release. The vendor-file mapping
remains `documented_file_import`, implemented locally with provider intake
acceptance `not_run`. It does not satisfy remote `create`, `update` or `upload`.

## Do not mix operational UI limits with historical intake

[Accepted File Formats and Size Restrictions](https://www.civicplus.help/meetings-select/docs/accepted-file-formats-and-size-restrictions)
documents operational UI limits, including 25MB DOC/DOCX, 300MB PDF and media
MP3/MP4 with no stated size ceiling. It also says uploaded PDFs are optimized
and originals are not retained. These do not establish FTP intake limits or
guarantee upstream hash equality. Preserve original local files and distinguish
local export receipts from consultant/vendor acceptance.
