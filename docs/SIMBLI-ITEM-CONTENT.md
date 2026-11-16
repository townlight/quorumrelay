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

The public client also declares `GetMinutes` with an explicit empty meeting-level item selector and `GetMeetingMinutes` with its current page-declared anonymous controls. When those declarations are present, the bounded read retains meeting minutes and attendance HTML as text, the validated RSS locator, and the supplied recursive item-minutes hierarchy, including its links and unknown fields. The hierarchy has no proven native item identity or agenda join; it remains within the meeting. Raw responses are supplemental captures bound to text provenance. Missing declarations, malformed responses and failed reads retain independent successful results and report partial coverage. Opaque request controls remain private.

Offline `simbli-meeting-minutes-json` accepts `{"meeting_id": "4942", "response": {...}}`; `simbli-simple-minutes-json` accepts the same envelope, optionally with a caller-supplied positive `agenda_item_id` for an item-scoped response. This is explicit supplied context, not a provider-issued minutes identity. A null response emits no invented record. See the [saved client excerpts](capabilities/evidence/simbli-minutes-client/source.json) and [scoped task 6 receipt](verification/task6-bounded-retrieval-2026-11-15.json). Nonempty minutes execution is synthetic; full catalog and live nonempty DTO availability remain unverified.

For a selected `agenda_item_id`, the fresh tree supplies the opaque item selector for a separate `GetMinutes` read after the selected content response. Supplied item minutes enrich that same item with raw capture provenance; failed or bounded item-minutes reads retain the verified item content and leave meeting-wide minutes independently eligible within the remaining budget. The selector is not used as a native identity, and the service request URL is not persisted.
