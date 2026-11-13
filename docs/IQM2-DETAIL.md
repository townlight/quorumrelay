# Supplied iQM2 public meeting detail

Current source adds `iqm2-meeting-detail-html` for the captured public `Detail_Meeting.aspx?ID=…` template. Use an exact supplied calendar/detail citation, not a constructed URL or staff action. Saved normalization can select the format; configured discovery and fetch select it automatically for the supplied detail route. The original `iqm2-html` calendar reader and all 34 compatibility outputs are unchanged. This mapping is absent from the frozen dev8 wheel.

```python
from pathlib import Path
from quorumrelay import Source, create_engine

source = Source(
    "iqm2", "https://santamonicacityca.iqm2.com/Citizens/Detail_Meeting.aspx?ID=1496",
    input_format="iqm2-meeting-detail-html",
)
engine = create_engine()
result = engine.normalize(
    source, Path("saved-detail.html").read_bytes(), input_format=source.input_format
)
```

The same format uses existing CLI/HTTP/MCP/TypeScript normalization and configured-source methods. Configured reads remain bounded and partial: one page does not establish a complete agenda, archive or vendor-wide compatibility. A configured detail source is supported; an arbitrary external-ID `fetch_record` route is not introduced.

The hidden native meeting ID and form action must match the selected citation. Explicit heading controls provide body, meeting type, displayed date/time and status literal. An empty status remains empty; no scheduled/cancelled semantics are invented. The timezone is unknown. Address text and raw rendered table cells/attributes are retained. Presentation columns and neighboring comments preserve source layout cues without becoming inferred agenda parents, adopted motions or votes. Page actions/scripts are not executed or submitted.

Native legislative-file links explicitly supplying the current `MeetingID` become `legislative_file` records with that meeting parent. Other supplied meeting IDs stay separate references, preserving their exact URL/ID/title/context. They do not become children of the current meeting. Unlinked headings and “No items” rows have no invented native identities.

Document locators retain their exact supplied FileOpen ID/type/context. The captured Agenda and Agenda Packet controls use types `14` and `1` and must match the independent hidden agenda ID (`1476`, distinct from meeting `1496`). Supporting-file (`4`) and staff-report (`30`) links require the explicitly supplied current meeting context. This is a captured control contract, not a universal enum definition. Documents have a meeting association only: the page does not explicitly supply a legislative-file parent on these URLs, so proximity to a report title is insufficient to invent one. Unbound/other-meeting locators remain references.

Attachments are fetched only through a separate existing capture-bound attachment call and its current permission/origin/byte/deadline guards. Mapping proves a supplied locator, not PDF bytes. The meeting/detail citation remains separate from a file URL, and raw capture provenance supports later interpretation of unknown fields.

One exact supplied anonymous GET returned 200 `text/html`, 89,973 bytes, SHA-256 `829b13ca9de361abb5c465e5480520e5f3c9780ab5c7f1e92cec2907f64abb61`. It yields one meeting, 17 same-meeting legislative-file records, 63 document locators, 14 other-meeting references and 142 rendered source rows. Eight new affected synthetic cases passed across the initial six passes and two corrected test-mutation reruns. They cover saved/default configured discovery/fetch, exact file-title search, lossless neutral export, separate synthetic PDF transfer and binding/duplicate/context guards. No second probe, real file download, staff write, credential acquisition, frozen rebuild or publication occurred. See the [execution receipt](verification/iqm2-public-detail-2026-11-12.json), `tests/test_iqm2_detail.py` and exact-byte base64 fixture.
