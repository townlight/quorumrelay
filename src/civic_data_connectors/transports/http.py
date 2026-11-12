"""Versioned, authenticated ASGI adapter. No provider-specific behavior lives here."""

from __future__ import annotations

import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import replace
from threading import Lock
from uuid import uuid4
from urllib.parse import urlsplit

import anyio
from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.middleware import Middleware
from starlette.exceptions import HTTPException
from jsonschema.exceptions import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Mount, Route

from .. import __version__
from ..models import OperationResult
from ..storage import ProgressRecorder, update_operation
from .openapi import document, validate_result
from .runtime import OPERATIONS, ServiceConfig, bound_request, execute, failure
from .files import allowed as file_input_allowed

HANDLE = re.compile(r"^[0-9a-f]{64}$")
ARTIFACT = re.compile(r"^[0-9a-f]{48}$")


def response(result, code=200):
    try:
        value = validate_result(result.public_dict())
    except (ValueError, TypeError, ValidationError):
        value, code = failure("invalid_result", "The operation returned a non-JSON result.").public_dict(), 500
    return JSONResponse(value, status_code=code)


class RequestLimit:
    """Enforce actual streamed bytes before JSON/multipart parsing, not Content-Length alone."""

    def __init__(self, app, config):
        self.app, self.config = app, config

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            host = urlsplit("http://" + headers.get(b"host", b"").decode("latin-1")).hostname
        except ValueError:
            host = None
        if host is None or host.lower() not in {h.lower().strip("[]") for h in self.config.allowed_hosts}:
            return await response(failure("host_denied", "Host is not allowed."), 400)(scope, receive, send)
        origin = headers.get(b"origin")
        if origin and origin.decode("latin-1") not in self.config.allowed_origins:
            return await response(failure("origin_denied", "Origin is not allowed."), 403)(scope, receive, send)
        upload = scope["path"] == "/v1/files"
        cap = self.config.transfer_bytes + 65536 if upload else self.config.json_bytes
        size, started = 0, False

        async def bounded_receive():
            nonlocal size
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > cap:
                    raise ValueError("transport_byte_limit")
            return message

        async def observed_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            # A streaming download has its own lifetime, not an input deadline.
            if scope["method"] in {"POST", "PUT", "PATCH"}:
                with anyio.fail_after(self.config.request_timeout):
                    await self.app(scope, bounded_receive, observed_send)
            else:
                await self.app(scope, bounded_receive, observed_send)
        except ValueError as error:
            if str(error) != "transport_byte_limit" or started:
                raise
            await response(failure("size_limit", "Request exceeds the configured transport byte limit."), 413)(
                scope, receive, send)
        except TimeoutError:
            if not started:
                await response(failure("deadline_exceeded", "Request exceeded the service deadline."), 503)(
                    scope, receive, send)


def create_app(engine, config: ServiceConfig | None = None, *, mcp_token_verifier=None, mcp_principal_resolver=None):
    config = config or ServiceConfig()
    config.validate()
    jobs, jobs_lock = {}, Lock()
    executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="civic-job")

    def authenticate(request):
        principal = config.authenticate(request.headers.get("authorization"))
        if principal is None:
            return None, response(failure("authentication_required", "A valid service bearer token is required."), 401)
        return principal, None

    def run(operation, payload, principal, context, content):
        try:
            result = execute(engine, principal, operation, payload, context=context, content=content)
            result = replace(result, operation_id=context.operation_id)
            if operation == "export" and isinstance(result.data, dict) and result.data.get("artifact_id"):
                artifact_id = result.data["artifact_id"]
                result = replace(result, data={**result.data, "file_handle": artifact_id,
                                              "download_path": "/v1/files/" + artifact_id})
        except Exception:
            result = failure("internal_error", "The operation failed; inspect protected service diagnostics.",
                             operation_id=context.operation_id)
        if engine.storage is not None:
            if isinstance(context.progress, ProgressRecorder):
                context.progress.flush()
            update_operation(engine.storage, context.operation_id, {
                "operation": operation, "state": result.status, "result": result.public_dict(),
            }, scope=context.scope)
        return result

    def scoped_file(handle, context):
        if not isinstance(handle, str) or not HANDLE.fullmatch(handle) or engine.storage is None:
            raise ValueError("The file handle is unavailable in this caller scope.")
        item = engine.storage.get("service_files", handle, scope=context.scope)
        if item is None:
            raise ValueError("The file handle is unavailable in this caller scope.")
        if not file_input_allowed(context) or item.value.get("expires_at", float("inf")) <= time.time():
            raise ValueError("The file input expired or its current authorization was revoked.")
        if item.value.get("purpose") == "input":
            from ..interchange import open_input
            _, stream = open_input(engine, handle, context=context)
            return {**item.value, "reference": item.value["storage_reference"]}, stream
        # Historical uploads had no purpose/expiry metadata. Preserve those
        # scoped immutable references, verifying their bytes before consumption.
        from ..write_files import open_write_file
        return item.value, open_write_file(engine.storage, item.value["reference"], scope=context.scope)

    async def dispatch(request: Request):
        principal, denied = authenticate(request)
        if denied:
            return denied
        operation = request.path_params["operation"]
        if operation not in OPERATIONS:
            return response(failure("unknown_operation", "Unknown API operation."), 404)
        if operation not in principal.operations:
            return response(failure("permission_denied", "Operation is not permitted by caller policy."), 403)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return response(failure("content_type", "Use application/json."), 415)
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("Each operation request must be a JSON object.")
            payload = dict(payload)
            if any(k in payload for k in ("authorization", "credentials", "principal", "client_id", "tenant", "context")):
                raise ValueError("Identity, credentials and grants cannot be supplied as operation arguments.")
            payload = bound_request(operation, payload, config)
            context = principal.context()
            context.operation_id = uuid4().hex
            content = None
            neutral_input = operation in {"import_preview", "import_bundle"} and payload.get("format") in {
                "json", "jsonl", "zip"}
            if "file_handle" in payload and not neutral_input:
                if "content_base64" in payload:
                    raise ValueError("Supply either file_handle or content_base64, not both.")
                item, stream = scoped_file(payload.pop("file_handle"), context)
                with stream:
                    if item["reference"]["byte_length"] > config.parser_bytes:
                        raise ValueError("This parser operation exceeds its configured parser byte limit.")
                    content = stream.read(config.parser_bytes + 1)
                if len(content) > config.parser_bytes:
                    raise ValueError("This parser operation exceeds its configured parser byte limit.")
            if operation == "cancel":
                operation_id = payload.get("operation_id")
                with jobs_lock:
                    event = jobs.get((context.scope, operation_id))
                if event is not None:
                    event.set()
            asynchronous = request.url.path.startswith("/v1/jobs/")
            if asynchronous and (engine.storage is None or operation in {"status", "cancel"}):
                return response(failure("storage_required", "Background work requires configured durable storage."), 400)
            if engine.storage is not None:
                update_operation(engine.storage, context.operation_id, {
                    "operation": operation, "state": "running", "cancel_requested": False,
                }, scope=context.scope)
                context.progress = ProgressRecorder(engine.storage, context.operation_id,
                                                    scope=context.scope, operation=operation)
            with jobs_lock:
                jobs[(context.scope, context.operation_id)] = context.cancellation

            def work():
                try:
                    return run(operation, payload, principal, context, content)
                finally:
                    with jobs_lock:
                        jobs.pop((context.scope, context.operation_id), None)

            if asynchronous:
                if len(jobs) > 64:
                    with jobs_lock:
                        jobs.pop((context.scope, context.operation_id), None)
                    return response(failure("busy", "Too many bounded operations; retry later."), 503)
                executor.submit(work)
                return response(OperationResult("partial", data={
                    "state": "running", "status_operation": {"operation_id": context.operation_id},
                }, operation_id=context.operation_id), 202)
            try:
                result = await anyio.to_thread.run_sync(work, abandon_on_cancel=True)
            finally:
                context.cancellation.set()
            return response(result)
        except (ValueError, TypeError, KeyError) as error:
            if str(error) == "transport_byte_limit":
                raise
            return response(failure("invalid_request", str(error)), 400)

    async def upload(request: Request):
        principal, denied = authenticate(request)
        if denied:
            return denied
        if not file_input_allowed(principal.context()):
            return response(failure("permission_denied", "File access is not permitted."), 403)
        if engine.storage is None or not callable(getattr(engine.storage, "save_capture", None)):
            return response(failure("storage_required", "File transfer requires scoped capture storage."), 400)
        context = principal.context()
        kind = request.headers.get("content-type", "").split(";")[0]
        try:
            if kind == "multipart/form-data":
                async with request.form(max_files=1, max_fields=0, max_part_size=65536) as form:
                    uploaded = form.get("file")
                    if not isinstance(uploaded, UploadFile):
                        raise ValueError("multipart upload requires exactly one file part named file.")
                    filename, content_type = uploaded.filename or "upload.bin", uploaded.content_type or "application/octet-stream"
                    reference = await anyio.to_thread.run_sync(
                        lambda: engine.storage.save_capture(uploaded.file, scope=context.scope,
                                                            max_bytes=config.transfer_bytes))
            elif kind == "application/octet-stream":
                filename, content_type = "upload.bin", "application/octet-stream"
                with tempfile.TemporaryFile() as staging:
                    size = 0
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > config.transfer_bytes:
                            return response(failure("size_limit", "File exceeds configured transfer byte limit."), 413)
                        staging.write(chunk)
                    staging.seek(0)
                    reference = await anyio.to_thread.run_sync(
                        lambda: engine.storage.save_capture(staging, scope=context.scope,
                                                            max_bytes=config.transfer_bytes))
            else:
                return response(failure("content_type", "Use multipart/form-data or application/octet-stream."), 415)
            handle = uuid4().hex + uuid4().hex
            if (len(filename) > 255 or "\0" in filename or len(content_type) > 255
                    or any(char in content_type for char in "\r\n")):
                raise ValueError("Invalid upload filename or content type metadata.")
            engine.storage.put("service_files", handle, {
                "reference": reference, "storage_reference": reference, "purpose": "input",
                "file_handle": handle, "filename": filename, "content_type": content_type,
                "max_bytes": config.transfer_bytes, "sha256": reference["sha256"],
                "byte_length": reference["byte_length"], "expires_at": time.time() + 3600},
                               scope=context.scope, create_only=True)
            return response(OperationResult("completed", data={"file_handle": handle, **reference,
                "filename": filename, "content_type": content_type}))
        except ValueError as error:
            if str(error) == "transport_byte_limit":
                raise
            limit = "exceeds" in str(error) and "limit" in str(error)
            return response(failure("size_limit" if limit else "invalid_file", str(error)), 413 if limit else 400)

    async def download(request: Request):
        principal, denied = authenticate(request)
        if denied:
            return denied
        if "fetch" not in principal.operations and "export" not in principal.operations:
            return response(failure("permission_denied", "File download is not permitted."), 403)
        context = principal.context()
        try:
            handle = request.path_params["handle"]
            if ARTIFACT.fullmatch(handle):
                from ..interchange import open_artifact
                metadata, source = open_artifact(engine, handle, context=context)
                if metadata["byte_length"] > config.transfer_bytes:
                    source.close()
                    raise ValueError("File exceeds the configured transfer byte limit.")
                def artifact_chunks():
                    with source:
                        while chunk := source.read(1024 * 1024):
                            yield chunk
                return StreamingResponse(artifact_chunks(), media_type="application/octet-stream", headers={
                    "Content-Disposition": 'attachment; filename="export.bin"',
                    "Content-Length": str(metadata["byte_length"]), "X-Content-Type-Options": "nosniff",
                })
            item, source = scoped_file(request.path_params["handle"], context)
            if item["reference"]["byte_length"] > config.transfer_bytes:
                source.close()
                raise ValueError("File exceeds the configured transfer byte limit.")
            def chunks():
                with source as stream:
                    while chunk := stream.read(1024 * 1024):
                        yield chunk
            return StreamingResponse(chunks(), media_type="application/octet-stream", headers={
                "Content-Disposition": 'attachment; filename="capture.bin"',
                "Content-Length": str(item["reference"]["byte_length"]),
                "X-Content-Type-Options": "nosniff",
            })
        except ValueError:
            return response(failure("not_found", "No downloadable file exists in this caller scope."), 404)

    async def info(request):
        principal, denied = authenticate(request)
        return denied or response(OperationResult("completed", data={
            "version": __version__, "schema_version": "2.0.0", "api_version": "v1",
            "operations": sorted(principal.operations),
        }))

    async def openapi(request):
        return JSONResponse(document())

    routes = [
        Route("/openapi.json", openapi, methods=["GET"]),
        Route("/v1/info", info, methods=["GET"]),
        Route("/v1/operations/{operation}", dispatch, methods=["POST"]),
        Route("/v1/jobs/{operation}", dispatch, methods=["POST"]),
        Route("/v1/files", upload, methods=["POST"]),
        Route("/v1/files/{handle}", download, methods=["GET"]),
    ]
    mcp_server = None
    if config.mcp:
        from .mcp import create_server, http_app
        mcp_server = create_server(engine, config=config, token_verifier=mcp_token_verifier,
                                   principal_resolver=mcp_principal_resolver)
        routes.append(Mount("/", app=http_app(mcp_server, config)))

    @asynccontextmanager
    async def lifespan(app):
        if mcp_server is not None:
            async with mcp_server.session_manager.run():
                yield
        else:
            yield
        with jobs_lock:
            for event in jobs.values():
                event.set()
        executor.shutdown(wait=True, cancel_futures=True)
        from ..interchange import cleanup_artifacts
        cleanup_artifacts(engine)

    async def http_error(request, error):
        return response(failure("invalid_http_request", "Check the request route, method, and multipart framing."),
                        error.status_code)

    app = Starlette(routes=routes, lifespan=lifespan,
                    exception_handlers={HTTPException: http_error},
                    middleware=[Middleware(RequestLimit, config=config)])
    app.state.engine, app.state.config = engine, config
    return app
