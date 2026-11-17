# Laserfiche Import Recovery

Status: four synthetic transport tests passed on November 16, 2026 (15.87 seconds). No live mutations were attempted. DeepSeek v4.1 Flash 1017 authored the tests; the coordinator applied and executed them.

## Evidence

- Laserfiche forum report: `POST /Folder/Import` can return HTTP 500 with an unknown import timeout after the repository has already created an entry and without returning an entry ID: https://answers.laserfiche.com/questions/235341/API-Import-timeout-500-unknown
- Official Repository API import guide: https://developer.laserfiche.com/docs/guides/documents-and-folders/guide_importing-documents/
- Vendor guidance for larger or longer imports: use the existing uploaded-parts route, `Folder/ImportUploadedParts`, rather than repeatedly issuing the simple `Folder/Import` request.

## Existing behavior retained

- A mutating HTTP 5xx, timeout, transport failure, or invalid/truncated response is treated as an ambiguous mutation outcome.
- `commit_write` durably records a sending intent before the outbound mutation. After an ambiguous outcome the item remains `uncertain`.
- Later commits or restarts reconcile `sending`, `uncertain`, and `pending` items read-only. They do not call `apply` again, so the simple `Folder/Import` request is not resent.
- If simple `Folder/Import` returns HTTP 500 after server-side creation but without an entry ID, the receipt remains `uncertain`. This is intentional because exact readback cannot prove which entry, if any, was created.
- `document_large` is an explicit caller choice. It uses the existing `CreateMultipartUploadUrls` -> signed part uploads -> `Folder/ImportUploadedParts` route and retains the returned `taskId` for task reconciliation.
- There is no automatic size or duration heuristic that switches a simple import to `document_large`. Routing stays explicit.
- If final `Folder/ImportUploadedParts` returns HTTP 500 before returning a `taskId`, the receipt retains `upload_id` and `part_etags` but remains `uncertain`. Repeat commits and restarts do not resend uploaded chunks or the final import request.
- `pdfOptions` accepts exactly the documented fields: `generateText`, `generatePages`, `generatePagesImageType`, and `keepPdfAfterImport`. Unknown nested fields, including OCR-like additions, are rejected.

## Operational recovery

1. Repeating `commit_write` for the same approved plan performs reconciliation only. Do not create a replacement plan or manually replay the import while its outcome remains uncertain.
2. Use the durable receipt to identify the plan, change key, upload ID, ETags, task ID, or absence of those references.
3. For no-ID simple import timeouts, perform a read-only repository review outside this connector using existing approved controls. The connector cannot safely infer the created entry.
4. For `ImportUploadedParts` with a `taskId`, continue read-only task polling through the existing reconciliation path.
5. For `ImportUploadedParts` without a `taskId`, keep the receipt `uncertain`; do not resend chunks or the final import.
6. Any manual corrective action must follow repository policy and must not be modeled as an automatic retry in this connector.

## Test coverage added

- Simple `Folder/Import` HTTP 500 after server-side create without entry ID: one mutation only across repeat commit and SQLite reopen.
- Final `Folder/ImportUploadedParts` HTTP 500 without task ID after uploaded parts: no resend of URL creation, signed chunk upload, or final import across repeat commit and SQLite reopen.
- Successful `document_large` route: uploaded-parts endpoints are used and the task reference is retained; simple `Folder/Import` is not called.
- `pdfOptions` validation: the four documented fields are accepted and an unknown OCR-like field is rejected.

## Files

- Tests: `tests/test_laserfiche_import_timeouts.py`
- Production changes: none in this assignment.
