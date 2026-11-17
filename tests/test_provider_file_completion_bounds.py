"""A saved file must not publish after its preparation deadline expires."""
import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors import interchange
from civic_data_connectors.providers import (
    civicplus_export, onbase_export, suiteone_export, telvue_chapter_export,
)
from test_civicplus_export import request as select_request
from test_onbase_export import request as onbase_request
from test_suiteone_export import request as suiteone_request
from test_telvue_chapter_export import request as telvue_request


@pytest.mark.parametrize("module,make_request", [
    (civicplus_export, select_request), (onbase_export, onbase_request),
    (suiteone_export, suiteone_request), (telvue_chapter_export, telvue_request),
])
def test_slow_capture_does_not_publish_expired_provider_file(tmp_path, monkeypatch, module, make_request):
    clock = [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    store = SQLiteStorage(tmp_path / "files.sqlite")
    original_save, original_put = store.save_capture, store.put
    published = []

    def slow_save(*args, **kwargs):
        result = original_save(*args, **kwargs)
        clock[0] = 2.0
        return result

    def put(collection, *args, **kwargs):
        if collection == "artifacts":
            published.append(args[0])
        return original_put(collection, *args, **kwargs)

    monkeypatch.setattr(store, "save_capture", slow_save)
    monkeypatch.setattr(store, "put", put)
    result = create_engine(storage=store).execute("export", {
        **make_request(), "stream": True, "bounds": {"deadline_seconds": 1},
    }, context=OperationContext(authorization=frozenset({"export_attachments"})))
    assert result.status == "failed" and not result.data, result.public_dict()
    assert not published, "Expired output must not become a downloadable artifact."


@pytest.mark.parametrize("module,make_request", [
    (civicplus_export, select_request), (onbase_export, onbase_request),
    (suiteone_export, suiteone_request), (telvue_chapter_export, telvue_request),
])
def test_temporary_copy_expiry_removes_unpublished_file(monkeypatch, module, make_request):
    clock = [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    original_copy = interchange._copy

    def slow_copy(*args, **kwargs):
        result = original_copy(*args, **kwargs)
        clock[0] = 2.0
        return result

    monkeypatch.setattr(interchange, "_copy", slow_copy)
    owner = create_engine()
    result = owner.execute("export", {
        **make_request(), "stream": True, "bounds": {"deadline_seconds": 1},
    }, context=OperationContext(authorization=frozenset({"export_attachments"})))
    assert result.status == "failed" and not result.data, result.public_dict()
    manager = owner._civic_artifacts
    assert not manager.values and manager.size == 0
    from pathlib import Path
    assert not list(Path(manager.directory.name).iterdir())
