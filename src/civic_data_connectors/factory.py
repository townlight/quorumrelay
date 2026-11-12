"""Default composition. Services and application databases remain caller-owned."""

from __future__ import annotations

from .engine import Engine
from .extensions import Connector, Storage


def create_engine(
    *, storage: Storage | None = None, connectors: tuple[Connector, ...] = (),
    provider_transport=None, provider_browser=None, write_adapters: dict | None = None,
    write_approval=None,
) -> Engine:
    """Register the shared engine operations without starting services or fetching.

    ``write_adapters=None`` uses evidenced built-in adapters; an explicit empty
    dictionary disables them. Neither choice grants write authorization or
    supplies credentials. Caller-owned storage is optional.
    """
    from . import imports, interchange, providers, search, storage as storage_operations, writes

    engine = Engine(storage=storage, connectors=connectors)
    providers.register(engine, transport=provider_transport, browser=provider_browser)
    storage_operations.register(engine)
    imports.register(engine)
    search.register(engine)
    interchange.register(engine)
    writes.register(engine, adapters=write_adapters, approval=write_approval)
    return engine
