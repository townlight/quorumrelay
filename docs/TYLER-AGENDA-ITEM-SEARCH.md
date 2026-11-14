# Tyler public agenda-item search

Current local source adds a separate `agenda_item` search mode to the existing Tyler native search handler. It uses the public calendar client's declared POST and response model, with a mandatory current tenant feature check. It does not obtain credentials or call a staff write endpoint.

```python
result = engine.execute("search", {
    "native": True,
    "source": {
        "provider": "tyler-meeting-manager",
        "url": "https://libertycountytxapp.meetingmanager.tylerapp.com/392259prod/tylermm/calendar/",
        "options": {
            "calendar_api_base": "https://libertycountytxapp.meetingmanager.tylerapp.com/tylermmcalendar392259prod/"
        }
    },
    "query": {
        "record_types": ["agenda_item"],
        "terms": ["water"],
        "date_from": "2026-01-01",
        "date_to": "2026-12-31"
    }
})
```

The example illustrates configuration, not a working live Liberty item-search claim. Its exact `v1/harness/feature-flags` GET returned HTTP404 during the source review. The client requires the response property `agenda-item-outcome` to be exactly `true`; otherwise the adapter does not POST an item search. Explicit false/missing flags return qualified incomplete coverage, not successful zero hits. HTTP failures return failed coverage. Deployment/version applicability remains a runtime qualification.

When enabled, POST `meetingCalendarSearch/agenda-items/search` uses `pageNo`, `pageSize`, `searchKeyword`, `startDate`, `endDate`, `meetingTypeIds`, and `votingOutcomes`. The current adapter sends no outcome filter. It supports distinct positive meeting type IDs or the client's all-types selection `[-1]`. Date bounds and a term or phrase are required. Meeting and item search must be requested separately. One bounded page returns a query/scope-bound continuation token when the declared total requires another page.

Native `agendaItemId` becomes an `agenda_item` identity in the configured tenant namespace. The response supplies meeting name/date/type, but no native parent meeting ID. Those metadata fields never create a parent identity. The returned title, description, outcome description and voting outcome are retained with original unknown fields and capture bytes. Visible supplied text supports exact local term/phrase matching; script/style/template content is suppressed. ISO dates can be normalized; other display dates remain explicitly unknown, and no timezone is inferred.

The result remains partial: upstream matching/ranking, complete full-document text, stable paging under concurrent changes and complete catalog coverage are unverified. Supporting documents and recordings are not inferred from item search.

Pinned vendor source-map declarations and excerpts are in `docs/capabilities/evidence/tyler-public-item-search`. Twenty-two synthetic cases cover the exact request, feature gate, bounds, failures, item identity, missing parent identity, date qualification, query-bound continuation and SQLite/import/reopen/ZIP preservation. The affected Tyler suite passed63 tests. This source postdates the preserved dev13 packages.
