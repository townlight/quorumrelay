"""Named historical files preserve exact inputs; no FTP or vendor acceptance."""

import base64
import hashlib
import io
import json
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.interchange import cleanup_artifacts, open_artifact, stage_input

PDF = (Path(__file__).parent / "fixtures" / "baseline" / "boarddocs-minooka.pdf").read_bytes()
SOURCE = {"provider": "civicplus-select", "url": "https://city.portal.civicclerk.com"}


def request(file_type="Agenda", payload=PDF):
    return {"provider_specific": True, "format": "civicplus-historical-files", "source": SOURCE,
            "meeting": {"body": "City Council", "meeting_type": "Regular Meeting", "meeting_date": "2020-12-18",
                        "unknown": {"keep": True}},
            "files": [{"file_type": file_type, "content_type": "application/pdf",
                       "content_base64": base64.b64encode(payload).decode()}]}


def engine():
    owner = create_engine()
    assert "civicplus-select" in owner.native_exports
    return owner


def context(**kwargs):
    return OperationContext(authorization=frozenset({"export_attachments"}), **kwargs)


@pytest.mark.parametrize("token", ["Agenda", "Agenda Packet", "Minutes"])
def test_official_example_filenames_exact_bytes_hashes_and_disclosed_losses(token):
    result = engine().execute("export", request(token), context=context())
    assert result.status == "completed", result.public_dict()
    content = base64.b64decode(result.data["content_base64"])
    name = f"City Council_Regular Meeting_{token}_12_18_2020.pdf"
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert archive.namelist() == [name, "manifest.json"]
        assert archive.read(name) == PDF
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest == result.data["manifest"]
    assert manifest["files"][0]["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert manifest["meeting"]["unknown"] == {"keep": True}
    assert manifest["vendor_transfer_performed"] is False
    assert manifest["vendor_import_accepted"] is False
    assert manifest["vendor_size_limit"] == "not_documented"
    assert manifest["projection_losses"]


def test_scoped_large_input_streamed_output_and_current_policy():
    owner, ctx = engine(), context(allowed_operations=frozenset({"export"}))
    staged = stage_input(owner, "pdf", io.BytesIO(PDF), filename="original.pdf", content_type="application/pdf",
                         context=ctx)
    req = request()
    req.update(stream=True, bounds={"parser_bytes": 1024})
    req["files"] = [{"file_type": "Agenda Packet", "file_handle": staged["file_handle"]}]
    result = owner.execute("export", req, context=ctx)
    assert result.status == "completed", result.public_dict()
    assert result.data["artifact_id"]
    _, stream = open_artifact(owner, result.data["artifact_id"], context=ctx)
    with stream, zipfile.ZipFile(stream) as archive:
        assert archive.read("City Council_Regular Meeting_Agenda Packet_12_18_2020.pdf") == PDF
    revoked = replace(ctx, authorization=frozenset())
    with pytest.raises(ValueError):
        open_artifact(owner, result.data["artifact_id"], context=revoked)
    denied = owner.execute("export", req, context=context(principal="another"))
    assert denied.status == "failed"
    cleanup_artifacts(owner)


@pytest.mark.parametrize("token", ["Packet", "Notice", "Notices", "Other", "Media", "Audio/Video"])
def test_ambiguous_tokens_are_mapping_gaps_without_fabricated_vendor_files(token):
    result = engine().execute("export", request(token), context=context())
    assert result.status == "unsupported"
    assert result.errors[0].code == "provider_filename_mapping_unverified"
    assert result.data is None


def test_authorization_delimiters_duplicates_file_bytes_and_bounds():
    owner, req = engine(), request()
    assert owner.execute("export", req).status == "failed"
    assert owner.execute("export", req, context=context(allowed_namespaces=frozenset())).status == "failed"
    for body in ("../City", "City_Council", "City\\Council", "City:Council", "City\x01Council", " City"):
        req = request()
        req["meeting"]["body"] = body
        assert owner.execute("export", req, context=context()).status == "failed"
    req = request()
    req["files"] *= 2
    assert owner.execute("export", req, context=context()).status == "failed"
    req = request()
    req["files"].append({**req["files"][0], "file_type": "Minutes"})
    assert owner.execute("export", req, context=context()).status == "failed"  # Duplicate bytes.
    for payload in (b"not PDF", b"%PDF-1.7\nnot a PDF object tree\n%%EOF"):
        assert owner.execute("export", request(payload=payload), context=context()).status == "failed"
    req = request()
    req["bounds"] = {"transfer_bytes": 10}
    assert owner.execute("export", req, context=context()).status == "failed"
    req = request()
    req["bounds"] = {"date_from": "2021-01-01"}
    assert owner.execute("export", req, context=context()).status == "failed"
    req = request()
    req["source"] = {**SOURCE, "body": "Other Council"}
    assert owner.execute("export", req, context=context()).status == "failed"
    req = request()
    req["files"][0]["content_type"] = "video/mp4"
    assert owner.execute("export", req, context=context()).status == "failed"
    cancelled = context()
    cancelled.cancellation.set()
    assert owner.execute("export", request(), context=cancelled).status == "cancelled"
