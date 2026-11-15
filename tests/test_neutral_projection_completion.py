"""Projection completion must honor cancellation and the whole operation deadline."""
import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors import interchange
from test_storage_search_imports import sample


@pytest.mark.parametrize("format,function", [("csv", "csv_projection"), ("ics", "icalendar_projection")])
@pytest.mark.parametrize("interruption", ["cancel", "deadline"])
def test_interruption_during_projection_does_not_publish_inline_output(monkeypatch, format, function, interruption):
    context, clock = OperationContext(), [0.0]
    monkeypatch.setattr(interchange.time, "monotonic", lambda: clock[0])
    original = getattr(interchange, function)

    def interrupted(*args, **kwargs):
        value = original(*args, **kwargs)
        if interruption == "cancel":
            context.cancellation.set()
        else:
            clock[0] = 2.0
        return value

    monkeypatch.setattr(interchange, function, interrupted)
    result = create_engine().execute("export", {"bundle": sample(), "format": format,
        "bounds": {"deadline_seconds": 1}}, context=context)
    assert result.status == ("cancelled" if interruption == "cancel" else "failed"), result.public_dict()
    assert result.data is None


@pytest.mark.parametrize("format", ["csv", "ics"])
@pytest.mark.parametrize("interruption", ["cancel", "deadline"])
def test_inline_encoding_cannot_outlive_the_projection_completion_boundary(monkeypatch, format, interruption):
    bundle, context, clock = sample(), OperationContext(), [0.0]
    monkeypatch.setattr(interchange.time, "monotonic", lambda: clock[0])
    original = interchange.base64.b64encode

    def slow_encode(*args, **kwargs):
        value = original(*args, **kwargs)
        if interruption == "cancel":
            context.cancellation.set()
        else:
            clock[0] = 2.0
        return value

    monkeypatch.setattr(interchange.base64, "b64encode", slow_encode)
    result = create_engine().execute("export", {"bundle": bundle, "format": format,
        "bounds": {"deadline_seconds": 1}}, context=context)
    assert result.status == ("cancelled" if interruption == "cancel" else "failed"), result.public_dict()
    assert result.data is None


@pytest.mark.parametrize("format", ["csv", "ics"])
def test_deadline_during_capture_save_cannot_publish_artifact(tmp_path, monkeypatch, format):
    clock = [0.0]
    monkeypatch.setattr(interchange.time, "monotonic", lambda: clock[0])
    store = SQLiteStorage(tmp_path / "projection.sqlite")
    original = store.save_capture

    def slow_save(*args, **kwargs):
        value = original(*args, **kwargs)
        clock[0] = 2.0
        return value

    monkeypatch.setattr(store, "save_capture", slow_save)
    result = create_engine(storage=store).execute("export", {"bundle": sample(), "format": format,
        "stream": True, "bounds": {"deadline_seconds": 1}})
    assert result.status == "failed" and result.data is None, result.public_dict()
    assert store.list("artifacts", scope=OperationContext().scope) == []


@pytest.mark.parametrize("format", ["csv", "ics"])
def test_deadline_during_temporary_copy_removes_unpublished_projection(monkeypatch, format):
    clock = [0.0]
    monkeypatch.setattr(interchange.time, "monotonic", lambda: clock[0])
    original = interchange._copy

    def slow_copy(*args, **kwargs):
        value = original(*args, **kwargs)
        clock[0] = 2.0
        return value

    monkeypatch.setattr(interchange, "_copy", slow_copy)
    owner = create_engine()
    result = owner.execute("export", {"bundle": sample(), "format": format,
        "stream": True, "bounds": {"deadline_seconds": 1}})
    assert result.status == "failed" and result.data is None, result.public_dict()
    manager = owner._civic_artifacts
    assert not manager.values and manager.size == 0
    from pathlib import Path
    assert not list(Path(manager.directory.name).iterdir())
