"""Approved response transfer bounds apply before and after client writes."""

import json

import pytest

from quorumrelay import Engine
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register

import test_boardable_agenda_write as boardable
import test_towncloud_draft_write as towncloud
from test_write_providers import make_engine


@pytest.mark.parametrize("fixture", [boardable, towncloud], ids=["boardable", "towncloud"])
def test_small_transfer_bound_rejects_preflight_without_plan_or_mutation(tmp_path, fixture):
    engine, caller, vendor = fixture.setup(tmp_path)
    original, limits = vendor.send, []

    def bounded(url, **kwargs):
        limits.append(kwargs["byte_limit"])
        return original(url, **kwargs)

    vendor.send = bounded
    result = engine.execute("plan_write", {"source": fixture.SOURCE, "changes": [fixture.CHANGE],
        "bounds": {"transfer_bytes": 16}}, context=caller)
    assert result.status == "failed", result.public_dict()
    assert limits == [16]
    assert not any(method == "POST" for method, _, _ in vendor.calls)
    assert not list(engine.storage.list("write_plans", scope=caller.scope))


@pytest.mark.parametrize("fixture", [boardable, towncloud], ids=["boardable", "towncloud"])
def test_oversized_post_response_reconciles_after_restart_without_second_post(tmp_path, fixture):
    engine, caller, vendor = fixture.setup(tmp_path)
    original, limits = vendor.send, []

    def oversized_post(url, **kwargs):
        limits.append(kwargs["byte_limit"])
        response = original(url, **kwargs)
        return WriteResponse(200, b"x" * 4097) if kwargs["method"] == "POST" else response

    vendor.send = oversized_post
    planned = engine.execute("plan_write", {"source": fixture.SOURCE, "changes": [fixture.CHANGE],
        "bounds": {"transfer_bytes": 4096}}, context=caller)
    assert planned.status == "completed", planned.public_dict()
    approval = {key: planned.data[key] for key in ("plan_id", "plan_hash")}
    first = engine.execute("commit_write", approval, context=caller)
    assert first.status == "partial", first.public_dict()
    assert all(limit == 4096 for limit in limits)
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    result = reopened.execute("commit_write", approval, context=caller)
    assert result.status == "completed", result.public_dict()
    assert sum(method == "POST" for method, _, _ in vendor.calls) == 1


def wistia_update(tmp_path):
    engine, caller, vendor, source = make_engine(tmp_path, "wistia", ["media:update"])
    vendor.rows["media1"] = {"id": 1, "hashed_id": "media1", "name": "Before", "tags": [],
                             "updated": "2026-11-11T00:00:00Z"}
    change = {"key": "media", "entity": "media", "operation": "update", "resource_id": "media1",
              "meeting_id": "meeting1", "fields": {"name": "After"}}
    return engine, caller, vendor, source, change


def test_shared_json_adapter_rejects_transfer_oversize_before_plan(tmp_path):
    engine, caller, vendor, source, change = wistia_update(tmp_path)
    original, limits = vendor.send, []

    def bounded(url, **kwargs):
        limits.append(kwargs["byte_limit"])
        return original(url, **kwargs)

    vendor.send = bounded
    result = engine.execute("plan_write", {"source": source, "changes": [change],
        "bounds": {"transfer_bytes": 16}}, context=caller)
    assert result.status == "failed", result.public_dict()
    assert limits == [16]
    assert not any(method != "GET" for method, _ in vendor.calls)


def test_shared_json_oversize_after_update_reconciles_without_second_mutation(tmp_path):
    engine, caller, vendor, source, change = wistia_update(tmp_path)
    original = vendor.send

    def oversized_update(url, **kwargs):
        response = original(url, **kwargs)
        if kwargs["method"] == "PUT":
            value = json.loads(response.content)
            value["padding"] = "x" * 4096
            return WriteResponse(200, json.dumps(value).encode())
        return response

    vendor.send = oversized_update
    planned = engine.execute("plan_write", {"source": source, "changes": [change],
        "bounds": {"transfer_bytes": 4096}}, context=caller)
    assert planned.status == "completed", planned.public_dict()
    approval = {key: planned.data[key] for key in ("plan_id", "plan_hash")}
    result = engine.execute("commit_write", approval, context=caller)
    assert result.status == "partial", result.public_dict()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "provider.sqlite"))
    register(reopened, default_adapters(vendor))
    result = reopened.execute("commit_write", approval, context=caller)
    assert result.status == "completed", result.public_dict()
    assert sum(method == "PUT" for method, _ in vendor.calls) == 1
