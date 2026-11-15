import base64
from dataclasses import replace
from hashlib import sha256

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.interchange import open_artifact
from quorumrelay.storage import SQLiteStorage


def request():
    return {"source": {"provider": "legistar", "url": "https://webapi.legistar.com/v1/fixture-city"},
        "provider_specific": True, "format": "legistar-legislative-text", "text_encoding": "ascii",
        "title": "Budget action", "body": "First line\nSecond line"}


@pytest.mark.parametrize("encoding,text", [("ascii", "Budget"), ("cp1252", "Café"), ("utf-8", "Budget 市")])
def test_exact_sections_bytes_hash_and_honest_scope(encoding, text):
    result = create_engine().execute("export", {**request(), "text_encoding": encoding, "title": text})
    assert result.status == "completed", result.public_dict()
    raw = base64.b64decode(result.data["content_base64"])
    assert raw == ("..title\r\n" + text + "\r\n..body\r\nFirst line\r\nSecond line\r\n").encode(encoding)
    manifest = result.data["manifest"]
    assert manifest["sha256"] == sha256(raw).hexdigest() and manifest["byte_length"] == len(raw)
    assert not manifest["vendor_import_accepted"] and not manifest["vendor_transfer_performed"]
    assert "encoding" in manifest["projection_losses"][2]


@pytest.mark.parametrize("changes", [
    {"body": "text\n..title\nInjected"}, {"title": "text\r  ..body"}, {"body": "\x00bad"},
    {"title": ""}, {"body": None}, {"text_encoding": "utf-16"}, {"text_encoding": None},
    {"title": "市"}, {"stream": "true"}, {"bounds": {"parser_bytes": 20}},
    {"bounds": {"transfer_bytes": 20}}, {"bounds": {"date_from": "2026-11-15"}},
    {"bounds": {"checkpoint": "unknown"}},
])
def test_ambiguous_or_lossy_input_has_no_output(changes):
    result = create_engine().execute("export", {**request(), **changes})
    assert result.status == "failed" and not result.data


def test_persistent_artifact_reopen_scope_and_inline_equality(tmp_path):
    path = tmp_path / "store.sqlite"
    ctx = OperationContext(tenant="a")
    engine = create_engine(storage=SQLiteStorage(path))
    inline = engine.execute("export", request(), context=ctx)
    result = engine.execute("export", {**request(), "stream": True}, context=ctx)
    assert result.status == "completed", result.public_dict()
    reopened = create_engine(storage=SQLiteStorage(path))
    metadata, stream = open_artifact(reopened, result.data["artifact_id"], context=ctx)
    with stream:
        assert stream.read() == base64.b64decode(inline.data["content_base64"])
        assert metadata["manifest"] == result.data["manifest"]
    with pytest.raises((PermissionError, ValueError)):
        open_artifact(reopened, result.data["artifact_id"], context=replace(ctx, tenant="b"))


def test_cancellation_before_and_after_encoding(monkeypatch):
    from civic_data_connectors.providers import legistar_text_export as module

    ctx = OperationContext()
    ctx.cancellation.set()
    assert create_engine().execute("export", request(), context=ctx).status == "cancelled"
    original = module.base64.b64encode
    ctx = OperationContext()

    def cancel(value):
        encoded = original(value)
        ctx.cancellation.set()
        return encoded

    monkeypatch.setattr(module.base64, "b64encode", cancel)
    result = create_engine().execute("export", request(), context=ctx)
    assert result.status == "cancelled" and not result.data


def test_deadline_after_encoding_and_export_authorization(monkeypatch):
    from civic_data_connectors.providers import legistar_text_export as module

    clock = iter([0, 0, 0, 2])
    monkeypatch.setattr(module, "monotonic", lambda: next(clock))
    result = create_engine().execute("export", {**request(), "bounds": {"deadline_seconds": 1}})
    assert result.status == "failed" and not result.data
    result = create_engine().execute("export", request(), context=OperationContext(allowed_namespaces=frozenset()))
    assert result.status == "failed" and not result.data
