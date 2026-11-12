# AgendaQuick supplied public agenda

Current source adds `agendaquick-public-agenda-html` for the captured public AgendaQuick meeting-notice template. The calendar already supplies the exact `agenda_publish.cfm` URL with tenant `id`, `dsp=ag` and native meeting `seq`. Configured discovery selects the agenda mapper for that supplied URL; saved normalization can select the format explicitly. Calendar and agenda-item search formats and all 34 original readers remain unchanged. The frozen dev8 wheel does not include this mapping.

```python
from pathlib import Path
from quorumrelay import Source, create_engine

engine = create_engine()
source = Source(
    "destiny-agendaquick",
    "https://public.destinyhosted.com/agenda_publish.cfm?id=98622&mt=ALL&get_month=11&get_year=2026&dsp=ag&seq=1737",
    input_format="agendaquick-public-agenda-html",
)
result = engine.normalize(
    source, Path("saved-agenda.html").read_bytes(), input_format=source.input_format
)
```

The same `source` and format use the existing CLI, HTTP, TypeScript and MCP normalization/discovery methods. No new transport fields are required. With an authorized configured public source, `engine.discover(source)` performs one bounded GET; it does not execute the page's scripts or submit a form.

The mapper requires the captured template's `MEETING NOTICE AND AGENDA` header, supplied body/date headings, matching tenant input, and same-source print control matching the native meeting sequence. It preserves the displayed time literally and leaves timezone unknown. It does not substitute the calendar URL's month for the agenda's displayed meeting date.

Linked memo rows carry their supplied native `seq`, explicit meeting `ag`, placement `ln`, revision `rev`, agenda number, title, URL and raw cells. Parent meeting IDs must agree, and duplicate native memo IDs fail rather than silently collapse. Unlinked headings have no invented item identity. Raw HTML remains in the exact capture; `agenda_items_availability` explicitly says `supplied_linked_items_only`. Rendered cells such as `No Action` remain source literals, not inferred structured motions/votes.

The agenda itself is a `text/html` locator. Only the explicitly labelled, same-origin `DOWNLOAD PDF PACKET` link becomes a packet locator. Memo pages, packet bytes and print controls are not fetched implicitly. The existing capture-bound attachment method can separately fetch the supplied packet within current origin/byte/deadline/permission limits. Configured discovery remains partial and does not claim a complete archive, agenda text, memo contents or write API.

The exact observed page returned HTTP 200, `text/html`, 59,886 bytes, SHA-256 `46d51dcbed8e61316589e796c8745cef9a4fbdff84b583feb29ca6b2ca2bb80c`. It yields meeting `1737`, 25 unique linked memo IDs and one packet locator. This is one captured public template/version, not a vendor promise about every deployment. No login, vendor write, extra detail traversal or live packet download was performed.

Evidence: [focused receipt](verification/agendaquick-public-agenda-2026-11-12.json), `tests/test_agendaquick_detail.py`, and exact-byte content encoded in `tests/fixtures/agendaquick-detail-1737.capture.json`. Seven new synthetic cases passed, with two existing calendar cases reused. The synthetic packet response verifies the real mapping-to-attachment path, separately from the actual HTML observation.

## Supplied memo contents

Current source additionally supports `agendaquick-public-memo-html`. Select the exact memo URL supplied by an agenda item; do not construct the `seq`, `ag`, `ln` or `rev` values. A configured source with `dsp=agm` uses this mapper automatically; saved normalization can select the format explicitly. This is source support, absent from the frozen dev8 wheel.

The captured memo for item `14719` independently establishes its native item ID with visible `AIR- 14719` and its Print control, revision `0` with that control, and meeting `1737` / placement `70543` with its Return control. The hidden tenant must also agree. The result is an `agenda_item` record with an explicit meeting parent, displayed title/date, six labelled information sections, raw table cells and exact HTML provenance. Empty Summary and Recommended Motion sections remain empty. These labels do not establish adopted motions, votes, speakers or a governing body.

Nonempty sections become searchable supplied-text segments scoped to the selected item. A literal `popupAttachments('…','ATTACHMENTS')` declaration supplies one same-origin PDF locator; parsing never executes JavaScript. The existing attachment method can fetch it separately with current capture/permission/transfer guards. No attachment is implicitly downloaded, and this observation does not establish its actual bytes.

One bounded anonymous GET returned HTTP 200, `text/html`, 13,777 bytes, SHA-256 `995a8e65f2da9dabdac848ccab23567d9e4de3d77711ccdf269f34369934afcd`. Eight new synthetic cases passed across the initial negative cases and corrected positive rerun. They cover saved/default-configured mapping, native parent/control mismatches, safe literal attachment handling, local section search, lossless JSON export and separate synthetic PDF transfer. The first positive run exposed an overly narrow section recognizer; the corrected recognizer uses the six exact captured labels, including the mixed-case Fiscal Impact suffix. This remains one public template, not a universal deployment or archive guarantee. See the [memo receipt](verification/agendaquick-public-memo-2026-11-12.json) and `tests/test_agendaquick_memo.py`.
