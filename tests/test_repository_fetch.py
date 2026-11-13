"""Pinned vendor GetEntry contract through the public engine; synthetic transport only."""

import base64
import json

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response
from test_repository_discovery import BASE, NAMESPACE, context, entry

ENTRY_URL = BASE.split("/Entries/")[0] + "/Entries/71"


class EntryTransport:
    def __init__(self, value=None, status=200, response_url=None):
        self.raw = json.dumps(entry(71) if value is None else value).encode()
        self.status, self.response_url, self.calls = status, response_url, []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert url == ENTRY_URL
        assert kwargs["allowed_origins"] == ("https://api.laserfiche.com",)
        assert kwargs["allow_redirects"] is False
        return Response(self.response_url or url, self.raw, "application/json", self.status)


@pytest.mark.parametrize("extra", [{}, {"value": [entry(72)]}])
def test_repository_entry_metadata_fetch_identity_capture_and_offline_replay(extra):
    transport = EntryTransport({**entry(71), **extra})
    owner = create_engine(provider_transport=transport)
    source = Source("laserfiche-weblink", BASE)
    result = owner.fetch_record(source, "71", context=context())
    assert result.status == "completed", result.public_dict()
    row = result.data["records"][0]
    expected = {"provider": "laserfiche-weblink", "namespace": NAMESPACE,
                "record_type": "document", "external_id": "71", "parent": None}
    assert {key: row["identity"][key] for key in expected} == expected
    assert row["identity"]["derivation"] == "provider_identifier"
    assert row["relationships"][0]["identity"]["external_id"] == "54"
    assert row["original"]["unknown"] == {"keep": [False, None]}
    assert row["original"] == json.loads(transport.raw)
    assert "meeting_date" not in row["normalized"]
    assert base64.b64decode(result.data["capture"]["content_base64"]) == transport.raw
    assert result.coverage["content_fetched"] is False and not result.coverage["catalog_complete"]
    assert "secret-read-token" not in json.dumps(result.public_dict())
    assert transport.calls[0][1]["headers"]["Authorization"] == "Bearer secret-read-token"
    replay = owner.normalize(source, transport.raw, input_format="laserfiche-repository-entries-json")
    assert replay.status == "completed", replay.public_dict()
    assert replay.data["records"][0]["identity"] == row["identity"]
    assert len(transport.calls) == 1


@pytest.mark.parametrize("identity", ["../71", "0", "-1", "https://evil.example", 71])
def test_repository_entry_rejects_invalid_ids_without_network(identity):
    transport = EntryTransport()
    result = create_engine(provider_transport=transport).fetch_record(
        Source("laserfiche-weblink", BASE), identity, context=context())
    assert result.status == "failed" and not transport.calls


@pytest.mark.parametrize("value", [entry(72), entry(71, parent=55), entry(71, kind="Unknown")])
def test_repository_entry_rejects_wrong_identity_parent_or_type(value):
    result = create_engine(provider_transport=EntryTransport(value)).fetch_record(
        Source("laserfiche-weblink", BASE), "71", context=context())
    assert result.status == "failed" and result.data is None


def test_repository_entry_access_bounds_failure_redirect_and_secret_echo():
    source = Source("laserfiche-weblink", BASE)
    transport = EntryTransport()
    owner = create_engine(provider_transport=transport)
    for caller in [OperationContext(), context(allowed_namespaces=frozenset()),
                   context(allowed_operations=frozenset({"discover"}))]:
        assert owner.fetch_record(source, "71", context=caller).status == "failed"
    assert not transport.calls
    cancelled = context()
    cancelled.cancellation.set()
    assert owner.fetch_record(source, "71", context=cancelled).status == "cancelled"
    assert not transport.calls
    assert owner.fetch_record(source, "71", context=context(), bounds=Bounds(parser_bytes=1)).status == "failed"
    for bad in [EntryTransport(status=403), EntryTransport(response_url=ENTRY_URL + "/other"),
                EntryTransport({**entry(71), "echo": "secret-read-token"})]:
        result = create_engine(provider_transport=bad).fetch_record(source, "71", context=context())
        assert result.status == "failed" and "secret-read-token" not in json.dumps(result.public_dict())
    for bounds in [Bounds(date_from="2026-11-01"), Bounds(checkpoint="not-a-detail-cursor")]:
        fresh = EntryTransport()
        assert create_engine(provider_transport=fresh).fetch_record(
            source, "71", context=context(), bounds=bounds).status == "failed"
        assert not fresh.calls
