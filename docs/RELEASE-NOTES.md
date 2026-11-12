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

Source work for the next development candidate includes Legistar supplied
vote/attendance reads, Laserfiche Repository folder listings, and preparation
of the documented CivicPlus historical PDF filenames. The latter produces a ZIP
delivery wrapper containing named files and a loss manifest; it does not submit
files, prove vendor ZIP import, or claim the unresolved MP4/filename mappings.
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
