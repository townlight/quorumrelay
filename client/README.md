# QuorumRelay HTTP client

Requires Node 20.3+ and an explicitly configured running connector service.
The owning application starts/stops the Python service, pins its version, owns
its durable SQLite state, and supplies separate caller-scoped service tokens.
This package never starts a service or discovers a localhost port.

```typescript
import { QuorumRelayClient, type RecordEnvelope } from "quorumrelay-client";
const client = new QuorumRelayClient({
  baseUrl: process.env.CIVIC_CONNECTOR_URL!,
  token: process.env.CIVIC_CONNECTOR_TOKEN,
});
const result = await client.execute("providers", {});
// Always inspect status, errors, and coverage. Partial is not complete.
```

For checkout development: `npm install && npm run build`.
For an unrelated fifth client: `npm pack` and install the resulting tarball
with `npm install <absolute-path-to-tarball>`. No reference product is needed.
Types are generated from packaged core schemas using
`python generate_types.py`; commit generated source with schema changes.
Engine failure remains an envelope. HTTP failure throws `ServiceError` carrying
the same envelope; network/abort errors remain distinct native errors.
Pass `{signal}` to execute/submit/upload/download/info for cancellation.
