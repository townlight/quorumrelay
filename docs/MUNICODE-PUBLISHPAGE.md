# Municode public PublishPage listings

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
