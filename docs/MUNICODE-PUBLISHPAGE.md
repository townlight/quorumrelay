# Municode public PublishPage listings and selected public agendas

The explicit `municode-publishpage-html` format reads the public HTML listing
served at `https://meetings.municode.com/PublishPage/index` or `/PublishPage`.
It is an additive format for the existing `municode-meetings` provider. The
original `municode-meetings-html` reader remains the reader for its original
Drupal table layout.

```python
from quorumrelay import create_engine

result = create_engine().execute("discover", {
    "source": {
        "provider": "municode-meetings",
        "input_format": "municode-publishpage-html",
        "url": (
            "https://meetings.municode.com/PublishPage/index"
            "?cid=EFFINGHAM"
            "&ppid=9639c19d-1d1f-4201-b8ff-163a28a35f08&p=1"
        ),
    },
    "bounds": {
        "date_from": "2026-11-01",
        "date_to": "2026-11-30",
        "max_records": 25,
    },
})
```

Supply the complete URL of the selected publication page. Its unique `cid`,
`ppid` and positive `p` values must agree with the captured page controls.
This public HTML path does not require Essential account credentials. Other
Essential account API paths retain their existing credential requirements.

The mapper retains meeting titles, supplied calendar dates, literal local time,
venue and supplied document/media locators. It does not infer a time zone,
cancellation or publication status from the title. The native `me` selector in
the tenant's ADA document links identifies a public listing record; equivalence
with an authenticated Essential API meeting ID is unverified. Document links
remain document links, rather than being represented as meeting-detail pages.

Discovery reads one explicitly selected HTML page and always reports partial
catalog coverage. Date bounds apply locally. A checkpoint continues within the
same response after refetching and checking its content hash. It is not a server
page cursor. Declared page options and links are retained as source context;
QuorumRelay does not execute their JavaScript or automatically traverse the
archive. An empty, malformed or mismatched response cannot establish a complete
empty catalog.

Original response bytes, source row values and page-control context accompany
the records. Linked agenda, packet, minutes and media files are not downloaded
by listing discovery. The separately documented authenticated
`/PublicApi/meeting/collection/{offset}` response, offset progression and
meeting/item write contracts remain unresolved by this HTML evidence.

The pinned source is one Effingham publication page containing 25 native row
identities and page options 1–7. Only page 1 was captured. The current capture's
HTTP status was not recorded after a local result-formatting error; the saved
body and its hash are available. An earlier observation of the same URL recorded
HTTP 200 separately. Neither observation is live engine acceptance, proof of a
particular Essential release, or a complete archive survey.

## Selected agenda and packet content

Use the existing listing source and its public meeting selector to request the
supplied HTML agenda or packet. `detail_kind` selects `agenda` (the default) or
`packet` in the source options:

```python
from quorumrelay import Source, create_engine

source = Source(
    "municode-meetings",
    "https://meetings.municode.com/PublishPage/index"
    "?cid=EFFINGHAM&ppid=9639c19d-1d1f-4201-b8ff-163a28a35f08&p=1",
    input_format="municode-publishpage-html",
    options={"detail_kind": "packet"},
)
result = create_engine().fetch_record(
    source, "4a737d59a401417fbd7fd597e964fdba"
)
```

The reader first rechecks the selected listing, then follows its exact supplied
ADA HTML link for that meeting. Both requests share transfer and deadline bounds.
The result retains the listing and detail captures, rendered section and item
text, and supplied links. Sections and items are positional content within the
meeting; the HTML does not establish native API item IDs.

One Effingham agenda and packet were captured with HTTP 200. Both contain 19
sections and 28 agenda items; the packet supplies 293 attachment links. This
establishes that selected public document layout, with no claim of complete
archive coverage, another tenant's layout or authenticated API identity.

## Authenticated API qualification

The public HTML reader does not resolve the separate Essential account API's
meeting/item response fields or collection paging rules. New Exa, Firecrawl,
GitHub and web searches returned the existing official article and Postman
collection without additional response examples. The saved public root and
listing declare no executable client scripts. Narrow connected-document searches
found no additional API contract; GitBook could not be searched because its
connection requires reauthentication.

An anonymous GET to the exact production meeting-detail example supplied by the
official Postman collection returned HTTP 401 with a Bearer challenge. That exact
route requires authorization. It does not prove response documentation is absent
elsewhere. A version-matched response specification or sanitized successful
collection/detail examples could establish the missing fields; a documented
offset rule is still needed before automatic API pagination can be implemented.
No live account credentials or vendor writes are required for synthetic contract
validation. See the [source receipts](capabilities/evidence/essential-public-detail/source.json).
