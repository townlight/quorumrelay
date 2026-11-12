# QuorumRelay core continuation, 2026-11-11

Current source candidate is `quorumrelay==0.1.0.dev2`, schema `2.0.0`. Scott lifted the implementation pause for the full approved plan. The historical handoff below is retained as dated evidence; its mock-only statement is not a scope reduction or a current authorization determination.

Canonical SDK imports and CLI use `quorumrelay`. Compatibility imports `civic_data_connectors` and CLI `civic-data-connectors` continue to work. Public facade modules reexport the same implementation objects, so Source/Record/Engine/storage classes are shared rather than duplicated. Wheel packaging includes both import trees. SDK and engine contract examples now use the approved identity.

Current checks:

- Existing combined baseline: `python -X utf8 -m pytest tests -q`: 338 passed, 45.27 seconds (before the two new public-package tests and root's concurrent interface changes).
- Public package plus storage/search/import/interchange/write affected tests: 74 passed, 4.74 seconds with normal Windows encoding. Fixed UTF-8 contract fixture reading in `test_write_providers.py`, which previously prevented ordinary Windows collection.
- Public facade tests after lint cleanup: 2 passed; owned facade/script/test Ruff checks pass.
- Existing R7 authorization and R8 integrity fixes inspected end to end and passed their checked-in regressions: current namespace/operation policy guards status reads, JSON/JSONL hashes are unconditional, ZIP logical hash is verified before persistence/callbacks. Existing R6 scoped write file resolution is present and passed affected write tests; root separately verified the HTTP part-handle path.
- Fresh Windows `.venv-quorumrelay-dev02`, installed wheel with service extras, run from outside checkout: 31 providers/34 formats, four native parsers, 14 handlers, independent normalization, exact unknown fields, packaged schemas/data, HTTP/MCP imports, shared canonical/legacy class identity pass. `uv pip check`: 35 compatible packages.

Immutable development snapshot (not the coordinated final artifact): `dist/quorumrelay-development-02/quorumrelay-0.1.0.dev2-py3-none-any.whl`, SHA256 `1ce4135c7f6a3fa9f6e89f453623f4f8329ebf6dfde232f3a82d2b8a38d99095`. Receipt: `docs/verification/quorumrelay-development-02.json`. Do not overwrite; root's concurrent transport/docs changes and later source edits require a separately located coordinated artifact. The subsequent facade lint edit only makes the version reexport explicit; source and this snapshot are deliberately distinguished.

Remaining outcomes belong to the full approved plan: current provider-by-provider capability/live evidence, authorized write test access/readback, coherent final artifact, all four consumer workflows and Windows installed acceptance, required signing/delivery and publication verification. None is waived by green core tests or this development installation. No vendor data, existing releases, installed applications or old artifacts were modified by this core continuation.

---

# Core implementation handoff, 2026-11-11

Candidate `0.1.0.dev1`, record schema `2.0.0`. Local repository only, no commit, remote creation, push, tag or publication. Original source trees were read, not modified.

## Implemented core scope

- Extracted every original reader (31 families, 34 format pairs), four Core mappings and the safe fetcher without reference-product imports.
- Kept exact v1 `compat.preview_export`, source namespaces, IDs, capture hashes, source fields and legacy filters.
- Added the lossless rich capture model, typed from/to-dict helpers preserving unknown fields, identity/capture/revision separation, supplied status/time-zone distinctions, bounds and complete result/coverage/error contracts.
- Added a real method/body/header network request extension with actual-socket DNS validation, TLS, exact-origin rules, redirect/deadline/stream limits and bounded structured error responses. Raw response headers remain private.
- Added scoped engine policy, trusted internal normalization delegation, default operation composition, SDK convenience calls, additive native-parser registration and connector read-hook dispatch.
- Added safe legacy projection: selected exact baseline pages only; explicitly new sources retain configured source identity; existing API/portal transitions require evidenced mappings.
- Packaged the independently researched capability inventory and exact provider/alias identities, with unknown-ID errors and one row per family. Research evidence remains separate from verified implementation acceptance.

## Core-owned files

`pyproject.toml`, `.gitignore`; `src/civic_data_connectors/{__init__,compat,normalization,fetch,models,extensions,engine,factory,legacy,capabilities,schemas}.py`; generated `src/civic_data_connectors/schemas/*.schema.json`; `tests/{test_baseline,test_core,test_fetch,test_legacy_projection,test_extension_dispatch,test_capabilities}.py`; `tests/fixtures/baseline/*`; `scripts/{capture_baseline,export_schemas,run_original_matrix,write_core_evidence,verify_installed_artifact}.py`; `examples/{example_connector,sdk_saved_capture}.py`, `examples/normalize-result.json`; `docs/{SOURCE-BASELINE,ENGINE-CONTRACT,SDK}.md`; this handoff and `docs/verification/{core,development-01}.json`.

Capability data JSON files are owned by inventory, not authored as guessed provider contracts. Provider, storage/search/interchange/write and transport modules remain their respective owners' work.

## Validation evidence

1. `python -m pytest tests/test_baseline.py tests/test_core.py tests/test_fetch.py tests/test_legacy_projection.py tests/test_extension_dispatch.py tests/test_capabilities.py -q`: **139 PASS**, 1.54 seconds after the final core identity change.
2. Exact original `check-source-matrix.py --local-parser-only` through the test-only import alias: **34 PASS**. Expectations were generated from pinned untouched original readers/Core, not the new code.
3. Combined intermediate source suite `python -m pytest tests -q`: **279 PASS**, 57.48 seconds; one Starlette/anyio deprecation warning. Later fixes are not covered by that old whole-suite snapshot.
4. Provider-native/core/baseline/projection subset before development artifact build: **164 PASS**, 2.06 seconds.
5. Owned-module/script/example Ruff checks: **PASS**.
6. Fresh Windows Python 3.13.5 environment installed the immutable development wheel with service extras. Outside the checkout: 31 providers, 34 baseline formats, 14 standard handlers, 4 native parser hooks; saved Legistar Event API normalization, exact unknown raw fields, schema/data resources, HTTP/MCP imports: **PASS**. No Townlight Runtime/Core, Brief or TownRecord package was importable. `uv pip check`: **PASS**, 35 packages.
7. Exact parser 16 MiB minus one/equal/plus one and streamed transfer 200 MiB equal/plus one synthetic boundary checks pass. Mock DNS resolver deadline, redirects/private IPv4/IPv6/mixed answers, credential escape, length mismatches and bounded non-2xx responses pass.

Machine-readable per-format IDs, fixture hashes, independently computed oracle hashes, actual hashes, parser paths, test nodes, source pins and scoped non-provider claims are in `docs/verification/core.json`. Installed artifact member hashes and smoke results are in `docs/verification/development-01.json`.

## Immutable artifacts

- Early baseline wheel: `dist/core-baseline/civic_data_connectors-0.1.0.dev1-py3-none-any.whl`
  SHA256 `00f911a2ec2038fea1114424e7650617d7cec9e4a3c2fff0d0208addd9114f02`.
- Coordinated development snapshot: `dist/development-01/civic_data_connectors-0.1.0.dev1-py3-none-any.whl`
  SHA256 `3028ba81d8f44548c213483800c448aa6d97ebec108a99d9a4daa8aa85999d25`.

Do not overwrite either artifact. Consumers can vendor the same development bytes with a relative path and exact version/hash. Later security, stream and integration fixes require a distinct final artifact and affected reruns.

## Remaining release boundaries

This is not a complete release claim. Mock tests do not establish live vendor write acceptance. User direction prohibits live vendor writes during this run. Unverified/blocked provider operations, outstanding independent findings in other modules, final coherent artifact validation, four installed Windows consumer gates, migration/profile checks, installer signing and separately authorized publication/delivery remain explicit owning-track requirements. No public source was mutated as a test.
