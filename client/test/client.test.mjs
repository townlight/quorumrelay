import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";
import test from "node:test";
import { CivicConnectorClient } from "../dist/index.js";

async function slowServer(run) {
  const timers = new Set();
  const server = createServer((req, res) => {
    res.writeHead(200, { "Content-Type": req.url.startsWith("/v1/files/") ? "application/octet-stream" : "application/json" });
    if (req.url.startsWith("/v1/files/")) {
      res.write("start");
      const timer = setTimeout(() => res.end("end"), 1000);
      timers.add(timer);
    } else {
      // Headers and first body bytes arrive promptly; the rest deliberately stalls.
      res.write('{"schema_version":"2.0.0",');
      const timer = setTimeout(() => res.end('"status":"completed","data":null,"errors":[],"coverage":{},"operation_id":null}'), 1000);
      timers.add(timer);
    }
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  try { await run(`http://127.0.0.1:${server.address().port}`); }
  finally {
    for (const timer of timers) clearTimeout(timer);
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
}

test("JSON timeout stays active after actual HTTP response headers", async () => {
  await slowServer(async baseUrl => {
    const client = new CivicConnectorClient({ baseUrl, timeoutMs: 80 });
    const start = performance.now();
    await assert.rejects(() => client.info(), error => ["AbortError", "TimeoutError"].includes(error.name));
    assert.ok(performance.now() - start < 600, "stalled body must not survive the request timeout");
  });
});

test("caller abort reaches an actual JSON response body after headers", async () => {
  await slowServer(async baseUrl => {
    const controller = new AbortController();
    const client = new CivicConnectorClient({ baseUrl, timeoutMs: 5000 });
    const pending = client.info({ signal: controller.signal });
    const timer = setTimeout(() => controller.abort(), 80);
    try { await assert.rejects(() => pending, error => error.name === "AbortError"); }
    finally { clearTimeout(timer); }
  });
});

test("download caller abort remains connected while consuming bytes", async () => {
  await slowServer(async baseUrl => {
    const controller = new AbortController();
    const client = new CivicConnectorClient({ baseUrl, timeoutMs: 5000 });
    const response = await client.download("a".repeat(64), { signal: controller.signal });
    controller.abort();
    await assert.rejects(() => response.arrayBuffer(), error => error.name === "AbortError");
  });
});

test("download timeout remains active while consuming bytes", async () => {
  await slowServer(async baseUrl => {
    const client = new CivicConnectorClient({ baseUrl, timeoutMs: 80 });
    const response = await client.download("b".repeat(64));
    await assert.rejects(() => response.arrayBuffer(), error => ["AbortError", "TimeoutError"].includes(error.name));
  });
});
