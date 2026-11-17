# eSCRIBE rendered agenda detail

The local `escribe-meeting-detail-html` format complements the unchanged calendar reader. Configure the exact published HTTPS `pub-*.escribemeetings.com/Meeting.aspx?Id=<UUID>` URL and format, then use ordinary `engine.fetch` or offline `engine.normalize`. It does not enumerate meetings or infer a new meeting URL from title text.

The vendor page supplies the meeting UUID, agenda titles/counters, rendered display positions, header date/local time/location and item-associated FileStream links. Dates come from header fields, not title parsing; time remains source-local with unknown timezone. The raw HTML remains intact. Item keys contain the exact capture SHA and display position, `native_item_id` stays null, and identity derivation/stability explicitly identify the one-capture limit. Changed HTML produces new local item keys rather than falsely matching unknown native IDs across revisions.

Only supplied same-origin `/filestream.ashx?DocumentId=` links become actionable documents. The ordinary capture-verified attachment path retains its origin, transfer and authorization guards. No script is executed and no comment/staff endpoint is called. A configured single agenda GET returns partial coverage; full catalog/native item identity and unobserved body/media/write fields are not claimed.

[Evidence and exact execution scope](verification/escribe-rendered-detail-2026-11-12.json) distinguish the existing114444-byte saved capture, minimized transcribed test fixture and five distinct synthetic cases. There was no new live network request. Frozen dev8 and installed consumer artifacts are unchanged; this source addition awaits coherent candidate acceptance and authorized delivery.
