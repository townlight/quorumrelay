# ClerkBase supplied document text

The existing `clerkbase-document-html` format accepts a published ClerkBase meeting
document under its supplied `/Content/.../*.htm` or `.html` citation. Saved
normalization and default configured document discovery now retain static document
body text and paragraphs in the rich record. No new format or upstream API is
introduced. Original compatibility output and URL-path meeting identity remain
unchanged.

Rich `normalized.document_text` and `normalized.document_paragraphs` preserve the
supplied text and paragraph attributes. `record.text` identifies the citation and
exact capture SHA-256. The governing `normalized.body` field is not populated from
document prose. Recommendations, votes, attendance and headings in minutes remain
source text; no structured vote, motion or agenda hierarchy is inferred.

Static extraction excludes script/style/navigation/header/footer/form/noscript
elements and nodes bearing `hidden`. It does not execute CSS or scripts and does
not claim browser-rendered accessibility text. Original HTML remains available in
the exact capture. Rich normalized hashes change when retained text changes;
source identity and unchanged compatibility fields remain stable.

Use the existing normalization/discovery, local search and JSON/JSONL/ZIP neutral
export interfaces. [Four scoped synthetic cases](verification/clerkbase-document-text-2026-11-12.json)
use the original pinned Richmond minutes capture and synthetic configured GET.
They check content preservation, local text matching, neutral roundtrip, source
revision hashing, idempotence, exclusion guards and original-output parity. These
checks do not claim a new live download, provider-native phrase semantics, complete
catalog coverage or upstream mutation. This change is local source work and is
not part of frozen dev8.
