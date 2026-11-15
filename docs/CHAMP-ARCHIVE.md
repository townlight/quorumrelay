# CHAMP calendar archive discovery

The existing CHAMP provider supports one explicitly selected calendar archive
group and month through the public vendor client's declared JSON routes.
Lake Zurich's official recordings page declares the native archive player; its
client and two captured API responses establish this mapping. This is separate
from fetching a configured event detail.

```python
from quorumrelay import create_engine

engine = create_engine()
result = engine.execute("discover", {
    "source": {
        "provider": "champ",
        "url": "https://play.champds.com/lakezurichil/archive/1",
        "options": {"archive_group_id": 1},
    },
    "bounds": {
        "date_from": "2026-11-01",
        "date_to": "2026-11-30",
        "max_pages": 2,
        "max_records": 25,
    },
})
assert result.status == "partial"
records = result.data["records"]
```

Use a positive native group ID belonging to the selected archive. Both dates
are required and must lie within one calendar month. The adapter reads archive
metadata, validates the customer/archive/group and calendar display type, then
requests that full month with the client's literal `LOCAL` start/end format.
It applies the caller's inclusive date bounds locally. A group name is retained
as archive context; it is not treated as a verified legislative body selector.
Only meeting summaries are exposed. List groups and other display types remain
unverified by this implementation.

The actual selected response contains two events, with native event IDs, local
and UTC date strings, supplied description HTML, publication status and last-modified
values. The adapter preserves original fields and exact capture bytes, exposes
supplied description text, and keeps the existing customer/event identity namespace.
It does not fetch event detail, documents, recordings or captions automatically.
No local timezone is invented from the relationship between the two date fields.

Each emitted bundle retains both the group response and its archive metadata
capture, plus the exact group/window request context in
`extensions.champ_archive_context`. That context survives neutral JSON, JSONL
and ZIP export and SQLite reopening. Resuming a local offset retains the original
metadata capture time; it does not claim another metadata request occurred.

All results remain partial, including an empty selected response. The response
has no verified server paging or exhaustion contract. A continuation is a bounded
local offset tied to the selected source, group, dates, caller scope and response
hash; it is not a provider cursor. A changed response requires restarting the
selection. A one-request page budget can pause after metadata and resume the
selected group. Record, parser-byte, aggregate transfer, deadline and cancellation
bounds apply.

The observed archive also enables an external ECI publisher. This adapter does
not retrieve those external records and reports that omission explicitly. Other
groups, months and external publisher coverage are not established by the two
observed CHAMP events. No staff write, media playback, import or publication is
performed.

The saved vendor captures and request derivation are in
[the source manifest](capabilities/evidence/champ-public-archive/source.json).
Offline execution tests use the exact captured JSON responses and separately
exercise error, continuation, persistence and neutral-export behavior. These are
synthetic engine checks against observed vendor-client contracts; the live
observations are the individual captured GETs, not a claim of full live catalog
acceptance.
