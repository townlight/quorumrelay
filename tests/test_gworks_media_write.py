"""Synthetic recovered gWorks media upload/list/association tests."""

from copy import deepcopy
import base64
import json
from urllib.parse import parse_qsl

import pytest

from quorumrelay import Engine, OperationContext
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from civic_data_connectors.providers import gworks_write as adapter
from civic_data_connectors.providers import gworks_media_write as media

P = "cms_meeting."
F = "cms_file."
ROOT = "https://api.dev.gworks.cloud/cms/secure/city/meeting/"
NS = "//api.dev.gworks.cloud/city/1311/cms"
SOURCE = {"provider": "gworks", "url": ROOT, "namespace": NS, "options": {"gworks_city_id": "1311"}}
PAYLOAD = b"%PDF-1.4 synthetic packet"
ROW = {P + "id": 7, P + "title": "Council hearing", P + "location": "City chambers",
       P + "meeting_ts": "2026-11-17T18:30:00-07:00", P + "category_ref_type_id": 2,
       P + "template_fl": False, P + "archived_fl": False, P + "agenda_published_fl": False,
       P + "minutes_published_fl": False, P + "agenda_published_dt": None, P + "minutes_published_dt": None,
       P + "data": [{"type": "section", "title": "Public business", "items": [
           {"type": "agenda-item", "value": "Bridge repair", "minute": "", "files": [], "extra": {"keep": True}}]}],
       P + "files": [{"name": "packet.pdf", "id": "45", "size": "42", "type": "application/pdf"}],
       "unrecognized": {"keep": "caf\u00e9"},
       P + "mod_ts": "rev-1"}


def sha(data):
    from hashlib import sha256
    return sha256(data).hexdigest()


def _stage(engine, caller, data, filename="agenda.pdf"):
    for name in ("stage_file", "stage_write_file"):
        method = getattr(engine, name, None)
        if method is not None:
            try:
                handle = method(data, filename=filename, content_type="application/pdf", context=caller)
            except TypeError:
                handle = method(data, context=caller)
            return {"file_handle": handle}
    return {"content_base64": base64.b64encode(data).decode()}


def file_part(engine, caller, data=PAYLOAD, filename="agenda.pdf"):
    return {"part": "file", "filename": filename, "content_type": "application/pdf",
            **_stage(engine, caller, data, filename)}


def upload_change(engine, caller, association=True):
    if not association:
        return {"key": "upload", "entity": "media", "operation": "upload", "fields": {},
                "files": [file_part(engine, caller)]}
    fields = {"meeting_id": "7", "target": "agenda_item", "usetype": "official",
              "section_index": 0, "item_index": 0,
              "expected_item": deepcopy(ROW[P + "data"][0]["items"][0])}
    return {"key": "upload", "entity": "media", "operation": "upload", "fields": fields,
            "files": [file_part(engine, caller)]}


class Vendor:
    mock = True

    def __init__(self):
        self.media = []
        self.meeting = deepcopy(ROW)
        self.calls = []
        self.counts = {"metadata": 0, "storage": 0, "meeting": 0}
        self.fail_metadata = None
        self.fail_storage = None
        self.corrupt_files = False
        self.signed_url = "https://files.dev.gworks.cloud/upload?X-Amz-Signature=secret"
        self.storage_bytes = None
        self.after_metadata = None
        self.after_storage = None
        self.after_files = None
        self.after_meeting = None

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert deadline_seconds > 0
        self.calls.append((method, url, body, headers))
        meeting_url = media.gworks_editor.ORIGIN + "/cms/secure/city/meeting/7"
        if url == meeting_url and method == "GET":
            return WriteResponse(200, json.dumps(self.meeting).encode())
        if url == meeting_url and method == "PUT":
            self.counts["meeting"] += 1
            assert headers["Authorization"] == "Bearer synthetic-secret"
            request = json.loads(body)
            for key, value in request.items():
                if key in {P + "date", P + "time", P + "section_count"}:
                    continue
                if key in {P + "data", P + "files"}:
                    self.meeting[key] = json.loads(value)
                elif key == P + "template_fl":
                    self.meeting[key] = value == "true"
                else:
                    self.meeting[key] = value
            self.meeting[P + "mod_ts"] = "rev-2"
            if self.after_meeting:
                self.after_meeting()
            return WriteResponse(200, json.dumps({P + "id": 7, P + "mod_ts": "rev-2"}).encode())
        if url == media.MEDIA_ROOT and method == "POST":
            self.counts["metadata"] += 1
            assert headers["Authorization"] == "Bearer synthetic-secret"
            request = json.loads(body)
            assert request[F + "filename"] == "agenda.pdf"
            assert request[F + "mime_type"] == "application/pdf"
            assert request[F + "size_kb"] == len(PAYLOAD) // 1000
            if self.fail_metadata == "timeout":
                raise TimeoutError()
            if self.fail_metadata == "error":
                return WriteResponse(500)
            if self.after_metadata:
                self.after_metadata()
            return WriteResponse(200, json.dumps({"signedUrl": self.signed_url}).encode())
        if url == self.signed_url and method == "PUT":
            self.counts["storage"] += 1
            assert "Authorization" not in headers
            assert headers["Content-Type"] == "application/pdf" and body == PAYLOAD
            if self.fail_storage == "error":
                return WriteResponse(500)
            self.storage_bytes = body
            self.media.append({F + "id": "99", F + "filename": "agenda.pdf", F + "mime_type": "application/pdf",
                               F + "size_kb": len(PAYLOAD) // 1000, F + "created_ts": "2026-11-16T00:00:00Z"})
            if self.after_storage:
                self.after_storage()
            if self.fail_storage == "timeout":
                raise TimeoutError()
            return WriteResponse(200)
        if url == media.FILES_ORIGIN + "/city/1311/media/agenda.pdf" and method == "GET":
            assert "Authorization" not in headers
            if self.corrupt_files:
                return WriteResponse(200, b"corrupt")
            content = self.storage_bytes or b""
            if self.after_files:
                self.after_files()
            return WriteResponse(200, content)
        if url == media.MEDIA_LIST and method == "POST":
            assert headers["Content-Type"] == "application/x-www-form-urlencoded"
            form = dict(parse_qsl(body.decode()))
            start, length, draw = int(form["start"]), int(form["length"]), int(form["draw"])
            rows = list(self.media)
            page = rows[start:start + length]
            return WriteResponse(200, json.dumps({"draw": draw, "recordsTotal": len(rows),
                "recordsFiltered": len(rows), "data": page}).encode())
        raise AssertionError((method, url))


def setup(tmp_path):
    vendor = Vendor()
    caller = OperationContext(principal="editor", client_id="test", tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}), allowed_namespaces=frozenset({NS}),
        credentials={"gworks": {"tenant": "city", "city_id": "1311", "city_code": "1311",
            "origin": adapter.gworks_editor.ORIGIN, "allowed_namespaces": [NS],
            "token": "synthetic-secret", "meeting_ids": ["7"],
            "permissions": ["media:upload", "meeting:update"]}})
    engine = Engine(storage=SQLiteStorage(tmp_path / "media.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, caller, vendor


def plan(engine, caller, change):
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=caller)
    assert result.status == "completed", result.public_dict()
    return {key: result.data[key] for key in ("plan_id", "plan_hash")}


def commit(engine, caller, approval):
    return engine.execute("commit_write", approval, context=caller)


def list_starts(vendor):
    starts = []
    for method, url, body, headers in vendor.calls:
        if url == media.MEDIA_LIST:
            starts.append(int(dict(parse_qsl(body.decode()))["start"]))
    return starts


def test_upload_associates_exact_new_row_and_preserves_meeting_unknowns(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, upload_change(engine, caller))
    assert vendor.counts == {"metadata": 0, "storage": 0, "meeting": 0}
    result = commit(engine, caller, approval)
    assert result.status == "completed", result.public_dict()
    item = result.data["items"][0]
    assert item["resource_id"] == "99"
    agenda = vendor.meeting[P + "data"][0]["items"][0]
    assert agenda["files"] == [{"filename": "agenda.pdf", "usetype": "official"}]
    assert agenda["extra"] == {"keep": True}
    assert vendor.meeting[P + "files"] == ROW[P + "files"]
    assert vendor.meeting["unrecognized"] == ROW["unrecognized"]
    assert vendor.counts == {"metadata": 1, "storage": 1, "meeting": 1}
    for method, url, body, headers in vendor.calls:
        if method == "PUT" and url.startswith(media.FILES_ORIGIN):
            assert "Authorization" not in headers
        if method == "GET" and url.startswith(media.FILES_ORIGIN):
            assert "Authorization" not in headers
    assert "synthetic-secret" not in json.dumps(result.public_dict())


def test_preexisting_filename_fails_with_intended_error_before_allocation(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    vendor.media.append({F + "id": "45", F + "filename": "agenda.pdf", F + "mime_type": "application/pdf",
                         F + "size_kb": len(PAYLOAD) // 1000, F + "created_ts": "2026-01-01T00:00:00Z"})
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [upload_change(engine, caller)]}, context=caller)
    assert result.status == "failed", result.public_dict()
    assert result.errors[0].code == "ambiguous_filename"
    assert vendor.counts == {"metadata": 0, "storage": 0, "meeting": 0}


def test_library_paging_reads_exact_bounded_pages(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    vendor.media = [{F + "id": str(i), F + "filename": f"file{i}.pdf", F + "mime_type": "application/pdf",
                     F + "size_kb": 1, F + "created_ts": "2026-01-01T00:00:00Z"} for i in range(1, 152) if i != 99]
    approval = plan(engine, caller, upload_change(engine, caller))
    starts = list_starts(vendor)
    assert 0 in starts and 100 in starts
    result = commit(engine, caller, approval)
    assert result.status == "completed", result.public_dict()
    assert vendor.counts == {"metadata": 1, "storage": 1, "meeting": 1}
    assert 100 in list_starts(vendor)


def test_allocation_timeout_uncertain_and_never_replayed(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, upload_change(engine, caller))
    vendor.fail_metadata = "timeout"
    result = commit(engine, caller, approval)
    assert result.data["items"][0]["state"] == "uncertain"
    assert vendor.counts == {"metadata": 1, "storage": 0, "meeting": 0}
    vendor.fail_metadata = None
    caller.cancellation.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "media.sqlite"))
    register(reopened, default_adapters(vendor))
    again = commit(reopened, caller, approval)
    assert again.data["items"][0]["state"] == "uncertain"
    assert vendor.counts == {"metadata": 1, "storage": 0, "meeting": 0}


@pytest.mark.parametrize("failure", ["error", "timeout"])
def test_storage_put_error_or_timeout_is_uncertain_and_never_replayed(tmp_path, failure):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, upload_change(engine, caller))
    vendor.fail_storage = failure
    result = commit(engine, caller, approval)
    assert result.data["items"][0]["state"] == "uncertain"
    assert vendor.counts == {"metadata": 1, "storage": 1, "meeting": 0}
    vendor.fail_storage = None
    caller.cancellation.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "media.sqlite"))
    register(reopened, default_adapters(vendor))
    again = commit(reopened, caller, approval)
    assert again.data["items"][0]["state"] == "uncertain"
    assert vendor.counts == {"metadata": 1, "storage": 1, "meeting": 0}


def test_mismatched_uploaded_bytes_are_uncertain_and_never_replayed(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, upload_change(engine, caller))
    vendor.corrupt_files = True
    result = commit(engine, caller, approval)
    assert result.data["items"][0]["state"] == "uncertain"
    assert vendor.counts == {"metadata": 1, "storage": 1, "meeting": 0}
    vendor.corrupt_files = False
    caller.cancellation.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "media.sqlite"))
    register(reopened, default_adapters(vendor))
    again = commit(reopened, caller, approval)
    assert again.data["items"][0]["state"] == "uncertain"
    assert vendor.counts == {"metadata": 1, "storage": 1, "meeting": 0}


@pytest.mark.parametrize("phase", ["metadata", "storage", "meeting"])
def test_cancellation_after_each_send_is_uncertain_and_restart_reconciles_without_replay(tmp_path, phase):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, upload_change(engine, caller))
    if phase == "metadata":
        vendor.after_metadata = caller.cancellation.set
    elif phase == "storage":
        vendor.after_storage = caller.cancellation.set
    else:
        vendor.after_meeting = caller.cancellation.set
    result = commit(engine, caller, approval)
    assert result.data["items"][0]["state"] == "uncertain"
    expected = {"metadata": 1, "storage": 1 if phase in {"storage", "meeting"} else 0,
                "meeting": 1 if phase == "meeting" else 0}
    assert vendor.counts == expected
    caller.cancellation.clear()
    vendor.after_metadata = vendor.after_storage = vendor.after_meeting = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "media.sqlite"))
    register(reopened, default_adapters(vendor))
    again = commit(reopened, caller, approval)
    assert vendor.counts == expected
    if phase == "meeting":
        assert again.data["items"][0]["state"] == "succeeded"
    else:
        assert again.data["items"][0]["state"] == "uncertain"


def test_restart_reconciles_confirmed_upload_without_mutation(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, upload_change(engine, caller, association=False))
    vendor.fail_storage = "timeout"
    result = commit(engine, caller, approval)
    assert result.data["items"][0]["state"] == "uncertain"
    assert vendor.counts == {"metadata": 1, "storage": 1, "meeting": 0}
    vendor.fail_storage = None
    caller.cancellation.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "media.sqlite"))
    register(reopened, default_adapters(vendor))
    again = commit(reopened, caller, approval)
    assert again.data["items"][0]["state"] == "succeeded"
    assert again.data["items"][0]["resource_id"] == "99"
    assert vendor.counts == {"metadata": 1, "storage": 1, "meeting": 0}


def test_cancelled_final_readback_blocks_upload_only_success_and_reconciliation(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, upload_change(engine, caller, association=False))
    vendor.after_files = caller.cancellation.set
    result = commit(engine, caller, approval)
    assert result.data["items"][0]["state"] == "uncertain"
    assert vendor.counts == {"metadata": 1, "storage": 1, "meeting": 0}
    caller.cancellation.clear()
    vendor.after_files = caller.cancellation.set
    reopened = Engine(storage=SQLiteStorage(tmp_path / "media.sqlite"))
    register(reopened, default_adapters(vendor))
    again = commit(reopened, caller, approval)
    assert again.data["items"][0]["state"] == "uncertain"
    assert vendor.counts == {"metadata": 1, "storage": 1, "meeting": 0}


def test_storage_response_bounds_and_write_response_subclass(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    class PermittedResponse(WriteResponse):
        pass
    class FakeTransport:
        def __init__(self, response):
            self.response = response
        def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
            return self.response
    class FakeAdapter:
        def __init__(self, response):
            self.transport = FakeTransport(response)
        def credentials(self, source, context):
            return {"city_code": "1311"}
    bounds = type("Bounds", (), {"parser_bytes": 10, "transfer_bytes": 10})()
    content = media._storage_get(FakeAdapter(PermittedResponse(200, b"1234567890")),
                                 SOURCE, caller, bounds, float("inf"), "agenda.pdf")
    assert content == b"1234567890"
    media._put_storage(FakeAdapter(PermittedResponse(200, b"")), caller, bounds, float("inf"),
                       "https://files.dev.gworks.cloud/upload", {"content_type": "application/pdf"}, b"")
    with pytest.raises(media.AmbiguousWrite):
        media._storage_get(FakeAdapter(PermittedResponse(200, b"12345678901")),
                           SOURCE, caller, bounds, float("inf"), "agenda.pdf")
    with pytest.raises(media.AmbiguousWrite):
        media._put_storage(FakeAdapter(PermittedResponse(200, b"x" * 11)), caller, bounds, float("inf"),
                           "https://files.dev.gworks.cloud/upload", {"content_type": "application/pdf"}, b"")


def test_unapproved_storage_destination_blocks_put(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    approval = plan(engine, caller, upload_change(engine, caller))
    vendor.signed_url = "https://evil.example/upload"
    result = commit(engine, caller, approval)
    assert result.data["items"][0]["state"] == "uncertain"
    assert vendor.counts == {"metadata": 1, "storage": 0, "meeting": 0}


def test_trusted_files_city_code_and_tenant_are_required_before_mutation(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    caller.credentials["gworks"].pop("city_code")
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [upload_change(engine, caller)]}, context=caller)
    assert result.status == "failed"
    assert vendor.counts == {"metadata": 0, "storage": 0, "meeting": 0}
    caller.credentials["gworks"]["city_code"] = "1311"
    caller.credentials["gworks"]["tenant"] = "other"
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [upload_change(engine, caller)]}, context=caller)
    assert result.status == "failed"
    assert vendor.counts == {"metadata": 0, "storage": 0, "meeting": 0}
