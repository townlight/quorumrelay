"""Connector and storage extension protocols shared by every interface."""

from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from typing import Any, Protocol, runtime_checkable

from .models import Bounds, OperationContext, OperationResult, Query, Source


@runtime_checkable
class Storage(Protocol):
    """The caller owns isolation, persistence and retention of each scoped value."""

    def put(self, collection: str, key: str, value: dict, *, scope: str,
            expected_version: str | None = None, create_only: bool = False) -> str: ...
    def get(self, collection: str, key: str, *, scope: str) -> StoredValue | None: ...
    def list(self, collection: str, *, scope: str) -> list[StoredValue]: ...


@dataclass(frozen=True)
class StoredValue:
    key: str
    value: dict
    version: str


class StorageConflict(ValueError):
    """An atomic create/version comparison failed; the original value is unchanged."""


@runtime_checkable
class Connector(Protocol):
    provider: str

    def capabilities(self) -> dict[str, Any]: ...
    def identify(self, url: str) -> OperationResult: ...
    def discover(self, source: Source, bounds: Bounds, context: OperationContext) -> OperationResult: ...
    def fetch(self, source: Source, request: dict, bounds: Bounds,
              context: OperationContext) -> OperationResult: ...
    def parse(self, source: Source, content: bytes, input_format: str,
              bounds: Bounds, context: OperationContext) -> OperationResult: ...
    def native_search(self, source: Source, query: Query, bounds: Bounds,
                      context: OperationContext) -> OperationResult: ...
    def export(self, source: Source, request: dict, context: OperationContext) -> OperationResult: ...
    def plan_write(self, source: Source, request: dict, context: OperationContext) -> OperationResult: ...
    def commit_write(self, source: Source, request: dict, context: OperationContext) -> OperationResult: ...


def check_connector(connector: Connector) -> list[str]:
    """Return conformance failures without making requests or writes."""
    failures = []
    if not isinstance(getattr(connector, "provider", None), str) or not connector.provider:
        failures.append("provider must be a nonempty string")
    arities = {"capabilities": 0, "identify": 1, "discover": 3, "fetch": 4, "parse": 5,
               "native_search": 4, "export": 3, "plan_write": 3, "commit_write": 3}
    for method, arity in arities.items():
        hook = getattr(connector, method, None)
        if not callable(hook):
            failures.append(f"{method} must be callable")
        else:
            try:
                signature(hook).bind(*([None] * arity))
            except (ValueError, TypeError):
                failures.append(f"{method} must accept the {arity} positional arguments declared by Connector")
    if not failures:
        capabilities = connector.capabilities()
        if not isinstance(capabilities, dict):
            failures.append("capabilities must return a dictionary")
    return failures
