"""Exact native identities for synchronous write receipts and recovery."""
from urllib.parse import parse_qs

import pytest

from civic_data_connectors import Engine
from civic_data_connectors.storage import SQLiteStorage
from civic_data_connectors.write_adapters import default_adapters
from civic_data_connectors.writes import register
from test_write_providers import DocumentedNetwork, make_engine, response, run


class IdentityNetwork(DocumentedNetwork):
    def __init__(self, defect):
        super().__init__("legistar")
        self.defect = defect

    def legistar(self, parsed, method, fields):
        if method == "GET" and self.rows and ("$filter" in parse_qs(parsed.query) or parsed.path in self.rows):
            rows = [dict(row) for row in self.rows.values()]
            for row in rows:
                if self.defect == "missing":
                    row.pop("EventId", None)
                elif self.defect == "wrong":
                    row["EventId"] = 2
                elif self.defect == "zero":
                    row["EventId"] = 0
            return response(rows if "$filter" in parse_qs(parsed.query) else rows[0])
        return super().legistar(parsed, method, fields)


def reopen(tmp_path, network):
    engine = Engine(storage=SQLiteStorage(tmp_path / "provider.sqlite"))
    register(engine, default_adapters(network))
    return engine


@pytest.mark.parametrize("defect", ["wrong", "missing"])
def test_acknowledged_id_requires_exact_readback_after_reopen(tmp_path, defect):
    network = IdentityNetwork(defect)
    engine, context, _, source = make_engine(tmp_path, "legistar", ["event:create"], network)
    result, approval = run(engine, context, source, {"key": "event", "entity": "event", "operation": "create",
        "fields": {"EventDate": "2026-11-15"}})
    assert result.data["items"][0]["state"] == "uncertain"
    assert result.data["items"][0]["resource_id"] == 1
    engine = reopen(tmp_path, network)
    item = engine.execute("commit_write", approval, context=context).data["items"][0]
    assert item["state"] == "uncertain" and item["resource_id"] == 1
    network.defect = None
    item = engine.execute("commit_write", approval, context=context).data["items"][0]
    assert item["state"] == "succeeded" and item["resource_id"] == 1
    assert sum(method == "POST" for method, _ in network.calls) == 1


@pytest.mark.parametrize("defect", ["missing", "zero"])
def test_lost_ack_lookup_requires_valid_native_id(tmp_path, defect):
    network = IdentityNetwork(defect)
    network.lose = True
    engine, context, _, source = make_engine(tmp_path, "legistar", ["event:create"], network)
    result, approval = run(engine, context, source, {"key": "event", "entity": "event", "operation": "create",
        "fields": {"EventDate": "2026-11-15"}})
    assert result.data["items"][0]["state"] == "uncertain"
    engine = reopen(tmp_path, network)
    item = engine.execute("commit_write", approval, context=context).data["items"][0]
    assert item["state"] == "uncertain" and item.get("resource_id") is None
    network.defect = None
    item = engine.execute("commit_write", approval, context=context).data["items"][0]
    assert item["state"] == "succeeded" and item["resource_id"] == 1
    assert sum(method == "POST" for method, _ in network.calls) == 1


def test_wistia_upload_requires_acknowledged_hashed_id(tmp_path):
    class WrongMedia(DocumentedNetwork):
        def wistia(self, parsed, method, fields, files, headers):
            if method == "GET" and parsed.path.endswith("/medias/media2") and self.wrong:
                return response({**self.rows["media2"], "hashed_id": "other"})
            return super().wistia(parsed, method, fields, files, headers)

    network = WrongMedia("wistia")
    network.wrong = True
    engine, context, _, source = make_engine(tmp_path, "wistia", ["media:upload"], network)
    result, approval = run(engine, context, source, {"key": "upload", "entity": "media", "operation": "upload",
        "meeting_id": "meeting1", "fields": {"name": "Synthetic", "url": "https://example.org/video.mp4"}})
    assert result.data["items"][0]["state"] == "uncertain"
    engine = reopen(tmp_path, network)
    assert engine.execute("commit_write", approval, context=context).data["items"][0]["state"] == "uncertain"
    network.wrong = False
    assert engine.execute("commit_write", approval, context=context).data["items"][0]["state"] == "succeeded"
    assert sum(method == "POST" for method, _ in network.calls) == 1


def test_laserfiche_task_entry_must_match_document_readback(tmp_path):
    import base64

    class WrongEntry(DocumentedNetwork):
        def laserfiche(self, parsed, method, fields, files):
            if method == "GET" and parsed.path.endswith("/Entries/1") and self.wrong:
                return response({**self.rows["1"], "id": 2})
            return super().laserfiche(parsed, method, fields, files)

    network = WrongEntry("laserfiche")
    network.wrong = True
    engine, context, _, source = make_engine(tmp_path, "laserfiche", ["document_large:upload"], network)
    result, approval = run(engine, context, source, {"key": "doc", "entity": "document_large", "operation": "upload",
        "parent_id": 9, "meeting_id": "meeting1", "fields": {"name": "packet.pdf"}, "files": [{
            "part": "file", "filename": "packet.pdf", "content_type": "application/pdf",
            "content_base64": base64.b64encode(b"synthetic meeting packet").decode()}]})
    assert result.data["items"][0]["state"] == "pending"
    engine = reopen(tmp_path, network)
    assert engine.execute("commit_write", approval, context=context).data["items"][0]["state"] == "uncertain"
    network.wrong = False
    assert engine.execute("commit_write", approval, context=context).data["items"][0]["state"] == "succeeded"
    assert sum("ImportUploadedParts" in url for method, url in network.calls if method == "POST") == 1
