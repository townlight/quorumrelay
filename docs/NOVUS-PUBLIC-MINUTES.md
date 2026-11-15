# Novus supplied Minutes documents

Use an explicitly supplied HTTPS `*.novusagenda.com/agendapublic/MeetingView.aspx?MeetingID=...&MinutesMeetingID=...&doctype=Minutes` URL with the existing `novus-public-listing-html` format, or omit the input format for configured fetch/discovery. Both IDs must be positive native decimal IDs. Duplicate/additional query members and fragments fail; redirects are disabled and response URL/MIME/transfer/parser bounds are checked.

The [official groundwater district archive PDF](https://gma2.hpwd.org/files/archives/2021/GMA2MinutesAug2021.pdf) preserves the exact selected URL. A separate anonymous GET returned its rendered HTML; [request and capture evidence](capabilities/evidence/novus-public-minutes/source.json) pins the bytes. This is an observed public layout, not a universal vendor API specification.

Minutes document168 is a `document` with `kind: minutes`, parent meeting210 and a meeting relationship. The reader verifies the public form action agrees with both native IDs and the document type. It retains rendered text, source heading, date/time literals and location. Local time has unknown time zone. The derived title labels the supplied body as Minutes. No native item IDs, structured votes, motions or attendance are inferred from prose.

The raw HTML, source text, native identity and parent relationship survive SQLite/reopen, local search and exact neutral ZIP round trips. No script executes and no linked resource is fetched. The [executed checks](verification/novus-public-minutes-2026-11-15.json) cover the selected actual capture plus injected network guards, not broad archive or staff-write acceptance. Other heading layouts fail closed. Root-to-detail traversal and native full-text search semantics remain separate.
