from copy import deepcopy

import pytest

from civic_data_connectors import Engine
from civic_data_connectors.storage import SQLiteStorage
from civic_data_connectors.write_adapters import default_adapters
from civic_data_connectors.writes import register

from test_write_providers import make_engine, run


def start(tmp_path, entity):
    engine, context, network, source = make_engine(tmp_path, "wistia", [f"{entity}:{'update' if entity == 'media_tags' else 'create'}"])
    if entity == "media_tags":
        network.rows["media1"] = {"hashed_id": "media1", "tags": []}
        change = {"key": "tags", "entity": entity, "operation": "update", "meeting_id": "meeting1",
                  "fields": {"hashed_ids": ["media1"], "tag_names": ["new"]}}
    else:
        change = {"key": "import", "entity": entity, "operation": "create", "meeting_id": "meeting1",
                  "fields": {"url": "https://example.com/video.mp4"}}
    committed, approval = run(engine, context, source, change)
    assert committed.data["items"][0]["state"] == "pending"
    return engine, context, network, approval


def poll(engine, context, approval):
    return engine.execute("commit_write", approval, context=context).data["items"][0]


@pytest.mark.parametrize("entity", ["media_tags", "media_import"])
@pytest.mark.parametrize("status", ["finished", "failed"])
@pytest.mark.parametrize("identity", ["other", None])
def test_unrelated_or_missing_job_identity_is_uncertain(tmp_path, entity, status, identity):
    engine, context, network, approval = start(tmp_path, entity)
    network.job.update(hashed_id=identity, id=9, status=status)
    assert poll(engine, context, approval)["state"] == "uncertain"
    assert sum(method == "POST" for method, _ in network.calls) == 1


def finished_import(network):
    network.job.update(status="finished", object={"type": "bulk_operation", "summary": {"total": 1, "succeeded": 1, "failed": 0},
        "results": [{"position": 0, "status": "succeeded", "operation": "create", "resource_type": "media", "id": "media2"}]})
    network.rows["media2"] = {"id": 2, "hashed_id": "media2"}


@pytest.mark.parametrize("readback", [{"hashed_id": "other"}, {}, None])
def test_import_requires_exact_created_media_readback(tmp_path, readback):
    engine, context, network, approval = start(tmp_path, "media_import")
    finished_import(network)
    network.rows["media2"] = deepcopy(readback)
    assert poll(engine, context, approval)["state"] == "uncertain"
    assert sum(method == "POST" for method, _ in network.calls) == 1


def test_import_valid_job_and_media_binding(tmp_path):
    engine, context, network, approval = start(tmp_path, "media_import")
    finished_import(network)
    item = poll(engine, context, approval)
    assert item["state"] == "succeeded" and item["resource_id"] == "media2"
    assert sum(method == "POST" for method, _ in network.calls) == 1


@pytest.mark.parametrize("obj", [None, [], {"type": "other", "results": []}, {"type": "bulk_operation", "results": [None]}])
def test_import_malformed_job_object_is_uncertain(tmp_path, obj):
    engine, context, network, approval = start(tmp_path, "media_import")
    network.job.update(status="finished", object=obj)
    assert poll(engine, context, approval)["state"] == "uncertain"



@pytest.mark.parametrize("job", [None, [], {}, {"hashed_id": "job3"}])
def test_malformed_polled_job_is_uncertain(tmp_path, job):
    engine, context, network, approval = start(tmp_path, "media_import")
    network.job = job
    assert poll(engine, context, approval)["state"] == "uncertain"


@pytest.mark.parametrize("status", ["queued", "started"])
def test_matching_pending_job_stays_pending_without_replay(tmp_path, status):
    engine, context, network, approval = start(tmp_path, "media_import")
    network.job["status"] = status
    assert poll(engine, context, approval)["state"] == "pending"
    assert sum(method == "POST" for method, _ in network.calls) == 1


@pytest.mark.parametrize("returned_id", ["other", None])
def test_tags_requires_exact_media_readback_after_finished_job(tmp_path, returned_id):
    engine, context, network, approval = start(tmp_path, "media_tags")
    network.job["status"] = "finished"
    network.rows["media1"]["hashed_id"] = returned_id
    assert poll(engine, context, approval)["state"] == "uncertain"
    assert sum(method == "POST" for method, _ in network.calls) == 1


def test_import_reconciles_persisted_job_after_engine_reopen(tmp_path):
    engine, context, network, approval = start(tmp_path, "media_import")
    finished_import(network)
    reopened = Engine(storage=SQLiteStorage(tmp_path / "provider.sqlite"))
    register(reopened, default_adapters(network))
    item = poll(reopened, context, approval)
    assert item["state"] == "succeeded" and item["resource_id"] == "media2"
    assert sum(method == "POST" for method, _ in network.calls) == 1


@pytest.mark.parametrize("returned_id", ["other", None])
def test_tags_rejects_wrong_media_in_preflight(tmp_path, returned_id):
    engine, context, network, source = make_engine(tmp_path, "wistia", ["media_tags:update"])
    network.rows["media1"] = {"hashed_id": returned_id, "tags": []}
    change = {"key": "tags", "entity": "media_tags", "operation": "update", "meeting_id": "meeting1",
              "fields": {"hashed_ids": ["media1"], "tag_names": ["new"]}}
    result = engine.execute("plan_write", {"source": source, "changes": [change]}, context=context)
    assert result.status == "failed"
    assert not any(method == "POST" for method, _ in network.calls)
