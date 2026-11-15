"""Historical documented CSV bytes and scoped local artifact behavior."""
import base64
import csv
from dataclasses import replace
from hashlib import sha256
import io

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.interchange import open_artifact
from quorumrelay.storage import SQLiteStorage


def request():
    return {"source": {"provider": "telvue", "url": "https://connect.telvue.com/", "namespace": "telvue:fixture"},
        "provider_specific": True, "format": "telvue-cloudcast-4.1-chapters-csv",
        "chapters": [{"start": "00:00:20", "end": "00:00:30", "title": 'Budget, "é"',
            "summary": "First\nsecond", "description": "=source text"},
            {"start": "00:00:30", "end": "00:00:40", "title": "Vote"}]}


def test_headerless_five_columns_exact_content_hash_and_explicit_losses():
    result = create_engine().execute("export", request())
    assert result.status == "completed", result.public_dict()
    raw = base64.b64decode(result.data["content_base64"])
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"), newline="")))
    assert rows == [["00:00:20", "00:00:30", 'Budget, "é"', "First\nsecond", "=source text"],
                    ["00:00:30", "00:00:40", "Vote", "", ""]]
    manifest = result.data["manifest"]
    assert manifest["byte_length"] == len(raw) and manifest["sha256"] == sha256(raw).hexdigest()
    assert manifest["chapter_count"] == 2 and manifest["documented_version"] == "4.1.0 / June 2014"
    assert not manifest["vendor_transfer_performed"] and not manifest["vendor_import_accepted"]
    assert "unverified" in manifest["projection_losses"][2]
    assert "encoding" in manifest["projection_losses"][3]


def test_scoped_persistent_file_matches_inline_and_is_denied_after_scope_revocation(tmp_path):
    path = tmp_path / "store.sqlite"
    owner, ctx = create_engine(storage=SQLiteStorage(path)), OperationContext(tenant="a")
    streamed = owner.execute("export", {**request(), "stream": True}, context=ctx)
    assert streamed.status == "completed", streamed.public_dict()
    reopened = create_engine(storage=SQLiteStorage(path))
    _, file = open_artifact(reopened, streamed.data["artifact_id"], context=ctx)
    with file:
        raw = file.read()
    inline = owner.execute("export", request(), context=ctx)
    assert raw == base64.b64decode(inline.data["content_base64"])
    for denied in [replace(ctx, tenant="b"), replace(ctx, allowed_namespaces=frozenset())]:
        with pytest.raises(ValueError):
            open_artifact(reopened, streamed.data["artifact_id"], context=denied)
    assert owner.execute("export", request(), context=replace(ctx, allowed_namespaces=frozenset())).status == "failed"


@pytest.mark.parametrize("case", ["empty", "count", "bytes", "quote_expansion", "title", "control",
    "unknown", "time", "end", "end_missing", "stream", "date", "checkpoint", "format"])
def test_invalid_requests_do_not_emit_a_file(case):
    req = request()
    if case == "empty":
        req["chapters"] = []
    elif case == "count":
        req["bounds"] = {"max_records": 1}
    elif case == "bytes":
        req["bounds"] = {"transfer_bytes": 10}
    elif case == "quote_expansion":
        req["chapters"] = [{"start": "00:00:20", "end": "00:00:30", "title": '"' * 100}]
        req["bounds"] = {"parser_bytes": 150}
    elif case == "title":
        req["chapters"][0]["title"] = " "
    elif case == "control":
        req["chapters"][0]["summary"] = "a\x00b"
    elif case == "unknown":
        req["chapters"][0]["native_id"] = 1
    elif case == "time":
        req["chapters"][0]["start"] = "00:60:00"
    elif case == "end":
        req["chapters"][0]["end"] = "00:00:19"
    elif case == "end_missing":
        del req["chapters"][0]["end"]
    elif case == "stream":
        req["stream"] = "true"
    elif case == "date":
        req["bounds"] = {"date_from": "2026-11-14"}
    elif case == "checkpoint":
        req["bounds"] = {"checkpoint": "not resumable"}
    else:
        req["format"] = "telvue-connect-chapters"
    result = create_engine().execute("export", req)
    assert result.status == "failed" and not result.data, result.public_dict()


def test_cancelled_request_has_no_output():
    ctx = OperationContext()
    ctx.cancellation.set()
    result = create_engine().execute("export", request(), context=ctx)
    assert result.status == "cancelled" and not result.data


@pytest.mark.parametrize("start,end,expected", [
    (20, 30, ["20", "30"]),
    ("00:00:20", "", ["00:00:20", ""]),
    (20, "00:00:30", ["20", "00:00:30"]),
])
def test_2022_bulk_format_seconds_optional_end_and_five_positions(start, end, expected):
    req = request()
    req.update(format="telvue-connect-chapters-csv", chapters=[{"start": start, "title": "Opening"}])
    if end != "":
        req["chapters"][0]["end"] = end
    result = create_engine().execute("export", req)
    assert result.status == "completed", result.public_dict()
    rows = list(csv.reader(io.StringIO(base64.b64decode(result.data["content_base64"]).decode())))
    assert rows == [[*expected, "Opening", "", ""]]
    manifest = result.data["manifest"]
    assert manifest["documented_version"] == "Add Chapters / December 2022"
    assert "headerless" in manifest["projection_losses"][2]
    assert not manifest["vendor_import_accepted"]


@pytest.mark.parametrize("value", [True, -1, 360000, 1.5, None])
def test_2022_seconds_requires_a_bounded_integer_not_a_coerced_value(value):
    req = request()
    req.update(format="telvue-connect-chapters-csv", chapters=[{"start": value, "title": "Opening"}])
    result = create_engine().execute("export", req)
    assert result.status == "failed" and not result.data
