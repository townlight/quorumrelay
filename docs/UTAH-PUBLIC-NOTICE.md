# Utah Public Notice supported reads

Provider ID: `utah-public-notice`. This guide describes the implemented public
read scope. No Utah write adapter is registered; notice draft, publish and upload
work is deferred until market demand warrants obtaining the missing native
contracts. Existing write adapters for other providers remain available.

## Supported operations

| Operation | Supported scope |
| --- | --- |
| Notice detail | One configured `https://www.utah.gov/pmn/sitemap/notice/{id}.html`, or saved `utah-notice-html` capture, with a published title and dated event. |
| Public discovery | Anonymous public form at `/pmn/` or `/pmn/search.html`, with an explicit body name and inclusive date range. |
| Native search | The same bounded public form, plus a nonempty title expression; exact body/date and local title matching apply to returned metadata. |
| Saved search results | `utah-public-search-html` maps the observed five-column result table into notice records and supplied attachment locators. |
| Attachment retrieval | Select a normalized document or recording by index with `fetch_attachment`; original notice/capture stays available when an attachment fails. |
| Local preservation | Original capture, native identity, supplied fields and locators survive the existing import, SQLite reopen and JSON/JSONL/ZIP export paths. |

Detail output includes the source title, local event date/time, description/agenda
text and PDF locators. Rich output also retains labeled notice fields, body,
entity, government type, notice types, posting/editing text, address prose and a
source-bound public-body relationship. The source time zone remains unknown.
The exact supplied calendar link and explicitly categorized MP3 locators are
retained; see [calendar and audio details](UTAH-SUPPLIED-ASSETS.md).

## Bounded example

```python
from quorumrelay import create_engine

engine = create_engine()
source = {
    "provider": "utah-public-notice",
    "url": "https://www.utah.gov/pmn/search.html",
    "body": "Ridges Estates Infrastructure Financing District",
}
bounds = {
    "date_from": "2026-11-11", "date_to": "2026-11-11",
    "max_pages": 1, "max_records": 3, "deadline_seconds": 20,
}
discovery = engine.execute("discover", {"source": source, "bounds": bounds})
search = engine.execute("search", {
    "native": True, "source": source, "query": {"terms": ["Board"]},
    "bounds": bounds,
})
```

Check `status`, `errors`, returned records/hits and `coverage`. Successful public
search/discovery remains `partial`: a response with no next control is evidence
only that the observed page was exhausted. It does not establish a complete
catalog or full-source search. Only the first term/phrase is sent to the native
title field; the complete query is applied locally to returned title/body/date
metadata. This is not upstream agenda text or attachment full-text search.

The form transport keeps cookies and CSRF state private, rejects redirects and
changed endpoints, and enforces transfer, parser, page, record, deadline and
cancellation limits. A supplied next control can yield an opaque continuation
checkpoint. Resume with the same engine, scope and query within 15 minutes;
checkpoints do not survive process restart. Synthetic paging tests do not prove
live multi-page behavior, government/ZIP search, or upstream result caps.

## Evidence and limits

The existing [bounded discovery receipt](verification/utah-bounded-engine-discovery-2026-11-12.json)
and [native search receipt](verification/utah-native-search-engine-2026-11-12.json)
record one body/date window returning notice `1120627`. These are earlier live
observations, not a fresh live verification. The notice `1101977` detail fixture
and its [field receipt](verification/utah-supplied-detail-2026-11-12.json) support
the supplied field mapping. Calendar bytes were previously fetched live; audio
byte transfer is synthetic evidence only, with no playback, duration or transcript
claim. Calendar parsing, timezone merging and broader calendar variants are
outside this supported scope.

The [admin source receipt](capabilities/evidence/utah-admin-client/source.json)
records draft/publish/upload intent constants, but lacks the rendered form's
action, method, encoding, complete fields, notice/body/CSRF association and
version-matched result/readback contract. Anonymous admin entry returned 401.
This is insufficient for a write mapping and does not establish vendor-wide API
absence. No vendor mutation was performed for this batch.

Source trace: `providers/__init__.py` registers native search and saved formats;
`providers/discovery.py` dispatches the bounded form; `providers/utah_search.py`
owns transport, filtering and continuation; `providers/utah_public.py` maps result
rows. `compat.read_utah_notice` and `engine.normalize` with
`providers/utah_detail.enrich_bundle` map detail captures;
`providers/retrieval.py` transfers selected assets. `write_adapters.default_adapters`
contains no Utah mapping. These implementation paths are under
`src/civic_data_connectors`; `src/quorumrelay` provides the public facade.

Batch validation: `work/batch4-utah.log` and `work/batch4-utah.xml` record 28
passing focused tests across `test_utah_public.py`, `test_utah_search.py`,
`test_utah_detail.py` and `test_utah_supplied_assets.py`. No source or test changes
were needed for this batch.
