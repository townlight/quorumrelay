"""Official extracted contracts are the independent oracle for native requests."""

import base64
import json
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from jsonschema import Draft202012Validator

from civic_data_connectors import Engine, OperationContext
from civic_data_connectors.storage import SQLiteStorage
from civic_data_connectors.write_adapters import (
    LEGISTAR, WriteAdapter, check_write_adapter, default_adapters,
)
from civic_data_connectors.write_transport import WriteResponse
from civic_data_connectors.writes import register


CONTRACTS = json.loads((Path(__file__).parents[1] / "docs/capabilities/provider-api-contracts.json").read_text(encoding="utf-8"))
SRT = "1\n00:00:01,000 --> 00:00:02,000\nSynthetic meeting\n"


def multipart(headers, body):
    message = BytesParser(policy=default).parsebytes(
        ("Content-Type: " + headers["Content-Type"] + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + body
    )
    fields, files = {}, []
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        value = part.get_payload(decode=True)
        if part.get_filename():
            files.append({"part": name, "filename": part.get_filename(), "content": value,
                          "content_type": part.get_content_type()})
        else:
            fields[name] = value.decode()
    if "request" in fields:
        fields = json.loads(fields["request"])
    return fields, files


def response(value=None, status=200, headers=None):
    return WriteResponse(status, b"" if value is None else json.dumps(value).encode(), headers or {})


class DocumentedNetwork:
    """Synthetic fixtures implement the wire shapes in official guides/OpenAPI."""

    mock = True

    def __init__(self, provider):
        self.provider = provider
        self.calls = []
        self.rows = {}
        self.files = {}
        self.fields = {}
        self.tags = {}
        self.captions = {"media1:eng": {"language": "eng", "id": "caption1", "media_id": "media1",
                                       "version": 1, "is_draft": False, "segments": None, "text": SRT}}
        self.pages = {}
        self.parts = []
        self.job = None
        self.deny = False
        self.lose = False
        self.reject_key = None
        self.last_request = None

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        parsed = urlsplit(url)
        self.calls.append((method, parsed.path))
        assert deadline_seconds > 0
        if parsed.hostname == "signed.example.org":
            assert "Authorization" not in headers
            if method == "PUT":
                self.parts.append(body)
                return WriteResponse(200, headers={"etag": "etag-" + str(len(self.parts))})
            return WriteResponse(200, self.files[parsed.path.strip("/")])
        if self.provider == "legistar":
            assert parse_qs(parsed.query)["token"] == ["synthetic-token"]
        else:
            assert headers["Authorization"] == "Bearer synthetic-token"
        if self.deny and method != "GET":
            return response({"error": "not authorized"}, 403)
        fields, files = {}, []
        if body:
            if headers["Content-Type"].startswith("multipart/form-data"):
                fields, files = multipart(headers, body)
            elif headers["Content-Type"] == "application/x-www-form-urlencoded":
                fields = {k: v[0] for k, v in parse_qs(body.decode()).items()}
            else:
                fields = json.loads(body)
        self.last_request = {"url": url, "method": method, "headers": headers, "fields": fields, "files": files}
        if self.provider == "legistar":
            return self.legistar(parsed, method, fields)
        if self.provider == "wistia":
            return self.wistia(parsed, method, fields, files, headers)
        return self.laserfiche(parsed, method, fields, files)

    def legistar(self, parsed, method, fields):
        if parsed.path.endswith("/File"):
            return WriteResponse(200, self.files[parsed.path[:-5]])
        if method == "GET":
            if "$filter" in parse_qs(parsed.query):
                term = parse_qs(parsed.query)["$filter"][0]
                return response([r for r in self.rows.values() if any(
                    k.endswith("Guid") and v in term for k, v in r.items() if isinstance(v, str)
                )])
            return response(self.rows[parsed.path])
        # Determine the independent official model from the native route suffix.
        suffix = parsed.path.split("/fixture-city/", 1)[1]
        entity = ("matter_attachment" if "/Attachments" in suffix else
                  "matter_text" if "/Texts" in suffix else "matter_history" if "/Histories" in suffix else
                  "event_item" if "/EventItems" in suffix else "event" if suffix.startswith("Events") else "matter")
        official = next(c for c in CONTRACTS["legistar"]
                        if c["method_path"].startswith(method + " ")
                        and (("Attachments" in c["method_path"]) == (entity == "matter_attachment"))
                        and (("Texts" in c["method_path"]) == (entity == "matter_text"))
                        and (("Histories" in c["method_path"]) == (entity == "matter_history"))
                        and (("EventItems" in c["method_path"]) == (entity == "event_item"))
                        and c["method_path"].split("/")[2] == ("Events" if entity.startswith("event") else "Matters"))
        known = {f["name"]: f for f in official["model_fields"]}
        assert set(fields).issubset(known)
        for field in official["model_fields"]:
            if field["requirement"] == "Required":
                assert field["name"] in fields
        assert "MatterAttachmentSort" not in fields
        assert "MeetingId" not in fields
        prefix = LEGISTAR[entity][1]
        row = {**fields, prefix + "Id": 1, prefix + "RowVersion": "AQ=="}
        path = parsed.path if method == "PUT" else parsed.path + "/1"
        self.rows[path] = row
        if "MatterAttachmentBinary" in row:
            self.files[path] = base64.b64decode(row["MatterAttachmentBinary"])
        if self.lose:
            self.lose = False
            raise TimeoutError("synthetic response loss")
        return response(row)

    def wistia(self, parsed, method, fields, files, headers):
        if parsed.hostname == "upload.wistia.com":
            assert "X-Wistia-API-Version" not in headers
            self.rows["media2"] = {"id": 2, "hashed_id": "media2", "name": fields.get("name", "synthetic"),
                                   "description": fields.get("description", ""), "status": "processing",
                                   "updated": "2026-11-11T00:00:00Z"}
            return response(self.rows["media2"])
        assert headers["X-Wistia-API-Version"] == "2026-09"
        route = parsed.path.removeprefix("/modern")
        if method == "GET":
            if route.startswith("/background_job_status/"):
                return response({"background_job_status": self.job})
            if "/captions/" in route:
                return response(self.captions[route.split("/")[2] + ":" + route.split("/")[4]])
            return response(self.rows[route.split("/")[-1]])
        for contract in CONTRACTS["wistia"]:
            for path, operations in contract["spec"]["paths"].items():
                pattern = path.replace("{mediaHashedId}", "media1").replace("{languageCode}", "eng")
                if route == pattern and method.lower() in operations:
                    content = operations[method.lower()]["requestBody"]["content"]
                    if not files:
                        kind = headers["Content-Type"]
                        Draft202012Validator(content[kind]["schema"]).validate(fields)
        if route == "/medias/import_url":
            self.job = {"id": 3, "hashed_id": "job3", "status": "queued"}
            return response({"message": "queued", "background_job_status": self.job}, 201)
        if route == "/taggings/bulk_create":
            for i in fields["hashed_ids"]:
                existing = [t["name"] if isinstance(t, dict) else t for t in self.rows[i].get("tags", [])]
                self.rows[i]["tags"] = [{"name": t} for t in sorted(set(existing + fields["tag_names"]))]
            self.job = {"id": 3, "hashed_id": "job3", "status": "queued"}
            return response({"message": "queued", "background_job_status": self.job})
        if "/captions" in route:
            key = "media1:eng"
            value = fields.get("caption_file") or (files[0]["content"].decode() if files else None)
            if route.endswith("/edits"):
                old = self.captions[key]["version"]
                if fields["expected_version"] != old:
                    return response({"reason": "stale_version", "errors": ["stale"]}, 409)
                for edit in fields["edits"]:
                    self.captions[key]["text"] = self.captions[key]["text"].replace(
                        edit["target_text"], edit["replacement_text"])
                self.captions[key]["version"] += 1
                return response({"applied": True, "media_id": "media1", "language": "eng",
                                 "version": {"from": old, "to": old + 1}, "edits": [], "warnings": []})
            self.captions[key]["text"] = value
            self.captions[key]["version"] += 1
            return response()
        self.rows["media1"].update(fields)
        self.rows["media1"]["updated"] = "2026-11-11T01:00:00Z"
        return response(self.rows["media1"])

    def laserfiche(self, parsed, method, fields, files):
        path = parsed.path
        root = "/repository/v2/Repositories/repo1"
        if path.endswith("/CreateMultipartUploadUrls"):
            assert fields["startingPartNumber"] == 1
            return response({"uploadId": "upload1", "urls": [
                "https://signed.example.org/part" + str(i) + "?sig=synthetic-signed-secret"
                for i in range(fields["numberOfParts"])
            ]})
        if path.endswith(("/ImportUploadedParts", "/UpdateUploadedParts")):
            assert fields["uploadId"] == "upload1" and fields["partETags"] == ["etag-1"]
            self.rows["1"] = {"id": 1, "name": fields.get("name", "large.pdf"), "pageCount": 0,
                              "lastModifiedTime": "2026-11-11T00:00:00Z"}
            self.files["1"] = b"".join(self.parts)
            return response({"taskId": "task1"}, 202)
        if path.endswith("/Tasks"):
            assert parse_qs(parsed.query)["taskIds"] == ["task1"]
            return response({"value": [{"id": "task1", "status": "Completed", "errors": [],
                                        "result": {"entryId": 1}}]})
        if path.endswith("/Export"):
            assert fields == {"part": "Edoc"}
            return response({"value": "https://signed.example.org/1?sig=synthetic-signed-secret"})
        if method == "GET":
            tail = path.split("/Entries/", 1)[1]
            identity = tail.split("/")[0]
            if tail.endswith("/Fields"):
                return response({"value": self.fields.get(identity, [])})
            if tail.endswith("/Tags"):
                return response({"value": [{"name": t} for t in self.tags.get(identity, [])]})
            if "/Pages/" in tail:
                number = int(tail.split("/Pages/")[1].split("/")[0])
                return response({"text": self.pages[identity][number - 1]})
            return response(self.rows[identity])
        assert path.startswith(root + "/Entries/")
        if path.endswith("/Folder/Import"):
            assert method == "POST"
            identity = "1"
            self.rows[identity] = {"id": 1, "name": fields["name"], "pageCount": 0,
                                   "lastModifiedTime": "2026-11-11T00:00:00Z"}
        else:
            identity = path.split("/Entries/")[1].split("/")[0]
            assert method in {"PATCH", "POST", "PUT"}
        row = self.rows[identity]
        if path.endswith("/Document/Pages"):
            self.pages[identity] = fields["textPages"] if method == "PUT" else (
                self.pages.get(identity, []) + fields["textPages"])
            row["pageCount"] = len(self.pages[identity])
        elif "/Document/Pages/" in path:
            number = int(path.rsplit("/", 1)[-1])
            self.pages[identity][number - 1] = fields["text"]
        for file in files:
            assert file["part"] == "file"
            self.files[identity] = file["content"]
        metadata = fields.get("metadata", {})
        if "templateName" in metadata:
            row["templateName"] = metadata["templateName"]
        if "fields" in metadata:
            self.fields[identity] = metadata["fields"]
        if "tags" in metadata:
            self.tags[identity] = sorted(set(self.tags.get(identity, []) + metadata["tags"]))
        return response(row, 201 if path.endswith("/Folder/Import") else 200)


def make_engine(tmp_path, provider, permissions, network=None):
    network = network or DocumentedNetwork(provider)
    namespace = {"legistar": "fixture-city", "wistia": "fixture-account", "laserfiche": "repo1"}[provider]
    source_url = {
        "legistar": "https://webapi.legistar.com/v1/fixture-city/events",
        "wistia": "https://fixture-account.wistia.com/",
        "laserfiche": "https://api.laserfiche.com/repository/v2/Repositories/repo1/Entries/9",
    }[provider]
    context = OperationContext(
        principal="editor", client_id="independent-fixture", tenant="newsroom-a",
        authorization=frozenset({"write:plan", "write:commit"}), allowed_namespaces=frozenset({namespace}),
        credentials={provider: {"token": "synthetic-token", "allowed_namespaces": [namespace],
                                "permissions": permissions, "meeting_ids": ["9", "meeting1"]}},
    )
    engine = Engine(storage=SQLiteStorage(tmp_path / "provider.sqlite"))
    register(engine, default_adapters(network))
    return engine, context, network, {"provider": provider, "url": source_url, "namespace": namespace}


def run(engine, context, source, change, bounds=None):
    result = engine.execute("plan_write", {"source": source, "changes": [change], "bounds": bounds or {}},
                            context=context)
    assert result.status == "completed", result.public_dict()
    assert "synthetic-token" not in json.dumps(result.public_dict())
    approval = {k: result.data[k] for k in ("plan_id", "plan_hash")}
    committed = engine.execute("commit_write", approval, context=context)
    return committed, approval


@pytest.mark.parametrize("entity,fields", [
    ("event", {"EventDate": "2026-11-11", "EventLocation": "Test room"}),
    ("event_item", {"EventItemTitle": "Supplied agenda item", "EventItemEventId": 9}),
    ("matter_attachment", {"MatterAttachmentName": "Meeting packet", "MatterAttachmentIsHyperlink": False,
                           "MatterAttachmentBinary": base64.b64encode(b"synthetic meeting PDF").decode()}),
    ("matter", {"MatterTypeId": 1, "MatterStatusId": 2, "MatterBodyId": 3, "MatterTitle": "Meeting matter"}),
    ("matter_text", {"MatterTextMatterId": 9, "MatterTextPlain": "Supplied meeting text"}),
    ("matter_history", {"MatterHistoryEventId": 9, "MatterHistoryActionText": "Supplied motion"}),
])
@pytest.mark.parametrize("operation", ["create", "update"])
def test_legistar_twelve_documented_entity_routes(tmp_path, entity, fields, operation):
    engine, context, network, source = make_engine(tmp_path, "legistar", [f"{entity}:create", f"{entity}:update"])
    parent = 9 if entity in {"event_item", "matter_attachment", "matter_text", "matter_history"} else None
    change = {"key": "item", "entity": entity, "operation": "create", "fields": fields,
              "meeting_id": "9" if entity not in {"event", "event_item"} else None, "parent_id": parent}
    result, _ = run(engine, context, source, change)
    assert result.status == "completed", result.public_dict()
    if operation == "update":
        change.update(operation="update", resource_id=1)
        result, _ = run(engine, context, source, change)
        assert result.status == "completed", result.public_dict()
        assert any(method == "PUT" for method, _ in network.calls)


def test_wistia_media_update_official_modern_body_and_tags(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "wistia", ["media:update"])
    network.rows["media1"] = {"id": 1, "hashed_id": "media1", "name": "Before", "tags": [{"name": "old"}],
                               "updated": "2026-11-11T00:00:00Z"}
    result, _ = run(engine, context, source, {"key": "media", "entity": "media", "operation": "update",
                                            "resource_id": "media1", "meeting_id": "meeting1",
                                            "fields": {"name": "After", "tags": ["new"]}})
    assert result.status == "completed", result.public_dict()
    assert network.rows["media1"]["tags"] == ["new"]


@pytest.mark.parametrize("as_file", [False, True])
def test_wistia_upload_uses_documented_distinct_server_and_form(tmp_path, as_file):
    engine, context, network, source = make_engine(tmp_path, "wistia", ["media:upload"])
    change = {"key": "upload", "entity": "media", "operation": "upload", "meeting_id": "meeting1",
              "fields": {"name": "Synthetic recording"}}
    if as_file:
        change["files"] = [{"part": "file", "filename": "recording.mp4", "content_type": "video/mp4",
                            "content_base64": base64.b64encode(b"synthetic media bytes").decode()}]
    else:
        change["fields"]["url"] = "https://example.org/synthetic.mp4"
    result, _ = run(engine, context, source, change)
    assert result.status == "completed", result.public_dict()
    assert result.data["items"][0]["readback"]["status"] == "processing"


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("as_file", [False, True])
def test_wistia_captions_json_or_file_empty_success_response_then_actual_get(tmp_path, operation, as_file):
    engine, context, network, source = make_engine(tmp_path, "wistia", [f"caption:{operation}"])
    change = {"key": "captions", "entity": "caption", "operation": operation, "parent_id": "media1",
              "language": "eng", "meeting_id": "meeting1", "fields": {}}
    if as_file:
        change["files"] = [{"part": "caption_file", "filename": "captions.srt", "content_type": "text/plain",
                            "content_base64": base64.b64encode(SRT.encode()).decode()}]
    else:
        change["fields"]["caption_file"] = SRT
    result, _ = run(engine, context, source, change)
    assert result.status == "completed", result.public_dict()
    assert any(method == "GET" and path.endswith("/captions/eng") for method, path in network.calls)


def test_wistia_caption_atomic_expected_version_and_readback(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "wistia", ["caption_edits:update"])
    change = {"key": "edits", "entity": "caption_edits", "operation": "update", "parent_id": "media1",
              "language": "eng", "meeting_id": "meeting1", "fields": {
                  "expected_version": 1, "edits": [{"target_text": "Synthetic", "replacement_text": "Fixture"}]}}
    result, _ = run(engine, context, source, change)
    assert result.status == "completed", result.public_dict()
    assert "Fixture meeting" in result.data["items"][0]["readback"]["text"]


def test_wistia_async_additive_tags_wait_then_read_every_target(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "wistia", ["media_tags:update"])
    network.rows = {i: {"hashed_id": i, "tags": [{"name": "old"}]} for i in ("media1", "media2")}
    result, approval = run(engine, context, source, {"key": "tags", "entity": "media_tags", "operation": "update",
                                                   "meeting_id": "meeting1", "fields": {
                                                       "hashed_ids": ["media1", "media2"], "tag_names": ["new"]}})
    assert result.status == "partial" and result.data["items"][0]["state"] == "pending"
    network.job["status"] = "finished"
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert all({t["name"] for t in m["tags"]} == {"old", "new"} for m in network.rows.values())
    assert sum(method == "POST" for method, _ in network.calls) == 1


@pytest.mark.parametrize("large", [False, True])
def test_laserfiche_file_submission_readback_and_durable_task(tmp_path, large):
    entity = "document_large" if large else "document"
    engine, context, network, source = make_engine(tmp_path, "laserfiche", [f"{entity}:upload"])
    data = b"synthetic meeting packet"
    change = {"key": "doc", "entity": entity, "operation": "upload", "parent_id": 9,
              "meeting_id": "meeting1", "fields": {"name": "packet.pdf"}, "files": [{
                  "part": "file", "filename": "packet.pdf", "content_type": "application/pdf",
                  "content_base64": base64.b64encode(data).decode()}]}
    result, approval = run(engine, context, source, change)
    if large:
        assert result.status == "partial" and result.data["items"][0]["state"] == "pending"
        assert result.data["items"][0]["part_etags"] == ["etag-1"]
        assert "synthetic-signed-secret" not in json.dumps(result.public_dict())
        result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert network.files["1"] == data
    assert result.data["items"][0]["readback"]["_file_sha256"]


def test_laserfiche_metadata_additive_patch_readback(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "laserfiche", ["document:update"])
    network.rows["1"] = {"id": 1, "name": "packet.pdf", "pageCount": 0,
                          "lastModifiedTime": "2026-11-11T00:00:00Z", "templateName": "Meeting"}
    network.tags["1"] = ["prior"]
    result, _ = run(engine, context, source, {
        "key": "metadata", "entity": "document", "operation": "update", "resource_id": 1,
        "meeting_id": "meeting1", "fields": {"metadata": {"templateName": "Meeting",
                                                           "fields": [{"name": "Body", "values": ["Council"]}],
                                                           "tags": ["reviewed"]}}})
    assert result.status == "completed", result.public_dict()
    assert network.tags["1"] == ["prior", "reviewed"]


def test_laserfiche_supplied_page_text_create_and_update(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "laserfiche",
                                                 ["document_pages:create", "document_page:update"])
    network.rows["1"] = {"id": 1, "name": "minutes.pdf", "pageCount": 1}
    network.pages["1"] = ["prior page"]
    result, _ = run(engine, context, source, {
        "key": "pages", "entity": "document_pages", "operation": "create", "resource_id": 1,
        "meeting_id": "meeting1", "fields": {"textPages": ["supplied text"]}})
    assert result.status == "completed", result.public_dict()
    result, _ = run(engine, context, source, {
        "key": "page", "entity": "document_page", "operation": "update", "resource_id": 1, "page_number": 2,
        "meeting_id": "meeting1", "fields": {"text": "corrected supplied text"}})
    assert result.status == "completed", result.public_dict()
    assert network.pages["1"] == ["prior page", "corrected supplied text"]


def test_extension_conformance_is_nonexecuting_and_shared_coordinator(tmp_path):
    class IndependentAdapter(WriteAdapter):
        """An extension can replace transport/mappings without changing any interface."""

    network = DocumentedNetwork("legistar")
    adapter = IndependentAdapter("legistar", network)
    assert check_write_adapter(adapter) == []
    assert network.calls == []
    engine, context, _, source = make_engine(tmp_path, "legistar", ["event:create"], network)
    extension_engine = Engine(storage=engine.storage)
    register(extension_engine, {"legistar": adapter})
    result, _ = run(extension_engine, context, source, {
        "key": "extension", "entity": "event", "operation": "create", "fields": {"EventDate": "2026-11-11"}})
    assert result.status == "completed"


def test_caption_create_language_is_bound_to_the_actual_body(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "wistia", ["caption:create"])
    # A provider fixture detects English only when the body language is absent.
    class CaptionWire:
        mock = True
        def __init__(self):
            self.tracks = {}
            self.calls = []
        def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
            self.calls.append((method, url))
            if method == "POST":
                fields = json.loads(body)
                language = fields.get("language", "eng")
                self.tracks[language] = {"language": language, "text": fields["caption_file"]}
                return response()
            return response(self.tracks[url.rsplit("/", 1)[-1]])
    wire = CaptionWire()
    target = Engine(storage=engine.storage)
    register(target, default_adapters(wire))
    result, _ = run(target, context, source, {
        "key": "fre", "entity": "caption", "operation": "create", "parent_id": "media1",
        "meeting_id": "meeting1", "language": "fre", "fields": {"caption_file": SRT}})
    assert result.status == "completed"
    assert set(wire.tracks) == {"fre"}
    invalid = target.execute("plan_write", {"source": source, "changes": [{
        "key": "conflict", "entity": "caption", "operation": "create", "parent_id": "media1",
        "meeting_id": "meeting1", "language": "fre", "fields": {"caption_file": SRT, "language": "eng"}}]},
        context=context)
    assert invalid.status == "failed"


def test_successful_mutation_failed_readback_is_uncertain_keeps_id_never_reposts(tmp_path):
    class ReadbackNotVisible(DocumentedNetwork):
        def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
            if method == "GET":
                self.calls.append((method, urlsplit(url).path))
                return response({}, 404)
            return super().send(url, method=method, body=body, headers=headers,
                                byte_limit=byte_limit, deadline_seconds=deadline_seconds)
    network = ReadbackNotVisible("legistar")
    engine, context, network, source = make_engine(tmp_path, "legistar", ["event:create"], network)
    result, approval = run(engine, context, source, {
        "key": "event", "entity": "event", "operation": "create", "fields": {"EventDate": "2026-11-11"}})
    assert result.status == "partial"
    assert result.data["items"][0]["state"] == "uncertain"
    assert result.data["items"][0]["resource_id"] == 1
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "partial"
    assert sum(method == "POST" for method, _ in network.calls) == 1


@pytest.mark.parametrize("persisted", [False, True])
def test_large_upload_cancellation_stops_before_import_finalization(tmp_path, persisted):
    from civic_data_connectors.storage import update_operation
    engine, context, network, source = make_engine(tmp_path, "laserfiche", ["document_large:upload"])
    context.operation_id = "cancel-fixture"
    class CancelOnPart(DocumentedNetwork):
        def send(self, url, **kwargs):
            result = super().send(url, **kwargs)
            if urlsplit(url).hostname == "signed.example.org" and kwargs["method"] == "PUT":
                if persisted:
                    update_operation(engine.storage, context.operation_id, {"cancel_requested": True},
                                     scope=context.scope)
                else:
                    context.cancellation.set()
            return result
    network = CancelOnPart("laserfiche")
    owner = Engine(storage=engine.storage)
    register(owner, default_adapters(network))
    result, _ = run(owner, context, source, {
        "key": "doc", "entity": "document_large", "operation": "upload", "parent_id": 9,
        "meeting_id": "meeting1", "fields": {"name": "packet.pdf"}, "files": [{
            "part": "file", "filename": "packet.pdf", "content_type": "application/pdf",
            "content_base64": base64.b64encode(b"synthetic packet").decode()}]})
    assert result.status == "cancelled", result.public_dict()
    assert result.data["items"][0]["part_etags"] == ["etag-1"]
    assert not any(path.endswith("/ImportUploadedParts") for _, path in network.calls)
