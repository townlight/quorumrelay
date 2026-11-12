# Simbli public item content

This local source addition is separate from the frozen dev8 wheel. It follows the vendor-served anonymous public client, not a guessed numeric item endpoint or staff route. See [contract and execution evidence](verification/simbli-item-content-2026-11-12.json).

```python
from quorumrelay import Source, create_engine
source = Source("simbli", "https://simbli.eboardsolutions.com/SB_Meetings/ViewMeeting.aspx?S=36031063&MID=4942",
                options={"agenda_item_id": 176766})
result = create_engine().fetch(source)
```

The engine obtains fresh page declarations and the current meeting tree. The selected native AgendaID must occur exactly once in that tree. Only its supplied opaque ID is sent to the declared GET model route, with anonymous user and current view; the returned private ID must match. Opaque controls and cookies are call-bound, never continuation tokens or stable citations. Failed or unavailable content retains successful earlier captures and reports partial errors.

Content fields preserve names, titles, control types, source HTML/text, order and presence values. Raw response fields remain in the capture. Attachment metadata is retained; only attachments with the same district and meeting produce the vendor-declared stable `/Meetings/Attachment.aspx` URL. Other scopes retain metadata without an actionable URL. The normalized item retains its meeting/parent relationship and replaces its tree-only duplicate in returned records. Bounds still apply; allow a page budget above the four base response captures for a selected item.

For offline use, `simbli-item-content-json` accepts an explicit envelope containing `meeting_id`, numeric `agenda_item_id`, optional `parent_item_external_id`, and `response` with `ItemDetails` and `ItemContents`. This is supplied request context, not identity inferred from title text. The exact network response is also retained separately in live fetch captures. Standard capture-verified `engine.fetch_attachment` retrieves the mapped supplied PDF; no arbitrary attachment URL is accepted.

Fourteen distinct focused cases were executed across the runs recorded in the evidence receipt. The separate bounded public read established one actual item response and one175050-byte PDF; it is not an integrated-engine live-read claim or a full-catalog claim. Aggregate agenda/minutes PDFs, other content controls and public native search still need their own contract mapping. No vendor write support is asserted by this read route.
