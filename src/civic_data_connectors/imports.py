"""Non-persisting previews and explicit opt-in reusable capture storage."""

from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from dataclasses import replace

from .engine import canonical_hash, source_identity_key
from .extensions import StorageConflict
from .models import Bounds, Error, OperationResult, SCHEMA_VERSION
from .storage import Mutation, operation_cancelled, tracked_handler, update_operation


def validate_bundle(bundle: dict) -> dict:
    """Validate required envelope fields without projecting unknown fields away."""
    if not isinstance(bundle, dict) or bundle.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("A capture bundle requires supported schema_version " + SCHEMA_VERSION)
    if not isinstance(bundle.get("records"), (list, tuple)) or not isinstance(bundle.get("capture"), dict):
        raise ValueError("A capture bundle requires records and capture objects.")
    seen = set()
    for record in bundle["records"]:
        if not isinstance(record, dict):
            raise ValueError("Every record must be a JSON object.")
        identity = record.get("identity")
        if not isinstance(identity, dict) or any(
            not isinstance(identity.get(k), str) or not identity[k]
            for k in ("provider", "namespace", "record_type", "external_id")
        ):
            raise ValueError("A record requires its complete stable source identity.")
        if not isinstance(record.get("normalized"), dict):
            raise ValueError("A record requires normalized fields.")
        key = source_identity_key(identity)
        if key in seen:
            raise ValueError("A bundle cannot contain duplicate source identities.")
        seen.add(key)
    capture = bundle["capture"]
    if "content_base64" in capture:
        data = base64.b64decode(capture["content_base64"], validate=True)
        if hashlib.sha256(data).hexdigest() != capture.get("sha256"):
            raise ValueError("The capture hash does not match its original bytes.")
        if capture.get("byte_length") != len(data):
            raise ValueError("The capture byte length does not match.")
    # Enforce JSON semantics, including absent/null distinction and finite numbers.
    json.dumps(bundle, allow_nan=False)
    return deepcopy(bundle)


def _load(owner, request, content, context):
    neutral_format = request.get("format")
    if neutral_format is not None and neutral_format not in {"json", "jsonl", "zip"}:
        raise ValueError("Import format must be json, jsonl or zip; provider inputs use input_format.")
    if neutral_format is not None:
        if "bundle" in request or "result" in request:
            raise ValueError("A neutral import accepts encoded content or a bundle, not both.")
        bounds = Bounds(**request.get("bounds", {}))
        limit = min(bounds.parser_bytes, bounds.transfer_bytes) if neutral_format == "json" else bounds.transfer_bytes
        if content is not None and "content_base64" in request:
            raise ValueError("Supply content bytes or content_base64, not both.")
        if "content_base64" in request:
            encoded = request["content_base64"]
            if not isinstance(encoded, str):
                raise ValueError("content_base64 must be a base64 string.")
            if len(encoded) > 4 * ((limit + 2) // 3):
                raise ValueError("Encoded neutral import exceeds its configured input byte limit.")
            content = base64.b64decode(encoded, validate=True)
        if content is None:
            raise ValueError("Neutral import requires content bytes or content_base64.")
        if not isinstance(content, bytes) or len(content) > limit:
            raise ValueError("Neutral import exceeds its configured input byte limit.")
        from .interchange import read_bundle
        bundle = read_bundle(content, format=neutral_format, bounds=bounds)
        return _load(owner, {key: value for key, value in {**request, "bundle": bundle}.items()
                             if key not in {"format", "content_base64"}}, None, context)
    if "result" in request:
        upstream = request["result"]
        if not isinstance(upstream, dict):
            raise ValueError("result must be a complete operation result object.")
        data = deepcopy(upstream.get("data"))
        if not isinstance(data, dict):
            return data, upstream.get("coverage", {}), upstream.get("status", "failed"), upstream.get("errors", [])
        request = {**request, "bundle": data, "coverage": upstream.get("coverage", {}),
                   "status": upstream.get("status", "completed"), "errors": upstream.get("errors", [])}
    if "bundle" in request:
        bundle = request["bundle"]
        if "capture" in bundle:
            bundle = validate_bundle(bundle)
        else:
            # Discovery aggregation keeps every original page bundle and capture.
            bundle = deepcopy(bundle)
            bundle.setdefault("schema_version", SCHEMA_VERSION)
            bundle.setdefault("records", [])
            if not isinstance(bundle["records"], (list, tuple)):
                raise ValueError("Discovery records must be an array.")
            for page in bundle.get("bundles", []):
                validate_bundle(page)
            validate_bundle({**bundle, "capture": {}})
        return bundle, request.get("coverage", {}), request.get("status", "completed"), request.get("errors", [])
    if "records" in request or "bundles" in request:
        data = {key: deepcopy(value) for key, value in request.items()
                if key in {"source", "records", "captures", "bundles", "extensions", "schema_version"}}
        if "records" not in data:
            data["records"] = [record for page in data.get("bundles", []) for record in page["records"]]
        return _load(owner, {**request, "bundle": data}, content, context)
    # An authorized import may internally parse a capture without granting the
    # caller a separately exposed normalize operation. Namespace policy stays put.
    delegated = context
    if context.allowed_operations is not None:
        delegated = replace(context, allowed_operations=context.allowed_operations | {"normalize"})
    result = owner.execute("normalize", request, content=content, context=delegated)
    return result.data, result.coverage, result.status, result.errors


def _errors(errors):
    return tuple(error if isinstance(error, Error) else Error(**error) for error in errors)


def preview(owner, request, content, context):
    bundle, coverage, status, errors = _load(owner, request, content, context)
    if bundle is None:
        return OperationResult(status, coverage=coverage, errors=_errors(errors),
                               operation_id=context.operation_id)
    if any(context.allowed_namespaces is not None
           and record["identity"]["namespace"] not in context.allowed_namespaces
           for record in bundle["records"]):
        return OperationResult("failed", errors=(Error("permission_denied",
            "The bundle includes a source outside the caller's namespace policy."),),
            operation_id=context.operation_id)
    if errors and status == "completed":
        status = "partial"
    changes = []
    for record in bundle["records"]:
        key = source_identity_key(record["identity"])
        old = owner.storage.get("records", key, scope=context.scope) if owner.storage else None
        outcome = "new"
        if old:
            old_content = {k: v for k, v in old.value.items() if k != "captured_at"}
            new_content = {k: v for k, v in record.items() if k != "captured_at"}
            outcome = "unchanged" if canonical_hash(old_content) == canonical_hash(new_content) else (
                "changed_capture" if old.value.get("normalized_sha256") == record.get("normalized_sha256")
                else "changed_source"
            )
        changes.append({"identity": record["identity"], "key": key, "outcome": outcome,
                        "expected_version": old.version if old else None})
    return OperationResult(status, data={"bundle": bundle, "changes": changes, "persisted": False},
                           errors=_errors(errors), coverage=coverage, operation_id=context.operation_id)


def import_bundle(owner, request, content, context):
    """Return the reusable bundle; storing requires an explicit persist flag."""
    if "persist" in request and type(request["persist"]) is not bool:
        raise ValueError("persist must be a JSON boolean.")
    result = preview(owner, request, content, context)
    if result.data is None or result.status in {"failed", "cancelled"}:
        return result
    if not request.get("persist", False):
        return result
    if owner.storage is None:
        return OperationResult.unsupported("import_bundle", reason="Persistence requires caller-configured storage.")
    bundle = result.data["bundle"]
    mutations = []
    captures = ([bundle["capture"]] if bundle.get("capture") else []) + list(bundle.get("captures", []))
    captures += [page["capture"] for page in bundle.get("bundles", [])]
    seen_captures = set()
    for capture in captures:
        if not capture.get("sha256") or capture["sha256"] in seen_captures:
            continue
        seen_captures.add(capture["sha256"])
        old = owner.storage.get("captures", capture["sha256"], scope=context.scope)
        # A capture includes source-specific fields; preserve each complete bundle
        # separately even when equal bytes are observed through different sources.
        if old is None:
            mutations.append(Mutation("captures", capture["sha256"], capture, create_only=True))
    bundle_key = canonical_hash(bundle)
    if owner.storage.get("bundles", bundle_key, scope=context.scope) is None:
        mutations.append(Mutation("bundles", bundle_key, bundle, create_only=True))
    for record, change in zip(bundle["records"], result.data["changes"]):
        revision_key = change["key"] + ":" + canonical_hash(record)
        if owner.storage.get("record_revisions", revision_key, scope=context.scope) is None:
            mutations.append(Mutation("record_revisions", revision_key, record, create_only=True))
        if change["outcome"] != "unchanged":
            mutations.append(Mutation("records", change["key"], record,
                                      expected_version=change["expected_version"],
                                      create_only=change["expected_version"] is None))
    completed = 0
    atomic = callable(getattr(owner.storage, "put_many", None))
    if operation_cancelled(owner.storage, context):
        return OperationResult("cancelled", data={**result.data, "persisted": False},
                               coverage=result.coverage, operation_id=context.operation_id)
    try:
        if atomic:
            owner.storage.put_many(mutations, scope=context.scope)
            completed = len(mutations)
        else:
            for mutation in mutations:
                if operation_cancelled(owner.storage, context):
                    break
                owner.storage.put(
                    mutation.collection, mutation.key, mutation.value, scope=context.scope,
                    expected_version=mutation.expected_version, create_only=mutation.create_only,
                )
                completed += 1
                if context.operation_id:
                    update_operation(owner.storage, context.operation_id,
                                     {"operation": "import_bundle", "completed_steps": completed,
                                      "total_steps": len(mutations), "bundle_key": bundle_key},
                                     scope=context.scope)
                context.report(operation="import_bundle", completed=completed, total=len(mutations))
    except StorageConflict:
        return OperationResult(
            "partial" if completed else "failed",
            data={**result.data, "persisted": False, "completed_steps": completed},
            errors=(Error("storage_conflict", "Stored records changed; preview again before applying."),),
            coverage={**result.coverage, "atomic": atomic, "total_steps": len(mutations)},
            operation_id=context.operation_id,
        )
    cancelled = completed < len(mutations)
    data = {**result.data, "persisted": not cancelled, "bundle_key": bundle_key,
            "completed_steps": completed, "atomic": atomic}
    if context.operation_id:
        update_operation(owner.storage, context.operation_id,
                         {"operation": "import_bundle", "status": "cancelled" if cancelled else result.status,
                          "bundle_key": bundle_key, "completed_steps": completed, "total_steps": len(mutations)},
                         scope=context.scope)
    return OperationResult("cancelled" if cancelled else result.status, data=data,
                           errors=result.errors, coverage=result.coverage, operation_id=context.operation_id)


def register(engine) -> None:
    # The outer operation is the policy decision, not the preview helper it uses.
    def bundle_handler(owner, request, content, context):
        delegated = context
        if context.allowed_operations is not None:
            delegated = replace(context, allowed_operations=context.allowed_operations | {"import_preview"})
        return import_bundle(owner, request, content, delegated)
    engine.register_operation("import_preview", tracked_handler("import_preview", preview))
    engine.register_operation("import_bundle", tracked_handler("import_bundle", bundle_handler))
