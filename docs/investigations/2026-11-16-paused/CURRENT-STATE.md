# QuorumRelay current state — November 16, 2026

## Current candidate: Simbli supporting-file upload

Supporting upload on an existing editable agenda item is implemented through the
registered dispatcher: native multipart descriptor, item lock/full save, preserved
unrelated fields, fresh final identity and independently matching original bytes.
Durable recovery reads only and never replays upload/save. No live staff mutation.

Acceptance: 46 final upload cases passed in125.70s;68 unchanged existing-title
cases re-executed in the earlier109-case run. Receipt records both runs and the
superseded earlier upload cases explicitly.25 metadata cases, capability validator
and required full Ruff passed. See docs/verification/simbli-supporting-upload-2026-11-16.json.
Commit/push and required new-candidate GitHub CI are the next delivery steps.
Previous pushed62a58ff passed all required CI steps in run44009550804.

Meeting/item creation, minutes and publication remain unfinished. Separate native
minutes access/release DTO types and client functions are captured as research in
capabilities/evidence/simbli-minutes-lock-followup/source.json; no minutes adapter.
The full31-vendor goal remains incomplete with26 open entries. TownCloud parked;
no contacts/payments/merge/release. No owned local background job.

The iCalendar inventory correction is delivered;11 projection cases passed.
DTEND/DESCRIPTION remain disclosed export omissions. PrimeGov login/helper
follow-up yielded sign-in/escaping only; sanitized source capture is retained.

## Current verified implementation: general Boardable Document Center writes

Root computer-file upload and existing-title update now execute through the
registered Boardable dispatcher. All227 affected cases passed (31new Document
Center cases plus196 existing Boardable write cases),504.10seconds. After
recording scoped evidence and the dispatcher re-execution,25metadata cases,
capability validation and required full Ruff passed. See
`docs/verification/boardable-document-center-2026-11-16.json` and
`docs/BOARDABLE-DOCUMENT-CENTER.md`. Delivered commit `1f8272e1bb655ce13704eb56e322ccae39047042` passed every required GitHub CI step in run44008005112.
Existing receipts remain historical; four new re-execution evidence records
bind the changed dispatcher to the same tested legacy/series/meeting-file scopes.
No vendor writes/accounts/payments/contacts occurred during this resumed work.

## Resumed: CI repaired; selected Simbli title write implemented

Scott resumed the full goal in the Desktop Goals document, with CI first.
Commit `db9c6fd66a33006c2889d921c26118796eb967ba` repairs the five
test-source line-ending bindings. Fresh Windows checkout reproduced all16
original failures before the fix and passed afterward. GitHub run44003626602
passed every required step in11m19s, including the full Python suite, client
build/tests, capability validation and Ruff. No validator checks were relaxed.

The recovered Simbli title-update draft is now corrected and registered.
Its68 synthetic engine/SQLite cases plus25 metadata cases passed (93total,
132.84seconds). Post-inventory bookkeeping25 metadata cases, capability
validator and full required Ruff also passed. Receipt and exact pinned inputs:
`docs/verification/simbli-item-write-2026-11-16.json`; native scope and remaining
work: `docs/SIMBLI-WRITES.md`. GitHub run44005225052 passed all required checks
for delivered Simbli commit `f5a786afcd75e3838b98b67784534837de35f27b`.

This closes only existing editable no-workflow agenda-item title updates.
Simbli meeting/item creation, supporting uploads, minutes and publication remain
unfinished. The older failed draft and results below are historical evidence.
The full31-vendor goal remains active and incomplete. TownCloud stays parked;
no merge, release, payment or vendor contact is authorized.

## Historical paused checkpoint

Scott paused development and authorized committing and pushing the current work.
This is a checkpoint, not a release or a claim that all 31 vendors are complete.

## Integrated candidate

Base before this checkpoint: `897442bf99dff40c4bd03126009083ad9fd485a3`.
The working tree includes recovered gWorks editor/media writes, MinuteTraq native
read/meeting/title/recording operations, Laserfiche recovery coverage, Boardable
current agenda/meeting/series/document operations and their evidence and docs.

Latest required full Python regression: **3,102 passed, zero failures/errors/skips**,
1,741.85 seconds. All 725 frozen inputs matched the tested candidate before
receipt/runtime bookkeeping. After bookkeeping, 724 inputs stayed byte-identical;
the sole changed frozen input is generated capabilities.json. Subsequent 25
metadata tests passed; capability validator and required Ruff passed. Client
inputs were unchanged and prior client evidence was reused. The full JUnit and
tested-input hashes are backed up here. Runtime inventory source SHA256:
`6500fdcbc7ec186feb4083a105615f73100248837fbdbc329d644dfc394323ce`.

## Simbli: unintegrated draft, failing checks

`simbli-unintegrated-draft.json` is a draft archive only. It is NOT registered,
installed, accepted or production code. Its isolated run after a test-import
repair: **14 passed, 13 failed** in 18.51 seconds. All thirteen failures share a
tuple/list plan-serialization comparison defect. Review also found missing
HTTP-status checks on tree/detail reads, incomplete handling of attachment
SecurityToken preservation, and named lock/identity/coverage issues documented in
`simbli-correction-assignment.md`. Do not weaken checks or treat it as accepted.

The correction request was interrupted at Scott's pause. Owned local exec50596
terminated with exit1. No correction artifact was returned. The remote model
provider's cancellation cannot be observed from the terminated request. No owned
local job remains. Do not restart automatically while paused.

Recovered official native contracts and sanitized public item structure are
backed up here. Public source has IsEditable=false; authorized editable tests
are synthetic. No Simbli staff mutation executed. Item save uses full DTO plus
independent readback, JSON lock acquisition at app2, form release at app2 and
bearer authentication. Simbli Cookie must never be sent to the app2 origin.
The native client's lock-error fail-open branch must not be copied.

Further supporting-upload research identified multipart `file` at
`/services/api/FileUpload/UploadFile` with native query context and new-upload
`attachmentId=0&id=0`. Client consumes Data.isSuccess and Data.FileDetail, then
includes the resulting attachment descriptor in the item save. This is research,
not a new upload implementation or observed staff response. Meeting setup's
exact declared EditMeeting route redirects anonymous access to Login.aspx.

## Remaining scope and restrictions

The full 31-vendor goal remains incomplete. See `goal-reference.txt`,
`vendor-findings.md`, the main capability inventory and remaining-research docs.
TownCloud is parked at Scott's instruction. Essential authenticated responses and
pagination remain unresolved. Other vendor-specific gaps remain documented.
No further development, vendor contacts, payments, accounts or releases are
authorized by this checkpoint instruction. Earlier evaluation access remains
recorded, but pause takes priority until Scott resumes.

To resume: inspect current repo and archived Simbli contract/draft/failures,
apply the named corrections in isolation, execute meaningful acceptance checks
and integrate only when supported. Do not reinterpret this checkpoint as approval
to merge, publish a release, or declare the vendor goal complete.
