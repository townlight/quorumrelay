# QuorumRelay architecture

Candidate <code>0.1.0.dev8</code> · schema <code>2.0.0</code>

QuorumRelay is a transport-neutral civic-data engine. The Python engine owns the shared operation and result contract, provider adapters, capture normalization, bounded search, interchange, and write coordination. Applications own caller identity, access policy, service lifecycle, persistent database location, editorial review, and mapping QuorumRelay records into their own canonical records.

The package is independently installable. Its four current consumer examples—TownReporter, Townlight, TownRecord and Brief—are reference integrations; none is a required runtime dependency. The dev8 wheel and source were checked independently; these checks do not establish full provider catalogs, vendor acceptance, or live provider-write acceptance. See [the installed development receipt](verification/quorumrelay-development-08.json) and [the coverage map](ENGINE-COVERAGE.md).

## 1. Components and call path

All interfaces call the same <code>Engine.execute(operation, request, content, context)</code> boundary. The standard factory composes built-in handlers but does not start a server, open a database or contact a provider. A caller can also register a typed connector and an application-owned <code>Storage</code> implementation.

~~~mermaid
flowchart LR
  subgraph Consumer["Consumer product and operator"]
    App["Application workflow"]
    Principal["Authenticated caller policy<br/>principal, client, tenant,<br/>operations, namespaces"]
    Secrets["Trusted private configuration<br/>provider credentials and grants"]
    AppDB["Application-owned records<br/>and editorial decisions"]
  end

  subgraph Surfaces["QuorumRelay interfaces"]
    SDK["Python SDK"]
    CLI["JSON / JSONL CLI"]
    HTTP["REST / file / job API"]
    MCP["MCP stdio / Streamable HTTP"]
    TS["TypeScript HTTP client"]
  end

  subgraph Core["Standalone QuorumRelay package"]
    Factory["create_engine composition"]
    Engine["Engine.execute<br/>shared schema 2.0.0 envelope"]
    ProviderOps["Provider operations<br/>identify / validate / discover / fetch"]
    Parse["Compatibility baseline<br/>and additive capture parsers"]
    Search["Local and registered native search"]
    Interchange["Import preview / persist<br/>and neutral export"]
    Writes["Typed write coordinator<br/>plan / commit / receipt"]
    Storage["Optional scoped Storage<br/>SQLite or consumer implementation"]
  end

  Provider["Configured provider origin"]
  Records["CaptureBundle / Records<br/>originals, identities, citations,<br/>relationships, text and coverage"]

  SDK --> Engine
  CLI --> Engine
  HTTP --> Engine
  MCP --> Engine
  TS --> HTTP
  Factory --> Engine
  Principal --> HTTP
  Principal --> CLI
  Principal --> SDK
  Secrets --> Principal
  Engine --> ProviderOps
  Engine --> Parse
  Engine --> Search
  Engine --> Interchange
  Engine --> Writes
  ProviderOps --> Provider
  Parse --> Records
  ProviderOps --> Records
  Search --> Records
  Interchange --> Records
  Engine <--> Storage
  Interchange <--> Storage
  Writes <--> Storage
  Records --> App
  App --> AppDB
~~~

The arrows to the provider are owned by provider-specific adapters and bounded transport helpers. The HTTP, CLI, MCP and TypeScript layers do not implement provider-specific parsing. The TypeScript package is an HTTP client; it does not start the service. A provider write also uses the shared coordinator rather than a transport-specific mutation path.

## 2. Read and capture lifecycle

A read can begin with an explicitly configured live source or with saved bytes supplied by the caller. The engine normalizes only the available evidence. It retains raw captures and unknown upstream fields so consumers can inspect exactly what was received alongside the shared normalized projection.

~~~mermaid
flowchart TD
  Request["SDK, CLI, REST or MCP request"] --> Validate["Validate operation, Source,<br/>namespace policy and Bounds"]
  Validate --> Capability{"Provider operation<br/>registered and permitted?"}
  Capability -- "No" --> Unsupported["unsupported or failed result<br/>with explicit reason"]
  Capability -- "Yes, live route" --> Route["Provider adapter selects<br/>fixed documented/evidenced route"]
  Capability -- "Yes, saved bytes" --> Saved["Caller supplies exact capture bytes<br/>and input_format"]
  Route --> Bound["Bounded public/account transport<br/>origin, TLS, byte, page,<br/>deadline and cancellation rules"]
  Bound --> Raw["Capture bytes and source metadata<br/>with hash and citation"]
  Saved --> Raw
  Raw --> Parser["Baseline reader or additive parser"]
  Parser --> Model["CaptureBundle and Records<br/>identity, normalized fields,<br/>original values, relationships, text"]
  Model --> Coverage["Coverage and status<br/>dates, pages, records, unknowns,<br/>failures, truncation, checkpoint"]
  Model --> Persist{"Caller explicitly<br/>requests persistence?"}
  Persist -- "No" --> Return["Return full result envelope"]
  Persist -- "Yes, storage configured" --> Scoped["Atomic scoped storage<br/>records, captures and history"]
  Scoped --> Return
~~~

Shared defaults are bounded: up to 1,000 records, 25 pages, 16 MiB parser bytes, 200 MiB transfer bytes and a 45-second operation deadline. Service transports impose their own outer request and timeout limits. Providers can impose smaller limits or require stricter filters. A response reaching one of these boundaries is reported as partial when appropriate; a bounded window is not a complete provider archive.

A <code>CaptureBundle</code> groups records with the configured source, capture metadata and a compatibility projection. Each record keeps source identity separately from normalized hashes, upstream revision and the destination application’s record ID. Local IDs derived from capture position retain their derivation and stability limits; they are never relabeled as provider-issued IDs. Text segments retain the supplied field, citation and provenance. A missing transcript, document, timezone or meeting body remains unknown.

The current fixed baseline preserves all 34 historical provider/input-format pairs. Twenty-eight additive parser hooks replay additional captured formats. These are separate from live discovery and from the selected provider’s exact operation coverage. Use the installed <code>providers</code> manifest and [capability inventory](capabilities/README.md) for provider-by-provider detail.

## 3. Trust boundaries and scoped state

The service authenticates a consumer before constructing a trusted principal context. The context and provider credentials are private inputs to the engine, not public request fields. A source namespace describes an upstream source identity; consumer tenant identifies whose stored work is being accessed. Those values serve different purposes and are checked independently.

~~~mermaid
flowchart LR
  subgraph Untrusted["Untrusted caller input"]
    Req["JSON request<br/>source, filters, bounds"]
    File["Uploaded bytes<br/>or linked source content"]
    ProviderData["Provider response<br/>HTML, JSON, PDF, captions"]
  end

  subgraph ServiceBoundary["Application-owned trust boundary"]
    Auth["Authenticate client/user"]
    Policy["Trusted principal policy<br/>operations and namespaces"]
    Credential["Secret manager / protected config<br/>provider-specific credentials"]
    Context["OperationContext<br/>caller scope, current grants,<br/>private credentials, cancellation"]
    Store["Storage partitioned by hash of<br/>principal + client + consumer tenant"]
  end

  subgraph EngineBoundary["QuorumRelay boundary"]
    Gate["Reject identity/grants/credentials<br/>from public request JSON"]
    Guard["Validate source namespace,<br/>fixed routes and public transport"]
    Engine["Shared engine and provider adapter"]
    Capture["Hash, preserve and parse<br/>bounded supplied data"]
  end

  Upstream["Configured upstream origin"]
  App["Consumer review and<br/>application record mapping"]

  Req --> Auth --> Policy --> Context
  Credential --> Context
  Req --> Gate --> Engine
  File --> Capture
  Context --> Gate
  Gate --> Guard --> Upstream
  Upstream --> ProviderData --> Capture --> Engine
  Engine <--> Store
  Engine --> App
~~~

The HTTP service defaults to loopback. Binding to another interface requires explicit network configuration, authenticated token policies and an explicit non-wildcard Host allowlist. Origin policy applies before request dispatch. Deployments terminate TLS at an operator-managed reverse proxy. Authenticated MCP additionally requires its resource URL, issuer and a verifier appropriate to the host; the built-in opaque service-token map is not a general OAuth authorization server.

An operation scope is a hash of principal, client ID and consumer tenant. SQLite storage uses that scope for key/value state and capture blobs; compare-and-set and create-only operations protect updates. Caller identity must not be supplied by request JSON or an arbitrary tenant header. An access token is not forwarded to provider URLs. Provider credentials are loaded by the application into the private context and bound to the provider’s exact origin/tenant/namespace contract.

Provider content is untrusted data, never an instruction to the engine or consumer. Public outbound requests are constrained to expected HTTP(S) origins, validated DNS destinations and bounded redirects/bytes/deadlines. Cross-origin credential forwarding is stripped or rejected. File uploads resolve to opaque scoped handles rather than filesystem paths. Downloads are limited by caller scope, current grants, expiry and recorded byte/hash information.

## 4. Write plan, commit and recovery

Provider writes are a separately authorized lifecycle. The plan binds the exact source, actor scope, provider-native change, parent/resource identity, expected version, credentials policy and any staged file hashes. A plan hash is not authorization; the application’s trusted policy must authorize planning and the exact plan commit.

~~~mermaid
sequenceDiagram
  actor Caller as Application caller
  participant Engine as QuorumRelay Engine
  participant Adapter as Typed provider adapter
  participant Store as Atomic scoped storage
  participant Provider as Configured provider

  Caller->>Engine: plan_write(source, changes)
  Engine->>Engine: Check operation grant, namespace and exact fields
  Engine->>Adapter: Validate native mapping and target
  Adapter->>Provider: Read before state when mapping requires it
  Provider-->>Adapter: Bounded before state
  Adapter-->>Engine: Immutable native request and preview
  Engine->>Store: Create exact plan and SHA-256 plan hash
  Store-->>Engine: Durable plan ID
  Engine-->>Caller: Plan preview, plan ID and hash
  Caller->>Caller: Review and authorize this exact plan
  Caller->>Engine: commit_write(plan ID, plan hash)
  Engine->>Store: Atomically claim and persist execution intent
  Engine->>Adapter: Apply only the approved plan
  Adapter->>Provider: Fixed documented mutation request
  Provider-->>Adapter: Bounded response or uncertain outcome
  Adapter->>Provider: Read back / reconcile according to mapping
  Provider-->>Adapter: Current provider state
  Adapter-->>Engine: Success, conflict, failure or uncertainty
  Engine->>Store: Persist receipt and per-item state
  Engine-->>Caller: Commit result; receipt remains queryable
~~~

Planning requires <code>write:plan</code>; commit requires <code>write:commit</code> plus the exact stored plan ID and digest. The engine does not accept edited client-returned plans. An execution intent is persisted before sending a mutation. Duplicate commits consult the durable receipt; if a response is lost, the adapter reconciles the original intent before any retry. Uncertain outcomes remain uncertain until the provider state can be identified. Successful siblings remain in partial batches; remote side effects are not rolled back automatically.

The engine exposes no arbitrary delete, vendor administration, unrestricted upload, guessed provider route or generic “publish this meeting” operation. An adapter exists only for its documented native mappings. Required provider account permissions and request/response behavior still need acceptance in an authorized test environment. For this candidate, live provider-write acceptance is **NOT_RUN**: the authorized test tenants and credentials were not supplied. Synthetic transport results exercise the same mapping logic without changing provider data.

## 5. Module boundaries

| Area | Source | Responsibility |
|---|---|---|
| Public types and engine | <code>models.py</code>, <code>engine.py</code>, <code>factory.py</code> | Versioned contracts, dispatch, operation bounds and standard composition |
| Provider identity, discovery and fetch | <code>providers/</code>, <code>capabilities.py</code> | Canonical IDs, fixed route mappings, provider captures, attachment/detail handlers and additive parser registration |
| Historical compatibility readers | <code>compat.py</code>, <code>normalization.py</code>, <code>legacy.py</code> | Preserve the 34 original reader outputs and carefully project legacy identities |
| Shared state | <code>storage.py</code>, <code>extensions.py</code> | Scoped atomic key/value storage and content-addressed captures |
| Search and interchange | <code>search.py</code>, <code>imports.py</code>, <code>interchange.py</code> | Local/native search, preview, explicit persistence, portable export and file artifacts |
| Writes | <code>writes.py</code>, <code>write_adapters.py</code>, <code>write_transport.py</code>, <code>write_files.py</code> | Immutable plans, native field mapping, bounded transport, file staging and durable receipts |
| Interfaces | <code>transports/</code>, <code>cli.py</code>, <code>client/</code> | HTTP, MCP, CLI and TypeScript request/response adaptation |

Read the [engine contract](ENGINE-CONTRACT.md) for types, bounds and extension protocols, the [write contract](WRITE-CONTRACT.md) for native mapping details, and the [user manual](USER-MANUAL.md) for installation and operating procedures.
