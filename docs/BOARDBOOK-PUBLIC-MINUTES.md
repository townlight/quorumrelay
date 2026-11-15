# BoardBook supplied public Minutes

Use the existing provider with an exact supplied HTTPS `meetings.boardbook.org/Public/Minutes/{organization}?meeting={nativeID}` URL. The additive format is `boardbook-public-minutes-html`; configured fetch/discovery selects it when omitted. The original31families/34baseline formats are unchanged.

The [original baseline listing and exact public response evidence](capabilities/evidence/boardbook-public-minutes/source.json) establish Minutes755664 in organization3307. A single anonymous GET returned91781bytes of HTML. The reader verifies the native organization/meeting-bound DownloadMinutes link, unique MeetingHeader,26native item rows and explicit parent IDs. It preserves the27meeting/item records, date/localtime/title, matching document locators and original bytes. Unknown time zone stays unknown.

Rendered `ActionsTakenRow-{nativeItemID}` content becomes source_fields.Actions and capture-bound searchable text. Hidden No Action placeholders are excluded. Action and voting prose remain source text; no typed motion/vote/attendance data is inferred. Existing agenda behavior and native parent identities are preserved.

Exact response URL/MIME, origin, transfer/parser limits and source-context guards apply to configured Minutes reads. No hidden loaders run. [Executed tests](verification/boardbook-public-minutes-2026-11-15.json) cover the actual capture, injected configured retrieval, separate synthetic PDF transfer, persistence/reopen/retry/local search and exact neutral ZIP.

BoardBook's existing namespace policy includes the source path. Agenda, Minutes and organization-listing paths therefore remain distinct scopes; matching numeric IDs do not silently merge them. No cross-path reconciliation, universal Minutes layout, archive completeness, staff API or vendor-import claim.
