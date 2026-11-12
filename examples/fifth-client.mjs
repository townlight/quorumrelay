// Run from an unrelated npm project after installing the packed client tarball.
import assert from "node:assert/strict";
import { QuorumRelayClient } from "quorumrelay-client";

const client = new QuorumRelayClient({
  baseUrl: process.env.CIVIC_CONNECTOR_URL,
  token: process.env.CIVIC_CONNECTOR_TOKEN,
});
const info = await client.info();
assert.equal(info.data.version, "0.1.0.dev4");
assert.equal(info.data.schema_version, "2.0.0");
const raw = [{ EventId: 7, EventBodyName: "Council", EventDate: "2026-11-11T00:00:00",
  EventTime: "7:00 PM", EventComment: "Parks budget", EventRowVersion: "r7" }];
const discovered = await client.execute("discover", {
  source: { provider: "legistar", url: "https://mock-city.legistar.com/Calendar.aspx", input_format: "legistar-events-json" },
  bounds: { date_from: "2026-11-11", date_to: "2026-11-11" },
  content_base64: Buffer.from(JSON.stringify(raw)).toString("base64"),
});
assert.equal(discovered.status, "partial"); // Saved capture is not a complete live catalog.
const preview = await client.execute("import_preview", { result: discovered });
const imported = await client.execute("import_bundle", { result: discovered, persist: true });
const searched = await client.execute("search", { query: { terms: ["Council"] } });
assert.equal(preview.data.persisted, false);
assert.equal(imported.data.persisted, true);
assert.ok(searched.data.hits.length >= 1);
const exported = await client.execute("export", { bundle: imported.data.bundle, format: "zip", stream: true });
const download = await client.download(exported.data.file_handle);
const bytes = new Uint8Array(await download.arrayBuffer());
assert.equal(Buffer.from(bytes.subarray(0, 2)).toString(), "PK");
// The documented example server supplies a synthetic upstream. Never commit a real plan here.
const planned = await client.execute("plan_write", {
  source: {provider: "legistar", url: "https://webapi.legistar.com/v1/mock-city/events", namespace: "mock-city"},
  changes: [{key: "fifth-client-example", entity: "event", operation: "create",
    fields: {EventDate: "2026-11-11T00:00:00", EventBodyId: 4}}],
});
assert.equal(planned.data.plan.mock, true, "The example refuses non-mock writes.");
const approval = {plan_id: planned.data.plan_id, plan_hash: planned.data.plan_hash};
const committed = await client.execute("commit_write", approval);
const receipt = await client.execute("receipt", {plan_id: approval.plan_id});
assert.deepEqual(committed.data, receipt.data);
assert.equal(receipt.data.mock, true);
console.log(JSON.stringify({ mode: "synthetic", live_acceptance: "NOT_RUN",
  discover: discovered.status, preview_persisted: preview.data.persisted,
  hits: searched.data.hits.length, exported_bytes: bytes.length, mock_receipt: receipt.data.mock }));
