"""Shared in-memory capture aliases must serialize as independent JSON occurrences."""

from copy import deepcopy
import io
import json
import zipfile

from civic_data_connectors.interchange import read_bundle, write_bundle
from test_storage_search_imports import sample


def test_zip_restores_every_inline_alias_and_deduplicates_blob_without_changing_input():
    bundle = sample()
    capture = bundle["capture"]
    bundle["captures"] = [capture, capture]
    bundle["bundles"] = [{"records": [], "capture": capture, "unknown": {"keep": [False, None]}}]
    before = deepcopy(bundle)
    output = io.BytesIO()
    write_bundle(bundle, output, format="zip")
    assert bundle == before
    restored = read_bundle(output.getvalue(), format="zip")
    assert restored == before
    with zipfile.ZipFile(io.BytesIO(output.getvalue())) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert len(manifest["capture_locations"]) == 4
        assert all(row["inline"] is True for row in manifest["capture_locations"])
        assert len([name for name in archive.namelist() if name.startswith("captures/")]) == 1
