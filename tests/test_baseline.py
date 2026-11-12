import base64
import hashlib
import json
from pathlib import Path

import pytest

from civic_data_connectors import Bounds, Engine, Source
from civic_data_connectors.compat import preview_export, source_formats
from civic_data_connectors.engine import canonical_hash

MATRIX = Path(__file__).parent / "fixtures" / "baseline"
CASES = json.loads((MATRIX / "cases.json").read_text(encoding="utf-8")) if MATRIX.exists() else []


def test_roster():
    assert len(CASES) == 34
    assert len({case["connector"] for case in CASES}) == 31
    assert {(c["connector"], c["input_format"]) for c in CASES} == {
        (f["connector"], f["input_format"]) for f in source_formats()
    }


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["connector"] + "/" + c["input_format"])
def test_original_corpus_exact_compatibility(case):
    data = (MATRIX / case["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == case["sha256"]
    result = preview_export(case["connector"], case["source_url"], data, input_format=case["input_format"])
    assert canonical_hash(result) == case["original_output_sha256"]
    assert result["source"]["namespace"] == case["original_namespace"]
    assert len(result["meetings"]) == case["original_record_count"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["connector"] + "/" + c["input_format"])
def test_rich_capture_is_lossless_and_compatible(case):
    data = (MATRIX / case["file"]).read_bytes()
    result = Engine().normalize(Source(case["connector"], case["source_url"]), data,
                                input_format=case["input_format"], bounds=Bounds(max_records=10000))
    assert result.status == "completed", result.errors
    assert canonical_hash(result.data["compatibility"]) == case["original_output_sha256"]
    assert base64.b64decode(result.data["capture"]["content_base64"]) == data
    assert result.data["capture"]["sha256"] == case["sha256"]
