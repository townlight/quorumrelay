# GWorks secure calendar range reads

The existing `gworks-secure-calendar-json` format now supports one explicit
range read as well as saved-response normalization. The observed vendor plugin
declares `POST https://api.gworks.cloud/cms/secure/city/meeting/list` and its
range/columns/order/start fields. Its captured core client establishes literal
unpadded `YYYY-M-D 00:00:00` / `23:59:59` range strings, JSON request encoding and
the Bearer authorization header. This is a calendar read, not a write operation.

Use the exact API source/format with the explicit `gworks_city_id` string option
and its matching namespace, for example city1311 with
`//files.frontdeskgworks.com/city/1311/cms/data.json`. `fetch` requires inclusive
date_from/date_to bounds. Detail, related-record, caption, body and checkpoint
selectors are not mapped for this range operation. `discover` still accepts saved
responses but does not invent authenticated catalog traversal.

The application supplies trusted private configuration through OperationContext:

```python
context.credentials["gworks"] = {
    "token": server_saved_read_token,
    "tenant": context.tenant,
    "city_id": "1311",
    "origin": "https://api.gworks.cloud",
    "allowed_namespaces": ["//files.frontdeskgworks.com/city/1311/cms/data.json"],
}
```

The current context tenant and allowed source namespace must match. Public
request JSON cannot grant those values. Credentials are sent only to the exact
API endpoint without redirects. Parser and transfer limits both apply to the
request/response; total deadline and cancellation are checked after transport
and parsing. Provider 401/403 is permission_denied. No account acquisition or live
call is required for accepted synthetic verification.

The observed request uses start0 and supplies no paging/total contract. Every
successful range read therefore stays **partial**, including an empty data array.
Returned rows retain the existing native ID and city namespace, flags, unknown
fields and complete original response. Local checks filter known ISO source dates
to the requested inclusive range. Numeric timestamp units are not guessed;
unknown dates remain explicitly listed. A selected response exceeding max_records
fails rather than silently dropping an unpaged tail.

The response does not independently assert its city. City binding is supplied by
trusted credential configuration, not represented as a vendor-returned tenant
claim. Publication flags do not create document URLs or meeting associations.
No staff write, upload, pagination, current server applicability or complete
calendar history is inferred. SQLite retry/reopen/search and JSON/JSONL/ZIP retain
the source facts and captures.

Source excerpts and their full captured-core hash are attributed in
`capabilities/evidence/gworks-published-client/calendar-read-source.json`.
Execution is synthetic against the declared request and response fields; see
`verification/gworks-calendar-read-2026-11-15.json`. The separately declared
Galena minutes editor URL returned404: an exact source result, not proof that all
gWorks integration documentation is inaccessible.
