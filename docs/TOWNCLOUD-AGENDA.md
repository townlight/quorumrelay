# TownCloud rendered agenda associations

Current source enriches the existing `towncloud-agenda-html` format. Saved normalization and default configured agenda discovery preserve the original meeting projection in `compatibility`, while rich records additionally retain nested rendered agenda items, their own supplied text and attachment associations. No new format or API is introduced. The frozen dev8 wheel does not contain this enrichment.

```python
from pathlib import Path
from quorumrelay import Source, create_engine

source = Source(
    "towncloud", "https://towncloud.io/go/bennett-co/agendas/1033",
    input_format="towncloud-agenda-html",
    options={"download_origins": [
        "https://towncloud-core-prod.s3.us-west-2.amazonaws.com"
    ]},
)
engine = create_engine()
result = engine.normalize(
    source, Path("saved-agenda.html").read_bytes(), input_format=source.input_format
)
# A separate authorized fetch_attachment call can fetch a supplied document.
# Parsing and discovery never download item attachments implicitly.
```

The captured HTML supplies a native meeting ID in its URL, but its `li.item` / `li.sub-item` elements have no native item IDs. Rich item keys therefore include the exact capture SHA-256 and display position; `native_item_id` remains null and derivation/stability explicitly identify a capture-local position. They must not be treated as stable vendor item IDs across revisions. Nested DOM ancestry establishes parent positions within that capture. Headings outside item elements have no invented item identities. Text owned by a parent excludes descendant item text, preserving association without duplicating a child's documents on its parent.

Supplied document paths contain native attachment IDs and the tenant path. Only the exact captured HTTPS S3 host and same configured tenant prefix qualify for these item associations. Titles, native IDs, item/meeting associations and literal locators are preserved; meeting/item citations remain the stable configured agenda URL. These are not byte hashes or proof of downloaded PDF contents. Cross-origin transfer requires the existing explicit `download_origins` setting and current permissions; mapping a link does not authorize its download.

The original 9,839-byte Bennett capture yields 11 rendered item positions, three sub-item parent links and eight native attachment IDs. The rich meeting retains its two existing agenda/packet locators plus eight item-document locators. Exact bytes remain in the capture, and original compatibility output remains equal to the unchanged reader. Rich digest changes when supplied content changes; native meeting identity remains stable. No speaker, adopted motion, vote, governing body or timezone is inferred from prose.

Four new affected synthetic cases cover saved/default-configured mapping, source association, item-owned text search, lossless neutral export, idempotence, revision semantics and separate generic attachment retrieval. The latter first verifies default cross-origin denial, then succeeds only with the explicitly configured S3 origin. Its PDF bytes are synthetic. No new live request, vendor mutation, frozen rebuild or publication was performed. See the [execution receipt](verification/towncloud-agenda-associations-2026-11-12.json) and `tests/test_towncloud_detail.py`.
