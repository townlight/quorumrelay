"""Synthetic public Engine tests for current Boardable Agenda Builder writes."""

import base64
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import hashlib
import json
from urllib.parse import quote

from quorumrelay import Engine, OperationContext
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register

API = "https://app.boardable.com/api/agenda-approvals"
ROOT = "https://app.boardable.com/quorumrelay-evaluation/"
SOURCE = {"provider": "boardable", "url": ROOT, "namespace": "boardable:current"}
ORG = "46098"
MEETING = "526552"
PARENT = 4819381
ITEM = 4819383
NEW_ITEM = 4819464
NEW_UPLOAD = 1458225
PAYLOAD = ("\ufeff" + "A" * 129 + "\r\n").encode("utf-8")
assert len(PAYLOAD) == 134


def _upload(upload_id, filename, mime, size, agenda_id=ITEM):
    return {
        "id": upload_id,
        "owner_id": None,
        "organization_id": int(ORG),
        "filename": filename,
        "agenda_id": agenda_id,
        "order": 0,
        "created_at": "2026-11-16T20:40:21.000000Z",
        "updated_at": "2026-11-16T20:40:26.000000Z",
        "name": filename,
        "file": str(upload_id) + "--fixture.bin",
        "mime_type": mime,
        "file_size": size,
        "url": ROOT + "agenda/uploads/download/" + str(upload_id) + "/" + quote(filename, safe=""),
        "downloadUrl": ROOT + "agenda/uploads/download/" + str(upload_id) + "/" + quote(filename, safe=""),
        "title": filename,
        "pdf": None,
        "uuid": {"uuid": "fixture"},
    }


class Vendor:
    mock = True

    def __init__(self):
        self.calls = []
        self.faults = set()
        self.last_json = None
        self.last_multipart = None
        self.after_mutation = None
        self.mutated = False
        self.upload_bytes = {}
        existing = _upload(1458197, "Mission and Vision Statement.pdf", "application/pdf", 41388)
        self.meeting = {
            "id": int(MEETING),
            "owner_id": 403839,
            "can_manage_agenda": True,
            "is_public": False,
            "needs_draft_preparation": False,
            "agenda_live_version": 1,
            "agenda_draft_version": 1,
            "agenda_items": [
                {"id": PARENT, "text": "Welcome", "description": "", "depth": 0, "order": 1,
                 "duration": 0, "is_private": False, "owner": None, "approval_tree": None,
                 "presenters": [], "uploads": [],
                 "children": [
                     {"id": ITEM, "text": "Reading of the mission and vision", "description": "",
                      "depth": 1, "order": 2, "duration": 0, "is_private": False,
                      "owner": {"id": 403839, "name": "CivicCast"},
                      "approval_tree": None, "presenters": [], "uploads": [existing],
                      "children": []}
                 ]},
                {"id": 4819384, "text": "Changes to the Agenda", "description": "", "depth": 0,
                 "order": 2, "duration": 0, "is_private": False, "owner": None,
                 "approval_tree": None, "presenters": [], "uploads": [], "children": []},
            ],
        }
        self.items = {
            ITEM: {
                "id": ITEM, "parent_agenda_id": PARENT, "text": "Reading of the mission and vision",
                "description": "", "duration": 0, "is_private": False,
                "meeting": {"id": int(MEETING), "title": "Test Board Meeting", "can_manage_agenda": True},
                "uploads": [deepcopy(existing)], "attachments": [{"id": 1458197, "type": "attachment",
                                                                  "attachment_id": 1458197,
                                                                  "filename": existing["filename"]}],
                "durationRange": {"min": 0, "max": 60},
                "approval_tree": None,
                "owner": {"id": 403839, "name": "CivicCast"},
                "presenters": [],
            }
        }

    def _parse_multipart(self, body, content_type):
        message = BytesParser(policy=default).parsebytes(
            ("Content-Type: " + content_type + "\r\n\r\n").encode() + body
        )
        fields, files = [], []
        for part in message.iter_parts():
            name = part.get_param("name", header="Content-Disposition")
            filename = part.get_filename()
            payload = part.get_payload(decode=True)
            if filename is not None:
                files.append({"name": name, "filename": filename,
                              "content_type": part.get_content_type(), "data": payload})
            else:
                fields.append((name, payload.decode("utf-8")))
        return fields, files

    def _append_created(self, title, description, duration, private, parent):
        uploads = []
        row = {"id": NEW_ITEM, "parent_agenda_id": parent, "text": title, "description": description,
               "depth": 0, "order": 10, "duration": duration, "is_private": private,
               "owner": {"id": 403839, "name": "CivicCast"},
               "approval_tree": None, "presenters": [], "uploads": uploads, "children": []}
        if parent:
            stack = list(self.meeting["agenda_items"])
            while stack:
                candidate = stack.pop()
                if candidate["id"] == parent:
                    row["depth"] = candidate.get("depth", 0) + 1
                    candidate.setdefault("children", []).append(row)
                    return row
                stack.extend(candidate.get("children", []))
        self.meeting["agenda_items"].append(row)
        return row

    def _append_update(self, update, files):
        item = self.items[ITEM]
        for key, value in update.items():
            if key == "title":
                item["text"] = value
            elif key == "description":
                item["description"] = value
            elif key == "duration":
                item["duration"] = int(value)
            elif key == "is_private":
                item["is_private"] = value in {"1", "true", True}
            elif key == "owner_id":
                item["owner"] = {"id": int(value), "name": "CivicCast"}
            elif key == "approval_tree_id":
                item["approval_tree"] = None if value in {"", None} else {"id": int(value)}
            elif key == "presenters":
                item["presenters"] = [{"id": int(v), "name": "Presenter"} for v in value]
            elif key == "attachments":
                ids = [int(row["attachment_id"]) for row in value if row.get("type") == "attachment"]
                item["uploads"] = [u for u in item["uploads"] if u["id"] in ids]
        if files:
            for file_row in files:
                upload_id = NEW_UPLOAD + len(item["uploads"])
                data = file_row["data"]
                self.upload_bytes[upload_id] = data
                row = _upload(upload_id, file_row["filename"], file_row["content_type"], len(data))
                if "wrong_download_url" in self.faults:
                    row["url"] = "https://evil.example/agenda/uploads/download/" + str(upload_id) + "/" + quote(file_row["filename"], safe="")
                    row["downloadUrl"] = row["url"]
                item["uploads"].append(row)
                if "duplicate_upload" in self.faults:
                    item["uploads"].append(deepcopy(row))
        for agenda_row in self.meeting["agenda_items"]:
            for child in agenda_row.get("children", []):
                if child["id"] == ITEM:
                    child["text"] = item["text"]
                    child["description"] = item["description"]
                    child["duration"] = item["duration"]
                    child["is_private"] = item["is_private"]
                    child["owner"] = deepcopy(item["owner"])
                    child["approval_tree"] = deepcopy(item["approval_tree"])
                    child["presenters"] = deepcopy(item["presenters"])
                    child["uploads"] = deepcopy(item["uploads"])
        self.mutated = True

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert deadline_seconds > 0
        self.calls.append((method, url, body, headers))
        assert "Authorization" not in headers
        meeting_url = API + "/meetings/" + MEETING
        if method == "GET" and url == meeting_url:
            if "readback_failure" in self.faults and self.mutated:
                raise TimeoutError()
            return WriteResponse(200, json.dumps({"data": deepcopy(self.meeting)}).encode())
        if method == "GET" and url.startswith(API + "/agenda-items/"):
            item_id = int(url.rsplit("/", 1)[1])
            if "readback_failure" in self.faults and self.mutated:
                raise TimeoutError()
            if item_id not in self.items:
                return WriteResponse(404)
            return WriteResponse(200, json.dumps({"data": deepcopy(self.items[item_id])}).encode())
        if method == "POST" and url == API + "/agenda-items":
            if "create_timeout_after_mutation" in self.faults:
                self._append_created("QuorumRelay API contract evaluation", "", 2, False, 0)
                self.mutated = True
                raise TimeoutError()
            if "create_no_id" in self.faults:
                self.mutated = True
                return WriteResponse(201, json.dumps({"data": {"text": "No id"}}).encode())
            if body[:1] == b"{":
                request = json.loads(body)
                self.last_json = request
                row = self._append_created(request["title"], request["description"], request["duration"],
                                           request["is_private"], request.get("parent_id") or 0)
            else:
                fields, files = self._parse_multipart(body, headers["Content-Type"])
                self.last_multipart = {"fields": fields, "files": files}
                values = dict(fields)
                row = self._append_created(values["title"], values.get("description", ""),
                                           int(values.get("duration", "0")),
                                           values.get("is_private") == "1",
                                           int(values.get("parent_id", "0")))
            self.items[NEW_ITEM] = {
                "id": NEW_ITEM, "parent_agenda_id": row.get("parent_agenda_id", 0),
                "text": row["text"], "description": row["description"], "duration": row["duration"],
                "is_private": row["is_private"], "meeting": {"id": int(MEETING), "can_manage_agenda": True},
                "uploads": [], "attachments": [], "durationRange": {"min": 0, "max": 60},
                "approval_tree": None, "owner": {"id": 403839, "name": "CivicCast"}, "presenters": [],
            }
            if self.last_multipart:
                for index, file_row in enumerate(self.last_multipart["files"]):
                    upload_id = NEW_UPLOAD + index
                    self.upload_bytes[upload_id] = file_row["data"]
                    upload = _upload(upload_id, file_row["filename"], file_row["content_type"],
                                     len(file_row["data"]), agenda_id=NEW_ITEM)
                    self.items[NEW_ITEM]["uploads"].append(upload)
            row["uploads"] = deepcopy(self.items[NEW_ITEM]["uploads"])
            self.mutated = True
            if self.after_mutation:
                self.after_mutation()
            return WriteResponse(201, json.dumps({"data": {"id": NEW_ITEM, "text": "QuorumRelay API contract evaluation"}}).encode())
        if url == API + "/agenda-items/" + str(ITEM) and method in {"PUT", "POST"}:
            if method == "PUT":
                request = json.loads(body)
                self.last_json = request
                update = {key: request[key] for key in ("title", "description", "duration", "is_private",
                                                        "owner_id", "approval_tree_id", "presenters")
                          if key in request}
                self._append_update(update, [])
            else:
                fields, files = self._parse_multipart(body, headers["Content-Type"])
                self.last_multipart = {"fields": fields, "files": files}
                values = dict(fields)
                presenters = []
                attachments = []
                for key, value in fields:
                    if key.startswith("presenters["):
                        presenters.append(value)
                    if key.endswith("[type]") and value == "attachment":
                        index = key.split("[")[1].split("]")[0]
                        attachments.append({"type": "attachment",
                                            "attachment_id": dict(fields)[f"attachments[{index}][attachment_id]"]})
                update = {"title": values["title"], "description": values.get("description", ""),
                          "duration": values["duration"], "is_private": values["is_private"],
                          "owner_id": values.get("owner_id"), "approval_tree_id": values.get("approval_tree_id"),
                          "presenters": presenters, "attachments": attachments}
                self._append_update(update, files)
            if "update_timeout_after_mutation" in self.faults:
                raise TimeoutError()
            if self.after_mutation:
                self.after_mutation()
            return WriteResponse(200, json.dumps({"message": "Updated."}).encode())
        if method == "GET" and url.startswith(ROOT + "agenda/uploads/download/"):
            assert "Cookie" in headers and "Authorization" not in headers
            tail = url[len(ROOT + "agenda/uploads/download/"):]
            upload_id = int(tail.split("/", 1)[0])
            data = self.upload_bytes.get(upload_id, b"")
            if "corrupt_file" in self.faults:
                data = b"corrupt"
            return WriteResponse(200, data)
        raise AssertionError((method, url))


def setup(tmp_path):
    vendor = Vendor()
    context = OperationContext(
        principal="editor", client_id="fixture", tenant="city",
        authorization=frozenset({"write:plan", "write:commit"}),
        allowed_namespaces=frozenset({SOURCE["namespace"]}),
        credentials={"boardable": {
            "tenant": "city", "org_url": ROOT, "current_agenda_builder": True,
            "allowed_namespaces": [SOURCE["namespace"]], "organization_id": ORG,
            "session_cookie": "boardable_session=secret-session", "csrf_token": "secret-csrf",
            "meeting_ids": [MEETING], "permissions": ["item:create", "item:update"],
            "owner_id": 403839,
        }},
    )
    engine = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(engine, default_adapters(vendor))
    return engine, context, vendor


def plan(engine, context, change):
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [change]}, context=context)
    assert result.status == "completed", result.public_dict()
    return {key: result.data[key] for key in ("plan_id", "plan_hash")}


def _stage(engine, caller, data=PAYLOAD, filename="agenda.txt"):
    for name in ("stage_file", "stage_write_file"):
        method = getattr(engine, name, None)
        if method is not None:
            try:
                handle = method(data, filename=filename, content_type="text/plain", context=caller)
            except TypeError:
                handle = method(data, context=caller)
            return {"file_handle": handle}
    return {"content_base64": base64.b64encode(data).decode()}


def file_part(engine, caller, *, inline=False, filename="agenda.txt"):
    reference = ({"content_base64": base64.b64encode(PAYLOAD).decode()}
                 if inline else _stage(engine, caller, filename=filename))
    return {"part": "file", "filename": filename, "content_type": "text/plain", **reference}


def create_change(engine, caller, **overrides):
    value = {
        "key": "create", "entity": "item", "operation": "create", "meeting_id": MEETING,
        "parent_id": 0, "fields": {"text": "QuorumRelay API contract evaluation",
                                    "description": "", "duration": 2, "is_private": False},
    }
    value.update(overrides)
    return value


def update_change(engine, caller, **overrides):
    value = {
        "key": "update", "entity": "item", "operation": "update", "meeting_id": MEETING,
        "resource_id": str(ITEM), "fields": {"text": "Updated title"},
    }
    value.update(overrides)
    return value


def test_json_create_exact_schema_and_restart_no_replay(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, create_change(engine, context))
    assert not any(method == "POST" for method, _, _, _ in vendor.calls)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert vendor.last_json == {
        "title": "QuorumRelay API contract evaluation", "description": "", "duration": 2,
        "meeting_id": int(MEETING), "extra_meeting_date_id": None, "parent_id": None,
        "approval_tree_id": None, "owner_id": 403839, "presenters": [], "is_private": False,
        "attachments": [],
    }
    assert result.data["items"][0]["resource_id"] == str(NEW_ITEM)
    assert "secret-" not in json.dumps(result.public_dict())
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    assert reopened.execute("commit_write", approval, context=context).status == "completed"
    assert sum(method == "POST" for method, _, _, _ in vendor.calls) == 1


def test_multipart_create_with_inline_file_and_exact_schema(tmp_path):
    engine, context, vendor = setup(tmp_path)
    change = create_change(engine, context, files=[file_part(engine, context, inline=True)])
    approval = plan(engine, context, change)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    fields = dict(vendor.last_multipart["fields"])
    assert fields["title"] == "QuorumRelay API contract evaluation"
    assert fields["meeting_id"] == MEETING and fields["owner_id"] == "403839"
    assert fields["attachments[0][type]"] == "upload"
    assert vendor.last_multipart["files"][0]["filename"] == "agenda.txt"
    assert vendor.last_multipart["files"][0]["data"] == PAYLOAD
    upload = result.data["items"][0]["readback"]["item"]["uploads"][0]
    assert upload["file_size"] == len(PAYLOAD)
    assert hashlib.sha256(PAYLOAD).hexdigest()


def test_json_update_preserves_existing_attachments_owner_and_presenters(tmp_path):
    engine, context, vendor = setup(tmp_path)
    change = update_change(engine, context, fields={"text": "Updated title", "description": "Desc",
                                                     "duration": 5, "is_private": True})
    approval = plan(engine, context, change)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert vendor.last_json["title"] == "Updated title"
    assert vendor.last_json["owner_id"] == 403839
    assert vendor.last_json["approval_tree_id"] is None
    assert vendor.last_json["presenters"] == []
    assert vendor.last_json["attachments"] == [{"type": "attachment", "attachment_id": 1458197}]
    assert result.data["items"][0]["readback"]["item"]["uploads"][0]["id"] == 1458197


def test_multipart_update_with_file_preserves_existing_and_uses_method_put(tmp_path):
    engine, context, vendor = setup(tmp_path)
    change = update_change(engine, context, fields={"text": "Updated with file"},
                           files=[file_part(engine, context)])
    approval = plan(engine, context, change)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    fields = vendor.last_multipart["fields"]
    values = dict(fields)
    assert values["_method"] == "PUT"
    assert values["approval_tree_id"] == ""
    assert values["owner_id"] == "403839"
    assert values["attachments[0][type]"] == "attachment"
    assert values["attachments[0][attachment_id]"] == "1458197"
    assert values["attachments[1][type]"] == "upload"
    uploads = result.data["items"][0]["readback"]["item"]["uploads"]
    assert uploads[0]["id"] == 1458197
    assert uploads[1]["filename"] == "agenda.txt" and uploads[1]["file_size"] == len(PAYLOAD)


def test_hierarchy_membership_and_needs_draft_preparation_block_mutation(tmp_path):
    engine, context, vendor = setup(tmp_path)
    bad_parent = create_change(engine, context, parent_id=999)
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [bad_parent]}, context=context)
    assert result.status == "failed"
    vendor.meeting["needs_draft_preparation"] = True
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [create_change(engine, context)]}, context=context)
    assert result.status == "failed"
    assert not any(method == "POST" for method, _, _, _ in vendor.calls)


def test_missing_auth_and_unsafe_origin_or_filename_do_not_send(tmp_path):
    engine, context, vendor = setup(tmp_path)
    context.credentials["boardable"].pop("session_cookie")
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [create_change(engine, context)]}, context=context)
    assert result.status == "failed"
    assert not vendor.calls
    context.credentials["boardable"]["session_cookie"] = "boardable_session=secret-session"
    context.credentials["boardable"]["org_url"] = "https://evil.example/org/"
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [create_change(engine, context)]}, context=context)
    assert result.status == "failed"
    context.credentials["boardable"]["org_url"] = ROOT
    bad = file_part(engine, context, filename="../escape.txt")
    result = engine.execute("plan_write", {"source": SOURCE, "changes": [update_change(engine, context, files=[bad])]}, context=context)
    assert result.status == "failed"
    assert not any(method == "POST" for method, _, _, _ in vendor.calls)


def test_conflict_after_plan_prevents_mutation(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, update_change(engine, context))
    vendor.meeting["agenda_items"][1]["text"] = "Changed elsewhere"
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "conflict"
    assert not any(method in {"PUT", "POST"} for method, _, _, _ in vendor.calls)


def test_create_conflict_after_plan_prevents_mutation(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, create_change(engine, context))
    vendor.meeting["agenda_items"][0]["text"] = "Changed elsewhere"
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "conflict"
    assert not any(method in {"PUT", "POST"} for method, _, _, _ in vendor.calls)


def test_item_detail_change_after_plan_prevents_update_mutation(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, update_change(engine, context))
    vendor.items[ITEM]["description"] = "Changed elsewhere"
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "conflict"
    assert not any(method in {"PUT", "POST"} for method, _, _, _ in vendor.calls)


def test_create_collateral_tree_change_is_uncertain_and_never_replayed(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, create_change(engine, context))

    def collateral():
        vendor.meeting["agenda_items"][1]["text"] = "Collateral"

    vendor.after_mutation = collateral
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    vendor.after_mutation = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(method == "POST" for method, _, _, _ in vendor.calls) == 1


def test_update_collateral_tree_change_is_uncertain_and_never_replayed(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, update_change(engine, context, fields={"text": "Collateral update"}))

    def collateral():
        vendor.meeting["agenda_items"][1]["text"] = "Collateral"

    vendor.after_mutation = collateral
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    vendor.after_mutation = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(method == "PUT" for method, _, _, _ in vendor.calls) == 1


def test_create_timeout_after_persisted_mutation_without_id_stays_uncertain(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add("create_timeout_after_mutation")
    approval = plan(engine, context, create_change(engine, context))
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    assert not result.data["items"][0].get("resource_id")
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(method == "POST" for method, _, _, _ in vendor.calls) == 1


def test_create_known_id_readback_failure_reconciles_after_restart(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add("readback_failure")
    approval = plan(engine, context, create_change(engine, context))
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    assert result.data["items"][0]["resource_id"] == str(NEW_ITEM)
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.status == "completed", again.public_dict()
    assert sum(method == "POST" for method, _, _, _ in vendor.calls) == 1


def test_unknown_created_id_is_not_rediscovered_by_title(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add("create_no_id")
    approval = plan(engine, context, create_change(engine, context))
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(method == "POST" for method, _, _, _ in vendor.calls) == 1


def test_cancellation_after_update_write_is_uncertain_and_restart_reconciles(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context, update_change(engine, context))
    vendor.after_mutation = context.cancellation.set
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    context.cancellation.clear()
    vendor.after_mutation = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.status == "completed", again.public_dict()
    assert sum(method == "PUT" for method, _, _, _ in vendor.calls) == 1


def test_update_timeout_after_persisted_mutation_restart_reconciles(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add("update_timeout_after_mutation")
    approval = plan(engine, context, update_change(engine, context))
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.status == "completed", again.public_dict()
    assert sum(method == "PUT" for method, _, _, _ in vendor.calls) == 1


def test_duplicate_new_upload_identity_is_uncertain_and_never_replayed(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add("duplicate_upload")
    approval = plan(engine, context, update_change(engine, context, files=[file_part(engine, context)]))
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(method == "POST" for method, _, _, _ in vendor.calls) == 1


def test_corrupt_downloaded_attachment_is_uncertain_then_exact_readback_recovers_without_replay(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add("corrupt_file")
    approval = plan(engine, context, update_change(engine, context, files=[file_part(engine, context)]))
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.status == "completed", again.public_dict()
    assert again.data["items"][0]["state"] == "succeeded"
    assert sum(method == "POST" for method, _, _, _ in vendor.calls) == 1


def test_wrong_declared_download_url_is_uncertain_without_route_following(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add("wrong_download_url")
    approval = plan(engine, context, update_change(engine, context, files=[file_part(engine, context)]))
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    assert sum(method == "POST" for method, _, _, _ in vendor.calls) == 1
    assert not any(method == "GET" and url.startswith("https://evil.example") for method, url, _, _ in vendor.calls)
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.data["items"][0]["state"] == "uncertain"
    assert sum(method == "POST" for method, _, _, _ in vendor.calls) == 1


def test_update_readback_failure_is_uncertain_then_restart_confirms(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add("readback_failure")
    approval = plan(engine, context, update_change(engine, context, fields={"text": "Readback update"}))
    result = engine.execute("commit_write", approval, context=context)
    assert result.data["items"][0]["state"] == "uncertain"
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / "write.sqlite"))
    register(reopened, default_adapters(vendor))
    again = reopened.execute("commit_write", approval, context=context)
    assert again.status == "completed", again.public_dict()
    assert sum(method == "PUT" for method, _, _, _ in vendor.calls) == 1


def test_file_handle_binding_survives_child_adapter_rebinding(tmp_path):
    engine, context, vendor = setup(tmp_path)
    change = update_change(engine, context, files=[file_part(engine, context, inline=False)])
    approval = plan(engine, context, change)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert vendor.last_multipart["files"][0]["data"] == PAYLOAD
