"""Neutral bundle delivery shares the operation's total completion bounds."""

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors import interchange
from test_storage_search_imports import sample


@pytest.mark.parametrize("format", ["json", "jsonl", "zip"])
@pytest.mark.parametrize("boundary", ["inline_cancel", "inline_deadline", "capture_save", "temporary_copy"])
def test_delivery_cannot_complete_after_interruption(tmp_path, monkeypatch, format, boundary):
    bundle, context, clock = sample(), OperationContext(), [0.0]
    monkeypatch.setattr(interchange.time, "monotonic", lambda: clock[0])
    serialized = False
    original_write = interchange.write_bundle

    def write(*args, **kwargs):
        nonlocal serialized
        result = original_write(*args, **kwargs)
        serialized = True
        return result

    monkeypatch.setattr(interchange, "write_bundle", write)

    def interrupt():
        assert serialized
        if boundary == "inline_cancel":
            context.cancellation.set()
        else:
            clock[0] = 2.0

    store = SQLiteStorage(tmp_path / "bundles.sqlite") if boundary == "capture_save" else None
    if boundary.startswith("inline"):
        original = interchange.base64.b64encode

        def encode(*args, **kwargs):
            value = original(*args, **kwargs)
            if serialized:
                interrupt()
            return value

        monkeypatch.setattr(interchange.base64, "b64encode", encode)
    elif store is not None:
        original = store.save_capture

        def save(*args, **kwargs):
            value = original(*args, **kwargs)
            interrupt()
            return value

        monkeypatch.setattr(store, "save_capture", save)
    else:
        original = interchange._copy

        def copy(*args, **kwargs):
            value = original(*args, **kwargs)
            if serialized:
                interrupt()
            return value

        monkeypatch.setattr(interchange, "_copy", copy)
    owner = create_engine(storage=store)
    result = owner.execute("export", {"bundle": bundle, "format": format,
        "stream": not boundary.startswith("inline"), "bounds": {"deadline_seconds": 1}}, context=context)
    assert serialized and (clock[0] == 2.0 or context.check_cancelled())
    assert result.status == ("cancelled" if boundary == "inline_cancel" else "failed"), result.public_dict()
    assert result.data is None
    if store is not None:
        assert store.list("artifacts", scope=context.scope) == []
    elif boundary == "temporary_copy":
        from pathlib import Path
        manager = owner._civic_artifacts
        assert not manager.values and manager.size == 0
        assert not list(Path(manager.directory.name).iterdir())
