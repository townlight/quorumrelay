# QuorumRelay release notes

## Unreleased

QuorumRelay is being built under the Townlight organization as an independent
package. The full first-release scope and acceptance requirements remain in
[the approved plan](IMPLEMENTATION-PLAN.md). No completed first release has
been published. Development packages and source checks are separate from
authorized vendor acceptance and installed reference-product acceptance.

The implementation preserves all 31 provider families and 34 original format
combinations, including the original compatibility identities and hashes.
The canonical package/import/command is `quorumrelay`; existing
`civic_data_connectors` imports and `civic-data-connectors` commands remain
compatible. The TypeScript package is `quorumrelay-client`, with
`QuorumRelayClient` and the retained `CivicConnectorClient` alias.

Python, CLI JSON/JSONL, HTTP/OpenAPI, MCP stdio and Streamable HTTP share the
engine's records, coverage, errors and exact-plan write contract. Optional scoped
storage retains captures, revisions, search evidence, operation state and write
receipts. Neutral JSON/JSONL/ZIP exports retain original captures and verify
hashes; CSV and iCalendar disclose projection losses. Large file inputs use
separate parser and transfer bounds.

Current source includes Legistar supplied
vote/attendance reads, Laserfiche Repository folder listings, and preparation
of CivicPlus historical PDF/MP4 filenames. The latter produces a ZIP
delivery wrapper containing named original files and a loss manifest. The
official-linked filename tester supports additional Notice, Other and Media
preparation, with a guard against whole-filename classification conflicts. It
does not submit files or prove consultant import, video playback or vendor ZIP
acceptance.
Novus public listing postbacks preserve the observed window and opaque scoped
continuations. Explicit Essential dev and TelVue Connect account routes retain
unknown fields and schema/pagination limits; Essential multimedia changes use
the same durable write lifecycle. The optional guarded WebLink session preserves
network boundaries but does not bypass site access challenges.
See [current engine coverage](ENGINE-COVERAGE.md) and the
[capability inventory](capabilities/README.md) for exact operation limits.

Progress-only storage updates are coalesced so normalizing a large listing does
not require a durable SQLite write for every record. Cancellation checks, final
operation state, capture persistence and write receipts retain their own
semantics. Generic input handles support the same scoped file-export path across
HTTP, CLI and MCP; legacy HTTP handles retain their existing uses.

Townlight, TownReporter, CivicCast Brief and TownRecord are the four reference
integrations. Their source and isolated workflow checks do not substitute for
the plan's installed Windows/profile/handoff and delivery requirements. Their
current evidence and remaining work are identified in
[the execution state](EXECUTION-STATE.md).

## Development candidate 0.1.0.dev6

This revision carries the supplied CivicClerk direct MP4 through the existing
`video_url` field as well as `url`, allowing consumers such as Townlight Station
to distinguish a direct-file candidate from a player page. Only an already
validated captured HTTPS `mediaStreamPath` with an MP4 URL path receives that
field. Generic player links and `.mp4` appearing only in a query remain untyped.
Guarded downloads and consumer file checks still apply. All 34 direct-normalize
compatibility outputs remain unchanged.

Dev5 and its complete verification receipts remain preserved. Immutable dev6
Python wheel SHA256:
`ec1e6c55dc29338dcf3033a1f8bba92bec1975f0108cbb92e2e2e18a4ec19ee1`.
TypeScript `0.1.0-dev.6` tarball SHA256:
`ab6439db9041a31acf70db8334089d2213346beda7fad40a6e4a184b561c07da`.
Source: `4b1c27ca571d1b781233fcd03389ce99ddf58932`.

Fresh Windows installed-package checks, the exact direct-media preview fields,
all 34 original-output comparisons and all ten copied external examples passed.
The 78 discovery checks and nine projection/package/Node checks cover the
changed source; unaffected dev5 checks are reused. The client compiled code,
types and README are byte-identical to dev5; only its package version changed.
See the [artifact receipt](verification/quorumrelay-development-06.json) and
[affected source checks](verification/quorumrelay-development-06-checks.json).
Installed consumer handoffs and hosted CI remain separate. No acceptance scope
is reduced and no live provider write is claimed.

## Development candidate 0.1.0.dev5

This revision preserves CivicClerk's captured absolute HTTPS `mediaStreamPath`
through discovery, canonical import preview and the matched legacy preview.
Direct normalization keeps all 34 original compatibility outputs unchanged.
Malformed and relative media paths remain raw evidence; no CDN URL is invented.
Existing source grants and guarded retrieval still govern downloads.

Historical-file preparation now includes canonical Notice and Other PDFs and
Media MP4 alongside Agenda, Agenda Packet and Minutes. Generated filenames must
match the official-linked tester's classification. MP4 checks verify bounded
container framing only; bytes and hashes remain exact. No provider transfer or
consultant acceptance is claimed. Credentials and the contradictory documented
FTP hosts remain unresolved.

Granicus native search now follows the observed same-origin Clip search form
and verified page-number continuation. It preserves captured responses and
stable clip identities, binds checkpoints to the source/query/caller and checks
resumed-page hashes. Exact local title/date matching applies to provider-returned
candidates. It remains explicitly partial metadata search; agenda text and
complete source coverage are not claimed.

The immutable Python wheel SHA256 is
`6a932d54cd24e3ead79ba9fe6921373e0eaaa6bc116fb10ae037eaa700c0b0d3`;
the TypeScript `0.1.0-dev.5` tarball SHA256 is
`9e53e23f6f862d5de32a131f4fc42eabf2dd22c8d00b67cf157a8f8467070f37`.
Both correspond to source `3e7111fe72d69b95e5a67d2a003cd8bd3a1386ab`.

The fresh Windows wheel environment passed its standalone checks and all 34
independent original-output comparisons. All ten copied external examples
passed, including both MCP transports and synthetic write workflows. Source
checks and bounded affected reruns cover all 466 collected cases; the receipt
preserves the initial stale-version failures and subsequent recovery rather
than representing those as a single uninterrupted run. Required hosted CI and
consumer acceptance remain separately recorded.

See the [installed artifact receipt](verification/quorumrelay-development-05.json)
and [source checks](verification/quorumrelay-development-05-checks.json).
This remains a development candidate with the entire original first-release
acceptance unchanged.

## Development checkpoint 0.1.0.dev4

This immutable development snapshot includes the additions described above.
It remains an integration candidate, with the original first-release acceptance
requirements unchanged.

- Python wheel SHA256:
  `f0f9bc97d549785458d8ac1d879258dc7750d5d420b1c9043d97026b41187ee1`.
- TypeScript `0.1.0-dev.4` tarball SHA256:
  `04e8cb799bc2d38632add738682a205d10c9b1e390cd9668910b19d026d60f11`.
- Source suite: 443 tests passed. The later capability-enum correction passed
  four affected package/capability checks and the validator's five negative cases.
- Client build and four transport tests passed. Fresh wheel service dependencies
  passed compatibility checks; the installed package has 31 providers, 34 baseline
  formats and 15 additive parsers, with no reference-product imports required.
- All 34 installed compatibility outputs matched the frozen independent original
  oracle with network and reference-product imports blocked.

See the [installed artifact receipt](verification/quorumrelay-development-04.json)
and [source checks](verification/quorumrelay-development-04-checks.json).
Consumer repins and installed acceptance are still underway.

## Development checkpoint 0.1.0.dev3

This immutable integration snapshot comes from source commit
`957bd141db4cc62fb9b027e31f5e082a110db98c`. It predates the source additions
described above.

- Python wheel SHA256:
  `3c6a3d2a8894a1f5ac839403d16bb29e88d231c4863d64e8def7ea004ca945b2`.
- TypeScript `0.1.0-dev.3` tarball SHA256:
  `c1854c1d777e365ee1e13d1cf87a44f7b9e5ca0bc089a99e95ed7671a1b915e9`.
- Source suite: 376 tests passed; Windows CI passed for that commit.
- Fresh installed wheel: all 34 original format outputs matched the frozen
  original oracle with network and reference-product imports blocked.

Its [installed artifact receipt](verification/quorumrelay-development-03.json)
identifies only those exact bytes. Earlier development artifacts remain preserved.
Dev4 is separately identified above; dev3's evidence applies only to its own bytes.

## Outstanding first-release acceptance

Authorized vendor test tenants and credentials have not been supplied. Live
write/readback acceptance remains incomplete, and mocked receipts do not replace
it. Other account-backed reads, unresolved provider contracts, installed-product
checks, signing where applicable, publication and post-delivery verification
remain as recorded in the plan and execution state. Unknown support is not
evidence that a vendor lacks a feature. No requirement has been waived.


## Development candidate 0.1.0.dev7

Preserves all 31 provider families and 34 original baseline formats. Adds the finite verified public-control batch: current layouts and supplied tree/year/group traversal, native metadata/excerpt search for PrimeGov, eSCRIBE, Swagit, SuiteOne, Select, AgendaCenter, AgendaQuick, Utah, iQM2 and ClerkBase, supplied PDF validation/resolvers, and precise supplied-media projection. Runtime registration now contains 28 additive parsers. Exact captures, native or explicitly supplied-URL identities, unknown fields and partial/failure coverage remain distinct.

Small-page continuation fixes cover mutable provider rank/DOM IDs, process-private expiring sessions and current caller grants, cumulative transfer limits and deadlines. No captcha bypass, staff route, inferred parent relationship or full-catalog/full-text claim is introduced. Existing dev6 artifacts and signed Townlight 1.8.4 acceptance remain immutable evidence of their own inputs; dev7 standalone/service installation and original 34-output comparisons passed. Exact consumer pins, hosted checks, native candidate acceptance and delivery are tracked separately in EXECUTION-STATE.md. Authorized vendor write acceptance remains unrun without supplied test access.

Frozen source: `de6204e1861e27af366cdc9973cf52ce53276add`. Wheel SHA256: `6b39f51174b2988a4240e1b7beb9d5c41dc731cc0826dbbaf0042827e410a44c`. TypeScript tarball SHA256: `b30c81a3493d2f664c79f6b68e863f331450ed4cee95b3597a91341d514cc36d`. Required core CI43228635187 passed at receipt-only descendant9355b640108b0b22fdd6fd500084066571914a00; its package code equals the frozen source. Source regression594passed/8optional browser skips; existing unchanged browser proof is retained.


## Development candidate 0.1.0.dev8

Corrects stale packaged implementation labels for the already-implemented Legistar/Swagit native search, Swagit/Peak/OnBase/Towpath configured discovery, and CivicWeb/Towpath dedicated detail retrieval. Runtime route code is unchanged from dev7. Registered native-search adapters are now checked against their packaged labels, alongside the explicitly changed discovery/detail mappings. Complete catalog and live provider write acceptance remain unclaimed. Dev7 artifacts and proof stay immutable; this distinct version carries the corrected metadata.

Frozen source `3862e5f4ad7064aee722e09bb438899c3566477f`; wheel SHA256 `bcfe691b4d1eb0de162f5f94985d0242a97b5d3d89bd5eeb9306d1ef28caf692`; TypeScript tarball SHA256 `0c11cd41c4361c157151229ba2920b48e4273445d4038a7d6d62aa2eb5de9bf8`. Fresh installed service/package checks pass with all 13 native-search labels implemented. Package module comparison differs from dev7 only in version and capabilities JSON; compiled client bytes are identical, package version only. Existing source, original-format and consumer workflow proof is reused; new capability/version checks passed. Required dev8 hosted CI and final client/native delivery remain separately tracked.
