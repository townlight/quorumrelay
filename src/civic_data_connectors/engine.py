"""One bounded engine boundary for SDK, CLI, HTTP and MCP adapters."""

from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlsplit

from . import compat
from .capabilities import canonical_provider_id, inventory_metadata, provider_capabilities
from .extensions import Connector, Storage, check_connector
from .models import (
    Bounds, CaptureBundle, Error, Identity, OperationContext, OperationResult, Query, Record, Source,
)

Handler = Callable[["Engine", dict, bytes | None, OperationContext], OperationResult]
Parser = Callable[[Source, bytes, str, Bounds, OperationContext], OperationResult]
_ACTIVE_DISPATCH = ContextVar("civic_engine_dispatch", default=None)
_INTERNAL_DEPENDENCIES = {
    "discover": frozenset({"normalize"}), "fetch": frozenset({"normalize"}),
    "import_preview": frozenset({"normalize"}),
}


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def source_identity_key(identity: Identity | dict) -> str:
    """Canonical source identity, never a consumer application record ID."""
    def identity_fields(value, depth=0):
        if depth > 32:
            raise ValueError("The source identity parent chain exceeds its supported depth.")
        if isinstance(value, Identity):
            value = value.public_dict()
        if not isinstance(value, dict):
            raise ValueError("A source identity and its parents must be objects.")
        parent = value.get("parent")
        return {**{key: value.get(key) for key in
                   ("provider", "namespace", "record_type", "external_id")},
                "parent": identity_fields(parent, depth + 1) if parent is not None else None}

    return canonical_hash(identity_fields(identity))


class Engine:
    def __init__(self, *, storage: Storage | None = None, connectors: tuple[Connector, ...] = ()):
        self.storage = storage
        self.connectors: dict[str, Connector] = {}
        self.handlers: dict[str, Handler] = {}
        self.parsers: dict[tuple[str, str], Parser] = {}
        self.native_searches: dict[str, Handler] = {}
        self.native_exports: dict[str, Handler] = {}
        for connector in connectors:
            self.register_connector(connector)

    def register_connector(self, connector: Connector) -> None:
        failures = check_connector(connector)
        if failures:
            raise ValueError("; ".join(failures))
        if connector.provider in self.connectors:
            raise ValueError(f"Connector already registered: {connector.provider}")
        self.connectors[connector.provider] = connector

    def register_operation(self, operation: str, handler: Handler) -> None:
        if operation in {"providers", "capabilities", "normalize"} or operation in self.handlers:
            raise ValueError(f"Operation already registered: {operation}")
        self.handlers[operation] = handler

    def register_parser(self, provider: str, input_format: str, parser: Parser) -> None:
        provider = canonical_provider_id(provider, allow_extension=True)
        key = (provider, input_format)
        baseline = {(item["connector"], item["input_format"]) for item in compat.source_formats()}
        if key in self.parsers or key in baseline:
            raise ValueError("An additive parser cannot replace an existing or baseline input format.")
        if not callable(parser):
            raise ValueError("A parser must implement the typed parse hook.")
        self.parsers[key] = parser

    def register_native_search(self, provider: str, handler: Handler) -> None:
        provider = canonical_provider_id(provider, allow_extension=True)
        if provider in self.native_searches or not callable(handler):
            raise ValueError("A native search handler must be callable and registered once per provider.")
        self.native_searches[provider] = handler

    def register_native_export(self, provider: str, handler: Handler) -> None:
        provider = canonical_provider_id(provider, allow_extension=True)
        if provider in self.native_exports or not callable(handler):
            raise ValueError("A native export handler must be callable and registered once per provider.")
        self.native_exports[provider] = handler

    def discover(self, source: Source, *, bounds: Bounds | None = None,
                 context: OperationContext | None = None) -> OperationResult:
        from dataclasses import asdict
        return self.execute("discover", {"source": source.public_dict(), "bounds": asdict(bounds or Bounds())},
                            context=context)

    def fetch(self, source: Source, request: dict | None = None, *, bounds: Bounds | None = None,
              context: OperationContext | None = None) -> OperationResult:
        from dataclasses import asdict
        return self.execute("fetch", {**(request or {}), "source": source.public_dict(),
                                     "bounds": asdict(bounds or Bounds())}, context=context)

    def fetch_attachment(self, source: Source, record: Record | dict, *, index: int = 0,
                         kind: str = "documents", capture: bytes | None = None, bounds: Bounds | None = None,
                         context: OperationContext | None = None, url_field: str = "url") -> OperationResult:
        """Fetch only a captured attachment from scoped storage or supplied original capture."""
        from dataclasses import asdict
        identity = record.identity if isinstance(record, Record) else record["identity"]
        return self.execute("fetch", {
            "source": source.public_dict(), "bounds": asdict(bounds or Bounds()),
            "attachment": {"record_key": source_identity_key(identity), "index": index, "kind": kind,
                           "url_field": url_field},
        }, content=capture, context=context)

    def fetch_record(self, source: Source, external_id: str, *, bounds: Bounds | None = None,
                     context: OperationContext | None = None) -> OperationResult:
        """Retrieve one known provider identity through its evidenced detail route."""
        return self.fetch(source, {"external_id": external_id}, bounds=bounds, context=context)

    def fetch_captions(self, source: Source, external_id: str, *, language: str | None = None,
                       bounds: Bounds | None = None, context: OperationContext | None = None) -> OperationResult:
        """Read supplied caption tracks; this never requests transcription or diarization."""
        return self.fetch(source, {"external_id": external_id, "caption_language": language or "*"},
                          bounds=bounds, context=context)

    def fetch_related(self, source: Source, parent_id: str, record_type: str, *,
                      external_id: str | None = None, bounds: Bounds | None = None,
                      context: OperationContext | None = None) -> OperationResult:
        """Read an evidenced provider child collection or one supplied child ID."""
        request = {"parent_id": parent_id, "record_type": record_type}
        if external_id is not None:
            request["external_id"] = external_id
        return self.fetch(source, request, bounds=bounds, context=context)

    def search(self, query: Query, *, context: OperationContext | None = None) -> OperationResult:
        from dataclasses import asdict
        return self.execute("search", {"query": asdict(query)}, context=context)

    def plan_write(self, source: Source, request: dict, *,
                   context: OperationContext | None = None) -> OperationResult:
        return self.execute("plan_write", {**request, "source": source.public_dict()}, context=context)

    def commit_write(self, request: dict, *, context: OperationContext | None = None) -> OperationResult:
        return self.execute("commit_write", request, context=context)

    def receipt(self, request: dict, *, context: OperationContext | None = None) -> OperationResult:
        return self.execute("receipt", request, context=context)

    def _allows(self, operation: str, context: OperationContext, namespace: str | None = None) -> bool:
        namespace_allowed = (namespace is None or context.allowed_namespaces is None
                             or namespace in context.allowed_namespaces)
        if not namespace_allowed:
            return False
        if context.allowed_operations is None or operation in context.allowed_operations:
            return True
        active = _ACTIVE_DISPATCH.get()
        return bool(active and active[0] is self and active[1] is context
                    and operation in _INTERNAL_DEPENDENCIES.get(active[2], ()))

    def _extension_operation(self, operation, request, content, context):
        source_data = request.get("source")
        provider = source_data.get("provider") if isinstance(source_data, dict) else request.get("provider")
        connector = self.connectors.get(provider)
        if connector is None:
            if operation == "export" and request.get("provider_specific") is True and provider:
                handler = self.native_exports.get(canonical_provider_id(provider, allow_extension=True))
                if handler is not None:
                    return handler(self, request, content, context)
            if operation == "search" and request.get("native") is True and provider:
                handler = self.native_searches.get(canonical_provider_id(provider, allow_extension=True))
                if handler is not None:
                    return handler(self, request, content, context)
            return None
        if operation == "identify":
            return connector.identify(request["url"])
        if not isinstance(source_data, dict):
            return None
        source = Source.from_dict(source_data)
        if context.allowed_namespaces is not None and source.namespace is None:
            raise ValueError("A restricted extension request requires an explicitly configured source namespace.")
        if not self._allows(operation, context, source.namespace):
            return OperationResult("failed", errors=(Error("permission_denied",
                "The configured extension namespace is outside the caller policy."),))
        bounds = Bounds(**request.get("bounds", {}))
        if operation == "validate_source":
            identified = connector.identify(source.url)
            if identified.status not in {"completed", "partial"}:
                return identified
            return OperationResult(identified.status, {"source": source.public_dict()},
                                   identified.errors, identified.coverage, context.operation_id)
        if operation == "discover":
            return connector.discover(source, bounds, context)
        if operation == "fetch":
            return connector.fetch(source, request, bounds, context)
        if operation == "search" and request.get("native") is True:
            return connector.native_search(source, Query(**request.get("query", {})), bounds, context)
        if operation == "export" and request.get("provider_specific") is True:
            return connector.export(source, request, context)
        # Writes always go through the shared immutable-plan/receipt implementation.
        return None

    def providers(self) -> OperationResult:
        providers = {}
        for item in compat.source_formats():
            providers.setdefault(item["connector"], []).append(item)
        rows = []
        for provider, formats in providers.items():
            capabilities = provider_capabilities(provider)
            rows.append({
                "provider": provider, "aliases": capabilities["aliases"], "formats": formats,
                "additional_formats": sorted(input_format for registered, input_format in self.parsers
                                             if registered == provider),
                "parse": {"implementation": "extracted_baseline", "acceptance": "fixture_passed",
                          "evidence": "all 34 baseline captures independently compared with pinned originals"},
                "capabilities": capabilities,
                "extension_capabilities": self.connectors[provider].capabilities()
                if provider in self.connectors else None,
            })
        for provider, connector in self.connectors.items():
            if provider not in providers:
                rows.append({"provider": provider, "formats": [],
                             "additional_formats": sorted(fmt for registered, fmt in self.parsers
                                                          if registered == provider),
                             "capabilities": connector.capabilities()})
        return OperationResult("completed", data={"providers": rows, "formats": compat.source_formats(),
                                                  "inventory": inventory_metadata()})

    def execute(self, operation: str, request: dict, *, content: bytes | None = None,
                context: OperationContext | None = None) -> OperationResult:
        context = context or OperationContext()
        if not self._allows(operation, context):
            return OperationResult("failed", errors=(Error("permission_denied",
                "The caller is not authorized for this operation."),), operation_id=context.operation_id)
        if context.check_cancelled():
            return OperationResult("cancelled", operation_id=context.operation_id)
        try:
            if not isinstance(request, dict):
                raise ValueError("The operation request must be a JSON object.")
            if operation == "providers":
                return self.providers()
            if operation == "capabilities":
                provider = request.get("provider")
                if provider and provider not in self.connectors:
                    provider = canonical_provider_id(provider)
                result = self.providers()
                rows = result.data["providers"]
                if provider:
                    rows = [row for row in rows if row["provider"] == provider]
                    if not rows:
                        raise ValueError("The configured provider is not registered.")
                return OperationResult("completed", data={"providers": rows})
            if operation == "normalize":
                if content is None:
                    encoded = request.get("content_base64")
                    if not isinstance(encoded, str):
                        raise ValueError("normalize requires content bytes or content_base64.")
                    content = base64.b64decode(encoded, validate=True)
                return self.normalize(
                    Source.from_dict(request["source"]), content,
                    input_format=request.get("input_format") or request["source"].get("input_format")
                    or "meeting-export", bounds=Bounds(**request.get("bounds", {})), context=context,
                )
            token = _ACTIVE_DISPATCH.set((self, context, operation))
            try:
                extension_result = self._extension_operation(operation, request, content, context)
            finally:
                _ACTIVE_DISPATCH.reset(token)
            if extension_result is not None:
                if not isinstance(extension_result, OperationResult):
                    raise ValueError("A connector hook must return the common OperationResult.")
                return extension_result
            handler = self.handlers.get(operation)
            if handler:
                token = _ACTIVE_DISPATCH.set((self, context, operation))
                try:
                    return handler(self, request, content, context)
                finally:
                    _ACTIVE_DISPATCH.reset(token)
            return OperationResult.unsupported(operation, reason=(
                "No evidenced implementation is registered for this operation; "
                "this does not establish that the provider lacks the capability."
            ))
        except (ValueError, TypeError, KeyError) as error:
            return OperationResult("failed", errors=(Error("invalid_input", str(error)),),
                                   operation_id=context.operation_id)

    def normalize(self, source: Source, content: bytes, *, input_format: str = "meeting-export",
                  bounds: Bounds | None = None, context: OperationContext | None = None) -> OperationResult:
        """Non-persisting import preview retaining exact input and v1 output."""
        bounds, context = bounds or Bounds(), context or OperationContext()
        if not self._allows("normalize", context, source.namespace):
            return OperationResult("failed", errors=(Error("permission_denied",
                "The caller is not authorized to normalize this source."),), operation_id=context.operation_id)
        if context.check_cancelled():
            return OperationResult("cancelled", operation_id=context.operation_id)
        try:
            if len(content) > min(bounds.parser_bytes, compat.MAX_INPUT_BYTES):
                raise ValueError("The parser input exceeds the configured parser byte limit.")
            parser = self.parsers.get((source.provider, input_format))
            if parser is not None:
                return _bounded_parser_result(parser(source, content, input_format, bounds, context), bounds, context)
            if source.provider in self.connectors:
                return _bounded_parser_result(
                    self.connectors[source.provider].parse(source, content, input_format, bounds, context),
                    bounds, context,
                )
            legacy = compat.preview_export(source.provider, source.url, content, input_format=input_format)
            namespace = legacy["source"]["namespace"]
            if source.namespace is not None and source.namespace != namespace:
                raise ValueError("The configured namespace does not match the provider source URL.")
            if not self._allows("normalize", context, namespace):
                return OperationResult("failed", errors=(Error("permission_denied",
                    "The source namespace is outside the caller's configured policy."),),
                    operation_id=context.operation_id)
            digest = hashlib.sha256(content).hexdigest()
            captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            original_values = None
            try:
                original_values = json.loads(content)
            except (ValueError, UnicodeError):
                pass
            rich_rows = deepcopy(legacy["meetings"])
            if source.provider == "tyler-meeting-manager":
                rich_rows = _rich_tyler(source.url, original_values)
            if source.provider == "first-party":
                rich_rows = _rich_calendar(source.url, content)
            records, unknown_dates, filtered = [], [], 0
            for index, row in enumerate(rich_rows):
                if context.check_cancelled():
                    break
                day = row.get("meeting_date") or (row.get("scheduled_start") or "")[:10]
                if (bounds.date_from or bounds.date_to) and not day:
                    unknown_dates.append(row["external_id"])
                if day and ((bounds.date_from and day < bounds.date_from)
                            or (bounds.date_to and day > bounds.date_to)):
                    filtered += 1
                    continue
                records.append(_record(source, namespace, row, original_values, digest, captured_at))
                context.report(operation="normalize", completed=index + 1, total=len(rich_rows))
            truncated = len(records) > bounds.max_records
            records = records[:bounds.max_records]
            capture = {
                "sha256": digest, "captured_at": captured_at, "input_format": input_format,
                "content_base64": base64.b64encode(content).decode("ascii"),
                "byte_length": len(content), "original_values": original_values,
                "source_url": source.url,
            }
            from dataclasses import replace
            configured = replace(source, namespace=namespace, input_format=input_format)
            bundle = CaptureBundle(configured, tuple(records), capture, legacy)
            cancelled = context.check_cancelled()
            status = "cancelled" if cancelled else "partial" if truncated or unknown_dates else "completed"
            coverage = {
                "sources": [configured.public_dict()], "date_from": bounds.date_from,
                "date_to": bounds.date_to, "date_inclusivity": "both",
                "actual_dates": sorted({r.normalized.get("meeting_date") or
                                        (r.normalized.get("scheduled_start") or "")[:10]
                                        for r in records} - {""}),
                "truncated": truncated, "filtered_records": filtered,
                "unknown_date_records": unknown_dates, "input_records": len(rich_rows),
                "returned_records": len(records), "available_text": "metadata_and_supplied_text_only",
                "failures": [], "checkpoint": None,
                "scope": "one saved capture, not a complete upstream catalog",
            }
            return OperationResult(status, bundle.public_dict(), coverage=coverage,
                                   operation_id=context.operation_id)
        except (compat.ImportInputError, ValueError, TypeError) as error:
            return OperationResult("failed", errors=(Error("invalid_capture", str(error), source=source.url),),
                                   coverage={"sources": [source.public_dict()], "failures": ["capture_parse"]},
                                   operation_id=context.operation_id)


def _bounded_parser_result(result, bounds, context):
    """Additive parse hooks share bounds, namespace policy and complete status semantics."""
    if not isinstance(result, OperationResult):
        raise ValueError("A parse hook must return OperationResult.")
    if result.status in {"failed", "unsupported"} or not isinstance(result.data, dict):
        return result
    data = deepcopy(result.data)
    rows = data.get("records")
    if not isinstance(rows, (list, tuple)):
        raise ValueError("A successful parse hook requires records in the shared capture bundle.")
    selected, unknown, filtered = [], [], 0
    for record in rows:
        namespace = record["identity"]["namespace"]
        if context.allowed_namespaces is not None and namespace not in context.allowed_namespaces:
            return OperationResult("failed", errors=(Error("permission_denied",
                "Parsed records include a source outside the configured namespace policy."),),
                operation_id=context.operation_id)
        normalized = record["normalized"]
        day = normalized.get("meeting_date") or (normalized.get("scheduled_start") or "")[:10]
        if not day and (bounds.date_from or bounds.date_to):
            unknown.append(record["identity"]["external_id"])
        if day and ((bounds.date_from and day < bounds.date_from) or (bounds.date_to and day > bounds.date_to)):
            filtered += 1
            continue
        selected.append(record)
    truncated = len(selected) > bounds.max_records
    data["records"] = selected[:bounds.max_records]
    status = result.status
    if context.check_cancelled():
        status = "cancelled"
    elif (truncated or unknown) and status == "completed":
        status = "partial"
    return OperationResult(status, data, result.errors, {
        **result.coverage, "date_from": bounds.date_from, "date_to": bounds.date_to,
        "date_inclusivity": "both", "truncated": result.coverage.get("truncated", False) or truncated,
        "unknown_date_records": unknown, "filtered_records": filtered, "input_records": len(rows),
        "returned_records": len(data["records"]),
        "scope": result.coverage.get("scope", "one saved capture, not a complete upstream catalog"),
    }, context.operation_id)


def _raw_row(provider, row, original):
    """Only baseline-evidenced JSON identifiers; never guess a live API mapping."""
    rows, key = None, None
    if provider == "primegov" and isinstance(original, list):
        rows, key = original, "id"
    elif provider == "tyler-meeting-manager" and isinstance(original, list):
        rows, key = original, "id"
    elif provider == "civicplus-select" and isinstance(original, dict):
        rows, key = original.get("value"), "id"
    elif provider == "escribe" and isinstance(original, dict):
        rows, key = original.get("d"), "ID"
    elif provider == "gworks" and isinstance(original, dict):
        rows, key = original.get("meetings"), "id"
    elif provider == "towncloud" and isinstance(original, dict):
        rows = original.get("data")
        if isinstance(rows, list):
            for item in rows:
                link = item.get("DT_RowData", {}).get("link") if isinstance(item, dict) else None
                if isinstance(link, str) and urlsplit(link).path.rstrip("/").rsplit("/", 1)[-1] == row["external_id"]:
                    return deepcopy(item)
        return {"capture_reference": "capture.original_values", "fields_available": "original_capture"}
    if isinstance(rows, list):
        return next((deepcopy(item) for item in rows if isinstance(item, dict)
                     and str(item.get(key)) == row["external_id"]), None)
    if isinstance(original, dict):
        return deepcopy(original)
    return {"capture_reference": "capture.content_base64", "fields_available": "original_capture"}


def _record(source, namespace, row, original, digest, captured_at):
    original_row = _raw_row(source.provider, row, original)
    start = row.get("scheduled_start") or row.get("source_start")
    zone = "unknown"
    if start:
        try:
            zone = "known_offset" if datetime.fromisoformat(start.replace("Z", "+00:00")).utcoffset() else "unknown"
            if start.endswith("Z") or start.endswith("+00:00"):
                zone = "known_offset"
        except ValueError:
            pass
    normalized = {**row, "time_zone_status": zone,
                  "agenda_items_availability": "supplied" if "agenda_items" in row else "absent"}
    agenda_field = {"legistar": "AgendaItems", "primegov": "items",
                    "granicus": "agenda", "novusagenda": "Agenda"}.get(source.provider)
    if (agenda_field and isinstance(original_row, dict) and "scheduled_start" in row
            and agenda_field not in original_row):
        normalized["agenda_items_availability"] = "absent"
    calendar_parameters = row.get("source_calendar_parameters", {}).get("DTSTART", "")
    if zone == "unknown" and calendar_parameters.startswith("TZID="):
        normalized["time_zone_status"] = "supplied_zone"
        normalized["source_time_zone"] = calendar_parameters.partition("=")[2]
    if source.body is not None:
        normalized["body"] = source.body
    revision = {"kind": "not_supplied", "value": None}
    if isinstance(original_row, dict):
        # Known baseline Tyler fields are source values, not local revision claims.
        if source.provider == "tyler-meeting-manager":
            normalized["source_status"] = {key: original_row[key] for key in
                                           ("canceled", "adjourned") if key in original_row}
    citations = tuple(dict.fromkeys([source.url] + ([row["url"]] if row.get("url") else [])))
    relationships = tuple(
        {"relation": kind, "value": deepcopy(value)}
        for field, kind in (("documents", "document"), ("recordings", "recording"),
                            ("agenda_items", "agenda_item"))
        for value in row.get(field, [])
    )
    derivation = "provider_or_legacy_reader"
    stability = "Stable according to the pinned input-format mapping; not an application identifier."
    if source.provider in {"boarddocs", "municode-meetings", "clerkbase"}:
        derivation, stability = "url_path", "Changes when the source path changes."
    if source.provider in {"towncloud", "tyler-meeting-manager"} and row.get("agenda_items"):
        normalized["agenda_item_identity_derivation"] = "position_in_capture"
    text = []
    if row.get("notice", {}).get("text"):
        text.append({"field": "notice.text", "text": row["notice"]["text"], "citation_url": source.url})
    for recording in row.get("recordings", []):
        for caption in recording.get("captions", []):
            text.append({"field": "recordings.captions", **caption,
                         "citation_url": recording.get("url") or source.url})
    return Record(
        Identity(source.provider, namespace, "meeting", row["external_id"],
                 derivation=derivation, stability=stability),
        normalized, source.url, citations, digest, captured_at, canonical_hash(row), revision,
        original_row, relationships, tuple(text),
    )


def _rich_tyler(source_url, original):
    rows = []
    for raw in original if isinstance(original, list) else []:
        if not isinstance(raw, dict):
            continue
        # Reuse the exact baseline calendar mapping without its workflow-only status filter.
        candidate = {**raw, "canceled": False, "adjourned": False}
        title = candidate.get("meetingTitle")
        if isinstance(title, str):
            candidate["meetingTitle"] = "Meeting " + title
        parsed = compat.read_tyler_meeting_manager(source_url, json.dumps([candidate]).encode())
        for row in parsed:
            row["title"] = title.strip()
            rows.append(row)
    return rows


def _rich_calendar(source_url, content):
    import re
    calendar = re.sub(r"\r?\n[ \t]", "", content.decode("utf-8-sig", errors="replace"))
    records = []
    for block in re.findall(r"^BEGIN:VEVENT\r?\n(.*?)^END:VEVENT", calendar, re.M | re.S):
        fields = {}
        parameters = {}
        for line in block.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                name, _, param = key.partition(";")
                fields.setdefault(name, value)
                if param:
                    parameters[name] = param
        adjusted = block.replace("STATUS:CANCELLED", "STATUS:CONFIRMED")
        for row in compat.read_public_calendar(
            source_url, f"BEGIN:VCALENDAR\nBEGIN:VEVENT\n{adjusted}\nEND:VEVENT\nEND:VCALENDAR".encode(),
        ):
            row["source_status"] = fields.get("STATUS")
            row["source_calendar_fields"] = fields
            row["source_calendar_parameters"] = parameters
            records.append(row)
    return records
