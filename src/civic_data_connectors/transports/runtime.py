"""Explicit engine composition and trusted caller configuration, without provider logic."""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass, field, fields
from pathlib import Path

from .. import Engine
from ..models import Error, OperationContext, OperationResult

OPERATIONS = (
    "providers", "capabilities", "identify", "validate_source", "discover", "fetch",
    "normalize", "search", "import_preview", "import_bundle", "export",
    "plan_write", "commit_write", "receipt", "status", "cancel",
)
READ_OPERATIONS = frozenset(OPERATIONS) - {"plan_write", "commit_write"}


def failure(code: str, message: str, *, operation_id=None) -> OperationResult:
    return OperationResult("failed", errors=(Error(code, message),), operation_id=operation_id)


@dataclass(frozen=True)
class Principal:
    principal: str = "local"
    client_id: str = "cli"
    tenant: str | None = None
    operations: frozenset[str] = READ_OPERATIONS
    authorization: frozenset[str] = frozenset()
    credentials: dict = field(default_factory=dict, repr=False)
    allowed_namespaces: frozenset[str] | None = None

    def context(self) -> OperationContext:
        args = dict(principal=self.principal, client_id=self.client_id, tenant=self.tenant,
                    authorization=self.authorization, credentials=dict(self.credentials))
        if "allowed_operations" in {f.name for f in fields(OperationContext)}:
            args["allowed_operations"] = self.operations
        if "allowed_namespaces" in {f.name for f in fields(OperationContext)}:
            args["allowed_namespaces"] = self.allowed_namespaces
        return OperationContext(**args)

    @classmethod
    def from_dict(cls, value: dict):
        if not isinstance(value, dict):
            raise ValueError("A trusted principal policy must be an object.")
        value = dict(value)
        for key in ("operations", "authorization", "allowed_namespaces"):
            if key in value and not (key == "allowed_namespaces" and value[key] is None):
                if not isinstance(value[key], list) or any(not isinstance(x, str) for x in value[key]):
                    raise ValueError(f"Trusted {key} policy must be an array of strings.")
                value[key] = frozenset(value[key])
        result = cls(**value)
        if not result.operations <= set(OPERATIONS):
            raise ValueError("Trusted policy contains an unknown operation.")
        return result


@dataclass
class ServiceConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    allow_network: bool = False
    tokens: dict[str, Principal] = field(default_factory=dict, repr=False)
    local: Principal = field(default_factory=lambda: Principal(client_id="local-service"))
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "[::1]")
    allowed_origins: tuple[str, ...] = ()
    json_bytes: int = 24 * 1024 * 1024
    parser_bytes: int = 16 * 1024 * 1024
    transfer_bytes: int = 200 * 1024 * 1024
    request_timeout: float = 60
    public_url: str | None = None
    issuer_url: str | None = None
    mcp: bool = False

    def validate(self):
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            if not self.allow_network or not self.tokens:
                raise ValueError("Network binding requires explicit allow_network and authenticated token policy.")
            if not self.allowed_hosts or "*" in self.allowed_hosts:
                raise ValueError("Network deployment requires an explicit Host allowlist.")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be an integer in 1..65535.")
        for value in (self.json_bytes, self.parser_bytes, self.transfer_bytes):
            if type(value) is not int or value <= 0:
                raise ValueError("Service byte limits must be positive integers.")
        if not 0 < self.request_timeout <= 3600:
            raise ValueError("request_timeout must be in (0, 3600].")
        if any(not token or len(token) < 16 for token in self.tokens):
            raise ValueError("Service tokens must contain at least 16 characters.")
        if self.mcp and self.tokens and (not self.public_url or not self.issuer_url):
            raise ValueError("Authenticated MCP requires public_url and issuer_url resource-server configuration.")

    def authenticate(self, header: str | None) -> Principal | None:
        if not self.tokens:
            return self.local
        if not header or not header.startswith("Bearer "):
            return None
        token = header[7:]
        for candidate, principal in self.tokens.items():
            if hmac.compare_digest(token.encode("utf-8"), candidate.encode("utf-8")):
                return principal
        return None

    @classmethod
    def from_dict(cls, value: dict):
        value = dict(value)
        if "tokens" in value:
            value["tokens"] = {token: Principal.from_dict(policy)
                               for token, policy in value["tokens"].items()}
        if "local" in value:
            value["local"] = Principal.from_dict(value["local"])
        for key in ("allowed_hosts", "allowed_origins"):
            if key in value:
                value[key] = tuple(value[key])
        result = cls(**value)
        result.validate()
        return result


def load_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("Configuration must be a JSON object.")
    return value


def build_engine(*, database: str | Path | None = None) -> Engine:
    """Composition is explicit. All provider behavior belongs to registered owners."""
    from .. import create_engine
    from ..storage import SQLiteStorage
    return create_engine(storage=SQLiteStorage(database) if database else None)


def execute(engine: Engine, principal: Principal, operation: str, request: dict, *,
            content: bytes | None = None, context: OperationContext | None = None) -> OperationResult:
    context = context or principal.context()
    if operation not in OPERATIONS:
        return failure("unknown_operation", "The requested operation is not part of this API.")
    if operation not in principal.operations:
        return failure("permission_denied", "The configured caller policy does not permit this operation.")
    if isinstance(request, dict) and any(key in request for key in
                                        ("authorization", "credentials", "principal", "client_id", "tenant", "context")):
        return failure("invalid_request", "Identity, credentials and grants are not operation arguments.")
    return engine.execute(operation, request, content=content, context=context)


def bound_request(operation, request, config):
    """Apply configured service resource ceilings without changing provider semantics."""
    if operation in {"providers", "capabilities", "identify", "validate_source", "receipt",
                     "commit_write", "status", "cancel"}:
        return request
    payload = dict(request)
    bounds = dict(payload.get("bounds", {}))
    for key, maximum in (("parser_bytes", config.parser_bytes),
                         ("transfer_bytes", config.transfer_bytes),
                         ("deadline_seconds", config.request_timeout)):
        value = bounds.get(key, maximum)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Request bounds must be numeric.")
        bounds[key] = min(value, maximum)
    payload["bounds"] = bounds
    return payload
