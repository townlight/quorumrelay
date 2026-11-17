"""Inventory fetch labels follow executed configured-source paths, not catalog claims."""
import base64
import json
from pathlib import Path

import pytest

from quorumrelay import Bounds, Source, create_engine
from civic_data_connectors.capabilities import provider_capabilities
from civic_data_connectors.providers.contracts import Response

ROOT = Path(__file__).parent / "fixtures/baseline"
CASES = [c for c in json.loads((ROOT / "cases.json").read_text()) if c["connector"] in {
    "civicplus-agenda-center", "swagit", "suiteone-media", "peak", "towncloud"}
    and c["input_format"] != "towncloud-table-json"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["connector"])
def test_existing_configured_fetch_is_implemented_with_exact_source_capture(case):
    raw = (ROOT / case["file"]).read_bytes()
    source = Source(case["connector"], case["source_url"], input_format=case["input_format"])
    calls = []

    class Transport:
        def request(self, url, **options):
            calls.append((url, options))
            assert url == source.url
            return Response(url, raw, "text/html")

    result = create_engine(provider_transport=Transport()).fetch(source,
        bounds=Bounds(max_pages=1, max_records=1000))
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert len(result.data["records"]) >= case["original_record_count"]
    assert len(calls) == 1
    capture, = result.data["captures"]
    assert capture["sha256"] == case["sha256"]
    assert base64.b64decode(capture["content_base64"]) == raw
    assert result.coverage.get("catalog_complete") is not True
    metadata = provider_capabilities(case["connector"])["operations"]["fetch"]
    assert metadata["implementation_status"] == "implemented"
    assert metadata["acceptance_status"] == "not_run"  # Historical broad acceptance is not promoted.
