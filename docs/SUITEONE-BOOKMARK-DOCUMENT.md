# SuiteOne document preparation

The official August 2021 [bookmark update](https://getsuiteone.com/wp-content/uploads/2021/08/S1_BookmarksUpdate_2021.pdf), page 1, permits ordinary Word or HTML documents for subsequent manual bookmarking. This is a separate intake from Liberty/DCR2 timed bookmark exports. QuorumRelay prepares an ordinary HTML document locally; it does not upload, replace bookmarks, associate a recording or set playback times.

```python
import base64
from quorumrelay import create_engine

result = create_engine().execute("export", {
    "source": {"provider": "suiteone-media",
               "url": "https://vermilionoh.suiteonemedia.com/"},
    "provider_specific": True,
    "format": "suiteone-bookmark-document",
    "title": "Council agenda",
    "paragraphs": ["Call to order", "Budget discussion"],
})
assert result.status == "completed"
html_bytes = base64.b64decode(result.data["content_base64"])
# Save html_bytes to result.data["manifest"]["filename"] in caller-owned storage.
```

Inputs are explicit plain text. Markup, URLs and event handlers are escaped into text; Unicode and line breaks are retained. The manifest reports the output SHA256, byte length, source namespace and projection losses. `bounds.max_records` limits paragraphs; parser/transfer byte limits include escaped output. Cancellation and deadlines apply. `stream: true` returns a scoped artifact handle accessible through `quorumrelay.interchange.open_artifact`, including with persistent SQLite storage. Namespace policy is checked when generating and opening it.

For manual intake, select the ordinary HTML document option in the event's Bookmarks upload workflow. Do not select **Liberty Exported Format** or **Replace Existing Bookmarks** for this generated document. The guide describes editing bookmark text and setting play time manually using the current video position. No upload is performed by the exporter.

This is a text projection, not a neutral interchange bundle. IDs, relationships, provenance, attachments, timestamps and speaker information are not encoded as machine fields. Keep a neutral JSON/ZIP bundle separately when those values must survive. The timed Liberty `*_content.HTML` schema remains unresolved. The Liberty Player 3.1 MP4/metadata export is a different product path and is not treated as that schema. Synthetic tests verify generated HTML, escaping, exact bytes/hash, durable artifact reopening and policy/bounds/cancellation; they do not claim a successful vendor import.


## Native DCR2 producer recovered, November16

Static inspection of the official free DCR2 Player5.0 package recovered the
Word add-in exporter. [Pinned producer facts](capabilities/evidence/suiteone-dcr2-export/source.json)
record the package and assembly hashes. No installer or player was run.
Classic horizontal/vertical exports replace Word bookmark controls with buttons
whose name/value are the caption and whose action is `StartMeUp(index)`.
The index is a native marker index. Optional clock/date caption text derives from
FILETIME. Playback offsets are separately obtained from the player and encoded
in companion player outputs; they are not seconds in the content button.
The modern single-page HTML5 exporter uses `ChgPlayPos(position)` and is a
separate format from SuiteOne's documented classic `_content.HTML` intake.

The actual control structure and caption/index semantics are now known.
SuiteOne's staff importer conversion and required export settings remain open;
no index-to-seconds conversion or native timed artifact is synthesized. The
existing ordinary HTML exporter and manual timing workflow remain applicable.


The newly pinned official March2021 post-recording guide (pages1–3) supplies
the missing historical pairing: upload the WMV produced by the same Word+DCR
export, then import `_content.HTML` through Minutes with the HTML/import-and-
Bookmarks option. It states that processing the uploaded media fills bookmark
duration times. That explains how a native marker index can be resolved against
its recording. This historical Minutes workflow and the August2021 Bookmarks-tab
workflow have separate documented UI instructions; current machine request/save
and readback schemas remain unmapped. No publication or import was executed.
