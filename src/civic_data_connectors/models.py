"""Transport-neutral versioned contracts. Unknown upstream fields live in raw data."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date
from math import isfinite
from threading import Event
from typing import Any, Callable, Literal
from urllib.parse import parse_qsl, unquote_plus, urlsplit, urlunsplit

SCHEMA_VERSION = "2.0.0"
Status = Literal["completed", "partial", "cancelled", "failed", "unsupported"]

_CREDENTIAL_KEYS = frozenset({
    "token", "apikey", "accesstoken", "idtoken", "refreshtoken", "password",
    "authorization", "cookie", "clientsecret", "credentials", "credential", "secret",
})


def _credential_key(key):
    return isinstance(key, str) and key.casefold().replace("_", "").replace("-", "") in _CREDENTIAL_KEYS


def _credential_error(path):
    return ValueError(
        f"Credential-bearing key at {path}; put credentials in private "
        "OperationContext.credentials using the provider's documented shape "
        "(for example, legistar_token for Legistar reads), never Source URLs or options."
    )


def _check_source_credentials(url, options):
    for key, _value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        if _credential_key(key):
            raise _credential_error(f"Source.url.query[{key!r}]")
    if not isinstance(options, dict):
        raise ValueError("Source.options must be an object.")
    pending, seen = [(options, "Source.options")], set()
    while pending:
        value, path = pending.pop()
        if not isinstance(value, (dict, list, tuple)) or id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, dict):
            for key, item in value.items():
                child = f"{path}[{key!r}]"
                if _credential_key(key):
                    raise _credential_error(child)
                pending.append((item, child))
        else:
            pending.extend((item, f"{path}[{index}]") for index, item in enumerate(value))


def citation_url(url: str) -> str:
    """Remove authentication from durable citations, not lossless raw captures."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    retained = []
    for part in parsed.query.split("&"):
        key = unquote_plus(part.partition("=")[0])
        normalized = key.casefold().replace("_", "").replace("-", "")
        if (_credential_key(key) or normalized in {"signature", "sig"}
                or key.casefold().startswith(("x-amz-", "x-goog-"))):
            continue
        retained.append(part)
    query = "&".join(retained)
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    if query == parsed.query and netloc == parsed.netloc:
        return url
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


def _public(value):
    if is_dataclass(value):
        return {**{f.name: _public(getattr(value, f.name)) for f in fields(value)},
                **deepcopy(getattr(value, "_unknown", {}))}
    if isinstance(value, dict):
        return {key: _public(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_public(item) for item in value]
    return deepcopy(value)


def _from_dict(cls, value: dict, **converted):
    known = {item.name for item in fields(cls)}
    obj = cls(**{key: converted.get(key, item) for key, item in value.items() if key in known})
    object.__setattr__(obj, "_unknown", {key: deepcopy(item) for key, item in value.items() if key not in known})
    return obj


@dataclass(frozen=True)
class Source:
    provider: str
    url: str
    namespace: str | None = None
    body: str | None = None
    input_format: str | None = None
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        parsed = urlsplit(self.url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None):
            raise ValueError("A source requires an HTTP(S) citation URL without embedded credentials.")
        _check_source_credentials(self.url, self.options)
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("A source requires a provider.")
        from .capabilities import canonical_provider_id
        object.__setattr__(self, "provider", canonical_provider_id(self.provider, allow_extension=True))
        if self.namespace is not None and (not isinstance(self.namespace, str) or not self.namespace):
            raise ValueError("An explicitly configured namespace cannot be empty.")

    def public_dict(self) -> dict:
        _check_source_credentials(self.url, self.options)
        return _public(self)

    @classmethod
    def from_dict(cls, value: dict) -> Source:
        return _from_dict(cls, value)


@dataclass(frozen=True)
class Bounds:
    date_from: str | None = None
    date_to: str | None = None
    max_records: int = 1000
    max_pages: int = 25
    parser_bytes: int = 16 * 1024 * 1024
    transfer_bytes: int = 200 * 1024 * 1024
    deadline_seconds: float = 45
    checkpoint: str | None = None

    def __post_init__(self):
        for name in ("max_records", "max_pages", "parser_bytes", "transfer_bytes"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer.")
        if (type(self.deadline_seconds) not in {float, int} or not isfinite(self.deadline_seconds)
                or self.deadline_seconds <= 0 or self.deadline_seconds > 3600):
            raise ValueError("deadline_seconds must be in (0, 3600].")
        for value in (self.date_from, self.date_to):
            if value is not None:
                date.fromisoformat(value)
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from cannot be later than date_to.")


@dataclass(frozen=True)
class Query:
    terms: tuple[str, ...] = ()
    phrases: tuple[str, ...] = ()
    namespaces: tuple[str, ...] = ()
    providers: tuple[str, ...] = ()
    body: str | None = None
    record_types: tuple[str, ...] = ()
    date_from: str | None = None
    date_to: str | None = None
    limit: int = 100

    def __post_init__(self):
        Bounds(date_from=self.date_from, date_to=self.date_to, max_records=self.limit)
        for key in ("terms", "phrases", "namespaces", "providers", "record_types"):
            value = getattr(self, key)
            if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
                raise ValueError(f"{key} must be an array of strings.")


@dataclass(frozen=True)
class Identity:
    provider: str
    namespace: str
    record_type: str
    external_id: str
    parent: dict | None = None
    derivation: str = "provider_or_legacy_reader"
    stability: str = "See the input-format identity mapping; not an application record identifier."

    def public_dict(self) -> dict:
        return _public(self)

    @classmethod
    def from_dict(cls, value: dict) -> Identity:
        return _from_dict(cls, value)


@dataclass(frozen=True)
class Record:
    identity: Identity
    normalized: dict[str, Any]
    source_url: str
    citation_urls: tuple[str, ...]
    capture_sha256: str
    captured_at: str
    normalized_sha256: str
    source_revision: dict[str, Any]
    original: Any = None
    relationships: tuple[dict[str, Any], ...] = ()
    text: tuple[dict[str, Any], ...] = ()
    extensions: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        object.__setattr__(self, "citation_urls",
                           tuple(dict.fromkeys(citation_url(url) for url in self.citation_urls)))
        object.__setattr__(self, "text", tuple(
            {**segment, "citation_url": citation_url(segment["citation_url"])}
            if isinstance(segment, dict) and isinstance(segment.get("citation_url"), str) else segment
            for segment in self.text
        ))

    def public_dict(self) -> dict:
        return _public(self)

    @classmethod
    def from_dict(cls, value: dict) -> Record:
        return _from_dict(cls, value, identity=Identity.from_dict(value["identity"]))


@dataclass(frozen=True)
class CaptureBundle:
    source: Source
    records: tuple[Record, ...]
    capture: dict[str, Any]
    compatibility: dict[str, Any]
    extensions: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def public_dict(self) -> dict:
        return _public(self)

    @classmethod
    def from_dict(cls, value: dict) -> CaptureBundle:
        return _from_dict(cls, value, source=Source.from_dict(value["source"]),
                          records=tuple(Record.from_dict(item) for item in value["records"]))


@dataclass(frozen=True)
class Error:
    code: str
    message: str
    retryable: bool = False
    source: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict:
        return _public(self)


@dataclass(frozen=True)
class OperationResult:
    status: Status
    data: Any = None
    errors: tuple[Error, ...] = ()
    coverage: dict[str, Any] = field(default_factory=dict)
    operation_id: str | None = None
    schema_version: str = SCHEMA_VERSION

    def public_dict(self) -> dict:
        return _public(self)

    @classmethod
    def from_dict(cls, value: dict) -> OperationResult:
        return _from_dict(cls, value, errors=tuple(_from_dict(Error, item) for item in value.get("errors", [])))

    @classmethod
    def unsupported(cls, operation: str, *, reason: str = "This operation is not implemented.") -> OperationResult:
        return cls("unsupported", errors=(Error("operation_unavailable", reason, details={"operation": operation}),))


@dataclass
class OperationContext:
    """Caller-owned state; do not put credentials into public requests/results."""

    principal: str = "local"
    client_id: str = "sdk"
    tenant: str | None = None
    authorization: frozenset[str] = frozenset()
    cancellation: Event = field(default_factory=Event)
    progress: Callable[[dict], None] | None = None
    credentials: dict[str, Any] = field(default_factory=dict, repr=False)
    operation_id: str | None = None
    allowed_operations: frozenset[str] | None = None
    allowed_namespaces: frozenset[str] | None = None

    def allows(self, operation: str, namespace: str | None = None) -> bool:
        return ((self.allowed_operations is None or operation in self.allowed_operations)
                and (namespace is None or self.allowed_namespaces is None or namespace in self.allowed_namespaces))

    def check_cancelled(self) -> bool:
        return self.cancellation.is_set()

    def report(self, **progress):
        if self.progress:
            self.progress(progress)

    @property
    def scope(self) -> str:
        import hashlib
        import json

        return hashlib.sha256(json.dumps(
            [self.principal, self.client_id, self.tenant], separators=(",", ":"),
        ).encode()).hexdigest()
