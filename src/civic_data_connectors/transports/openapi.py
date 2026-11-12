"""OpenAPI from packaged core schemas, validated against real outgoing envelopes."""

import json
from importlib.resources import files

from jsonschema import Draft202012Validator

from .. import __version__
from .runtime import OPERATIONS


def schemas():
    result = {}
    for entry in files("civic_data_connectors").joinpath("schemas").iterdir():
        if entry.name.endswith(".schema.json"):
            value = json.loads(entry.read_text(encoding="utf-8"))
            value.pop("$id", None)
            value.pop("$schema", None)
            result[entry.name.removesuffix(".schema.json")] = value
    return result


def document():
    components = schemas()
    components["request"] = {
        "type": "object",
        "properties": {
            "source": {"$ref": "#/components/schemas/source"},
            "bounds": {"$ref": "#/components/schemas/bounds"},
            "query": {"$ref": "#/components/schemas/query"},
            "content_base64": {"type": "string", "contentEncoding": "base64"},
            "file_handle": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "stream": {"type": "boolean", "description": "Export to a scoped artifact, then stream the file handle."},
        },
        "additionalProperties": True,
        "description": "The operation-specific shared engine request, never a caller identity or grant.",
    }
    result = {"description": "Complete engine result, including partial coverage and structured errors.",
              "content": {"application/json": {"schema": {"$ref": "#/components/schemas/result"}}}}
    responses = {str(code): result for code in (200, 202, 400, 401, 403, 404, 413, 415, 500, 503)}
    paths = {}
    for operation in OPERATIONS:
        paths[f"/v1/operations/{operation}"] = {"post": {
            "operationId": operation,
            "summary": f"Execute shared {operation} operation",
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/request"}}}},
            "responses": responses,
        }}
        if operation not in {"status", "cancel"}:
            paths[f"/v1/jobs/{operation}"] = {"post": {
                "operationId": f"submit_{operation}",
                "summary": "Submit bounded work; inspect with status and cancel through shared operations.",
                "requestBody": {"required": True, "content": {"application/json": {
                    "schema": {"$ref": "#/components/schemas/request"}}}},
                "responses": responses,
            }}
    paths["/v1/files"] = {"post": {
        "operationId": "upload_file",
        "summary": "Upload bytes to an opaque caller-scoped handle, never a filesystem path.",
        "requestBody": {"required": True, "content": {
            "multipart/form-data": {"schema": {"type": "object", "required": ["file"], "properties": {
                "file": {"type": "string", "format": "binary"}}}},
            "application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
        }}, "responses": responses,
    }}
    paths["/v1/files/{handle}"] = {"get": {
        "operationId": "download_file",
        "parameters": [{"name": "handle", "in": "path", "required": True,
                        "schema": {"type": "string", "pattern": "^([0-9a-f]{48}|[0-9a-f]{64})$"}}],
        "responses": {**responses, "200": {"description": "Bounded byte stream.",
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}},
    }}
    paths["/v1/info"] = {"get": {"operationId": "service_info", "responses": responses}}
    return {
        "openapi": "3.1.0", "info": {"title": "QuorumRelay", "version": __version__},
        "paths": paths, "security": [{"serviceBearer": []}],
        "components": {"schemas": components, "securitySchemes": {
            "serviceBearer": {"type": "http", "scheme": "bearer",
                              "description": "Service token, not an upstream provider credential."}}},
    }


def validate_result(value):
    """Validation uses JSON wire values rather than Python's tuple representation."""
    value = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    Draft202012Validator(schemas()["result"]).validate(value)
    return value
