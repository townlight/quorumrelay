# Diligent Community public reader

Provider: `diligent-community`. This is separate from `boarddocs` archives and
`civicweb`. Supported hosts are HTTPS `{tenant}.community.diligentoneplatform.com`.
Other host variants are not yet mapped. No account, browser or credential is needed
for the observed public reads. No write is implemented; unavailable write contracts
are deferred per market demand under [the delivery scope](DELIVERY-SCOPE.md).

## Supported operations

- `discover`: explicit inclusive date bounds, public published meeting metadata,
  native IDs, provider body labels and original calendar/time strings. Optional
  body matching uses the supplied provider label; migrated body classifications
  are not independently verified. Results remain partial even for an empty list.
- `fetch_record`: one meeting's native ID, name, location and time. The observed
  detail response omits a calendar date; no date is inferred from its title.
- `fetch_related(..., "document")`: public agenda/minutes document records with
  parent meeting identity, retained HTML, extracted source text and same-tenant
  native document attachment links. Private flags and closed/unknown document
  types do not become downloadable records. Original response evidence is retained.
- `fetch_attachment`: retrieve a selected captured document from caller-scoped
  storage. Replay its original public fields to verify identity and membership.
  Requests stay on the same tenant; redirects, empty files and HTML MIME or
  recognizable HTML document signatures fail while retaining the source record.
  PDF MIME requires PDF bytes; arbitrary mislabeled challenges cannot be ruled out.
- Saved parsing, local import/search and neutral JSON/JSONL/ZIP export use the
  existing shared engine. Writes, native search, video bytes, caption extraction
  and native agenda-item identity mapping are not claimed.

```python
from quorumrelay import Bounds, Source, create_engine
from quorumrelay.storage import SQLiteStorage

engine = create_engine(storage=SQLiteStorage("community.sqlite"))
source = Source("diligent-community",
                "https://boonecountyil.community.diligentoneplatform.com")
meetings = engine.discover(source, bounds=Bounds(
    date_from="2026-11-01", date_to="2026-11-16", max_records=100))
documents = engine.fetch_related(source, "1655", "document")
if documents.data and documents.data["records"]:
    engine.execute("import_bundle", {"bundle": documents.data, "persist": True})
    # Index zero is the agenda document; later entries are its declared attachments.
    # HTML agenda text is already in the retained record, not a verified binary file.
    record = documents.data["records"][0]
    if len(record["normalized"]["documents"]) > 1:
        downloaded = engine.fetch_attachment(source, record, index=1)
```

Saved formats: `diligent-community-meetings-json`,
`diligent-community-meeting-json`, `diligent-community-documents-json`.
Saved-input fetch parses supplied bytes without a network request; selected-record
and attachment requests cannot be combined with saved input.
Provider URL recognition alone is not tenant acceptance. Local listing continuation
is hash-bound to the response, source, body, dates and caller scope; it is not an
upstream pagination contract. A changed response requires restarting the listing.
Document lists have explicit record limits and report truncation; increase the
bound to reread a larger selected response. No complete archive is promised.

## Evidence and limits

The captured deployed public client declares `MeetingsService.svc/meetings`
date-range GET, `/{id}/meetingData` and `/{id}/meetingDocuments`. The selected
meeting page names open/closed agenda and minutes document type values.
The Community response wraps documents in `Documents`, unlike the existing
CivicWeb saved-array parser. Routes were verified on the configured Boone County
tenant; no CivicWeb contract is silently assumed equivalent.

On November 16, 2026, integrated public execution returned three meetings for
November 1–16, one public agenda document for meeting 1655, and a 326,108-byte
supporting PDF, SHA256
`6aa7ef34b94a1e32d5c65a10d85ac255be9c9a459bd0716ac65f3b266da67ba3`.
An initial file request returned a same-native-ID trailing-slash redirect. The
canonical slash route was inspected and then read directly; redirects stay disabled.
The nonpublic PDF descriptor 42882 was not downloaded or exposed as a record.
This is one-tenant acceptance, not universal live testing. Synthetic fixtures cover
adversarial inputs, bounds, cancellation, cross-scope isolation, original-field
membership, file validation, storage reopen and neutral interchange.

Sources:
- [Configured public tenant](https://boonecountyil.community.diligentoneplatform.com/)
- [Selected meeting](https://boonecountyil.community.diligentoneplatform.com/Portal/MeetingInformation.aspx?Org=Cal&Id=1655)
- [Official Community workflow documentation](https://help.diligentoneplatform.com/helpdocs/d1p/en-us/Content/community/community_admin_guide/community-getting-started.htm)

Official administrative guides establish UI features, not machine write contracts.
The broader Diligent developer portal does not establish Community write coverage.
Preserve BoardDocs reading support for historical material; never substitute a
Community tenant for a BoardDocs tenant by name or inferred migrated identity.
