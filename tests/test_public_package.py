"""The approved public package reuses original object identities and resources."""

import importlib

import quorumrelay
import civic_data_connectors


def test_public_sdk_compatibility_identity_and_engine():
    for name in quorumrelay.__all__:
        assert getattr(quorumrelay, name) is getattr(civic_data_connectors, name)
    assert quorumrelay.__version__ == "0.1.0.dev7"
    engine = quorumrelay.create_engine()
    listed = engine.providers()
    assert listed.status == "completed"
    assert len(listed.data["providers"]) == 31
    assert len(listed.data["formats"]) == 34
    legistar = next(row for row in listed.data["providers"] if row["provider"] == "legistar")
    assert legistar["additional_formats"] == ["legistar-event-json", "legistar-events-json", "legistar-rollcalls-json", "legistar-votes-json"]


def test_public_submodule_classes_and_schema_resources():
    from quorumrelay.models import Record, Source
    from quorumrelay.storage import SQLiteStorage
    from quorumrelay.schemas import json_schema
    from civic_data_connectors.models import Record as OldRecord
    from civic_data_connectors.storage import SQLiteStorage as OldStorage
    assert Record is OldRecord
    assert Source is quorumrelay.Source
    assert SQLiteStorage is OldStorage
    assert json_schema("record")["properties"]["schema_version"]["const"] == "2.0.0"
    for module in ("engine", "providers", "providers.native", "write_files", "interchange"):
        assert importlib.import_module("quorumrelay." + module)
