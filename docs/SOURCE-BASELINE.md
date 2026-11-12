# Source baseline

Extraction date: 2026-11-11. These source trees were reported clean by the baseline owner before extraction.

| Repository | Exact revision | Reused source |
|---|---|---|
| townlight/townlight | d4470aeae662c759351f63140b035edac10d9a52 | desktop/runtime/python-services/townlight_runtime/meeting_imports.py and meeting_import_fetch.py |
| townlight/core | 88fe5bd19110058b93d72ce4bb5ae9c2d68d0106 | townlight_core/connectors/imports.py |
| townlight/meetings | f8ccf82807597e228ba276e1b3f89d053a7c0018 | identity/persistence semantics inspected separately, not copied into the standalone engine |

The compatibility-reader/Core extraction changes only package-local imports. Original v1 source namespaces, IDs, capture hashes and filters remain unchanged. The standalone fetcher additionally provides bounded POST/PUT/PATCH requests with explicit origins, stripped cross-origin headers and stronger deadline checks. The v2 capture model preserves original input independently of legacy filters. Reference-product source trees are not edited by extraction.

`compat.preview_export(connector, source_url, content, input_format=...)` supplies the exact existing v1 contract. Live Legistar Event API data is not the Legistar meeting-export format and requires a distinct evidenced mapping.

This is a local development candidate, not a published package or installed Windows acceptance result. Synthetic/mock tests are authorized; live provider writes are not.
