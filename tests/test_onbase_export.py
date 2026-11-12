"""Synthetic destination configuration; emitted bytes checked against Hyland layout rules."""

import base64
import hashlib
import io
import json
import zipfile
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.interchange import cleanup_artifacts, open_artifact, stage_input

SOURCE = {"provider": "onbase", "url": "https://city.example.org/OnBaseAgendaOnline"}
PAYLOAD = b"Explicit synthetic meeting document; no file type inferred."


def request():
    return {"provider_specific": True, "format": "onbase-tagged-dip-files", "source": SOURCE,
        "tags": {"begin": "BEGIN:", "document_type": "DocTypeName:",
                 "file_type": "FileType:", "file_name": "FileName:"},
        "index_encoding": "ascii",
        "files": [{"file_type": "document", "content_type": "text/plain",
                   "content_base64": base64.b64encode(PAYLOAD).decode()}],
        "documents": [{"file_index": 0, "filename": "agenda.txt", "document_type": "Meeting Agenda",
                       "file_type_number": 42, "keywords": [
                           {"tag": "MeetingID:", "keyword_type": "Meeting ID", "value": "123"}]}]}


def context(**kwargs):
    return OperationContext(authorization=frozenset({"export_attachments"}), **kwargs)


def test_emitted_layout_bytes_and_destination_configuration_are_explicit():
    result = create_engine().execute("export", request(), context=context())
    assert result.status == "completed", result.public_dict()
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(result.data["content_base64"]))) as archive:
        # Independent expected layout from Hyland: case-sensitive configured tags,
        # no delimiters, newline separator, exclusive Begin; File Type before Name.
        assert archive.read("index.txt") == (
            b"BEGIN:\r\nDocTypeName:Meeting Agenda\r\nFileType:42\r\nMeetingID:123\r\nFileName:agenda.txt\r\n")
        assert archive.read("agenda.txt") == PAYLOAD
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest == result.data["manifest"]
    assert manifest["configuration"]["field_order"] == [
        {"tag": "BEGIN:", "keyword_type": ">>Begin Document, Exclusive"},
        {"tag": "DocTypeName:", "keyword_type": ">>Document Type"},
        {"tag": "FileType:", "keyword_type": ">>File Type"},
        {"tag": "MeetingID:", "keyword_type": "Meeting ID"},
        {"tag": "FileName:", "keyword_type": ">>File Name"}]
    assert manifest["files"][0]["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert manifest["vendor_transfer_performed"] is False
    assert manifest["vendor_import_accepted"] is False
    assert "No Agenda meeting/item relationship" in manifest["projection_losses"][0]


@pytest.mark.parametrize("mutation", ["newline", "taglength", "tagprefix", "path", "reserved", "reservedspace", "filetype", "system"])
def test_unsafe_or_ambiguous_destination_mapping_rejected(mutation):
    req = request()
    doc = req["documents"][0]
    if mutation == "newline":
        doc["document_type"] = "Meeting\nBEGIN:"
    elif mutation == "taglength":
        req["tags"]["begin"] = "a" * 20 + ":"
    elif mutation == "tagprefix":
        req["tags"]["begin"] = "FileName:Extra:"
    elif mutation == "path":
        doc["filename"] = "../agenda.txt"
    elif mutation == "reserved":
        doc["filename"] = "CON.txt"
    elif mutation == "reservedspace":
        doc["filename"] = "CON .txt"
    elif mutation == "filetype":
        doc["file_type_number"] = True
    else:
        doc["keywords"][0]["keyword_type"] = ">>Revision"
    result = create_engine().execute("export", req, context=context())
    assert result.status == "failed", result.public_dict()
    assert not result.data


def test_multiple_documents_repeated_keywords_unknown_metadata_and_collision():
    req = request()
    req["files"].append(deepcopy(req["files"][0]))
    second = deepcopy(req["documents"][0])
    second.update(file_index=1, filename="minutes.txt", document_type="Meeting Minutes", unknown="manifest only")
    second["keywords"].append({"tag": "MeetingID:", "keyword_type": "Meeting ID", "value": "456"})
    req["documents"].append(second)
    result = create_engine().execute("export", req, context=context())
    assert result.status == "completed", result.public_dict()
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(result.data["content_base64"]))) as archive:
        raw = archive.read("index.txt")
        assert raw.count(b"BEGIN:\r\n") == 2
        assert b"MeetingID:123\r\nMeetingID:456\r\n" in raw
        assert b"manifest only" not in raw
    assert result.data["manifest"]["files"][1]["mapping"]["unknown"] == "manifest only"
    second["filename"] = "AGENDA.TXT"
    assert create_engine().execute("export", req, context=context()).status == "failed"


def test_scoped_streamed_files_and_revoked_output_policy():
    owner, ctx = create_engine(), context(allowed_operations=frozenset({"export"}))
    staged = stage_input(owner, "document", io.BytesIO(PAYLOAD), filename="document.txt",
                         content_type="text/plain", context=ctx)
    req = request()
    req["files"] = [{"file_type": "document", "file_handle": staged["file_handle"]}]
    req["stream"] = True
    result = owner.execute("export", req, context=ctx)
    assert result.status == "completed", result.public_dict()
    _, stream = open_artifact(owner, result.data["artifact_id"], context=ctx)
    with stream, zipfile.ZipFile(stream) as archive:
        assert archive.read("agenda.txt") == PAYLOAD
    with pytest.raises(ValueError):
        open_artifact(owner, result.data["artifact_id"], context=replace(ctx, authorization=frozenset()))
    assert owner.execute("export", req, context=context(principal="another")).status == "failed"
    cleanup_artifacts(owner)


def test_transfer_encoding_bounds_and_cancellation():
    req = request()
    req["documents"][0]["document_type"] = "Conseil municipal é"
    assert create_engine().execute("export", req, context=context()).status == "failed"
    req["index_encoding"] = "utf-8"
    assert create_engine().execute("export", req, context=context()).status == "completed"
    req["bounds"] = {"transfer_bytes": 10}
    assert create_engine().execute("export", req, context=context()).status == "failed"
    req.pop("bounds")
    cancelled = context()
    cancelled.cancellation.set()
    assert create_engine().execute("export", req, context=cancelled).status == "cancelled"


def test_independent_vendor_example_figure_is_pinned_separately_from_spa_shells():
    root = Path(__file__).parents[1] / "docs/capabilities/evidence/onbase-dip"
    source = json.loads((root / "source.json").read_bytes())
    figure = source["sources"][0]["figure"]
    raw = (root / figure["path"]).read_bytes()
    assert raw.startswith(b"GIF89a")
    assert hashlib.sha256(raw).hexdigest() == figure["sha256"]
    assert "SPA bootstrap shell" in source["sources"][0]["http_body_kind"]
    assert source["release"] == "Foundation26.1"
