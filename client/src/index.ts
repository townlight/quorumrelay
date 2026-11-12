import type { OperationResult } from "./generated.js";
export type * from "./generated.js";

export type Operation =
  | "providers" | "capabilities" | "identify" | "validate_source" | "discover" | "fetch"
  | "normalize" | "search" | "import_preview" | "import_bundle" | "export"
  | "plan_write" | "commit_write" | "receipt" | "status" | "cancel";

export interface ClientOptions {
  /** Service root, explicitly owned/configured by the deploying application. */
  baseUrl: string;
  /** Local service token, not a provider credential. */
  token?: string;
  timeoutMs?: number;
  fetch?: typeof globalThis.fetch;
}

export class ServiceError extends Error {
  constructor(message: string, readonly httpStatus: number, readonly result?: OperationResult) {
    super(message);
    this.name = "ServiceError";
  }
}

function envelope(value: unknown): OperationResult {
  if (typeof value !== "object" || value === null) throw new TypeError("Invalid connector response.");
  const row = value as Record<string, unknown>;
  if (row.schema_version !== "2.0.0" || !["completed", "partial", "cancelled", "failed", "unsupported"].includes(String(row.status))
      || !Array.isArray(row.errors) || typeof row.coverage !== "object" || row.coverage === null
      || !("data" in row) || !(row.operation_id === null || typeof row.operation_id === "string")) {
    throw new TypeError("Connector response does not match schema 2.0.0.");
  }
  return row as OperationResult;
}

export class CivicConnectorClient {
  readonly baseUrl: string;
  private readonly options: ClientOptions;
  private readonly fetcher: typeof globalThis.fetch;

  constructor(options: ClientOptions) {
    if (!options.baseUrl) throw new TypeError("An explicit connector service baseUrl is required.");
    const url = new URL(options.baseUrl);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
      throw new TypeError("Use an HTTP(S) service root without credentials, query, or fragment.");
    }
    if (options.timeoutMs !== undefined && (!Number.isFinite(options.timeoutMs) || options.timeoutMs <= 0)) {
      throw new TypeError("timeoutMs must be positive.");
    }
    this.baseUrl = url.href.replace(/\/$/, "");
    this.options = options;
    this.fetcher = options.fetch ?? globalThis.fetch;
  }

  private async request(path: string, init: RequestInit, signal?: AbortSignal): Promise<Response> {
    // Keep cancellation live after headers arrive, including while response bodies stream.
    const timeout = AbortSignal.timeout(this.options.timeoutMs ?? 60_000);
    const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout;
    const headers = new Headers(init.headers);
    if (this.options.token) headers.set("Authorization", `Bearer ${this.options.token}`);
    return this.fetcher(this.baseUrl + path, { ...init, headers, signal: requestSignal, redirect: "error" });
  }

  private async json(path: string, init: RequestInit, signal?: AbortSignal): Promise<OperationResult> {
    const response = await this.request(path, init, signal);
    const result = envelope(await response.json());
    if (!response.ok) throw new ServiceError(`Connector service returned HTTP ${response.status}.`, response.status, result);
    return result;
  }

  /** Returns the complete engine envelope. A partial/failed engine result is not flattened or hidden. */
  execute(operation: Operation, request: Record<string, unknown> = {}, options: { signal?: AbortSignal } = {}): Promise<OperationResult> {
    return this.json(`/v1/operations/${encodeURIComponent(operation)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
    }, options.signal);
  }

  submit(operation: Operation, request: Record<string, unknown> = {}, options: { signal?: AbortSignal } = {}): Promise<OperationResult> {
    return this.json(`/v1/jobs/${encodeURIComponent(operation)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
    }, options.signal);
  }

  info(options: { signal?: AbortSignal } = {}): Promise<OperationResult> {
    return this.json("/v1/info", { method: "GET" }, options.signal);
  }

  upload(file: Blob, options: { signal?: AbortSignal } = {}): Promise<OperationResult> {
    const body = new FormData();
    body.append("file", file, "capture.bin");
    return this.json("/v1/files", { method: "POST", body }, options.signal);
  }

  /** Caller owns consuming/closing the byte stream; download does not buffer the file. */
  async download(handle: string, options: { signal?: AbortSignal } = {}): Promise<Response> {
    if (!/^([0-9a-f]{48}|[0-9a-f]{64})$/.test(handle)) throw new TypeError("Invalid opaque file handle.");
    const response = await this.request(`/v1/files/${handle}`, { method: "GET" }, options.signal);
    if (!response.ok) {
      const result = envelope(await response.json());
      throw new ServiceError(`Connector download returned HTTP ${response.status}.`, response.status, result);
    }
    return response;
  }
}

/** Canonical QuorumRelay name; the earlier client name remains compatible. */
export { CivicConnectorClient as QuorumRelayClient };
