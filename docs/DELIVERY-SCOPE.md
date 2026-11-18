# Delivery scope — November 18, 2026

Release **0.1.0.dev15** includes readers for all 31 baseline families and separate Cablecast and Diligent Community readers. Among the baseline families, 12 active connectors have mapped writes, 18 are read-only, and TownCloud is parked with its existing draft-text adapter. The tables below describe the operations and evidence for each family.

## Acceptance rule

- Preserve implemented, verified writes and their existing safeguards.
- Deliver reliable reads for selected platforms. Name the exact supported
  operations and disclose partial coverage; a URL or untested parser is not
  accepted reading support.
- When existing documentation and concrete source leads do not establish a safe
  machine write contract, defer those writes **per market demand**. Do not repeat
  exhausted searches, invent payloads, or claim the upstream product cannot write.
- Deferral changes delivery scope, not implementation or acceptance evidence.
  Preserve existing capability statuses, receipts and historical limitations.
- Verification uses saved public observations and scoped synthetic execution where documented. Earlier batch notes below describe their local acceptance at the time.

## First batch — locally accepted

1. Diligent Community public reader; retain BoardDocs archive support. BoardDocs
   retirement makes its historical customer count unsuitable as a current legacy
   deployment count. Community writes are deferred pending usable contracts.
2. Granicus Legistar and MediaManager: retain existing reads and verified writes;
   defer unresolved migration, recording and publication contracts.
3. Simbli: retain reads, existing-item title updates and supporting-document
   upload. Defer unresolved meeting/item creation, minutes and publication writes.
4. BoardBook: public reads; defer external import and native writes/uploads.
5. CivicPlus Select/CivicClerk: retain reads, event updates and section writes;
   defer unresolved creation/defaults, time conversion, item and upload writes.
6. eSCRIBE: retain existing reads and verified native operations; defer unresolved
   general upload assembly/replacement/readiness and import contracts.

Each platform is accepted for its documented supported operations, not for every
possible read or write. Existing qualified reads need not become universal archive
surveys. Meaningful affected checks and required repository checks still apply.

## Priority reconciliation

| Priority | Supported reading basis retained | Writes retained / deferred |
| --- | --- | --- |
| Diligent Community | New bounded public meeting listing, selected detail and public documents, agenda HTML/text, captured supporting-file retrieval, local persistence/search/export. See [reader guide](DILIGENT-COMMUNITY.md). | Read-only; administrative writes deferred. BoardDocs archive readers remain unchanged. |
| Legistar / MediaManager | Legistar Events/detail, related records and supplied files; selected public MediaManager listings and mapped SOAP reads. Preserve native IDs and known coverage limits. | Existing mapped native operations remain; missing migration/import, recording replacement, publication/readiness and generated-minutes contracts deferred. |
| Simbli | Configured public discovery, selected agenda/item/supporting-document/minutes reads and saved parsing. Current anonymous security challenges remain a live-access limitation; do not bypass or claim universal live access. | Existing-item title and supporting-document writes retained. Creation, minutes editing and publication deferred. Exact base 667f40e passed GitHub CI attempt 2. |
| BoardBook | Configured organization listing, selected agenda/minutes parsing, public document retrieval and scoped native search. Search-index IDs are not silently canonical meeting/item IDs. | No new native writes; external import, creation/update and upload deferred. |
| Select / CivicClerk | Bounded Events discovery, event detail/files and scoped supplied media/caption locators. Preserve publication filtering and date/identity limitations. | Native event updates and section writes retained. Unresolved event-create defaults, normalized clock conversion, item writes and uploads deferred. |
| eSCRIBE | Public meeting/document reads and explicit PublishingService reads, selected item/history and document selectors; retain unpaged/partial qualifications. | Mapped native operations retained. General upload sequencing/assembly, replacement/readiness and opaque import contracts deferred. |

Existing evidence is reused for unchanged implementations. Examples:
[Legistar related reads](verification/legistar-related-reads-2026-11-11.json),
[BoardBook public document](verification/boardbook-public-document-2026-11-12.json),
[Select supplied assets](verification/civicclerk-supplied-assets-2026-11-14.json),
[eSCRIBE PublishingService](verification/escribe-publishing-2026-11-15.json).
These are scoped receipts, not a fresh universal vendor certification. Runtime
operation statuses remain unchanged; this document changes prioritization and
acceptance scope, never historical evidence or unsupported claims into passes.

## Second batch — locally accepted

Scott authorized this batch after the first six completed. Complete these five
in order, then stop. The acceptance rule above remains unchanged: retain working
writes, deliver documented supported reads, and defer unavailable write contracts
per market demand. No publication is added to this authorization.

1. CivicPlus Agenda Center (distinct from Select/CivicClerk).
2. CivicWeb / iCompass.
3. PrimeGov / OneMeeting (one product lineage).
4. Swagit.
5. Granicus Peak.

Sol 6.1, Terra 6.1 and Luna 6 perform bounded assignments with the lead coordinating.
Existing implementation and acceptance evidence are inspected before changes;
unchanged evidence is reused. Completion is recorded per provider below when verified.

| Priority | Local acceptance | Supported scope and limits |
| --- | --- | --- |
| 1. Agenda Center | Verified: 9 focused tests passed; source unchanged | Configured/year-category discovery, saved parsing, title/date search and captured document bytes. [Reader guide](CIVICPLUS-AGENDA-CENTER.md). Native writes deferred; plan returns `mapping_unverified`. |
| 2. CivicWeb / iCompass | Verified: 64 focused tests passed; source unchanged | Bounded meeting/document lists, selected detail/print PDF, explicit FilePro folder/document/search reads. [FilePro guide](CIVICWEB-FILEPRO.md). Native writes deferred. |
| 3. PrimeGov / OneMeeting | Verified: 156 focused/shared discovery tests passed; source unchanged | Bounded upcoming/year archives, public metadata/excerpt and tracking-number search, capture-bound document retrieval and selected speaker-request outline. [Guide](PRIMEGOV-PUBLIC-OUTLINE.md). No full-agenda or authenticated API claim; native writes deferred. |
| 4. Swagit | Verified: 32 focused tests passed; source unchanged | Listing and metadata search, selected player transcript and declared WebVTT track retrieval, captured attachment transfer. [Guide](SWAGIT-PUBLIC-TRANSCRIPTS.md). No playback/full-catalog certification; native writes deferred. |
| 5. Peak | Verified: 55 focused tests passed; source unchanged | Configured publisher listings and captured packet links, agenda-publication RSS and bounded group/excerpt search. [RSS guide](PEAK-PUBLICATION-FEEDS.md), [search guide](PEAK-PUBLIC-SEARCH.md). No full-catalog, nonempty minutes-feed or playback claim; native writes deferred. |

All five completed locally in the approved order. No production code or tests
needed modification for this batch. The focused runs above and reused 3,280-pass
full-suite evidence support only these documented operations. See the
[second-batch acceptance receipt](verification/second-batch-acceptance-2026-11-16.json)
for candidate fingerprints, test artifacts and limits. Existing writes are
unchanged; these five have no built-in write adapters. No next batch, publication
or live vendor mutation is authorized by this completion.

## Third batch — locally accepted

Scott authorized these five after the second batch completed, under the same
acceptance rule: preserve working writes, verify documented reads, and defer writes
without usable contracts per market demand. Finish in order, then stop.

1. Laserfiche / WebLink.
2. Hyland OnBase.
3. TelVue.
4. Town Hall Streams.
5. SuiteOne.

Sol 6.1, Terra 6.1 and Luna 6 perform bounded assignments with the lead coordinating.
Reuse unchanged evidence and fix only concrete gaps within the supported scope.
No vendor mutation, publication, or further batch is authorized.

| Priority | Local acceptance | Supported scope and limits |
| --- | --- | --- |
| 1. Laserfiche / WebLink | Verified: 11 affected tests after fix; final full suite passed | Guarded WebLink reads and saved listing replay; separate Repository API reads/search/export and existing mapped writes retained. Fixed missing saved listing parser. No inferred complete archive or new write contract. |
| 2. OnBase | Verified: 173 focused tests passed; source unchanged | Bounded public listing/window/detail and capture-bound document reads; scoped native search and local Tagged DIP preparation retained. No universal/live-PDF claim; native writes deferred. |
| 3. TelVue | Verified: 134 focused/account/shared tests passed; source unchanged | Public CloudCast MRSS/player/search/captions, explicit Connect media/video/playlist/item reads and local chapter CSV retained. Existing playlist reorder/add-existing-media writes preserved; upload/readiness contracts deferred. No live Connect or playback claim. |
| 4. Town Hall Streams | Verified: 49 focused tests passed; source unchanged | Archive and location/event detail, bounded native metadata search and explicitly supplied transcript reads retained. HLS locator/playlist is not playback acceptance; nonempty transcript execution is synthetic. Native writes deferred. |
| 5. SuiteOne | Verified: 229 focused/shared tests passed; source unchanged | Bounded archive/older-group discovery, keyword candidates with local matching, selected transcript/WebVTT and supplied documents, local HTML bookmark-document preparation retained. No playback, universal catalog or vendor-import claim; native writes deferred. |

Third-batch final candidate verification: 3,283 Python tests passed, zero failures,
with the existing Starlette/AnyIO deprecation warning. Ruff, capability validation
and whitespace checks passed. The unchanged client build and four client tests
are reused. See [third-batch acceptance](verification/third-batch-acceptance-2026-11-16.json)
for exact source/test fingerprints and evidence. All jobs ended; stop after these
five. Local completion does not claim a new hosted-CI run, publication or installation.

## Fourth batch — locally accepted

Scott approved this revised order on November 17, 2026:

1. Utah Public Notice.
2. gWorks.
3. AgendaQuick.
4. ClerkBase / Clerk's HQ.
5. Tyler Meeting Manager.

Preserve working writes, verify documented supported reads, and defer unavailable
write contracts per market demand. For gWorks, establish the actual meeting
product/interface and existing connector coverage before accepting its scope;
company-wide customer totals do not establish meeting-product penetration.
Sol 6.1, Terra 6.1 and Luna 6 handle bounded serial assignments with the lead
coordinating. Finish these five, then stop. No publication or vendor mutation.

| Priority | Focused verification | Supported scope and limits |
| --- | --- | --- |
| 1. Utah Public Notice | 28 tests passed; source unchanged | Bounded body/date discovery and title search, selected notice detail and supplied attachments/calendar/audio; [guide](UTAH-PUBLIC-NOTICE.md). Partial coverage; calendar transfer has prior live evidence, audio transfer synthetic. Native writes deferred. |
| 2. gWorks | 149 tests passed; source unchanged | FrontDesk Agendas & Minutes Builder public city JSON/published HTML, authorized partial secure-calendar range reads; [product/deployment scope](GWORKS-PUBLISHED-HTML.md). Existing editor reads and meeting/media writes remain development-bound with synthetic verification. Production writes and live transaction acceptance unverified; no origin substitution. |
| 3. AgendaQuick | 30 tests passed; four test labels shortened | Calendar/period discovery, supplied agenda/memo detail and captured attachments; [guide](AGENDAQUICK-DETAIL.md). Native item search explicitly limited to public.destinyhosted.com tenant98622; no full-archive claim. Native writes deferred. |
| 4. ClerkBase / Clerk's HQ | 37 tests passed after paging fix | Bounded public tree traversal, scoped native search and supplied HTML document text; [guide](CLERKBASE-DOCUMENT.md). Fixed rejection of valid next-page controls10/19/100, preserving existing bounds. Separate OnBoardGOV is excluded; native writes deferred. |
| 5. Tyler Meeting Manager | 63 tests passed; source unchanged | Bounded same-tenant calendar/detail/search, feature-gated agenda-item search, selected agenda/minutes/packet PDFs and supplied player metadata; [guide](TYLER-PUBLIC.md). No universal archive, live packet or playback claim; native writes deferred. |

Final full-suite verification passed: **3,285 passed, 8 skipped, zero failures**,
with the existing Starlette/AnyIO deprecation warning. The eight skips are unchanged
optional WebLink browser cases because Playwright is absent from the isolated
test environment. A fresh follow-up using the already-installed Python 3.12
Playwright and headless Chrome passed all 10 WebLink session tests, including
all eight skipped cases, with zero skips. The candidate source/test fingerprint
remained unchanged. Combined current-candidate evidence covers 3,293 unique tests;
the original full-run result above remains unchanged. Ruff, capability
validation and whitespace checks passed. The unchanged client build and four
client tests are reused. The first full-suite attempt was interrupted after
timezone failures in an older environment missing the declared `tzdata` dependency;
the final run used an isolated environment with the repository's declared
service/test dependencies. See the [fourth-batch receipt](verification/fourth-batch-acceptance-2026-11-17.json)
for candidate bindings, results and limits. All five are locally accepted for
the operations above; all owned jobs ended. Stop after these five.
No new live vendor requests or mutations were made; historical live captures and
synthetic contract tests retain their separate evidence limits.

## Fifth batch — locally accepted

| Order | Provider | Supported operations and boundaries |
| --- | --- | --- |
| 1 | iQM2 / MinuteTraq | Public listings, selected detail, legislative files, scoped search and player/caption reads. Selected authenticated SOAP agenda/minutes reads. Existing item-title, meeting create/update and M2 recording writes retained. [SOAP guide](IQM2-MINUTETRAQ-SOAP.md). |
| 2 | Digital Towpath | Bounded listing traversal via supplied year links, selected numeric meeting detail and published document locators. Slug IDs are URL-derived. Read-only. [Detail evidence](verification/towpath-supplied-detail-2026-11-12.json). |
| 3 | Essential / Municode Meetings | Public PublishPage listings, selected agenda and packet reads, and separately configured account reads. Production responses with unverified schemas stay raw and partial. Retains the development multimedia update and readback. Production multimedia writes deferred. [Public reader guide](MUNICODE-PUBLISHPAGE.md). |
| 4 | Boardable | Configured public discovery, selected detail, documents and scoped search. Retains legacy agenda and current Agenda Builder operations, mapped single meetings and weekly series, meeting-file upload and Document Center operations. [Write guide](BOARDABLE-WRITES.md). |
| 5 | iCalendar | Read supplied first-party meeting feeds, preserve event identities and retained source fields, and export a local calendar projection. Source updates and calendar-server publishing are deferred. |

Retain existing writes within their mapped contracts. Operations without a write
contract remain deferred per market demand.

In order, the focused checks passed 205, 11, 71, 19 and 21 tests. The Boardable
run exercised representative operations from its 286 previously passing cases.
The iCalendar checks cover cancelled events and supplied timezone parameters in
rich records, local metadata search and lossy calendar export. Recurrence expansion
is outside this scope. The Python source/test fingerprint matched the candidate
from the fourth batch. See the [acceptance receipt](verification/fifth-batch-acceptance-2026-11-17.json).

## Sixth batch — locally accepted

| Order | Provider | Supported operations and boundaries |
| --- | --- | --- |
| 1 | CHAMP | Read-only. Selected archive group and month, event detail, native agenda relationships, linked documents and supplied media locators. Archive coverage is partial and excludes external ECI events. [Archive guide](CHAMP-ARCHIVE.md) and [agenda guide](CHAMP-AGENDA.md). |
| 2 | Wistia | Public embeds and supplied captions, authenticated media and caption reads, and bounded search. Retains mapped media uploads, updates, URL imports, caption operations, bulk tags and media swaps. Asynchronous completion requires the mapped job and readback checks. Swap readback verifies the target identity and type. Replacement bytes and playback remain unverified. [Swap guide](WISTIA-SWAP.md). |
| 3 | NovusAGENDA | Read-only archive support for documented public listings, search, selected agendas, cover sheets and minutes. Preserve source identifiers, text and document relationships within captured layouts. [Cover sheet guide](NOVUS-COVERSHEET.md) and [minutes guide](NOVUS-PUBLIC-MINUTES.md). |

The focused runs passed 47 CHAMP, 94 Wistia and 44 NovusAGENDA cases. The
[sixth-batch receipt](verification/sixth-batch-acceptance-2026-11-17.json)
records the tested candidate, results and reused regression evidence.

## Changes in dev15

Production gWorks now maps exactly one title, location or scheduled-time update
on one authorized unpublished existing meeting. Schedule inputs require a known
explicit offset and whole minutes; full preservation readback and durable
no-replay behavior apply. This is captured-client and synthetic acceptance;
live production acceptance remains unverified. See the
[production editor guide](GWORKS-EDITOR.md#production-one-unpublished-meeting-title-location-or-schedule)
and [schedule receipt](verification/gworks-production-schedule-2026-11-18.json).

TownCloud public reading covers configured published listings, selected rendered agendas,
and supplied agenda, minutes, packet and supporting-document retrieval with scoped
download origins. See the [TownCloud reader guide](TOWNCLOUD-AGENDA.md).
Further TownCloud writes remain parked. The existing draft-text adapter is preserved.

Wistia media swap can report an additional original-file metadata match when
the provider supplies comparable fields. See the [swap guide](WISTIA-SWAP.md).

## Future releases per market demand

Wistia recording copy, Simbli draft-item creation, CivicPlus Select unpublished
event creation and Diligent Community draft PDF attachment remain deferred
pending usable contracts. TownCloud's write work stays parked.

## BoardDocs lifecycle evidence

- [Austin ISD, June 8, 2026](https://www.austinisd.org/announcements/2026/06/08/boarddocs-sunsets-transitions-diligent-community)
  attributes its migration to BoardDocs being sunsetted.
- [Palm Beach Schools, Fall 2025](https://www2.palmbeachschools.org/ebooks/TIMEArchive/Fall2025/files/basic-html/page13.html)
  reports BoardDocs/LT support ending after June 2026.
- [Diligent's current landing page](https://www.diligent.com/lp/boarddocs)
  still promises existing-customer support. No universal shutdown date is asserted.

## Local acceptance completion

The six priorities passed local acceptance on November 16, 2026: 3,280 Python tests, Ruff, capability validation and whitespace checks. The unchanged client build and four client tests are reused. See [candidate receipt](verification/diligent-community-acceptance-2026-11-16.json) for exact source hashes and evidence limits. This is local implementation completion; no publication or new hosted-CI pass is claimed.
