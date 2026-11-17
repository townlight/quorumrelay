# OnBase public native search

The Fitchburg Agenda Online connector supports the observed anonymous
`/Meetings/Search?dropid=7&searchTerm=...` destination. The public form declared
this route through a same-origin 302; a separate explicit GET returned the
search results. The connector uses that GET directly with redirects disabled.
It does not acquire a login or retain a form session.

```python
from quorumrelay import create_engine

result = create_engine().execute("search", {
    "native": True,
    "source": {
        "provider": "onbase",
        "url": "https://agendas.fitchburgwi.gov/OnBaseAgendaOnline/",
    },
    "query": {"terms": ["Council"], "record_types": ["meeting"]},
    "bounds": {"max_records": 100, "max_pages": 1},
})
```

The first term or phrase supplies provider candidates. Exact local terms,
phrases and dates apply to the returned title/date metadata. Body filters and
other record types are rejected because their mapping is unestablished.
The date option is the portal's **This Year**; the server's year/time zone is
unverified. Query dates narrow those candidates locally and do not request
historical years. Other deployments return unsupported for this handler.

The observed response has 100 native meeting rows, including one without
documents, and an explicit search-limit warning. Responsive duplicate cells
are not additional records. Native `data-meeting-id` and row IDs must agree;
supplied links and title/date must agree with the mapped row. A fileless row
retains its native ID and source citation without an invented detail URL.
Unknown source data remains in the response capture.

The result remains partial. Check `provider_limit_reached`, `truncated`,
`provider_candidates` and failures. Full-document matching, history, total and
pagination are unverified; checkpoints are rejected. An empty local match is
not a claim that the vendor has no matching records. Fetch, parse, size, MIME,
changed URL and other failures return failed rather than a successful empty
result. The original response and mapped candidates are available in
`result.data["bundle"]` for import and neutral ZIP export.

[Source and sanitization](capabilities/evidence/onbase-public-search/source.json)
record the actual anonymous observation separately from
[local execution](verification/onbase-native-search-2026-11-14.json).
The committed fixture replaces exactly one public anti-forgery value; its hash
and the pre-sanitization response hash are recorded separately. The runtime
capture retains the bytes actually received. No live write or release occurred.
