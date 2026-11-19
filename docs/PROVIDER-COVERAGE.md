# Provider coverage for v0.1.0.dev15

QuorumRelay registers **33 providers**: 31 baseline families plus Cablecast and Diligent Community. The package includes 34 baseline formats, 74 additional parsers and 23 native search handlers. Twelve families have active upstream write mappings, 20 are read-only, and TownCloud write work is parked.

| Platform and provider ID | Discovery and retrieval | Native search scope | Upstream writes |
| --- | --- | --- | --- |
| [Boardable](BOARDABLE-WRITES.md) (`boardable`) | Configured public listings, meeting detail and selected documents | Public meeting metadata | Agenda and item edits, mapped meetings and weekly series, meeting files and Document Center |
| [BoardBook](BOARDBOOK-DETAIL.md) (`boardbook`) | Organization listings and selected agenda/minutes documents | Public search-index entries and excerpts | Read-only |
| [Cablecast / Reflect](USER-MANUAL.md#meeting-lists-and-meeting-video-civicweb-and-cablecast) (`cablecast`) | Public shows and selected detail with video and caption-playlist links | — | Read-only |
| [CHAMP](CHAMP-ARCHIVE.md) (`champ`) | Selected archive group/month, event detail and linked documents | — | Read-only |
| [CivicPlus Agenda Center](CIVICPLUS-AGENDA-CENTER.md) (`civicplus-agenda-center`) | Configured year/category listings and selected documents | Public title, keyword and date candidates | Read-only |
| [CivicPlus Select / CivicClerk](CIVICCLERK-SELECT.md) (`civicplus-select`) | Events, selected detail and files, supplied media/captions | Public grouped candidates | Existing event updates and agenda-section create/update |
| [CivicWeb / iCompass](CIVICWEB-FILEPRO.md) (`civicweb`) | Bounded meeting/document lists, selected detail and FilePro reads | FilePro candidates and snippets | Read-only |
| [ClerkBase / Clerk’s HQ](CLERKBASE-DOCUMENT.md) (`clerkbase`) | Configured public tree and supplied HTML documents | Public sidebar candidates | Read-only |
| [Destiny AgendaQuick](AGENDAQUICK-DETAIL.md) (`destiny-agendaquick`) | Calendar periods, selected agenda/memo detail and attachments | Scoped metadata and selected tenant item search | Read-only |
| [Digital Towpath](verification/towpath-supplied-detail-2026-11-12.json) (`digital-towpath`) | Supplied year listings, selected meeting detail and document locators | — | Read-only |
| [Diligent BoardDocs](BOARDDOCS-PUBLIC.md) (`boarddocs`) | Saved agenda PDFs, opt-in public committee list and selected printable agenda | — | Read-only archive support |
| [Diligent Community](DILIGENT-COMMUNITY.md) (`diligent-community`) | Bounded public list, detail, agenda text and selected supporting files | — | Read-only |
| [eSCRIBE](ESCRIBE-PUBLISHING-SERVICE.md) (`escribe`) | Public calendar and documents, selected PublishingService records and files | Public grouped candidates | Mapped records and attachments, scoped single-chunk upload and item-history creation |
| [Granicus Legistar](PROVIDER-NATIVE-MAPPINGS.md#legistar-events) (`legistar`) | Events, selected detail, related records and supplied files | Bounded EventBodyName matching | Mapped create/update operations for selected legislative entities |
| [Granicus MediaManager](WRITE-CONTRACT.md) (`granicus`) | Public publisher captures and selected SOAP reads | Public clip title/date candidates | Selected clip metadata, media assignment and minutes operations |
| [Granicus Peak](PEAK-PUBLICATION-FEEDS.md) (`peak`) | Configured publisher listings, selected packet links and agenda RSS | Public group and excerpt search | Read-only |
| [Granicus Swagit](SWAGIT-PUBLIC-TRANSCRIPTS.md) (`swagit`) | Public listings, selected player transcripts/WebVTT and captured attachments | Public title and metadata | Read-only |
| [gWorks FrontDesk](GWORKS-EDITOR.md) (`gworks`) | Public JSON/HTML listings and supplied documents, selected configured editor/calendar access | — | One title, location or explicit-offset schedule field on an existing unpublished production meeting. Separate development meeting/media mappings. |
| [Hyland OnBase Agenda Online](ONBASE-PUBLIC-WINDOWS.md) (`onbase`) | Bounded public list/window/detail and selected capture-bound documents | Scoped candidates | Read-only |
| [iQM2 / MinuteTraq](IQM2-MINUTETRAQ-SOAP.md) (`iqm2`) | Public calendar, detail, files and player/captions, selected SOAP agenda/minutes | Public mixed-kind metadata | Existing item title, mapped meeting create/update and M2 recording transfer |
| [Laserfiche WebLink / Repository](PROVIDER-NATIVE-MAPPINGS.md#laserfiche-repository-entry-metadata) (`laserfiche-weblink`) | Guarded WebLink reads and selected authenticated Repository API reads and document exports | Configured Repository folder search | Selected Repository document/media operations |
| Municipal iCalendar (`first-party`) | Supplied first-party calendar feeds; retained event identities and status | — | Read-only |
| [Municode Meetings / CivicPlus Essential](MUNICODE-PUBLISHPAGE.md) (`municode-meetings`) | Public PublishPage, selected agendas/packets and separately configured account reads | — | Development multimedia update only; production write deferred |
| [NovusAGENDA](NOVUS-PUBLIC-MINUTES.md) (`novusagenda`) | Public archive, selected agendas, cover sheets and minutes | Public containing-text candidates and local matching | Read-only |
| [PrimeGov / OneMeeting](PRIMEGOV-PUBLIC-OUTLINE.md) (`primegov`) | Public upcoming and annual archives, supplied documents and selected outline | Public metadata, excerpts and tracking number | Read-only |
| [Simbli](SIMBLI-WRITES.md) (`simbli`) | Configured public discovery, selected agenda/items/minutes and supporting documents; anonymous access can be blocked | — | Existing item title and supporting-document upload |
| [SuiteOne Media](SUITEONE-SUPPLIED-TRANSCRIPTS.md) (`suiteone-media`) | Configured archive/groups, selected transcripts/WebVTT and supplied documents | Bounded keyword candidates | Read-only |
| [TelVue CloudCast / Connect](TELVUE-WRITES.md) (`telvue`) | Public CloudCast feeds/player/captions and configured Connect account reads | Public video metadata | Playlist reorder and add existing media |
| [Town Hall Streams](TOWN-HALL-STREAMS-DETAIL.md) (`town-hall-streams`) | Archive, event detail and explicitly supplied transcript reads | Bounded metadata | Read-only |
| [TownCloud](TOWNCLOUD-AGENDA.md) (`towncloud`) | Direct and embedded listings, selected agenda/minutes/packet and supporting documents | — | Parked; existing unpublished draft-text adapter retained |
| [Tyler Meeting Manager](TYLER-PUBLIC.md) (`tyler-meeting-manager`) | Configured calendar, selected detail and documents, supplied player metadata | Calendar and feature-gated agenda-item candidates | Read-only |
| [Utah Public Notice Website](UTAH-PUBLIC-NOTICE.md) (`utah-public-notice`) | Bounded notices, selected detail and supplied attachments/calendar/audio | Public title/body/date candidates | Read-only |
| [Wistia](WISTIA-SWAP.md) (`wistia`) | Public embeds/captions, configured account media and caption reads | Bounded account search | Media upload/update/URL import, captions, tags and swap; recording copy deferred |

All 33 can use **local search over captured metadata and available text**. A dash means the release has no registered native-search handler for that provider. A registered handler still needs the configured source and supports only the mapped fields. Public or account reads are bounded to the documented source and selectors.

**Interchange works across the roster.** Use JSON, JSONL or ZIP for portable bundles; CSV and iCalendar are projections with reported field losses. Five providers have additional local file preparation: Legistar Text Editor, CivicPlus Select historical media/documents, OnBase Tagged DIP, SuiteOne bookmark documents and TelVue chapter CSV. Those exports leave the destination unchanged.

Use `providers` for exact input formats and `capabilities` with a provider ID for operation evidence. Some capability entries preserve the historical research snapshot. Use this table and the [delivery scope](DELIVERY-SCOPE.md) for release claims and the [provider mappings](PROVIDER-NATIVE-MAPPINGS.md) and [write contract](WRITE-CONTRACT.md) for request details. Scoped synthetic execution is separate from live provider acceptance. [Deferred writes](DELIVERY-SCOPE.md#future-releases-per-market-demand) remain deferred per market demand.
