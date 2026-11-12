"""Synthetic local acceptance. No network and no vendor mutation."""

import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from civic_data_connectors import Engine
from civic_data_connectors import imports, search, storage
from civic_data_connectors.engine import canonical_hash, source_identity_key
from civic_data_connectors.extensions import StorageConflict
from civic_data_connectors.models import OperationContext
from civic_data_connectors.storage import Mutation, SQLiteStorage


def sample(provider="legistar"):
    raw = b'{"unknown":[null,false,0,"",{"unicode":"caf\\u00e9"}]}'
    digest = hashlib.sha256(raw).hexdigest()
    record = {
        "schema_version": "2.0.0",
        "identity": {"provider": provider, "namespace": "city.example", "record_type": "meeting",
                     "external_id": "7", "parent": None},
        "normalized": {"title": "Budget workshop", "meeting_date": "2026-11-11", "body": "Council",
                       "agenda_items": [{"title": "Parks budget"}]},
        "source_url": "https://city.example/meetings",
        "citation_urls": ["https://city.example/meeting/7"],
        "capture_sha256": digest, "captured_at": "2026-11-11T15:00:00Z",
        "normalized_sha256": "normalized-v1",
        "source_revision": {"kind": "provider", "value": "r7"},
        "original": json.loads(raw), "relationships": [],
        "text": [{"field": "minutes", "text": "The café water district adopted the parks budget.",
                  "citation_url": "https://city.example/meeting/7", "page": 4,
                  "timestamp": "00:02:19", "provenance": {"method": "consumer_supplied"},
                  "completeness": "complete"}],
        "extensions": {"unknown": [None, False, 0, "", {"x": "é"}]}, "future": {"a": False},
    }
    return {
        "schema_version": "2.0.0", "source": {"provider": provider, "url": record["source_url"]},
        "records": [record], "capture": {"sha256": digest, "byte_length": len(raw),
                                       "content_base64": base64.b64encode(raw).decode()},
        "compatibility": {}, "extensions": {"unknown_top": True}, "unknown_bundle": {"a": []},
    }


@pytest.fixture
def engine(tmp_path):
    owner = Engine(storage=SQLiteStorage(tmp_path / "store.sqlite"))
    storage.register(owner)
    imports.register(owner)
    search.register(owner)
    return owner


def test_representative_preview_store_search_repeat_and_revision(engine):
    bundle = sample()
    before = deepcopy(bundle)
    preview = engine.execute("import_preview", {"bundle": bundle})
    assert preview.status == "completed"
    assert preview.data["persisted"] is False
    assert engine.storage.list("records", scope=OperationContext().scope) == []
    stored = engine.execute("import_bundle", {"bundle": bundle, "persist": True})
    assert stored.status == "completed", stored.public_dict()
    assert bundle == before
    found = engine.execute("search", {"query": {"terms": ["budget"], "phrases": ["water district"],
                                               "body": "Council", "date_from": "2026-11-11",
                                               "date_to": "2026-11-11", "record_types": ["meeting"]}})
    assert found.status == "completed", found.public_dict()
    assert len(found.data["hits"]) == 1
    assert found.data["hits"][0]["matches"][-1]["page"] == 4
    assert found.data["hits"][0]["matches"][-1]["timestamp"] == "00:02:19"
    assert found.data["hits"][0]["record"] == before["records"][0]
    again = engine.execute("import_bundle", {"bundle": bundle, "persist": True})
    assert again.data["changes"][0]["outcome"] == "unchanged"
    assert len(engine.storage.list("records", scope=OperationContext().scope)) == 1
    revised = deepcopy(bundle)
    revised["records"][0]["normalized"]["title"] = "Changed budget"
    revised["records"][0]["normalized_sha256"] = "normalized-v2"
    changed = engine.execute("import_bundle", {"bundle": revised, "persist": True})
    assert changed.data["changes"][0]["outcome"] == "changed_source"
    key = source_identity_key(bundle["records"][0]["identity"])
    assert len(engine.storage.history("records", key, scope=OperationContext().scope)) == 2


def test_cas_conflict_rollback_isolation_and_aliases(engine):
    store = engine.storage
    version = store.put("checkpoints", "p", {"value": 1}, scope="a", create_only=True)
    snapshot = store.get("checkpoints", "p", scope="a")
    snapshot.value["value"] = 99
    assert store.get("checkpoints", "p", scope="a").value == {"value": 1}
    assert store.get("checkpoints", "p", scope="b") is None
    with pytest.raises(StorageConflict):
        store.put_many([Mutation("checkpoints", "new", {}, create_only=True),
                        Mutation("checkpoints", "p", {"lost": True}, expected_version="wrong")], scope="a")
    assert store.get("checkpoints", "new", scope="a") is None
    def compete(index):
        try:
            store.put("checkpoints", "p", {"winner": index}, scope="a", expected_version=version)
            return True
        except StorageConflict:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(compete, range(8))) == 1


def test_restart_fresh_process_and_streamed_capture(engine):
    store = engine.storage
    scope = OperationContext().scope
    store.put("receipts", "uncertain", {"status": "ambiguous", "partial": [1, None]}, scope=scope)
    code = (
        "import json,sys; from civic_data_connectors.storage import SQLiteStorage;"
        "s=SQLiteStorage(sys.argv[1]);"
        "print(json.dumps(s.get('receipts','uncertain',scope=sys.argv[2]).value))"
    )
    env = {**os.environ, "PYTHONPATH": str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src")}
    result = subprocess.run([sys.executable, "-c", code, str(store.path), scope],
                            capture_output=True, text=True, env=env, check=True)
    assert json.loads(result.stdout) == {"status": "ambiguous", "partial": [1, None]}
    data = b"x" * (16 * 1024 * 1024 + 1)
    reference = store.save_capture(io.BytesIO(data), scope=scope, max_bytes=len(data))
    with SQLiteStorage(store.path).open_capture(reference, scope=scope) as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == hashlib.sha256(data).hexdigest()
    with pytest.raises(ValueError):
        store.open_capture(reference, scope="other")
    with pytest.raises(ValueError):
        store.save_capture(io.BytesIO(data), scope=scope, max_bytes=len(data) - 1)


def test_cancellation_survives_progress_and_cross_scope_status(engine):
    context = OperationContext(operation_id="job-1")
    storage.update_operation(engine.storage, "job-1", {"completed": 1}, scope=context.scope)
    assert engine.execute("cancel", {"operation_id": "job-1"}, context=context).status == "completed"
    storage.update_operation(engine.storage, "job-1", {"completed": 2, "cancel_requested": False},
                             scope=context.scope)
    assert storage.operation_cancelled(engine.storage, context)
    assert engine.execute("status", {"operation_id": "job-1"},
                          context=OperationContext(tenant="other")).status == "failed"
    result = engine.execute("search", {"records": sample()["records"]}, context=context)
    assert result.status == "cancelled"


def test_progress_recorder_bounds_slow_storage_and_flushes_latest(engine, monkeypatch):
    # Even if every report is more than a second apart, count gates each write.
    ticks = iter(range(2000))
    monkeypatch.setattr(storage.time, "monotonic", lambda: next(ticks))
    writes = []
    real_update = storage.update_operation

    def counted(*args, **kwargs):
        writes.append(args[2])
        return real_update(*args, **kwargs)

    monkeypatch.setattr(storage, "update_operation", counted)
    recorder = storage.ProgressRecorder(engine.storage, "bounded", scope="default", operation="discover")
    for i in range(1, 416):
        recorder({"operation": "normalize", "completed": i, "total": 500})
    recorder.flush()
    assert len(writes) <= 19
    assert engine.storage.get("operations", "bounded", scope="default").value["progress"]["completed"] == 415
    recorder({"operation": "discover", "pages": 1})
    assert writes[-1]["progress"]["operation"] == "discover"
    storage.update_operation(engine.storage, "bounded", {"cancel_requested": True}, scope="default")
    recorder({"operation": "discover", "pages": 2})
    recorder.flush()
    assert engine.storage.get("operations", "bounded", scope="default").value["cancel_requested"] is True


def test_tracked_handler_forwards_callbacks_and_flushes_on_error(engine):
    seen = []
    context = OperationContext(operation_id="error-progress", progress=seen.append)

    def handler(owner, request, content, delegated):
        for i in range(1, 101):
            delegated.report(operation="normalize", completed=i, total=200)
        raise ValueError("synthetic failure")

    with pytest.raises(ValueError, match="synthetic failure"):
        storage.tracked_handler("search", handler)(engine, {}, None, context)
    assert len(seen) == 100
    saved = engine.storage.get("operations", context.operation_id, scope=context.scope).value
    assert saved["progress"]["completed"] == 100
    assert saved["status"] == "failed"


def test_exact_terms_phrases_filters_and_partial_empty(engine):
    record = sample()["records"][0]
    assert engine.execute("search", {"records": [record], "query": {"terms": ["bud"]}}).data["hits"] == []
    assert engine.execute("search", {"records": [record], "query": {"phrases": ["budget water"]}}).data["hits"] == []
    for query in ({"providers": ["other"]}, {"namespaces": ["other"]}, {"body": "Board"},
                  {"date_to": "2026-11-10"}, {"record_types": ["item"]}):
        assert engine.execute("search", {"records": [record], "query": query}).data["hits"] == []
    record["text"] = [{"field": "pdf", "completeness": "unreadable"}]
    result = engine.execute("search", {"records": [record], "query": {"terms": ["nonexistent"]}})
    assert result.status == "partial"
    assert result.data["hits"] == []
    assert result.coverage["available_text"][0]["status"] == "metadata_only"
    assert result.coverage["available_text"][0]["unavailable"][0]["reason"] == "unreadable"
    record["normalized"].pop("meeting_date")
    result = engine.execute("search", {"records": [record], "query": {"date_from": "2026-11-11"}})
    assert result.status == "partial"
    assert result.coverage["failures"][0]["reason"] == "unknown_date"
    assert len(result.data["hits"]) == 1


def test_all_31_family_records_are_portably_searchable(engine):
    providers = engine.execute("providers", {}).data["providers"]
    assert len(providers) == 31
    records = [sample(row["provider"])["records"][0] for row in providers]
    result = engine.execute("search", {"records": records, "query": {"terms": ["budget"]}})
    assert len(result.data["hits"]) == 31
    truncated = engine.execute("search", {"records": records, "query": {"limit": 1}})
    assert truncated.status == "partial" and truncated.coverage["truncated"]


def test_discovery_partial_errors_survive_import(engine):
    bundle = sample()
    upstream = {"schema_version": "2.0.0", "status": "partial",
                "data": {"source": bundle["source"], "records": bundle["records"],
                         "captures": [bundle["capture"]], "bundles": [bundle]},
                "coverage": {"failures": [{"page": 2}], "truncated": True},
                "errors": [{"code": "page_failed", "message": "Mock page failed"}]}
    result = engine.execute("import_bundle", {"result": upstream, "persist": True})
    assert result.status == "partial", result.public_dict()
    assert result.errors[0].code == "page_failed"
    assert result.coverage == upstream["coverage"]
    assert result.data["bundle"]["bundles"][0] == bundle
    assert canonical_hash(result.data["bundle"]["records"][0]) == canonical_hash(bundle["records"][0])


def test_allowed_import_can_delegate_normalization_and_namespace_policy(engine):
    context = OperationContext(allowed_operations=frozenset({"import_bundle"}))
    content = json.dumps({"MeetingId": 4, "MeetingName": "Council", "MeetingDate": "2026-11-11T10:00:00Z"}).encode()
    result = engine.execute("import_bundle", {"source": {"provider": "legistar", "url": "https://city.example"},
                                             "persist": True}, content=content, context=context)
    assert result.status == "completed", result.public_dict()
    blocked = OperationContext(allowed_namespaces=frozenset({"other"}))
    assert engine.execute("import_bundle", {"bundle": sample(), "persist": True}, context=blocked).status == "failed"
    assert engine.execute("search", {"records": sample()["records"]}, context=blocked).data["records"] == []
    invalid = engine.execute("import_bundle", {"bundle": sample(), "persist": "false"})
    assert invalid.status == "failed"


class ExternalStore:
    """Example consumer-owned database adapter implementing only the baseline."""
    def __init__(self):
        self.values, self.lock = {}, threading.RLock()

    def get(self, collection, key, *, scope):
        with self.lock:
            return deepcopy(self.values.get((scope, collection, key)))

    def list(self, collection, *, scope):
        with self.lock:
            return [deepcopy(v) for (s, c, k), v in self.values.items() if s == scope and c == collection]

    def put(self, collection, key, value, *, scope, expected_version=None, create_only=False):
        from civic_data_connectors.extensions import StoredValue
        with self.lock:
            old = self.values.get((scope, collection, key))
            if (create_only and old) or (expected_version is not None
                                       and (old is None or old.version != expected_version)):
                raise StorageConflict("Version conflict.")
            version = str(int(old.version) + 1 if old else 1)
            self.values[(scope, collection, key)] = StoredValue(key, deepcopy(value), version)
            return version


def test_external_baseline_partial_cancel_resume_and_revision_retention():
    owner = Engine(storage=ExternalStore())
    imports.register(owner)
    search.register(owner)
    context = OperationContext(operation_id="first")
    context.progress = lambda progress: context.cancellation.set() if progress["completed"] == 2 else None
    partial = owner.execute("import_bundle", {"bundle": sample(), "persist": True}, context=context)
    assert partial.status == "cancelled"
    assert partial.data["completed_steps"] == 2
    resumed = owner.execute("import_bundle", {"bundle": sample(), "persist": True},
                            context=OperationContext(operation_id="retry"))
    assert resumed.status == "completed", resumed.public_dict()
    scope = OperationContext().scope
    assert len(owner.storage.list("record_revisions", scope=scope)) == 1
    assert len(owner.storage.list("records", scope=scope)) == 1
    assert owner.execute("search", {"query": {"terms": ["budget"]}}).data["hits"]


def test_tracked_progress_result_and_request_binding(engine):
    context = OperationContext(operation_id="tracked")
    request = {"records": sample()["records"], "query": {"terms": ["budget"]}}
    assert engine.execute("search", request, context=context).status == "completed"
    status = engine.execute("status", {"operation_id": "tracked"}, context=context)
    assert status.data["status"] == "completed"
    assert status.data["progress"]["completed"] == 1
    assert status.data["result"]["data"]["hits"]
    assert engine.execute("search", {"records": []}, context=context).status == "failed"


def test_status_rechecks_current_source_and_original_operation_policy(engine):
    record = sample()["records"][0]
    record["identity"]["namespace"] = "city-a"
    original = OperationContext(operation_id="old-search",
        allowed_operations=frozenset({"search", "status"}), allowed_namespaces=frozenset({"city-a"}))
    result = engine.execute("search", {"records": [record]}, context=original)
    assert result.data["hits"][0]["record"]["text"]
    for narrowed in (
        OperationContext(allowed_operations=frozenset({"search", "status"}),
                         allowed_namespaces=frozenset({"city-b"})),
        OperationContext(allowed_operations=frozenset({"status"}), allowed_namespaces=frozenset({"city-a"})),
    ):
        status = engine.execute("status", {"operation_id": "old-search"}, context=narrowed)
        assert status.status == "failed"
        assert status.errors[0].code == "permission_denied"
        assert status.data is None


def test_unmapped_native_search_does_not_silently_search_local_records(engine):
    result = engine.execute("search", {"native": True, "records": sample()["records"], "query": {}})
    assert result.status == "unsupported"
    assert result.data is None
    assert "does not establish" in result.errors[0].message
    malformed = engine.execute("search", {"native": "true", "records": sample()["records"]})
    assert malformed.status == "failed"


def _text_pdf():
    # A standalone PDF with one supplied-text page and one blank/scanned-like
    # page. Text below is literal input, not produced by our extraction helper.
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> /Contents 7 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    text = b"BT /F1 12 Tf 72 720 Td (Public hearing budget) Tj ET"
    objects += [b"<< /Length " + str(len(text)).encode() + b" >>\nstream\n" + text + b"\nendstream",
                b"<< /Length 0 >>\nstream\n\nendstream"]
    data, offsets = b"%PDF-1.4\n", [0]
    for number, value in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(number).encode() + b" 0 obj\n" + value + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 8\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    data += f"trailer << /Size 8 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return data


def test_supplied_html_pdf_text_extraction_anchors_unreadable_and_limits(engine):
    from civic_data_connectors.models import Bounds
    html = search.extract_text_segments(
        b"<h1>Public hearing</h1><script>not supplied meeting text</script><p>Water &amp; budget.</p>",
        media_type="text/html", citation_url="https://city.example/detail")
    assert html.status == "completed"
    assert "Water & budget." in html.data["segments"][0]["text"]
    assert "not supplied" not in html.data["segments"][0]["text"]
    pdf = engine.execute("extract_text", {"source": {"provider": "boarddocs",
                          "url": "https://city.example/packet", "namespace": "city.example"},
                          "media_type": "application/pdf",
                          "content_base64": base64.b64encode(_text_pdf()).decode()})
    assert pdf.status == "partial"
    assert pdf.data["segments"][0]["text"] == "Public hearing budget"
    assert pdf.data["segments"][0]["page"] == 1
    assert pdf.coverage["failures"][0]["page"] == 2
    assert "scanned" in pdf.coverage["failures"][0]["reason"]
    capped = search.extract_text_segments(_text_pdf(), media_type="application/pdf",
                                         citation_url="https://city.example/packet", bounds=Bounds(max_pages=1))
    assert capped.status == "partial" and capped.coverage["truncated"]
    unreadable = search.extract_text_segments(b"%PDF invalid", media_type="application/pdf",
                                              citation_url="https://city.example/packet")
    assert unreadable.status == "partial" and unreadable.data["segments"] == []
    too_large = search.extract_text_segments(b"x" * 10, media_type="text/plain",
                                             citation_url="https://city.example/text", bounds=Bounds(parser_bytes=9))
    assert too_large.status == "failed"
    record = sample()["records"][0]
    record["text"] = pdf.data["segments"]
    # Explicit association is caller-owned and evidence-backed, not a generic
    # assignment of every listing's text to every meeting.
    found = engine.execute("search", {"records": [record], "query": {"phrases": ["public hearing"]},
                                      "coverage": pdf.coverage})
    assert found.status == "partial"
    assert found.data["hits"][0]["matches"][0]["page"] == 1
