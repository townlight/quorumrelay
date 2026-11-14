# Tyler Meeting Manager public reads

Configure the public calendar URL and the exact same-tenant `calendar_api_base` observed in its client. Discovery requires inclusive dates. Its optional `meeting_type_ids` is a bounded integer list; the existing default `[-1]` remains unchanged. The Liberty County public client and October 2026 response showed that `[]` returned three meetings while `[-1]` returned none. Choose a selection supported by the tenant's client; neither selection establishes a complete archive.

For rows with an observed API base, posted agenda and minutes IDs expose the client's non-packet PDF locators. Explicit attachment retrieval binds the selected locator to the captured meeting and checks the PDF prefix. Selected detail requires an already stored calendar meeting with its native string ID and numeric meeting and recurring IDs, and checks all three against the public response. Native search submits the first requested term or phrase to the client's search route, then applies local exact matching to captured metadata. Search pagination uses the observed page number and size; server ordering, total consistency, full text and archive completeness remain provider-dependent and unverified. Checkpoints bind the query, caller scope and page size.

The exact public Liberty captures and request details are in [the observation](capabilities/evidence/tyler-liberty/observation.json). Its PDF was retrieved as public bytes and is retained in the work evidence path identified there; synthetic PDF bytes in tests do not prove rendering. These reads do not establish staff writes, playback, processing or a full catalog.

When `calendar_api_base` is explicitly configured, native calendar discovery,
selected detail and metadata search use a richer mapping that retains public
cancelled and adjourned records, including titles beginning with “Cancelled”.
Cancellation flags and agenda/minutes/video status values stay literal; the
mapper does not assign undocumented enum meanings or infer a flag from the title.
`startDateTime`, separate `startTime` and supplied rescheduling fields retain
their source values. The meeting date uses the literal date component, without
inventing a timezone conversion or combining the values into a scheduled instant.
Supplied agenda-item titles remain searchable metadata without positional IDs
being represented as native item identities. Malformed visible records fail
explicitly. Private visibility records remain excluded. The original baseline
compatibility parser and its historical filtering/output are unchanged.

Native calendar and search checkpoint bindings now name the retained-status
mapping. Tokens created under the former row-filtering semantics are rejected
before network access; start a fresh request to obtain a current token. Other
providers' checkpoints are unchanged. This prevents a saved local row offset
from being interpreted against a differently filtered calendar page.
