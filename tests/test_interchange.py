"""Neutral interchange, file guards and independently specified projections."""

import base64
import hashlib
import io
import json
import zipfile
import secrets
from copy import deepcopy

import pytest

from civic_data_connectors import Engine, imports, interchange, search
from civic_data_connectors.interchange import (
    Attachment, csv_projection, icalendar_projection, read_bundle, write_bundle,
)
from civic_data_connectors.models import Bounds, OperationContext
from civic_data_connectors.storage import SQLiteStorage
from test_storage_search_imports import sample


@pytest.mark.parametrize("format", ["json", "jsonl", "zip"])
def test_lossless_unknown_schema_identity_capture_roundtrip(format):
    bundle = sample()
    bundle["records"][0]["original"]["sha256"] = "not a capture"
    bundle["records"][0]["original"]["content_base64"] = "unknown original field"
    output = io.BytesIO()
    manifest = write_bundle(bundle, output, format=format)
    assert manifest["projection_losses"] == []
    payload = output.getvalue()
    assert hashlib.sha256(payload).hexdigest() == manifest["output"]["sha256"]
    assert read_bundle(payload, format=format) == bundle
    engine = Engine()
    imports.register(engine)
    result = engine.execute("import_preview", {"format": format}, content=payload)
    assert result.status == "completed", result.public_dict()
    assert result.data["bundle"] == bundle
    base64_result = engine.execute("import_preview",
                                  {"format": format, "content_base64": base64.b64encode(payload).decode()})
    assert base64_result.status == "completed", base64_result.public_dict()
    assert base64_result.data["bundle"] == bundle
    conflict = engine.execute("import_preview",
                              {"format": format, "content_base64": base64.b64encode(payload).decode()},
                              content=payload)
    assert conflict.status == "failed"
    assert "not both" in conflict.errors[0].message
    for bad in ("%%%not base64", 4):
        invalid = engine.execute("import_preview", {"format": format, "content_base64": bad})
        assert invalid.status == "failed" and invalid.errors
    bounded = engine.execute("import_preview", {"format": format,
                            "content_base64": base64.b64encode(payload).decode(),
                            "bounds": {"parser_bytes": 16, "transfer_bytes": 16}})
    assert bounded.status == "failed"


@pytest.mark.parametrize("format", ["json", "jsonl"])
def test_text_export_resolves_stored_capture_portably(tmp_path, format):
    bundle = sample()
    raw = base64.b64decode(bundle["capture"].pop("content_base64"))
    store = SQLiteStorage(tmp_path / "capture-export.sqlite")
    bundle["capture"]["storage_reference"] = store.save_capture(io.BytesIO(raw), scope="scope", max_bytes=len(raw))
    before = deepcopy(bundle)
    target = io.BytesIO()
    write_bundle(bundle, target, format=format, storage=store, scope="scope")
    recovered = read_bundle(target.getvalue(), format=format)
    assert recovered["records"] == bundle["records"]
    assert base64.b64decode(recovered["capture"]["content_base64"]) == raw
    assert recovered["capture"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert bundle == before
    with pytest.raises(ValueError):
        write_bundle(bundle, io.BytesIO(), format=format, storage=store, scope="other")


def test_provider_export_never_silently_becomes_neutral():
    from civic_data_connectors import create_engine
    result = create_engine().execute("export", {"bundle": sample(), "provider_specific": True})
    assert result.status == "unsupported"
    assert "does not establish" in result.errors[0].message


def test_engine_import_search_export_roundtrip_no_remote_action(tmp_path):
    engine = Engine(storage=SQLiteStorage(tmp_path / "data.sqlite"))
    imports.register(engine)
    search.register(engine)
    interchange.register(engine)
    assert engine.execute("import_bundle", {"bundle": sample(), "persist": True}).status == "completed"
    result = engine.execute("search", {"query": {"phrases": ["water district"]}})
    exported = engine.execute("export", {"records": result.data["records"], "format": "zip",
                                         "coverage": result.coverage})
    assert exported.status == "completed", exported.public_dict()
    restored = engine.execute("import_bundle", {"format": "zip", "persist": True},
                              content=base64.b64decode(exported.data["content_base64"]))
    assert restored.status == "completed"
    assert restored.data["changes"][0]["outcome"] == "unchanged"


def test_attachment_allowlist_and_filename_is_only_data():
    attachments = [
        Attachment("allowed", io.BytesIO(b"authorized attachment"), "../../unsafe-name.pdf",
                   "https://city.example/meeting/7/packet"),
        Attachment("denied", io.BytesIO(b"do not include"), "other.pdf", "https://city.example/other"),
    ]
    output = io.BytesIO()
    manifest = write_bundle(sample(), output, attachments=attachments,
                            authorized_attachments=frozenset({"allowed"}))
    assert manifest["not_included"] == [{"id": "denied", "reason": "not_authorized"}]
    captured = []
    read_bundle(output.getvalue(), attachment_sink=lambda metadata, stream:
                captured.append((metadata, stream.read())))
    assert len(captured) == 1
    assert captured[0][1] == b"authorized attachment"
    assert captured[0][0]["filename"] == "../../unsafe-name.pdf"
    with zipfile.ZipFile(io.BytesIO(output.getvalue())) as archive:
        assert not any("unsafe" in name or ".." in name for name in archive.namelist())
        assert b"do not include" not in b"".join(archive.read(name) for name in archive.namelist())


def _rewrite_zip(payload, transform):
    source, destination = io.BytesIO(payload), io.BytesIO()
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(destination, "w") as after:
        for item in before.infolist():
            name, data = transform(item.filename, before.read(item.filename))
            after.writestr(name, data)
    return destination.getvalue()


@pytest.mark.parametrize("malicious", ["../escape", "/absolute", "C:/drive", "folder\\escape", "folder/./entry"])
def test_zip_path_escape_rejected(malicious):
    output = io.BytesIO()
    write_bundle(sample(), output)
    payload = _rewrite_zip(output.getvalue(), lambda name, data:
                           (malicious if name == "bundle.json" else name, data))
    with pytest.raises(ValueError):
        read_bundle(payload)


def test_hash_mismatch_duplicate_member_and_unexpected_member_rejected():
    output = io.BytesIO()
    write_bundle(sample(), output)
    broken = _rewrite_zip(output.getvalue(), lambda name, data:
                          (name, data + b" " if name == "records.jsonl" else data))
    with pytest.raises(ValueError, match="hash/length"):
        read_bundle(broken)
    duplicated = io.BytesIO(output.getvalue())
    with pytest.warns(UserWarning):
        with zipfile.ZipFile(duplicated, "a") as archive:
            archive.writestr("bundle.json", b"{}")
    with pytest.raises(ValueError, match="Duplicate"):
        read_bundle(duplicated.getvalue())
    extra = io.BytesIO(output.getvalue())
    with zipfile.ZipFile(extra, "a") as archive:
        archive.writestr("surprise.txt", b"unexpected")
    with pytest.raises(ValueError, match="Unexpected"):
        read_bundle(extra.getvalue())


def test_stream_original_larger_than_parser_cap_and_storage_reference(tmp_path):
    # Capture is a 17 MiB synthetic packet, metadata and each record remain small.
    data = b"%PDF synthetic not parsed\n" + b"x" * (17 * 1024 * 1024)
    store = SQLiteStorage(tmp_path / "captures.sqlite")
    reference = store.save_capture(io.BytesIO(data), scope="scope-a", max_bytes=len(data))
    bundle = sample()
    bundle["capture"] = {"sha256": hashlib.sha256(data).hexdigest(), "byte_length": len(data),
                         "storage_reference": reference, "citation_url": "https://city.example/durable"}
    output = io.BytesIO()
    write_bundle(bundle, output, storage=store, scope="scope-a")
    restored = read_bundle(output.getvalue(), capture_storage=store, scope="scope-b")
    assert restored["capture"]["citation_url"] == "https://city.example/durable"
    with store.open_capture(restored["capture"]["storage_reference"], scope="scope-b") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == hashlib.sha256(data).hexdigest()
    with pytest.raises(ValueError, match="capture_storage"):
        read_bundle(output.getvalue())
    with pytest.raises(ValueError):
        read_bundle(output.getvalue(), bounds=Bounds(transfer_bytes=16 * 1024 * 1024))


def test_csv_rfc4180_quoting_formula_guard_and_explicit_losses():
    record = sample()["records"][0]
    record["normalized"]["title"] = '=SUM(1,2)\r\n"quoted"'
    payload, losses = csv_projection([record])
    # RFC 4180: embedded quote doubled, comma/newline field enclosed in quotes.
    assert b'"\'=SUM(1,2)\r\n""quoted"""' in payload
    assert b"\r\n" in payload
    assert losses["lossless"] is False
    assert "future.a" in losses["records"][0]["omitted_fields"]
    assert "original.unknown[0]" in losses["records"][0]["omitted_fields"]
    items, losses = csv_projection([record], kind="items")
    assert b"Parks budget" in items
    assert b"item_external_id" in items
    assert losses["lossless"] is False


def test_ical_rfc5545_literal_datetime_escaping_folding_and_stable_uid():
    record = sample()["records"][0]
    record["normalized"]["scheduled_start"] = "1998-01-18T07:30:00Z"
    record["normalized"]["title"] = "Hello, council; path\\name\n" + "é" * 100
    payload, losses = icalendar_projection([record])
    # Literal RFC 5545 section 3.8.2.4 example, not output generated as expectation.
    assert b"DTSTART:19980118T073000Z\r\n" in payload
    assert b"SUMMARY:Hello\\, council\\; path\\\\name\\n" in payload
    assert all(len(line) <= 75 for line in payload.split(b"\r\n"))
    assert b"DTSTAMP:20261111T150000Z" in payload
    first_uid = next(line for line in payload.split(b"\r\n") if line.startswith(b"UID:"))
    changed = deepcopy(record)
    changed["normalized"]["title"] = "Revised title"
    second, _ = icalendar_projection([changed])
    assert first_uid in second
    changed["normalized"]["scheduled_start"] = "1998-01-18T07:30:00"
    floating, floating_losses = icalendar_projection([changed])
    assert b"DTSTART:19980118T073000\r\n" in floating
    assert "floating" in str(floating_losses)
    assert losses["lossless"] is False
    assert "future.a" in losses["records"][0]["omitted_fields"]


@pytest.mark.parametrize("durable", [False, True])
def test_registered_streaming_attachment_artifact_scope_policy_expiry_cleanup(tmp_path, durable):
    store = SQLiteStorage(tmp_path / "artifacts.sqlite") if durable else None
    engine = Engine(storage=store)
    interchange.register(engine)
    context = OperationContext(authorization=frozenset({"export_attachments"}),
                               allowed_operations=frozenset({"export"}),
                               allowed_namespaces=frozenset({"city.example"}))
    data = secrets.token_bytes(17 * 1024 * 1024)
    interchange.stage_attachment(engine, "packet", io.BytesIO(data), filename="../packet.pdf",
                                  citation_url="https://city.example/durable-packet",
                                  namespace="city.example", context=context)
    result = engine.execute("export", {"bundle": sample(), "format": "zip", "stream": True,
                                       "attachment_ids": ["packet"]}, context=context)
    assert result.status == "completed", result.public_dict()
    assert "content_base64" not in result.data
    artifact_id = result.data["artifact_id"]
    target = Engine(storage=store) if durable else engine
    metadata, stream = interchange.open_artifact(target, artifact_id, context=context)
    assert metadata["byte_length"] > 16 * 1024 * 1024
    assert "storage_reference" not in metadata
    with stream:
        captured = []
        read_bundle(stream, attachment_sink=lambda info, payload: captured.append(hashlib.file_digest(payload, "sha256").hexdigest()))
    assert captured == [hashlib.sha256(data).hexdigest()]
    for blocked in (
        OperationContext(tenant="other", authorization=context.authorization),
        OperationContext(allowed_operations=frozenset(), authorization=context.authorization),
        OperationContext(allowed_namespaces=frozenset({"other"}), authorization=context.authorization),
        OperationContext(),
    ):
        with pytest.raises(ValueError):
            interchange.open_artifact(target, artifact_id, context=blocked)
    if durable:
        item = store.get("artifacts", artifact_id, scope=context.scope)
        store.put("artifacts", artifact_id, {**item.value, "expires_at": 0},
                  scope=context.scope, expected_version=item.version)
    else:
        engine._civic_artifacts.values[(context.scope, "artifacts", artifact_id)][0]["expires_at"] = 0
    with pytest.raises(ValueError):
        interchange.open_artifact(target, artifact_id, context=context)
    interchange.cleanup_artifacts(engine)
    assert not hasattr(engine, "_civic_artifacts")


@pytest.mark.parametrize("format", ["json", "zip"])
def test_saved_bundle_export_is_exact_and_scoped(tmp_path, format):
    engine = Engine(storage=SQLiteStorage(tmp_path / "bundles.sqlite"))
    imports.register(engine)
    interchange.register(engine)
    bundle = sample()
    bundle["unknown_bundle"] = {"original": [False, 0, "", None, {"non_ascii": "café"}]}
    imported = engine.execute("import_bundle", {"bundle": bundle, "persist": True})
    key = imported.data["bundle_key"]
    exported = engine.execute("export", {"bundle_key": key, "format": format})
    assert exported.status == "completed", exported.public_dict()
    assert read_bundle(base64.b64decode(exported.data["content_base64"]), format=format) == bundle
    for blocked in (OperationContext(tenant="different"), OperationContext(allowed_namespaces=frozenset())):
        result = engine.execute("export", {"bundle_key": key, "format": format}, context=blocked)
        assert result.status == "failed" and result.errors
    assert engine.execute("export", {"bundle_key": "f" * 64}).status == "failed"


@pytest.mark.parametrize("format", ["json", "jsonl", "zip"])
def test_original_bundle_integrity_checked_before_capture_storage(tmp_path, format):
    class ObservedStorage(SQLiteStorage):
        saves = 0
        def save_capture(self, *args, **kwargs):
            self.saves += 1
            return super().save_capture(*args, **kwargs)
    store = ObservedStorage(tmp_path / "integrity.sqlite")
    output = io.BytesIO()
    write_bundle(sample(), output, format=format)
    payload = output.getvalue()
    if format == "json":
        item = json.loads(payload)
        item["bundle"]["unknown_bundle"]["tampered"] = True
        payload = json.dumps(item).encode()
    elif format == "jsonl":
        lines = payload.splitlines()
        item = json.loads(lines[0])
        item["bundle"]["unknown_bundle"]["tampered"] = True
        lines[0] = json.dumps(item).encode()
        payload = b"\n".join(lines) + b"\n"
    else:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        item = json.loads(members["bundle.json"])
        item["unknown_bundle"]["tampered"] = True
        members["bundle.json"] = json.dumps(item).encode()
        manifest = json.loads(members["manifest.json"])
        for entry in manifest["entries"]:
            if entry["path"] == "bundle.json":
                entry["sha256"] = hashlib.sha256(members["bundle.json"]).hexdigest()
                entry["byte_length"] = len(members["bundle.json"])
        members["manifest.json"] = json.dumps(manifest).encode()
        changed = io.BytesIO()
        with zipfile.ZipFile(changed, "w") as archive:
            for name, value in members.items():
                archive.writestr(name, value)
        payload = changed.getvalue()
    with pytest.raises(ValueError, match="bundle hash"):
        read_bundle(payload, format=format, capture_storage=store, scope="scope")
    assert store.saves == 0


@pytest.mark.parametrize("durable", [False, True])
def test_generic_input_staging_immutable_scoped_verified_and_not_export_granted(tmp_path, durable):
    engine = Engine(storage=SQLiteStorage(tmp_path / "inputs.sqlite") if durable else None)
    context = OperationContext(allowed_operations=frozenset({"normalize"}))
    data = b"immutable supplied input"
    item = interchange.stage_input(engine, "upload-1", io.BytesIO(data), filename="../../input.pdf",
                                    content_type="application/pdf", context=context, max_bytes=len(data))
    metadata, stream = interchange.open_input(engine, item["file_handle"], context=context,
                                               expected_sha256=hashlib.sha256(data).hexdigest(),
                                               expected_byte_length=len(data))
    with stream:
        assert stream.read() == data
    assert metadata["filename"] == "../../input.pdf"  # Metadata, never a path.
    with pytest.raises(ValueError):
        interchange.stage_input(engine, "upload-1", io.BytesIO(b"replaced"), filename="new",
                                  content_type="application/pdf", context=context)
    for other in (OperationContext(tenant="other"), OperationContext(allowed_operations=frozenset({"status"}))):
        with pytest.raises(ValueError):
            interchange.open_input(engine, item["file_handle"], context=other)
    with pytest.raises(ValueError):
        interchange.open_input(engine, item["file_handle"], context=context, expected_sha256="0" * 64)
    with pytest.raises(ValueError):
        interchange.open_input(engine, item["file_handle"], context=context, expected_byte_length=1)
    with pytest.raises(ValueError):
        interchange.stage_input(engine, "too-large", io.BytesIO(b"123"), filename="input",
                                  content_type="text/plain", context=context, max_bytes=2)
    interchange.cleanup_artifacts(engine)
