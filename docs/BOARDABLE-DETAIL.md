# Boardable captured listing to known detail

Current source supports `fetch_record` for a Boardable meeting already imported from a public listing into the caller's scoped storage. It uses the listing's captured numeric ID and slug through the existing public detail mapping. It never guesses a slug from an ID, searches other organizations, or traverses another listing to find a match. This addition is not present in the frozen dev8 wheel.

```python
from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage

engine = create_engine(storage=SQLiteStorage("connector-data.sqlite"))
source = Source(
    "boardable",
    "https://site.boardable.com/ventura-county-community-college-district/meetings",
)
context = OperationContext(principal="reader", client_id="my-client", tenant="city")
listing = engine.discover(source, context=context)
if listing.data and listing.data.get("records"):
    imported = engine.execute(
        "import_bundle", {"result": listing.public_dict(), "persist": True}, context=context
    )
    if imported.data and imported.data.get("persisted"):
        meeting_id = listing.data["records"][0]["identity"]["external_id"]
        detail = engine.fetch_record(source, meeting_id, context=context)
```

The same existing engine request works through CLI JSON, HTTP, the TypeScript client and MCP: operation `fetch`, the exact original `source`, and `external_id` as a numeric string. Import the complete discovery result with `persist: true` first, using the same caller/client/tenant scope and an operator-configured persistent store. These are local persistence operations, not Boardable writes. The current `fetch` grant and source namespace must remain authorized; internal normalization uses the engine's existing fetch dependency and does not grant externally callable normalization.

The handler verifies the stored record identity, original configured listing URL, capture format, byte length and SHA-256. It reparses the exact captured listing to recover one matching record and its detail URL, rather than trusting mutable normalized metadata. The guarded GET allows only the exact public site origin with redirects disabled, current byte/deadline limits and cancellation. The existing detail parser must return exactly the requested native identity in the same organization namespace.

Successful detail results remain `partial`: one detail is not a complete catalog. The result retains the detail capture plus the source listing in `captures`, and reports its listing digest in coverage. Listing and detail dates remain separate captured observations; this path does not resolve their previously observed discrepancy. Supplied document links are locators. Their bytes still require the separate capture-bound attachment operation and its download-origin authorization; no attachment is fetched implicitly.

Missing scoped listing records/captures require importing the listing again. A different configured root URL, caller scope, tampered capture, duplicate/missing native identity, redirect or mismatching detail fails closed. This path does not establish Boardable native search or private create/update/upload contracts.

Evidence: [focused receipt](verification/boardable-known-detail-2026-11-12.json), [existing public detail/document observation](verification/boardable-detail-document-2026-11-12.json), and `tests/test_boardable_detail.py`. The new route has synthetic execution against the captured listing/reference-table contract; no new live request or provider mutation was performed.
