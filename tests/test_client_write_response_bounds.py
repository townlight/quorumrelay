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
import test_civicclerk_section_write as civicclerk
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


@pytest.mark.parametrize("provider", ["wistia", "civicclerk"])
@pytest.mark.parametrize("interruption", ["cancel", "deadline"])
@pytest.mark.parametrize("stage", ["readback", "mutation", "parse"])
def test_final_readback_interruption_stays_uncertain_and_reopens_without_repeat(
        tmp_path, monkeypatch, provider, interruption, stage):
    import civic_data_connectors.write_adapters as adapters
    import civic_data_connectors.writes as writes

    now = [100.0]
    monkeypatch.setattr(adapters, "monotonic", lambda: now[0])
    monkeypatch.setattr(writes, "monotonic", lambda: now[0])
    if provider == "wistia":
        engine, caller, vendor, source, change = wistia_update(tmp_path)
        database = "provider.sqlite"
    else:
        engine, caller, vendor = civicclerk.setup(tmp_path)
        vendor.rows[41] = {"id": 41, "agendaId": 91, "sectionName": "Before", "sectionText": "Keep"}
        source, change = civicclerk.SOURCE, civicclerk.change("update", sectionName="After")
        database = "write.sqlite"
    planned = engine.execute("plan_write", {"source": source, "changes": [change],
        "bounds": {"deadline_seconds": 5}}, context=caller)
    assert planned.status == "completed", planned.public_dict()
    approval = {key: planned.data[key] for key in ("plan_id", "plan_hash")}
    original, sent, final_read = vendor.send, [False], [False]

    def interrupt():
        if interruption == "cancel":
            caller.cancellation.set()
        else:
            now[0] += 6

    def interrupted_readback(url, **kwargs):
        response = original(url, **kwargs)
        if kwargs["method"] == "PUT":
            sent[0] = True
            if stage == "mutation":
                interrupt()
        elif (sent[0] and kwargs["method"] == "GET"
              and (provider == "wistia" or url.endswith("/Sections/41"))):
            final_read[0] = True
            if stage == "readback":
                interrupt()
        return response

    sanitize = adapters.sanitize

    def interrupted_parse(*args, **kwargs):
        value = sanitize(*args, **kwargs)
        if stage == "parse" and final_read[0]:
            interrupt()
        return value

    monkeypatch.setattr(adapters, "sanitize", interrupted_parse)
    vendor.send = interrupted_readback
    result = engine.execute("commit_write", approval, context=caller)
    assert result.status == "partial", result.public_dict()
    assert result.data["items"][0]["state"] == "uncertain"
    caller.cancellation.clear()
    vendor.send = original
    monkeypatch.setattr(adapters, "sanitize", sanitize)
    reopened = Engine(storage=SQLiteStorage(tmp_path / database))
    register(reopened, default_adapters(vendor))
    result = reopened.execute("commit_write", approval, context=caller)
    assert result.status == "completed", result.public_dict()
    assert sum(call[0] == "PUT" for call in vendor.calls) == 1
