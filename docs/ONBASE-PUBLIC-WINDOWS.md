# OnBase public date windows and embedded results

The public Akron Agenda Online page retrieved on November 13, 2026 supplies a
`showSearchResults(new SearchResults({...}))` JSON argument instead of the older
HTML meeting table. The additive `onbase-public-listing-html` reader now decodes
that argument as data, without executing JavaScript. Native IDs, source dates
and offsets, meeting-type names, availability flags and unknown row fields are
retained. It does not change the baseline `onbase-agenda-online-html` reader.

Configure the public HTTPS `/OnBaseAgendaOnline/` or `/OnBaseAgendaOnline/Meetings`
root and supply inclusive `date_from` and `date_to` bounds to `discover`. The
observed custom-date GET uses `/Meetings/Search` with `dropid=11`, `dropsv` and
`dropev` in `MM/DD/YYYY` form. Requests remain on the exact configured origin,
reject redirects, enforce parser/transfer/deadline bounds, and use the existing
capture-bound continuation for a local record limit. Resume checks the captured
page hash; it does not silently continue against changed results.

The captured vendor client supplies the document URL templates and type codes:
agenda 1, minutes 2, summary 3, agenda packet 5 and minutes packet 6. Links are
emitted only for the corresponding true availability flag and supplied document
name. Links are locators, not proof that a PDF was retrieved. Nonempty `Documents`
and `Media` submodels remain raw and unmapped until their contracts are verified.

The public table and selected meeting HTML readers use the same document-type
mapping: type 6 is `minutes_packet`, matching the embedded-results reader.
This corrects their earlier generic `attachment` label without changing supplied
URLs, meeting identities, raw captures or the baseline compatibility reader.

An explicit attachment fetch also recognizes the captured meeting-packet wrapper
for document types 5 and 6 with `isAttachment=true`. Its native meeting, document
type, zero item/publish IDs and non-section flag must match before the declared
`InvokeDownloadAttachment` preparation POST and `ViewDocument` GET. Typed
preparation readback and PDF bytes remain required; redirects, cross-origin
requests and changed scope are rejected under existing transfer, parser, deadline
and cancellation bounds. The [captured packet wrapper](capabilities/evidence/onbase-packet/source.json)
was obtained by public GET only. Tests execute preparation and PDF retrieval
synthetically; they do not establish live packet availability or Agenda writes.

The October 2026 window returned three meetings, but its `NoMoreResults` value was
false. No `GetMoreFullTextResults` traversal or complete-archive claim is made.
Results remain partial and explicitly describe their window and completeness
limits. Keyword search, other deployment shapes, staff writes and Agenda import
or meeting association remain separate requirements.

The [source record](capabilities/evidence/onbase-search-model/source.json) binds
the public response to the extracted JSON and literal client snippets. Tests use
that captured model inside synthetic HTML, plus labeled failure variations, and
exercise SQLite import/retry/reopen, metadata search and ZIP roundtrip.
