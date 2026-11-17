"""A production request contract does not establish its response schema."""

import base64
import json

import pytest

from quorumrelay import Source, create_engine
from test_account_apis import MEETING, Network, structure
from test_essential_production import PRODUCTION, caller
from civic_data_connectors.providers.contracts import Response


@pytest.mark.parametrize("value", [
    {"meetingStructure": structure()},
    {"meetingStructure": {"meetingId": MEETING, "audioVideoDetails": {"audioVideoUrl": "https://example.org/a.mp4"}}},
    {"unknownResponse": [None, False, {"meetingId": MEETING}]},
])
def test_production_multimedia_retains_exact_raw_response_without_development_projection(value):
    raw = json.dumps(value).encode()

    class ProductionNetwork(Network):
        def request(self, url, **options):
            self.calls.append((url, options))
            assert url == PRODUCTION + "/PublicApi/meeting/multimedia/" + MEETING
            assert options["allowed_origins"] == (PRODUCTION,) and options["allow_redirects"] is False
            return Response(url, raw, "application/json")

    network = ProductionNetwork(value)
    source = Source("municode-meetings", PRODUCTION, namespace="account-a")
    result = create_engine(provider_transport=network).fetch(source,
        {"api_resource": "multimedia", "external_id": MEETING}, context=caller())
    assert result.status == "partial" and not result.errors, result.public_dict()
    assert result.data["records"] == []
    assert result.coverage["schema_mapping"].startswith("unverified")
    assert result.coverage["requested_id"] == MEETING
    assert result.data["capture"]["original_values"] == value
    assert base64.b64decode(result.data["capture"]["content_base64"]) == raw
    assert len(network.calls) == 1
