"""Versioned portable JSON schemas, with no reference-product dependencies."""

from __future__ import annotations

from copy import deepcopy

from .models import SCHEMA_VERSION


def _object(properties, required=(), **extra):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": True, **extra}


TEXT = {"type": "string"}
NULL_TEXT = {"type": ["string", "null"]}
OBJECT = {"type": "object"}
SHA256 = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
VERSION = {"const": SCHEMA_VERSION}

SOURCE = _object({
    "provider": {"type": "string", "minLength": 1},
    "url": {"type": "string", "format": "uri", "pattern": "^https?://"},
    "namespace": NULL_TEXT, "body": NULL_TEXT, "input_format": NULL_TEXT, "options": OBJECT,
}, ("provider", "url"))
IDENTITY = _object({
    "provider": TEXT, "namespace": TEXT, "record_type": TEXT, "external_id": TEXT,
    "parent": {"type": ["object", "null"]}, "derivation": TEXT, "stability": TEXT,
}, ("provider", "namespace", "record_type", "external_id"))
ERROR = _object({
    "code": TEXT, "message": TEXT, "retryable": {"type": "boolean"}, "source": NULL_TEXT, "details": OBJECT,
}, ("code", "message"))
RECORD = _object({
    "schema_version": VERSION, "identity": IDENTITY, "normalized": OBJECT,
    "source_url": TEXT, "citation_urls": {"type": "array", "items": TEXT},
    "capture_sha256": SHA256, "captured_at": {"type": "string", "format": "date-time"},
    "normalized_sha256": SHA256, "source_revision": OBJECT, "original": {},
    "relationships": {"type": "array", "items": OBJECT},
    "text": {"type": "array", "items": _object({
        "field": TEXT, "text": TEXT, "citation_url": TEXT, "page": {"type": "integer", "minimum": 1},
        "timestamp": {}, "provenance": {}, "completeness": TEXT, "language": TEXT,
    }, ("field", "text", "citation_url"))}, "extensions": OBJECT,
}, ("schema_version", "identity", "normalized", "source_url", "citation_urls", "capture_sha256",
    "captured_at", "normalized_sha256", "source_revision"))
CAPTURE = _object({
    "sha256": SHA256, "captured_at": {"type": "string", "format": "date-time"},
    "input_format": TEXT, "content_base64": {"type": "string", "contentEncoding": "base64"},
    "byte_length": {"type": "integer", "minimum": 0}, "original_values": {},
    "source_url": TEXT, "storage_reference": {},
}, ("sha256", "captured_at", "input_format", "byte_length", "source_url"))
BUNDLE = _object({
    "schema_version": VERSION, "source": SOURCE, "records": {"type": "array", "items": RECORD},
    "capture": CAPTURE, "compatibility": OBJECT, "extensions": OBJECT,
}, ("schema_version", "source", "records", "capture", "compatibility"))
RESULT = _object({
    "schema_version": VERSION,
    "status": {"enum": ["completed", "partial", "cancelled", "failed", "unsupported"]},
    "data": {}, "errors": {"type": "array", "items": ERROR}, "coverage": OBJECT,
    "operation_id": NULL_TEXT,
}, ("schema_version", "status", "data", "errors", "coverage", "operation_id"))
QUERY = _object({
    **{name: {"type": "array", "items": TEXT} for name in
       ("terms", "phrases", "namespaces", "providers", "record_types")},
    "body": NULL_TEXT, "date_from": NULL_TEXT, "date_to": NULL_TEXT,
    "limit": {"type": "integer", "minimum": 1},
})
BOUNDS = _object({
    "date_from": NULL_TEXT, "date_to": NULL_TEXT,
    **{name: {"type": "integer", "minimum": 1} for name in
       ("max_records", "max_pages", "parser_bytes", "transfer_bytes")},
    "deadline_seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 3600},
    "checkpoint": NULL_TEXT,
}, additionalProperties=False)
CAPABILITY = _object({
    "id": TEXT, "canonical_id": TEXT, "family_id": TEXT, "name": TEXT,
    "aliases": {"type": "array", "items": TEXT},
    "baseline_formats": {"type": "array", "items": TEXT},
    "operations": {"type": "object", "additionalProperties": _object({
        "capability_status": TEXT, "implementation_status": TEXT, "acceptance_status": TEXT,
        "evidence_level": TEXT, "evidence_ids": {"type": "array", "items": TEXT},
    }, ("capability_status", "implementation_status", "acceptance_status"))},
    "evidence": {"type": "array", "items": OBJECT},
    "outbound_mappings": {"type": "array", "items": OBJECT},
}, ("canonical_id", "operations", "evidence"))

SCHEMAS = {
    "source": SOURCE, "identity": IDENTITY, "record": RECORD, "error": ERROR,
    "capture": CAPTURE, "capture-bundle": BUNDLE, "result": RESULT, "query": QUERY, "bounds": BOUNDS,
    "capability": CAPABILITY,
}


def json_schema(name: str) -> dict:
    """Return an independent copy suitable for OpenAPI, validation or publishing."""
    if name not in SCHEMAS:
        raise ValueError(f"Unknown schema: {name}")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:civic-data-connectors:schema:{SCHEMA_VERSION}:{name}",
        "title": f"Civic data connectors {name} {SCHEMA_VERSION}",
        **deepcopy(SCHEMAS[name]),
    }
