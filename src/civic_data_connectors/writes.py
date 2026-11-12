"""Exact authorized plans, CAS write intents, readback and scoped durable receipts."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from time import monotonic

from .engine import canonical_hash
from .extensions import StorageConflict
from .models import Bounds, Error, OperationResult, SCHEMA_VERSION, Source
from .storage import operation_cancelled, update_operation
from .write_adapters import (
    AmbiguousWrite, WriteChange, WriteFailure, check_write_adapter, default_adapters, sanitize,
)
from .write_files import open_write_file, resolve_write_files


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _exact(value, keys):
    if not isinstance(value, dict) or set(value) - set(keys):
        raise ValueError("The request contains unsupported members.")


class WriteCoordinator:
    def __init__(self, adapters=None, *, approval=None):
        self.adapters = adapters if adapters is not None else default_adapters()
        if not isinstance(self.adapters, dict):
            raise TypeError("write_adapters must be a provider-keyed adapter registry or None for built-ins.")
        for provider, adapter in self.adapters.items():
            failures = check_write_adapter(adapter)
            if provider != getattr(adapter, "provider", None):
                failures.append("The registry key must match the adapter provider.")
            if failures:
                raise ValueError("; ".join(failures))
        self.approval = approval

    def _adapter(self, source):
        adapter = self.adapters.get(source.provider)
        if adapter is None:
            raise WriteFailure("mapping_unverified", "No verified write adapter is registered for this provider.")
        return adapter

    @staticmethod
    def _storage(engine):
        if engine.storage is None:
            raise WriteFailure("storage_required", "Writes require an explicit atomic durable storage adapter.")
        return engine.storage

    @staticmethod
    def _grant(context, permission):
        operation = {"write:plan": "plan_write", "write:commit": "commit_write"}[permission]
        if permission not in context.authorization or not context.allows(operation):
            raise WriteFailure("permission_denied", "The trusted server policy does not authorize this operation.")

    @staticmethod
    def _failure(error, context):
        code = error.code if isinstance(error, WriteFailure) else "invalid_input"
        return OperationResult("failed", errors=(Error(code, str(error)),), operation_id=context.operation_id)

    def plan_write(self, engine, request, content, context):
        try:
            self._grant(context, "write:plan")
            storage = self._storage(engine)
            _exact(request, ("source", "changes", "bounds"))
            if content is not None:
                raise ValueError("Supply explicitly named file parts in changes, not an unbound content stream.")
            source, bounds = Source(**request["source"]), Bounds(**request.get("bounds", {}))
            adapter = self._adapter(source)
            if callable(getattr(adapter, "bind_files", None)):
                adapter = adapter.bind_files(storage, context.scope)
            adapter.validate_source(source, context)
            changes = request.get("changes")
            if not isinstance(changes, list) or not changes or len(changes) > bounds.max_records:
                raise ValueError("Provide a nonempty changes array within max_records.")
            # File bytes use the separate transfer bound, not the metadata parser bound.
            metadata = deepcopy(request)
            for change in metadata["changes"]:
                if isinstance(change.get("fields"), dict):
                    change["fields"].pop("MatterAttachmentBinary", None)
                for part in change.get("files", ()):
                    if isinstance(part, dict):
                        part.pop("content_base64", None)
            if len(json.dumps(metadata, allow_nan=False).encode()) > bounds.parser_bytes:
                raise ValueError("Write metadata exceeds the parser byte limit.")
            config = adapter.credentials(source, context)
            # Fail, rather than store, a credential embedded in source-supplied data.
            if sanitize(request, config) != request:
                raise ValueError("Public write data contains credentials or signed authorization data.")
            deadline = monotonic() + bounds.deadline_seconds
            prepared, keys, resources = [], set(), set()
            for raw in changes:
                if operation_cancelled(storage, context):
                    return OperationResult("cancelled", operation_id=context.operation_id)
                change_input = deepcopy(raw)
                change_input["files"] = resolve_write_files(engine, raw.get("files", ()), context=context, bounds=bounds)
                change = WriteChange.from_dict(change_input)
                if change.key in keys:
                    raise ValueError("Batch change keys must be unique.")
                keys.add(change.key)
                if change.resource_id is not None:
                    target = (change.entity, str(change.parent_id), str(change.resource_id), change.language,
                              change.page_number)
                    if target in resources:
                        raise ValueError("Overlapping changes to one resource require separate reviewed plans.")
                    resources.add(target)
                value = adapter.prepare(source, change, context, bounds, deadline)
                if canonical_hash(sanitize(value, config)) != canonical_hash(value):
                    raise ValueError("The provider plan contains secret authorization data.")
                prepared.append(value)
            plan_id = str(uuid.uuid4())
            from dataclasses import asdict
            plan = {
                "schema_version": SCHEMA_VERSION, "plan_id": plan_id, "created_at": _now(),
                "principal": context.principal, "client_id": context.client_id, "tenant": context.tenant,
                "scope": context.scope, "source": source.public_dict(), "bounds": asdict(bounds),
                "changes": prepared, "mock": adapter.mock,
                "live_acceptance": "NOT_RUN", "authorization_policy": "explicit_exact_plan_commit",
            }
            digest = canonical_hash(plan)
            storage.put("write_plans", plan_id, {"plan": plan, "plan_hash": digest},
                        scope=context.scope, create_only=True)
            return OperationResult("completed", data={"plan": deepcopy(plan), "plan_id": plan_id,
                                                      "plan_hash": digest},
                                   coverage={"mock": adapter.mock, "changes": len(prepared),
                                             "live_acceptance": "NOT_RUN"},
                                   operation_id=context.operation_id)
        except (WriteFailure, ValueError, TypeError, KeyError) as error:
            return self._failure(error, context)

    def _load_plan(self, engine, request, context):
        storage = self._storage(engine)
        stored = storage.get("write_plans", request["plan_id"], scope=context.scope)
        if stored is None:
            raise WriteFailure("not_found", "No write plan exists in this principal/client/tenant scope.")
        plan = stored.value.get("plan")
        digest = stored.value.get("plan_hash")
        if not isinstance(plan, dict) or digest != canonical_hash(plan) or plan.get("scope") != context.scope:
            raise WriteFailure("plan_tampered", "The immutable stored plan no longer matches its digest/scope.")
        if request.get("plan_hash") is not None and request["plan_hash"] != digest:
            raise WriteFailure("plan_mismatch", "Commit must approve this exact immutable plan hash.")
        namespace = plan.get("source", {}).get("namespace")
        if context.allowed_namespaces is not None and namespace not in context.allowed_namespaces:
            raise WriteFailure("permission_denied", "The target namespace is no longer authorized.")
        return storage, plan, digest

    def commit_write(self, engine, request, content, context):
        try:
            self._grant(context, "write:commit")
            _exact(request, ("plan_id", "plan_hash"))
            if not isinstance(request.get("plan_hash"), str) or not request["plan_hash"]:
                raise ValueError("Explicit commit requires the exact plan_id and plan_hash.")
            if content is not None:
                raise ValueError("A commit cannot replace a plan's bound file content.")
            storage, plan, digest = self._load_plan(engine, request, context)
            source, bounds = Source(**plan["source"]), Bounds(**plan["bounds"])
            adapter = self._adapter(source)
            if callable(getattr(adapter, "bind_files", None)):
                adapter = adapter.bind_files(storage, context.scope)
            if adapter.mock != plan["mock"]:
                raise WriteFailure("plan_mismatch", "A plan cannot switch between mock and real transports.")
            for prepared in plan["changes"]:
                adapter.authorize(source, WriteChange.from_dict(prepared["change"]), context)
                for part in prepared["native"].get("files", ()):
                    with open_write_file(storage, part["reference"], scope=context.scope):
                        pass
            if not context.allows("commit_write", source.namespace):
                raise WriteFailure("permission_denied", "The trusted client policy denies commit to this namespace.")
            if self.approval is not None and not self.approval(deepcopy(plan), digest, context):
                raise WriteFailure("permission_denied", "The configured exact-plan approval policy denied commit.")
            stored = storage.get("receipts", plan["plan_id"], scope=context.scope)
            if stored is None:
                receipt = {
                    "schema_version": SCHEMA_VERSION, "plan_id": plan["plan_id"], "plan_hash": digest,
                    "scope": context.scope, "mock": adapter.mock, "live_acceptance": "NOT_RUN",
                    "created_at": _now(), "updated_at": _now(),
                    "items": [{"key": p["change"]["key"], "state": "planned"} for p in plan["changes"]],
                }
                try:
                    version = storage.put("receipts", plan["plan_id"], receipt, scope=context.scope,
                                          create_only=True)
                except StorageConflict:
                    return self.receipt(engine, {"plan_id": plan["plan_id"]}, None, context)
            else:
                receipt, version = stored.value, stored.version
                if receipt.get("plan_hash") != digest:
                    raise WriteFailure("plan_tampered", "The durable receipt does not match the approved plan.")
            deadline = monotonic() + bounds.deadline_seconds
            operation_id = context.operation_id or plan["plan_id"]
            update_operation(storage, operation_id, {"operation": "commit_write", "status": "running",
                                                     "plan_id": plan["plan_id"]}, scope=context.scope)
            def cancelled():
                state = storage.get("operations", operation_id, scope=context.scope)
                return operation_cancelled(storage, context) or bool(state and state.value.get("cancel_requested"))

            for index, prepared in enumerate(plan["changes"]):
                item = receipt["items"][index]
                if item["state"] in {"succeeded", "failed", "conflict", "cancelled"}:
                    continue
                if cancelled():
                    # Do not hide completed siblings or turn an uncertain send into cancellation.
                    if item["state"] == "planned":
                        item.update(state="cancelled", reason="Cancelled before mutation.")
                        version = self._save(storage, receipt, version, context)
                    continue
                if monotonic() >= deadline:
                    break
                if item["state"] in {"sending", "uncertain", "pending"}:
                    try:
                        outcome = adapter.reconcile(source, prepared, item, context, bounds, deadline)
                    except (WriteFailure, ValueError):
                        outcome = {"state": "uncertain", "reason": "Readback reconciliation could not complete."}
                    item.update(outcome)
                    version = self._save(storage, receipt, version, context)
                    # Never resubmit this item, even if reconciliation finds nothing.
                    continue
                item.update(state="sending", intent_id=str(uuid.uuid4()), started_at=_now())
                version = self._save(storage, receipt, version, context)
                # Intent is durable before the first possible outbound mutation.
                try:
                    def persist_step(step):
                        nonlocal version
                        item.update(step)
                        version = self._save(storage, receipt, version, context)
                        return cancelled()

                    outcome = adapter.apply(source, prepared, context, bounds, deadline, persist=persist_step)
                except AmbiguousWrite:
                    outcome = {"state": "uncertain", "reason": "Mutation may have succeeded; reconcile before retry."}
                except WriteFailure as error:
                    outcome = {"state": {"conflict": "conflict", "cancelled": "cancelled"}.get(error.code, "failed"),
                               "error": {"code": error.code, "message": str(error)}}
                except Exception:
                    # Unanticipated adapter/parse errors after send must not enable replay.
                    outcome = {"state": "uncertain", "reason": "Adapter could not confirm the request outcome."}
                item.update(outcome)
                item["finished_at"] = _now()
                version = self._save(storage, receipt, version, context)
                context.report(operation="commit_write", completed=index + 1, total=len(plan["changes"]),
                               plan_id=plan["plan_id"])
            result = self._result(receipt, context)
            update_operation(storage, operation_id, {"status": result.status, "data": result.data,
                                                     "coverage": result.coverage}, scope=context.scope)
            return result
        except StorageConflict:
            # Another exact commit/reconciliation owns the newer state; do not send again.
            return self.receipt(engine, {"plan_id": request["plan_id"]}, None, context)
        except (WriteFailure, ValueError, TypeError, KeyError) as error:
            return self._failure(error, context)

    @staticmethod
    def _save(storage, receipt, version, context):
        receipt["updated_at"] = _now()
        return storage.put("receipts", receipt["plan_id"], receipt, scope=context.scope,
                           expected_version=version)

    def receipt(self, engine, request, content, context):
        try:
            if not ({"write:plan", "write:commit", "write:receipt"} & context.authorization):
                raise WriteFailure("permission_denied", "The trusted server policy does not authorize write receipts.")
            _exact(request, ("plan_id",))
            storage, plan, digest = self._load_plan(engine, request, context)
            if not context.allows("receipt", plan["source"]["namespace"]):
                raise WriteFailure("permission_denied", "The trusted client policy denies this receipt.")
            source = Source(**plan["source"])
            adapter = self._adapter(source)
            for prepared in plan["changes"]:
                adapter.authorize(source, WriteChange.from_dict(prepared["change"]), context)
            stored = storage.get("receipts", plan["plan_id"], scope=context.scope)
            if stored is None:
                return OperationResult("completed", data={"plan_id": plan["plan_id"], "plan_hash": digest,
                                                          "state": "planned", "mock": plan["mock"],
                                                          "live_acceptance": "NOT_RUN", "items": []},
                                       operation_id=context.operation_id)
            if stored.value.get("plan_hash") != digest:
                raise WriteFailure("plan_tampered", "Receipt does not match the approved plan.")
            return self._result(stored.value, context)
        except (WriteFailure, ValueError, TypeError, KeyError) as error:
            return self._failure(error, context)

    @staticmethod
    def _result(receipt, context):
        receipt = deepcopy(receipt)
        states = [item["state"] for item in receipt["items"]]
        if states and all(s == "succeeded" for s in states):
            status, state = "completed", "succeeded"
        elif states and all(s == "cancelled" for s in states):
            status, state = "cancelled", "cancelled"
        elif states and all(s in {"failed", "conflict"} for s in states):
            status, state = "failed", "failed"
        else:
            status, state = "partial", "partial"
        receipt["state"] = state
        errors = tuple(Error(item.get("error", {}).get("code", item["state"]),
                             item.get("error", {}).get("message", item.get("reason", "Write not confirmed.")),
                             details={"key": item["key"]})
                       for item in receipt["items"] if item["state"] != "succeeded")
        return OperationResult(
            status, data=receipt, errors=errors,
            coverage={"mock": receipt["mock"], "live_acceptance": "NOT_RUN", "changes": len(states),
                      "succeeded": states.count("succeeded"), "outstanding": [
                          item["key"] for item in receipt["items"]
                          if item["state"] in {"planned", "sending", "uncertain", "pending"}
                      ]},
            operation_id=context.operation_id or receipt["plan_id"],
        )


def register(engine, adapters=None, *, approval=None):
    """Register one coordinator for all transports; contexts are trusted server inputs."""
    coordinator = WriteCoordinator(adapters, approval=approval)
    engine.register_operation("plan_write", coordinator.plan_write)
    engine.register_operation("commit_write", coordinator.commit_write)
    engine.register_operation("receipt", coordinator.receipt)
    return coordinator
