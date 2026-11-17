"""Synthetic regressions for durable write plans across upload expiry and upgrades."""

import io
from dataclasses import replace

import pytest

from civic_data_connectors.engine import canonical_hash
from civic_data_connectors.interchange import stage_input
from test_write_providers import DocumentedNetwork, SRT, make_engine


def file_plan(engine, context, source, change, *, handle_shape=False, legacy_upload=False):
    data = SRT.encode() if change["entity"] == "caption" else b"synthetic recording"
    if legacy_upload:
        handle = "a" * 64
        reference = engine.storage.save_capture(io.BytesIO(data), scope=context.scope, max_bytes=4096)
        engine.storage.put("service_files", handle, {"reference": reference}, scope=context.scope)
    else:
        handle = stage_input(engine, "recovery-input", io.BytesIO(data), filename="input.bin",
                             content_type="application/octet-stream", context=context,
                             max_bytes=4096)["file_handle"]
    change = {**change, "files": [{"part": "caption_file" if change["entity"] == "caption" else "file",
                                   "filename": "input.bin",
                                   "content_type": "application/octet-stream", "file_handle": handle}]}
    planned = engine.execute("plan_write", {"source": source, "changes": [change]}, context=context)
    assert planned.status == "completed", planned.public_dict()
    approval = {key: planned.data[key] for key in ("plan_id", "plan_hash")}
    stored = engine.storage.get("write_plans", approval["plan_id"], scope=context.scope)
    plan = stored.value["plan"]
    part = plan["changes"][0]["native"]["files"][0]
    assert part["reference"]["kind"] == "sqlite_capture"
    assert "file_handle" not in part["reference"]
    if handle_shape:
        # Reproduce the already-persisted intermediate shape without changing
        # the approved plan behind its digest: save and approve its exact hash.
        part["reference"] = {"file_handle": handle, "scope": context.scope,
                             "sha256": part["reference"]["sha256"], "byte_length": len(data)}
        approval["plan_hash"] = canonical_hash(plan)
        engine.storage.put("write_plans", approval["plan_id"],
                           {**stored.value, "plan": plan, "plan_hash": approval["plan_hash"]},
                           scope=context.scope, expected_version=stored.version)
    return approval, handle


def expire(engine, context, handle):
    item = engine.storage.get("service_files", handle, scope=context.scope)
    engine.storage.put("service_files", handle, {**item.value, "expires_at": 0},
                       scope=context.scope, expected_version=item.version)


@pytest.mark.parametrize("shape", ["durable", "handle", "legacy_upload"])
def test_expired_upload_does_not_expire_exact_plan_commit_or_replay(tmp_path, shape):
    engine, context, network, source = make_engine(tmp_path, "wistia", ["media:upload"])
    approval, handle = file_plan(engine, context, source,
        {"key": "media", "entity": "media", "operation": "upload", "meeting_id": "meeting1",
         "fields": {"name": "Synthetic"}}, handle_shape=shape == "handle",
        legacy_upload=shape == "legacy_upload")
    expire(engine, context, handle)
    for _ in range(2):
        result = engine.execute("commit_write", approval, context=context)
        assert result.status == "completed", result.public_dict()
    assert sum(method == "POST" for method, _ in network.calls) == 1
    denied = engine.execute("commit_write", approval,
                            context=replace(context, authorization=frozenset({"write:plan"})))
    assert denied.status == "failed"


@pytest.mark.parametrize("handle_shape", [False, True])
def test_expired_upload_allows_uncertain_caption_readback_without_resend(tmp_path, handle_shape):
    class LostReadback(DocumentedNetwork):
        lose_readback = False

        def send(self, url, **kwargs):
            if kwargs["method"] == "GET" and self.lose_readback:
                self.lose_readback = False
                raise TimeoutError("synthetic readback loss")
            response = super().send(url, **kwargs)
            if kwargs["method"] == "PUT":
                self.lose_readback = True
            return response

    engine, context, network, source = make_engine(tmp_path, "wistia", ["caption:update"],
                                                  LostReadback("wistia"))
    approval, handle = file_plan(engine, context, source,
        {"key": "caption", "entity": "caption", "operation": "update", "parent_id": "media1",
         "meeting_id": "meeting1", "language": "eng", "fields": {}}, handle_shape=handle_shape)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "partial", result.public_dict()
    assert result.data["items"][0]["state"] == "uncertain"
    expire(engine, context, handle)
    result = engine.execute("commit_write", approval, context=context)
    assert result.status == "completed", result.public_dict()
    assert sum(method == "PUT" for method, _ in network.calls) == 1


def test_handle_shaped_plan_rejects_metadata_substitution_and_other_scope(tmp_path):
    engine, context, network, source = make_engine(tmp_path, "wistia", ["media:upload"])
    approval, handle = file_plan(engine, context, source,
        {"key": "media", "entity": "media", "operation": "upload", "meeting_id": "meeting1",
         "fields": {"name": "Synthetic"}}, handle_shape=True)
    item = engine.storage.get("service_files", handle, scope=context.scope)
    engine.storage.put("service_files", handle, {**item.value, "sha256": "0" * 64},
                       scope=context.scope, expected_version=item.version)
    assert engine.execute("commit_write", approval, context=context).status == "failed"
    assert engine.execute("commit_write", approval, context=replace(context, tenant="other")).status == "failed"
    assert not network.calls


@pytest.mark.parametrize("provider,slug", [("legistar", "fixture-city"),
                                           ("wistia", "fixture-account"), ("laserfiche", "repo1")])
def test_legacy_write_namespace_retained_without_credential_aliasing(tmp_path, provider, slug):
    engine, context, _, source = make_engine(tmp_path, provider, [])
    config = context.credentials[provider]
    legacy = replace(context, allowed_namespaces=frozenset({slug}), credentials={provider: {
        **config, "allowed_namespaces": [slug]}})
    from civic_data_connectors import Source
    adapter = engine.handlers["plan_write"].__self__.adapters[Source(**source).provider]
    adapter.validate_source(Source(**{**source, "namespace": slug}), legacy)
    with pytest.raises(ValueError):
        adapter.validate_source(Source(**{**source, "namespace": slug}), context)
    if provider == "wistia":
        adapter.validate_source(Source(**{**source, "url": "https://api.wistia.com/", "namespace": slug}), legacy)
