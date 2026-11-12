"""Packaged provider identity and evidence inventory, separate from runtime grants."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files

from .compat import source_formats


@lru_cache(maxsize=1)
def _identities():
    return json.loads(files("civic_data_connectors").joinpath("data/provider-identities.json").read_text("utf-8"))


def canonical_provider_id(provider: str, *, allow_extension: bool = False) -> str:
    if not isinstance(provider, str):
        raise ValueError("A provider ID must be a string.")
    provider = provider.strip().lower()
    result = _identities()["alias_to_canonical"].get(provider)
    if result is None:
        if allow_extension:
            return provider
        raise ValueError("The configured provider ID or alias is not registered.")
    return result


@lru_cache(maxsize=1)
def _inventory():
    inventory = json.loads(files("civic_data_connectors").joinpath("data/capabilities.json").read_text("utf-8"))
    rows = {row["canonical_id"]: row for row in inventory["providers"]}
    expected = {item["connector"] for item in source_formats()}
    if len(inventory["providers"]) != 31 or set(rows) != expected:
        raise ValueError("The packaged capability inventory does not match the fixed baseline provider roster.")
    return inventory, rows


def provider_capabilities(provider: str) -> dict:
    canonical = canonical_provider_id(provider)
    return deepcopy(_inventory()[1][canonical])


def inventory_metadata() -> dict:
    return deepcopy({key: value for key, value in _inventory()[0].items() if key != "providers"})
