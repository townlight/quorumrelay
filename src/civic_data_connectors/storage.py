"""Optional scoped SQLite storage, CAS state, and bounded streaming captures.

The application owns the database path and its filesystem permissions. No database
is opened merely by importing this module or constructing the core Engine.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from functools import wraps
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator, Protocol, runtime_checkable

from .extensions import Storage, StorageConflict, StoredValue
from .models import Error, OperationResult


def _encode(value: dict) -> str:
    if not isinstance(value, dict):
        raise ValueError("Stored values must be JSON objects.")
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


@dataclass(frozen=True)
class Mutation:
    collection: str
    key: str
    value: dict
    expected_version: str | None = None
    create_only: bool = False


@runtime_checkable
class AtomicStorage(Storage, Protocol):
    """Optional extension: all mutations commit or none do."""

    def put_many(self, mutations: list[Mutation], *, scope: str) -> list[str]: ...


@runtime_checkable
class CaptureStorage(Protocol):
    """Optional external-store extension; stream bytes without a parser cap.

    References are opaque, scoped, immutable and retrievable after restart.
    Implementations must enforce max_bytes on actual bytes, not headers.
    """

    def save_capture(self, stream: BinaryIO, *, scope: str, max_bytes: int) -> dict: ...
    def open_capture(self, reference: dict, *, scope: str) -> BinaryIO: ...


class SQLiteStorage:
    """Each call owns its connection; SQLite arbitrates threads and processes."""

    def __init__(self, path: str | Path, *, timeout: float = 15):
        self.path = Path(path).absolute()
        self.timeout = timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS values_store (
                    scope TEXT NOT NULL, collection TEXT NOT NULL, key TEXT NOT NULL,
                    value TEXT NOT NULL, version INTEGER NOT NULL,
                    PRIMARY KEY(scope, collection, key));
                CREATE TABLE IF NOT EXISTS value_history (
                    scope TEXT NOT NULL, collection TEXT NOT NULL, key TEXT NOT NULL,
                    version INTEGER NOT NULL, value TEXT NOT NULL,
                    PRIMARY KEY(scope, collection, key, version));
                CREATE TABLE IF NOT EXISTS capture_blobs (
                    id INTEGER PRIMARY KEY, scope TEXT NOT NULL, sha256 TEXT NOT NULL,
                    size INTEGER NOT NULL, content BLOB NOT NULL,
                    UNIQUE(scope, sha256));
            """)

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path, timeout=self.timeout, isolation_level=None)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _put(db, mutation: Mutation, scope: str) -> str:
        if not all(isinstance(x, str) and x for x in (scope, mutation.collection, mutation.key)):
            raise ValueError("Storage scope, collection and key must be nonempty strings.")
        value = _encode(mutation.value)
        row = db.execute(
            "SELECT version FROM values_store WHERE scope=? AND collection=? AND key=?",
            (scope, mutation.collection, mutation.key),
        ).fetchone()
        if mutation.create_only and row:
            raise StorageConflict("The scoped key already exists.")
        if mutation.expected_version is not None and (
            not row or str(row[0]) != mutation.expected_version
        ):
            raise StorageConflict("The stored version changed or the scoped key is absent.")
        version = row[0] + 1 if row else 1
        db.execute(
            "INSERT INTO values_store VALUES (?,?,?,?,?) "
            "ON CONFLICT(scope,collection,key) DO UPDATE SET value=excluded.value,version=excluded.version",
            (scope, mutation.collection, mutation.key, value, version),
        )
        db.execute("INSERT INTO value_history VALUES (?,?,?,?,?)",
                   (scope, mutation.collection, mutation.key, version, value))
        return str(version)

    def put(self, collection: str, key: str, value: dict, *, scope: str,
            expected_version: str | None = None, create_only: bool = False) -> str:
        return self.put_many(
            [Mutation(collection, key, value, expected_version, create_only)], scope=scope,
        )[0]

    def put_many(self, mutations: list[Mutation], *, scope: str) -> list[str]:
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                versions = [self._put(db, mutation, scope) for mutation in mutations]
                db.commit()
                return versions
            except BaseException:
                db.rollback()
                raise

    def get(self, collection: str, key: str, *, scope: str) -> StoredValue | None:
        with self._connection() as db:
            row = db.execute(
                "SELECT value,version FROM values_store WHERE scope=? AND collection=? AND key=?",
                (scope, collection, key),
            ).fetchone()
        return StoredValue(key, json.loads(row[0]), str(row[1])) if row else None

    def iter_values(self, collection: str, *, scope: str) -> Iterator[StoredValue]:
        """A read-transaction snapshot consumed incrementally, in stable key order."""
        with self._connection() as db:
            db.execute("BEGIN")
            for key, value, version in db.execute(
                "SELECT key,value,version FROM values_store WHERE scope=? AND collection=? ORDER BY key",
                (scope, collection),
            ):
                yield StoredValue(key, json.loads(value), str(version))

    def list(self, collection: str, *, scope: str) -> list[StoredValue]:
        return list(self.iter_values(collection, scope=scope))

    def history(self, collection: str, key: str, *, scope: str) -> list[StoredValue]:
        with self._connection() as db:
            return [
                StoredValue(key, json.loads(value), str(version))
                for value, version in db.execute(
                    "SELECT value,version FROM value_history "
                    "WHERE scope=? AND collection=? AND key=? ORDER BY version",
                    (scope, collection, key),
                )
            ]

    def save_capture(self, stream: BinaryIO, *, scope: str, max_bytes: int) -> dict:
        if not isinstance(scope, str) or not scope or type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError("A scoped capture requires a positive transfer limit.")
        digest, size = hashlib.sha256(), 0
        # Disk-backed staging bounds RAM independently from the transfer/parser limit.
        with tempfile.TemporaryFile() as staging:
            while True:
                chunk = stream.read(min(1024 * 1024, max_bytes - size + 1))
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("The capture exceeds the transfer byte limit.")
                digest.update(chunk)
                staging.write(chunk)
            sha256 = digest.hexdigest()
            staging.seek(0)
            with self._connection() as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    row = db.execute(
                        "SELECT id FROM capture_blobs WHERE scope=? AND sha256=?", (scope, sha256),
                    ).fetchone()
                    if row is None:
                        cursor = db.execute(
                            "INSERT INTO capture_blobs(scope,sha256,size,content) VALUES (?,?,?,zeroblob(?))",
                            (scope, sha256, size, size),
                        )
                        if size:
                            with db.blobopen("capture_blobs", "content", cursor.lastrowid) as blob:
                                while chunk := staging.read(1024 * 1024):
                                    blob.write(chunk)
                    db.commit()
                except BaseException:
                    db.rollback()
                    raise
        return {"kind": "sqlite_capture", "sha256": sha256, "byte_length": size}

    def open_capture(self, reference: dict, *, scope: str) -> BinaryIO:
        """Return a closable disk-backed stream, never a caller-controlled path."""
        if reference.get("kind") != "sqlite_capture":
            raise ValueError("The capture storage reference is not supported.")
        stream = tempfile.TemporaryFile()
        try:
            with self._connection() as db:
                db.execute("BEGIN")
                row = db.execute(
                    "SELECT id,size FROM capture_blobs WHERE scope=? AND sha256=?",
                    (scope, reference.get("sha256")),
                ).fetchone()
                if row is None:
                    raise ValueError("The capture is unavailable in the caller's scope.")
                if reference.get("byte_length", row[1]) != row[1]:
                    raise ValueError("The capture reference byte length does not match.")
                if row[1]:
                    with db.blobopen("capture_blobs", "content", row[0], readonly=True) as blob:
                        while chunk := blob.read(1024 * 1024):
                            stream.write(chunk)
            stream.seek(0)
            return stream
        except BaseException:
            stream.close()
            raise


def update_operation(storage: Storage, operation_id: str, patch: dict, *, scope: str) -> str:
    """Merge progress with CAS, retaining an independently requested cancellation."""
    for _ in range(32):
        old = storage.get("operations", operation_id, scope=scope)
        value = {**(old.value if old else {}), **patch}
        if old and old.value.get("cancel_requested"):
            value["cancel_requested"] = True
        try:
            return storage.put(
                "operations", operation_id, value, scope=scope,
                expected_version=old.version if old else None, create_only=old is None,
            )
        except StorageConflict:
            continue
    raise StorageConflict("Operation progress is busy; retry without discarding state.")


def operation_cancelled(storage, context) -> bool:
    if context.check_cancelled():
        return True
    if storage is not None and context.operation_id:
        value = storage.get("operations", context.operation_id, scope=context.scope)
        return bool(value and value.value.get("cancel_requested"))
    return False


def state_namespaces(value) -> set[str]:
    """Extract source-policy bindings from stored envelopes, including old state."""
    found = set()
    if isinstance(value, dict):
        identity = value.get("identity")
        if isinstance(identity, dict) and isinstance(identity.get("namespace"), str):
            found.add(identity["namespace"])
        if isinstance(value.get("namespace"), str) and any(
            key in value for key in ("provider", "source_url", "resource", "operation", "target", "citation_url")
        ):
            found.add(value["namespace"])
        for key in ("source", "target"):
            source = value.get(key)
            if isinstance(source, dict) and isinstance(source.get("namespace"), str):
                found.add(source["namespace"])
        for key in ("namespaces", "source_namespaces"):
            namespaces = value.get(key)
            if isinstance(namespaces, (list, tuple)):
                found.update(namespace for namespace in namespaces if isinstance(namespace, str))
        for child in value.values():
            found.update(state_namespaces(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(state_namespaces(child))
    return found


def _can_read_state(value, context):
    operation = value.get("operation")
    if not context.allows(operation):
        return False
    return all(context.allowed_namespaces is None or namespace in context.allowed_namespaces
               for namespace in state_namespaces(value))


def tracked_handler(operation, handler):
    """Persist progress for caller-supplied IDs without overriding cancellation.

    Storage is optional. A caller using its own jobs can supply progress instead.
    A restart reuses its operation ID; this helper records state, not auto-retries.
    """
    @wraps(handler)
    def tracked(owner, request, content, context):
        if owner.storage is None or not context.operation_id:
            return handler(owner, request, content, context)
        from dataclasses import replace
        from .engine import canonical_hash
        binding = canonical_hash({"operation": operation, "request": request,
                                  "content_sha256": hashlib.sha256(content).hexdigest() if content is not None else None})
        for _ in range(32):
            old = owner.storage.get("operations", context.operation_id, scope=context.scope)
            if old and (old.value.get("request_sha256") not in {None, binding}
                        or old.value.get("operation") not in {None, operation}):
                raise StorageConflict("An operation ID cannot be reused for a different request.")
            if old and old.value.get("request_sha256") == binding:
                break
            try:
                owner.storage.put("operations", context.operation_id,
                    {**(old.value if old else {}), "operation": operation, "request_sha256": binding},
                    scope=context.scope, expected_version=old.version if old else None,
                    create_only=old is None)
                break
            except StorageConflict:
                continue
        else:
            raise StorageConflict("The operation ID is busy; retry without replacing its binding.")
        if operation_cancelled(owner.storage, context):
            return OperationResult("cancelled", operation_id=context.operation_id)
        previous = context.progress
        def progress(value):
            update_operation(owner.storage, context.operation_id,
                             {"operation": operation, "progress": value}, scope=context.scope)
            if previous:
                previous(value)
        class ScopedCancellation:
            def is_set(self):
                return operation_cancelled(owner.storage, context)
            def set(self):
                context.cancellation.set()
        delegated = replace(context, progress=progress, cancellation=ScopedCancellation())
        update_operation(owner.storage, context.operation_id,
                         {"operation": operation, "status": "running", "request_sha256": binding}, scope=context.scope)
        try:
            result = handler(owner, request, content, delegated)
        except Exception:
            update_operation(owner.storage, context.operation_id,
                             {"operation": operation, "status": "failed"}, scope=context.scope)
            raise
        update_operation(owner.storage, context.operation_id,
                         {"operation": operation, "status": result.status,
                          "coverage": result.coverage,
                          "source_namespaces": sorted(state_namespaces(request) | state_namespaces(result.public_dict())),
                          "result": result.public_dict()}, scope=context.scope)
        return result
    return tracked


def register(engine) -> None:
    """Optional local operation state handlers; composition may choose other owners."""
    def status(owner, request, content, context):
        if owner.storage is None:
            return OperationResult.unsupported("status", reason="No optional storage is configured.")
        item = owner.storage.get("operations", request["operation_id"], scope=context.scope)
        if item is None:
            return OperationResult("failed", errors=(Error("not_found", "No operation in this scope."),))
        if not _can_read_state(item.value, context):
            return OperationResult("failed", errors=(Error("permission_denied",
                "The operation or its source evidence is no longer authorized."),))
        return OperationResult("completed", data=item.value, operation_id=request["operation_id"])

    def cancel(owner, request, content, context):
        if owner.storage is None:
            return OperationResult.unsupported("cancel", reason="No optional storage is configured.")
        operation_id = request["operation_id"]
        item = owner.storage.get("operations", operation_id, scope=context.scope)
        if item is None:
            return OperationResult("failed", errors=(Error("not_found", "No operation in this scope."),))
        if not _can_read_state(item.value, context):
            return OperationResult("failed", errors=(Error("permission_denied",
                "The operation or its source evidence is no longer authorized."),))
        update_operation(owner.storage, operation_id, {"cancel_requested": True}, scope=context.scope)
        return OperationResult("completed", data={"cancel_requested": True}, operation_id=operation_id)

    engine.register_operation("status", status)
    engine.register_operation("cancel", cancel)
