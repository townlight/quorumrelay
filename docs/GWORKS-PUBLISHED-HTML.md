# GWorks published meeting HTML

## Product and deployment scope

This connector addresses **FrontDesk Agendas & Minutes Builder**, identified by
the vendor's [builder resource](https://www.gworks.com/resource/frontdesk-agendas-and-minutes-builder)
and its captured public citizen client. Pinned source provenance is in
`capabilities/evidence/gworks-current-builder/source.json` and
`capabilities/evidence/gworks-published-client/source.json`. The company's overall
local-government customer count does not establish this module's installed base.

Existing reads cover configured public city JSON, selected published agenda/minutes
HTML, and the separately credential-bound [secure calendar range](GWORKS-SECURE-CALENDAR.md).
These paths preserve native meeting identity under the configured city, original
captures and explicitly partial coverage. They support local persistence, search
and neutral export; no account-wide or cross-customer catalog is inferred.

The [editor reader and mapped meeting/media writes](GWORKS-EDITOR.md) belong to a
separate captured development deployment. Existing create/update/publication and
upload/association mappings are preserved. Their synthetic execution does not
establish production applicability or live write acceptance; production write
contracts remain deferred per market demand. No production origin is substituted
for a development origin.

Fourth-batch verification passed 149 focused read/write tests with no source or
test changes (`work/batch4-gworks.log` and `.xml`). This closes the documented
supported scope, not a claim of universal tenant compatibility.

## Selected published HTML

Select `gworks-published-meeting-html` for an exact HTTPS `https://files.frontdeskgworks.com/city/{city}/cms/{meeting}_agenda.html` or `_minute.html` source. This additive format preserves the original 34 compatibility formats and native meeting ID in the existing city listing namespace. It maps the rendered title, wall-clock date/time (zone unknown), location, sections/children and same-city supporting-file links. Item IDs are local to the exact SHA256 capture, never staff item identifiers. The supplied PDF resolver must bind the same city, meeting and document kind. Supporting links are locators until separately fetched under existing transfer policy.

The vendor citizen client declares this HTML load path. A real public city1311 meeting5017 response is pinned under `tests/fixtures/gworks-published`; source provenance and client extract are under `docs/capabilities/evidence/gworks-published-client`. Thirteen new tests include a real capture mapping, SQLite import twice/reopen/search, ZIP identity and original-byte preservation, separate synthetic attachment transfer, and mismatched/unsafe metadata rejection. The affected suite passed 156 tests. This is selected-page evidence, not provider-wide acceptance.

The secure calendar client uses a distinct POST/Bearer and flattened-field contract. Static JSON flags are not assumed equivalent to its publication flags. No staff writes, upload association, native item IDs, tenant-wide catalog completeness or timezone inference is added.

For a saved secure-calendar response select `gworks-secure-calendar-json` with the exact source URL `https://api.gworks.cloud/cms/secure/city/meeting/list`, `options={"gworks_city_id":"1311"}`, and the matching optional namespace `//files.frontdeskgworks.com/city/1311/cms/data.json`. The city ID is configured by the owning application; it is not asserted by the response. Native meeting IDs match the public city namespace only under that configuration.

This format requires `{ "data": [...] }` with flattened `cms_meeting.id`, `.title`, `.meeting_ts` and separately retained boolean publication flags. It preserves unknown values and the original envelope. ISO date strings retain their supplied precision; numeric timestamp units and time zones are not guessed. Flags alone supply no document locator. Saved discovery stays partial and discovery without saved input fails before any network request. An explicitly bounded, authorized range fetch is also implemented; see [secure calendar range reads](GWORKS-SECURE-CALENDAR.md) for its trusted credential binding and partial-result limits. Twenty-five synthetic cases and 124 affected passes cover original-byte ZIP, SQLite/reopen/search, native baseline identity, wrong shapes and tenant policy. No account acquisition or live secure-calendar acceptance is claimed.
