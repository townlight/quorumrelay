"""Synthetic wire fixtures for documented routes, never live account acceptance."""

import base64
import hashlib
import json
from copy import deepcopy

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from quorumrelay.write_transport import WriteResponse

ESSENTIAL = "https://meetingsgov.devmunicode.com"
TELVUE = "https://connect.telvue.com"
MEETING = "0c916582-cbed-40ca-af41-b449b83ec9bd"
ENTITY = "cc51ce12-6c51-4b70-97d4-0fdee0a98be2"


def context(provider):
    origin = ESSENTIAL if provider == "municode-meetings" else TELVUE
    return OperationContext(principal="editor", client_id="fixture", tenant="newsroom-a",
        allowed_namespaces=frozenset({"account-a"}), authorization=frozenset({"write:plan", "write:commit"}),
        credentials={provider: {"origin": origin, "namespace": "account-a", "tenant": "newsroom-a",
            "token": "synthetic-long-bearer", "access_key": "synthetic-long-access",
            "secret_passphrase": "synthetic-long-passphrase", "permissions": ["meeting_multimedia:update"],
            "meeting_ids": [MEETING]}})


def structure():
    return {"Id": MEETING, "MeetingId": MEETING, "PublishState": 1,
        "AudioVideoDetails": {"AudioVideoProviderType": 0, "AudioVideoUrl": "https://example.org/before.mp4", "unknown": None},
        "unknown": {"false": False, "array": [None, 0]},
        "MultimediaItems": [{"EntityId": ENTITY, "EntityName": "Item", "EntityTypeName": "agenda_item",
            "TimeStamp": 60, "MultimediaDisplayOptions": 0, "CustomDisplay": "", "IncludeNumbering": True,
            "UseDefaultMultimediaSettings": True, "MultimediaBaseUrl": "", "unknown": "retained"}]}


class Network:
    mock = True

    def __init__(self, value):
        self.value, self.calls, self.status, self.lose, self.redirect, self.oversize = value, [], 200, False, False, False

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs["deadline_seconds"] > 0
        assert kwargs["allow_redirects"] is False
        assert kwargs["allowed_origins"] == (ESSENTIAL if "devmunicode" in url else TELVUE,)
        raw = json.dumps(self.value, ensure_ascii=False).encode()
        return Response(TELVUE + "/wrong" if self.redirect else url, raw,
                        "application/json", self.status)

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        self.calls.append((url, {"method": method, "body": body, "headers": headers}))
        assert headers["Authorization"] == "Bearer synthetic-long-bearer"
        assert url.startswith(ESSENTIAL + "/PublicApi/meeting/multimedia/")
        if method == "POST":
            self.value = {"meetingStructure": json.loads(body)}
            if self.lose:
                raise TimeoutError("lost response synthetic-long-bearer")
            return WriteResponse(204, b"")
        return WriteResponse(self.status, json.dumps(self.value).encode())


@pytest.mark.parametrize("resource,path,key", [
    ("media", "/api/v2/media.json", "media"),
    ("videos", "/api/v2/videos.json", "videos"),
    ("playlists", "/api/v2/playlists.json", "playlists"),
])
def test_telvue_wire_capture_mapping_and_saved_replay(resource, path, key):
    row = {"id": 32261, "title": "Council", "name": "Playlist", "transcript": "Exact supplied text",
        "duration_in_seconds": 139, "updated_at": "2026-11-11T00:00:00Z", "unknown": [None, False],
        "sources": [{"url": "https://example.org/video.mp4", "type": "http"},
                    {"url": "rtmp://example.org/video", "type": "rtmp"}],
        "chapters": [{"id": 1, "start_time": 60.0, "end_time": 90.0}], "playables_count": 2}
    network = Network({key: [row]})
    engine = create_engine(provider_transport=network)
    source = Source("telvue", TELVUE, namespace="account-a")
    result = engine.fetch(source, {"api_resource": resource}, context=context("telvue"))
    assert result.status == "partial", result.public_dict()
    assert network.calls[0][0] == TELVUE + path
    headers = network.calls[0][1]["headers"]
    assert headers["CONNECT-ACCESS-KEY"] == "synthetic-long-access"
    assert headers["CONNECT-SECRET-PASSPHRASE"] == "synthetic-long-passphrase"
    assert "Authorization" not in headers
    record = result.data["records"][0]
    assert record["original"] == row
    assert record["normalized"]["chapters"] == row["chapters"]
    assert record["text"][0]["text"] == row["transcript"]
    assert record["source_revision"]["value"] == row["updated_at"]
    assert len(record["normalized"]["recordings"]) == 1  # RTMP remains original, not HTTP attachment.
    assert "meeting_date" not in record["normalized"]
    raw = base64.b64decode(result.data["capture"]["content_base64"])
    assert hashlib.sha256(raw).hexdigest() == result.data["capture"]["sha256"]
    replay = engine.normalize(source, raw, input_format=f"telvue-connect-{resource}-json")
    assert replay.status == "completed", replay.public_dict()
    assert replay.data["records"][0]["identity"] == record["identity"]
    assert result.coverage["catalog_complete"] is False
    assert "synthetic-long" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("resource,key", [("media", "medium"), ("playlists", "playlist")])
def test_telvue_details_and_identity_mismatch(resource, key):
    network = Network({key: {"id": 8, "title": "Detail"}})
    engine = create_engine(provider_transport=network)
    source = Source("telvue", TELVUE, namespace="account-a")
    result = engine.fetch(source, {"api_resource": resource, "external_id": "8"}, context=context("telvue"))
    assert result.status == "partial", result.public_dict()
    assert network.calls[-1][0] == TELVUE + f"/api/v2/{resource}/8.json"
    network.value[key]["id"] = 9
    assert engine.fetch(source, {"api_resource": resource, "external_id": "8"}, context=context("telvue")).status == "failed"
    before = len(network.calls)
    assert engine.fetch(source, {"api_resource": "videos", "external_id": "8"}, context=context("telvue")).status == "failed"
    assert len(network.calls) == before


def test_essential_unknown_schemas_are_exact_raw_partial_not_empty_success():
    network = Network({"unverifiedEnvelope": {"vendorUnknown": [None, False]}})
    engine = create_engine(provider_transport=network)
    source = Source("municode-meetings", ESSENTIAL, namespace="account-a")
    for resource in ("meeting", "item"):
        result = engine.fetch(source, {"api_resource": resource, "external_id": MEETING}, context=context(source.provider))
        assert result.status == "partial", result.public_dict()
        assert result.data["records"] == []
        assert result.data["capture"]["original_values"] == network.value
        assert "unverified" in result.coverage["schema_mapping"]
        assert network.calls[-1][0] == ESSENTIAL + f"/PublicApi/{resource}/{MEETING}"
    filters = {"Words": "council", "CreatedMeetingFromDate": {"Day": -1, "Month": -1, "Year": -1},
        "CreatedMeetingToDate": {"Day": 11, "Month": 11, "Year": 2026}, "ArchivedState": 0, "MeetingTypeIds": []}
    result = engine.fetch(source, {"api_resource": "collection", "offset": 0, "filters": filters}, context=context(source.provider))
    assert result.status == "partial", result.public_dict()
    assert len(network.calls) == 3  # Never invent stride or automatically paginate unknown envelope.
    url, call = network.calls[-1]
    assert url.endswith("/PublicApi/meeting/collection/0") and call["method"] == "POST"
    assert json.loads(call["body"]) == filters
    assert call["headers"]["Authorization"] == "Bearer synthetic-long-bearer"
    network.value = {"meetingStructure": structure()}
    result = engine.fetch(source, {"api_resource": "multimedia", "external_id": MEETING}, context=context(source.provider))
    assert result.status == "partial", result.public_dict()
    assert result.data["records"][0]["original"] == structure()
    parent = result.data["records"][0]["identity"]["parent"]
    assert parent["external_id"] == MEETING and parent["record_type"] == "meeting"
    assert result.data["records"][0]["relationships"] == [{"relation": "meeting", "identity": parent}]


@pytest.mark.parametrize("provider,origin", [("telvue", TELVUE), ("municode-meetings", ESSENTIAL)])
def test_account_binding_rejects_cross_tenant_origin_namespace_missing_and_revoked_grants(provider, origin):
    network = Network({})
    engine = create_engine(provider_transport=network)
    source = Source(provider, origin, namespace="account-a")
    for mutate in (lambda c: c.credentials[provider].update(tenant="other"),
                   lambda c: c.credentials[provider].update(origin="https://example.org"),
                   lambda c: c.credentials[provider].update(namespace="account-b"),
                   lambda c: c.credentials[provider].update(allowed_namespaces="prefix-account-a-suffix"),
                   lambda c: setattr(c, "allowed_operations", frozenset()),
                   lambda c: setattr(c, "allowed_namespaces", frozenset({"account-b"}))):
        caller = context(provider)
        mutate(caller)
        assert engine.fetch(source, {"external_id": MEETING}, context=caller).status == "failed"
    assert engine.fetch(Source(provider, origin), {"external_id": MEETING}, context=context(provider)).status == "failed"
    assert not network.calls


def test_account_response_bounds_cancellation_failures_no_secret_echo_and_no_guess_filters():
    network = Network({"media": [{"id": 1}]})
    engine = create_engine(provider_transport=network)
    source = Source("telvue", TELVUE, namespace="account-a")
    for bounds in (Bounds(parser_bytes=1), Bounds(transfer_bytes=1), Bounds(checkpoint="forged"), Bounds(date_from="2026-11-01")):
        assert engine.fetch(source, bounds=bounds, context=context("telvue")).status == "failed"
    caller = context("telvue")
    caller.cancellation.set()
    assert engine.fetch(source, context=caller).status == "cancelled"
    network.redirect = True
    assert engine.fetch(source, context=context("telvue")).status == "failed"
    network.redirect = False
    network.status = 403
    assert engine.fetch(source, context=context("telvue")).status == "failed"
    network.status = 200
    network.value = {"media": [{"id": 1, "echo": "synthetic-long-passphrase"}]}
    result = engine.fetch(source, context=context("telvue"))
    assert result.status == "failed" and "synthetic-long" not in json.dumps(result.public_dict())


def write_setup(tmp_path):
    network = Network({"meetingStructure": structure()})
    engine = create_engine(storage=SQLiteStorage(tmp_path / "essential.sqlite"), write_adapters=default_adapters(network))
    source = {"provider": "municode-meetings", "url": ESSENTIAL, "namespace": "account-a"}
    change = {"key": "timestamp", "entity": "meeting_multimedia", "operation": "update",
        "resource_id": MEETING, "meeting_id": MEETING,
        "fields": {"AudioVideoDetails": {"AudioVideoUrl": "https://example.org/after.mp4"},
            "MultimediaItems": [{"EntityId": ENTITY, "TimeStamp": 125, "UseDefaultMultimediaSettings": False,
                                 "MultimediaBaseUrl": "https://example.org/after.mp4"}]}}
    caller = context(source["provider"])
    return engine, network, source, change, caller


def test_essential_write_full_preservation_conflict_receipt_and_no_replay(tmp_path):
    engine, network, source, change, caller = write_setup(tmp_path)
    plan = engine.execute("plan_write", {"source": source, "changes": [change]}, context=caller)
    assert plan.status == "completed", plan.public_dict()
    approval = {k: plan.data[k] for k in ("plan_id", "plan_hash")}
    result = engine.execute("commit_write", approval, context=caller)
    assert result.status == "completed", result.public_dict()
    after = network.value["meetingStructure"]
    assert after["unknown"] == structure()["unknown"]
    assert after["AudioVideoDetails"]["unknown"] is None
    assert after["MultimediaItems"][0]["unknown"] == "retained"
    assert after["MultimediaItems"][0]["TimeStamp"] == 125
    assert [k[1]["method"] for k in network.calls] == ["GET", "GET", "POST", "GET"]
    assert network.calls[2][0] == ESSENTIAL + "/PublicApi/meeting/multimedia/update/" + MEETING
    assert result.coverage["live_acceptance"] == "NOT_RUN" and result.coverage["mock"] is True
    assert engine.execute("commit_write", approval, context=caller).status == "completed"
    assert len(network.calls) == 4
    caller.credentials["municode-meetings"]["permissions"] = []
    assert engine.execute("receipt", {"plan_id": approval["plan_id"]}, context=caller).status == "failed"


def test_essential_changed_before_and_lost_mutation_response_reconcile_without_resend(tmp_path):
    engine, network, source, change, caller = write_setup(tmp_path)
    plan = engine.execute("plan_write", {"source": source, "changes": [change]}, context=caller)
    assert plan.status == "completed", plan.public_dict()
    approval = {k: plan.data[k] for k in ("plan_id", "plan_hash")}
    network.value["meetingStructure"]["unknown"]["false"] = True
    assert engine.execute("commit_write", approval, context=caller).status == "failed"
    assert not any(k[1]["method"] == "POST" for k in network.calls)
    # New explicit plan for the new before state; possible accepted POST is never repeated.
    change = deepcopy(change)
    change["key"] = "retry-exact"
    plan = engine.execute("plan_write", {"source": source, "changes": [change]}, context=caller)
    approval = {k: plan.data[k] for k in ("plan_id", "plan_hash")}
    network.lose = True
    uncertain = engine.execute("commit_write", approval, context=caller)
    assert uncertain.status == "partial", uncertain.public_dict()
    result = engine.execute("commit_write", approval, context=caller)
    assert result.status == "completed", result.public_dict()
    assert sum(k[1]["method"] == "POST" for k in network.calls) == 1
    assert "synthetic-long" not in json.dumps(result.public_dict())


def test_essential_write_policy_and_unmapped_operations_fail_without_mutation(tmp_path):
    engine, network, source, change, caller = write_setup(tmp_path)
    for patch in ({"operation": "create"}, {"entity": "meeting"}, {"meeting_id": ENTITY},
                  {"fields": {"PublishState": "invalid-type"}}, {"expected_version": "stale"}):
        result = engine.execute("plan_write", {"source": source, "changes": [{**change, **patch}]}, context=caller)
        assert result.status == "failed", result.public_dict()
    assert not any(k[1]["method"] == "POST" for k in network.calls)
    caller.credentials["municode-meetings"]["tenant"] = "other-account"
    before = len(network.calls)
    assert engine.execute("plan_write", {"source": source, "changes": [change]}, context=caller).status == "failed"
    assert len(network.calls) == before


def test_full_structure_with_sensitive_unknown_key_fails_instead_of_silently_dropping_it(tmp_path):
    engine, network, source, change, caller = write_setup(tmp_path)
    network.value["meetingStructure"]["token"] = "unknown-vendor-value"
    result = engine.execute("plan_write", {"source": source, "changes": [change]}, context=caller)
    assert result.status == "failed", result.public_dict()
    assert not any(k[1]["method"] == "POST" for k in network.calls)


def test_escaped_json_credential_echo_and_legacy_namespace_remain_guarded():
    from quorumrelay.providers.account_api import reject_credential_echo
    with pytest.raises(ValueError, match="credential material"):
        reject_credential_echo(b'{"echo":"synthetic-long-\\u0070assphrase"}',
                               {"secret_passphrase": "synthetic-long-passphrase"})
    engine = create_engine()
    # Account-only identity binding does not relax existing public tenant namespaces.
    for provider, url in (("telvue", "https://videoplayer.telvue.com/player/abc"),
                          ("municode-meetings", "https://city.municodemeetings.com/")):
        result = engine.execute("validate_source", {"source": {
            "provider": provider, "url": url, "namespace": "invented-account-namespace"}})
        assert result.status == "failed"


def test_essential_full_documented_model_field_patches_and_fixed_identity(tmp_path):
    engine, network, source, change, caller = write_setup(tmp_path)
    change["fields"] = {"Id": MEETING, "MeetingId": MEETING, "PublishState": 2,
        "AudioVideoDetails": {"AudioVideoProviderType": 3},
        "MultimediaItems": [{"EntityId": ENTITY, "EntityName": "Renamed", "EntityTypeName": "Item",
            "MultimediaDisplayOptions": 4, "CustomDisplay": "Supplied", "IncludeNumbering": False}]}
    plan = engine.execute("plan_write", {"source": source, "changes": [change]}, context=caller)
    assert plan.status == "completed", plan.public_dict()
    approval = {key: plan.data[key] for key in ("plan_id", "plan_hash")}
    result = engine.execute("commit_write", approval, context=caller)
    assert result.status == "completed", result.public_dict()
    after = network.value["meetingStructure"]
    assert after["PublishState"] == 2 and after["AudioVideoDetails"]["AudioVideoProviderType"] == 3
    assert after["AudioVideoDetails"]["AudioVideoUrl"] == structure()["AudioVideoDetails"]["AudioVideoUrl"]
    assert after["MultimediaItems"][0]["IncludeNumbering"] is False
    change["fields"]["Id"] = ENTITY
    assert engine.execute("plan_write", {"source": source, "changes": [change]}, context=caller).status == "failed"


def test_public_write_transport_disables_redirects_before_forwarding_account_auth(monkeypatch):
    from types import SimpleNamespace
    from quorumrelay.write_transport import PublicWriteTransport
    from civic_data_connectors import fetch
    calls = []

    def request(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status=302, content=b"", headers={"Location": "/other-account"})

    monkeypatch.setattr(fetch, "request_public_response", request)
    response = PublicWriteTransport().send(ESSENTIAL + "/PublicApi/meeting/multimedia/" + MEETING,
        method="GET", body=None, headers={"Authorization": "Bearer synthetic-long-bearer"},
        byte_limit=1000, deadline_seconds=1)
    assert response.status == 302
    assert len(calls) == 1 and calls[0][1]["allow_redirects"] is False
