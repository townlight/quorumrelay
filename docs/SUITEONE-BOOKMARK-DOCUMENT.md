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
