# Wistia media swap

The local source supports the official Wistia Data API 2026-09 media swap contract through the existing SDK, CLI, HTTP and MCP `plan_write` / `commit_write` / `receipt` path. The frozen dev8 artifact does not contain this addition.

Use entity `media_swap`, operation `update`, explicit original `resource_id`, an allowed `meeting_id`, and `fields.replacement_media_id`. The two existing media IDs must differ and their provider media types must match. The server policy must grant `media_swap:update` and authorize both IDs when `resource_ids` is configured. Wistia runtime permissions cover both resources; synthetic fixtures need no vendor account.

```json
{"key":"replace-recording","entity":"media_swap","operation":"update","resource_id":"original","meeting_id":"meeting1","fields":{"replacement_media_id":"replacement"}}
```

Planning reads both media, preserves unknown returned fields, and binds both fingerprints plus the replacement's effect on existing embeds and URLs. Commit requires the exact plan hash and current grants, then compares both media again. This is an explicit requested replacement; ingestion never swaps media. The comparison is preflight conflict detection, not an atomic vendor compare-and-swap guarantee.

The request is `PUT https://api.wistia.com/modern/medias/{mediaHashedId}/swap`, JSON containing only `replacement_media_id`, with `X-Wistia-API-Version: 2026-09` and private Bearer authentication. Vendor documentation says a background job performs the replacement while preserving the original hashed ID and URLs. This route is distinct from uploading a replacement file or an overwrite feature.

A successful request produces a durable **pending** receipt with the returned job. Subsequent commit attempts reconcile using GET on that exact job; they never repeat the PUT. Failed jobs are failed, queued/started jobs remain pending, and lost acknowledgements remain uncertain. An exact acknowledged job reporting **finished**, followed by target-media GET confirming the original hashed ID and approved media type, yields provider-confirmed completion. Missing/mismatched job or target identity stays uncertain. The receipt expressly limits this proof: replacement bytes and playable processing are not independently verified. Queued acceptance is not completion. Remote byte hashes, automatic transcripts and undocumented replacement fields are not inferred.

Exact vendor Markdown/OpenAPI captures, URL/version/hash provenance and the job-status schema are in `docs/capabilities/evidence/wistia-swap/`. `tests/test_wistia_swap.py` independently validates synthetic request/response shapes against those captures and exercises the actual engine, SQLite reopen, grants and recovery. No vendor mutation was performed. Provider-confirmed completion follows the documented job semantics; no extra independent byte-identity gate is imposed.
