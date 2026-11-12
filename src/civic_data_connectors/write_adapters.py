"""Official native write mappings for the bounded meeting-data domain.

No simulated provider exists here. Inject WriteTransport to exercise these same
request/response/readback paths with synthetic data without making live writes.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import re
import uuid
from copy import copy, deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from time import monotonic
from urllib.parse import parse_qsl, quote, urlencode, urlsplit
from typing import Protocol, runtime_checkable

from .engine import canonical_hash
from .models import OperationContext, Source
from .write_transport import PublicWriteTransport, WriteResponse, WriteTransport
from .write_files import open_write_file


def _legistar_client(source):
    """Keep URL client routing separate from canonical/legacy source identity."""
    from .compat import source_namespace
    parsed = urlsplit(source.url)
    match = re.fullmatch(r"/v1/([A-Za-z0-9_-]+)(?:/.*)?", parsed.path)
    if parsed.hostname != "webapi.legistar.com" or match is None:
        raise ValueError("A Legistar write source must identify its exact API Client.")
    client = match.group(1)
    # The canonical reader namespace remains authoritative for new shared sources.
    # Original write-only configurations used the client slug and stay explicit.
    if source.namespace not in {client, source_namespace("legistar", parsed)}:
        raise ValueError("The Legistar source identity does not match its API Client.")
    return client


def _laserfiche_repository(source):
    """Separate repository routing from canonical or explicit legacy identity."""
    from .compat import source_namespace
    parsed = urlsplit(source.url)
    match = re.match(r"/repository/v2/Repositories/([A-Za-z0-9_-]+)(?:/|$)", parsed.path)
    if parsed.hostname != "api.laserfiche.com" or match is None:
        raise ValueError("A Laserfiche write source must identify its exact Repository API.")
    repository = match[1]
    if source.namespace not in {repository, source_namespace("laserfiche-weblink", parsed)}:
        raise ValueError("The Laserfiche source identity does not match its API repository.")
    return repository


class WriteFailure(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class AmbiguousWrite(WriteFailure):
    def __init__(self, message="The provider outcome is uncertain; do not repeat the mutation."):
        super().__init__("uncertain_outcome", message)


class WriteCancelled(WriteFailure):
    def __init__(self):
        super().__init__("cancelled", "Cancelled before the next outbound step; completed steps remain in the receipt.")


@dataclass(frozen=True)
class WriteChange:
    key: str
    entity: str
    operation: str
    fields: dict
    resource_id: str | int | None = None
    parent_id: str | int | None = None
    language: str | None = None
    page_number: int | None = None
    meeting_id: str | None = None
    expected_version: str | int | None = None
    files: tuple[dict, ...] = ()

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Each change must be an object.")
        return cls(**{**value, "files": tuple(value.get("files", ()))})


@dataclass(frozen=True)
class NativeRequest:
    method: str
    url: str
    content_type: str
    body: dict
    headers: dict
    files: tuple[dict, ...] = ()

    def public_dict(self):
        return asdict(self)


@runtime_checkable
class WriteAdapterProtocol(Protocol):
    """Trusted extension hooks; every mutation still goes through WriteCoordinator."""

    provider: str
    mock: bool

    def credentials(self, source: Source, context: OperationContext) -> dict: ...
    def validate_source(self, source: Source, context: OperationContext) -> None: ...
    def authorize(self, source: Source, change: WriteChange, context: OperationContext) -> None: ...
    def prepare(self, source: Source, change: WriteChange, context: OperationContext,
                bounds, deadline: float) -> dict: ...
    def apply(self, source: Source, prepared: dict, context: OperationContext,
              bounds, deadline: float, *, persist=None) -> dict: ...
    def reconcile(self, source: Source, prepared: dict, item: dict, context: OperationContext,
                  bounds, deadline: float) -> dict: ...


def check_write_adapter(adapter) -> list[str]:
    """Non-executing structural conformance, safe to call during registration."""
    failures = []
    if not isinstance(getattr(adapter, "provider", None), str) or not adapter.provider:
        failures.append("A write adapter requires a provider identifier.")
    if type(getattr(adapter, "mock", None)) is not bool:
        failures.append("A write adapter must declare its transport's mock status.")
    for name in ("credentials", "validate_source", "authorize", "prepare", "apply", "reconcile"):
        if not callable(getattr(adapter, name, None)):
            failures.append(f"A write adapter requires {name}.")
    return failures


def _fields(strings="", integers="", booleans="", dates="", binaries="", objects="", arrays=""):
    return {name: kind for names, kind in (
        (strings, "string"), (integers, "integer"), (booleans, "boolean"),
        (dates, "date"), (binaries, "binary"), (objects, "object"), (arrays, "array"),
    ) for name in names.split()}


EVENT_FIELDS = _fields(
    strings="EventGuid EventBodyName EventTime EventVideoStatus EventAgendaStatusName "
    "EventMinutesStatusName EventLocation EventAgendaFile EventMinutesFile EventComment "
    "EventVideoPath EventMedia EventInSiteURL",
    integers="EventId EventBodyId EventAgendaStatusId EventMinutesStatusId",
    dates="EventLastModifiedUtc EventDate EventAgendaLastPublishedUTC EventMinutesLastPublishedUTC",
    binaries="EventRowVersion", arrays="EventItems",
)
ITEM_FIELDS = _fields(
    strings="EventItemGuid EventItemAgendaNumber EventItemVersion EventItemAgendaNote "
    "EventItemMinutesNote EventItemActionName EventItemActionText EventItemPassedFlagName "
    "EventItemTitle EventItemTally EventItemAccelaRecordId EventItemMover EventItemSeconder "
    "EventItemMatterGuid EventItemMatterFile EventItemMatterName EventItemMatterType EventItemMatterStatus",
    integers="EventItemId EventItemEventId EventItemAgendaSequence EventItemMinutesSequence "
    "EventItemVideo EventItemVideoIndex EventItemActionId EventItemPassedFlag EventItemRollCallFlag "
    "EventItemFlagExtra EventItemConsent EventItemMoverId EventItemSeconderId EventItemMatterId",
    dates="EventItemLastModifiedUtc", binaries="EventItemRowVersion", arrays="EventItemMatterAttachments",
)
ATTACHMENT_FIELDS = _fields(
    strings="MatterAttachmentGuid MatterAttachmentName MatterAttachmentHyperlink "
    "MatterAttachmentFileName MatterAttachmentMatterVersion MatterAttachmentDescription",
    integers="MatterAttachmentId MatterAttachmentAgiloftId",
    booleans="MatterAttachmentIsHyperlink MatterAttachmentIsSupportingDocument "
    "MatterAttachmentShowOnInternetPage MatterAttachmentIsMinuteOrder MatterAttachmentIsBoardLetter "
    "MatterAttachmentPrintWithReports",
    dates="MatterAttachmentLastModifiedUtc", binaries="MatterAttachmentRowVersion MatterAttachmentBinary",
)
MATTER_FIELDS = _fields(
    strings="MatterGuid MatterFile MatterName MatterTitle MatterTypeName MatterStatusName MatterBodyName "
    "MatterEnactmentNumber MatterRequester MatterNotes MatterVersion MatterReference "
    + " ".join(f"MatterText{i}" for i in range(1, 6))
    + " " + " ".join(f"MatterEXText{i}" for i in range(1, 12)),
    integers="MatterId MatterTypeId MatterStatusId MatterBodyId MatterAgiloftId",
    booleans="MatterRestrictViewViaWeb",
    dates="MatterLastModifiedUtc MatterIntroDate MatterAgendaDate MatterPassedDate MatterEnactmentDate "
    "MatterDate1 MatterDate2 " + " ".join(f"MatterEXDate{i}" for i in range(1, 11)),
    binaries="MatterRowVersion", arrays="MatterReports",
)
MATTER_FIELDS["MatterCost"] = "number"
TEXT_FIELDS = _fields(
    strings="MatterTextGuid MatterTextVersion MatterTextPlain MatterTextRtf",
    integers="MatterTextId MatterTextMatterId", dates="MatterTextLastModifiedUtc",
    binaries="MatterTextRowVersion",
)
HISTORY_FIELDS = _fields(
    strings="MatterHistoryGuid MatterHistoryAgendaNumber MatterHistoryVersion MatterHistoryAgendaNote "
    "MatterHistoryMinutesNote MatterHistoryActionName MatterHistoryActionText MatterHistoryActionBodyName "
    "MatterHistoryPassedFlagName MatterHistoryTally MatterHistoryAccelaRecordId MatterHistoryMoverName "
    "MatterHistorySeconderName",
    integers="MatterHistoryId MatterHistoryEventId MatterHistoryAgendaSequence MatterHistoryMinutesSequence "
    "MatterHistoryVideo MatterHistoryVideoIndex MatterHistoryActionId MatterHistoryActionBodyId "
    "MatterHistoryPassedFlag MatterHistoryRollCallFlag MatterHistoryFlagExtra MatterHistoryConsent "
    "MatterHistoryMoverId MatterHistorySeconderId MatterHistoryMatterStatusId",
    dates="MatterHistoryLastModifiedUtc MatterHistoryActionDate", binaries="MatterHistoryRowVersion",
)
VOTE_FIELDS = _fields(
    strings="VoteGuid VotePersonName VoteValueName",
    integers="VoteId VotePersonId VoteValueId VoteSort VoteResult VoteEventItemId",
    dates="VoteLastModifiedUtc", binaries="VoteRowVersion",
)
ROLL_CALL_FIELDS = _fields(
    strings="RollCallGuid RollCallPersonName RollCallValueName",
    integers="RollCallId RollCallPersonId RollCallValueId RollCallSort RollCallResult RollCallEventItemId",
    dates="RollCallLastModifiedUtc", binaries="RollCallRowVersion",
)
LEGISTAR = {
    "event": (EVENT_FIELDS, "Event", "Events", ("EventDate",)),
    "event_item": (ITEM_FIELDS, "EventItem", "Events/{parent}/EventItems", ()),
    "matter_attachment": (ATTACHMENT_FIELDS, "MatterAttachment", "Matters/{parent}/Attachments",
                          ("MatterAttachmentName",)),
    "matter": (MATTER_FIELDS, "Matter", "Matters",
               ("MatterTypeId", "MatterStatusId", "MatterBodyId")),
    "matter_text": (TEXT_FIELDS, "MatterText", "Matters/{parent}/Texts", ("MatterTextMatterId",)),
    "matter_history": (HISTORY_FIELDS, "MatterHistory", "Matters/{parent}/Histories", ()),
    "vote": (VOTE_FIELDS, "Vote", "EventItems/{parent}/Votes", ("VotePersonId", "VoteValueId")),
    "roll_call": (ROLL_CALL_FIELDS, "RollCall", "EventItems/{parent}/RollCalls",
                  ("RollCallPersonId", "RollCallValueId")),
}


def validate_fields(value, schema, *, required=()):
    if not isinstance(value, dict):
        raise ValueError("Native fields must be an object.")
    unknown = value.keys() - schema.keys()
    if unknown:
        raise WriteFailure("unsupported_field", "Unsupported native field(s): " + ", ".join(sorted(unknown)))
    for name in required:
        if name not in value or value[name] is None:
            raise ValueError(f"The native field {name} is required.")
    for name, item in value.items():
        kind = schema[name]
        if item is None:
            # Explicit nullable cases are declared individually, not assumed.
            raise ValueError(f"{name} is not declared nullable by this mapping.")
        valid = (
            kind in {"string", "date", "binary"} and isinstance(item, str)
            or kind == "integer" and type(item) is int
            or kind == "boolean" and type(item) is bool
            or kind == "object" and isinstance(item, dict)
            or kind == "array" and isinstance(item, list)
            or kind == "number" and type(item) in {int, float} and math.isfinite(item)
        )
        if not valid:
            raise ValueError(f"{name} must have native type {kind}.")
        if kind == "date":
            datetime.fromisoformat(item.replace("Z", "+00:00"))
        if kind == "binary":
            try:
                base64.b64decode(item, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError(f"{name} must be base64 encoded bytes.") from None
        nested = {"EventItems": ITEM_FIELDS, "EventItemMatterAttachments": ATTACHMENT_FIELDS,
                  "MatterReports": _fields(strings="ReportName ReportURL ReportType")}.get(name)
        if nested is not None:
            for child in item:
                validate_fields(child, nested)


def safe_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value):
        raise ValueError("A provider resource identifier is required.")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", str(value)):
        raise ValueError("Provider identifiers cannot contain URL path/query characters.")
    return quote(str(value), safe="")


def _public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Writes require an HTTPS URL without embedded credentials or fragment.")
    if parsed.port not in {None, 443}:
        raise ValueError("Custom provider ports are not permitted.")
    forbidden = {"token", "access_token", "api_key", "signature", "sig", "key", "authorization"}
    if any(k.lower() in forbidden for k, _ in parse_qsl(parsed.query)):
        raise ValueError("Credentials and signed authorization URLs cannot appear in public inputs.")
    return parsed


def sanitize(value, credentials=None):
    """Remove credentials even from a hostile provider response before persistence."""
    secrets = []
    for key in ("token", "access_token", "authorization", "api_key"):
        secret = (credentials or {}).get(key)
        if isinstance(secret, str) and secret:
            secrets.append(secret)
    if isinstance(value, dict):
        return {k: sanitize(v, credentials) for k, v in value.items()
                if k.lower() not in {"token", "access_token", "authorization", "api_key", "cookie", "set-cookie"}}
    if isinstance(value, (list, tuple)):
        return [sanitize(v, credentials) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
        if value.startswith(("http://", "https://")):
            parsed = urlsplit(value)
            original_query = parse_qsl(parsed.query)
            query = [(k, v) for k, v in original_query
                     if k.lower() not in {"token", "access_token", "sig", "signature", "authorization",
                                          "x-amz-signature", "x-amz-credential", "x-amz-security-token"}]
            if query != original_query:
                value = parsed._replace(query=urlencode(query)).geturl()
    return value


class WriteAdapter:
    """Real native request mapper/executor using an injectable safe transport."""

    def __init__(self, provider, transport: WriteTransport | None = None):
        self.provider = provider
        self.family = "laserfiche" if provider == "laserfiche-weblink" else provider
        self.transport = transport or PublicWriteTransport()
        self.file_storage = None
        self.file_scope = None

    def bind_files(self, storage, scope):
        """Return an isolated per-invocation binding, never mutate a shared adapter."""
        bound = copy(self)
        bound.file_storage, bound.file_scope = storage, scope
        return bound

    def _open_file(self, part):
        if self.file_storage is None or self.file_scope is None:
            raise ValueError("The adapter requires a trusted scoped file resolver.")
        return open_write_file(self.file_storage, part["reference"], scope=self.file_scope)

    def _file_bytes(self, part):
        with self._open_file(part) as stream:
            return stream.read(part["reference"]["byte_length"] + 1)

    @property
    def mock(self):
        return self.transport.mock is True

    def credentials(self, source: Source, context: OperationContext):
        config = context.credentials.get(self.provider) or context.credentials.get(self.family)
        if not isinstance(config, dict) or not config.get("token"):
            raise WriteFailure("credentials_required", "Server-side provider credentials are required.")
        if source.namespace not in config.get("allowed_namespaces", [config.get("namespace")]):
            raise WriteFailure("permission_denied", "The provider credential does not authorize this namespace.")
        return config

    def validate_source(self, source, context):
        if source.provider != self.provider or not source.namespace:
            raise ValueError("A write source requires the exact provider and namespace.")
        parsed = _public_url(source.url)
        if not context.tenant:
            raise WriteFailure("permission_denied", "A trusted application tenant is required for write isolation.")
        if context.allowed_namespaces is not None and source.namespace not in context.allowed_namespaces:
            raise WriteFailure("permission_denied", "The target namespace is outside the trusted client policy.")
        if source.options:
            raise ValueError("Write sources do not accept arbitrary options or credential overrides.")
        if self.family == "legistar":
            _legistar_client(source)
        elif self.family == "wistia":
            host = parsed.hostname
            if host not in {"api.wistia.com", "upload.wistia.com", "fast.wistia.com"} and host not in {
                f"{source.namespace}.wistia.com", f"{source.namespace}.wistia.net",
            }:
                raise ValueError("The Wistia source is not an authorized provider/account origin.")
        elif self.family == "laserfiche":
            _laserfiche_repository(source)
        else:
            raise WriteFailure("mapping_unverified", "No verified native write mapping is installed.")
        self.credentials(source, context)

    def authorize(self, source, change, context):
        self.validate_source(source, context)
        permissions = self.credentials(source, context).get("permissions", ())
        if f"{change.entity}:{change.operation}" not in permissions:
            raise WriteFailure("permission_denied", "Server policy does not authorize this provider operation.")
        # Linked documents/media/matter content must be explicitly assigned to a meeting.
        if change.entity not in {"event", "event_item"} and not change.meeting_id:
            raise ValueError("This document/media operation requires an explicit meeting_id relationship.")
        if change.meeting_id:
            safe_id(change.meeting_id)
            if str(change.meeting_id) not in self.credentials(source, context).get("meeting_ids", ()):
                raise WriteFailure("permission_denied", "This meeting relationship is not in the saved source policy.")
        config = self.credentials(source, context)
        if change.parent_id is not None:
            allowed_parents = config.get("resource_ids") if self.family == "wistia" else config.get("parent_ids")
            if allowed_parents is not None and str(change.parent_id) not in allowed_parents:
                raise WriteFailure("permission_denied", "The parent resource is outside the source policy.")
        allowed = self.credentials(source, context).get("resource_ids")
        if change.resource_id is not None and allowed is not None and str(change.resource_id) not in allowed:
            raise WriteFailure("permission_denied", "The resource is outside the server-saved source policy.")
        if change.entity == "media_tags" and allowed is not None:
            if any(str(i) not in allowed for i in change.fields.get("hashed_ids", ())):
                raise WriteFailure("permission_denied", "A tag target is outside the source policy.")

    def _call(self, source, context, native, bounds, deadline, *, raw=False, private_response=False):
        if context.check_cancelled():
            raise WriteCancelled()
        config = self.credentials(source, context)
        headers = {"Accept": "application/json", **native.headers}
        url = native.url
        if self.family == "legistar":
            url += ("&" if "?" in url else "?") + urlencode({"token": config["token"]})
        else:
            headers["Authorization"] = "Bearer " + config["token"]
        if native.method == "GET":
            body = None
        elif native.content_type == "multipart/form-data":
            boundary = "civic-connectors-" + uuid.uuid4().hex
            chunks = [
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"request\"\r\n"
                "Content-Type: application/json\r\n\r\n".encode()
                + json.dumps(native.body, ensure_ascii=False, allow_nan=False).encode() + b"\r\n"
            ]
            # Wistia upload uses ordinary form fields, not Laserfiche's request part.
            if self.family == "wistia":
                chunks = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n"
                          f"{v}\r\n".encode() for k, v in native.body.items()]
            for part in native.files:
                chunks.append(
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"{part['part']}\"; "
                    f"filename=\"{part['filename']}\"\r\nContent-Type: {part['content_type']}\r\n\r\n".encode()
                    + self._file_bytes(part) + b"\r\n"
                )
            body = b"".join(chunks) + f"--{boundary}--\r\n".encode()
            headers["Content-Type"] = native.content_type + "; boundary=" + boundary
        elif native.content_type == "application/x-www-form-urlencoded":
            body = urlencode(native.body).encode()
            headers["Content-Type"] = native.content_type
        else:
            body = json.dumps(native.body, ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")).encode()
            headers["Content-Type"] = native.content_type
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure("deadline_exceeded", "The bounded write deadline expired before the request.")
        try:
            response = self.transport.send(
                url, method=native.method, body=body, headers=headers,
                byte_limit=bounds.transfer_bytes if raw else bounds.parser_bytes, deadline_seconds=remaining,
            )
        except (OSError, TimeoutError, RuntimeError, ValueError):
            # Never echo transport errors: they may contain credentialed URLs.
            raise AmbiguousWrite() from None
        if not isinstance(response, WriteResponse):
            raise AmbiguousWrite("The configured transport returned an invalid response.")
        if len(response.content) > (bounds.transfer_bytes if raw else bounds.parser_bytes):
            raise AmbiguousWrite("The provider response exceeded the bounded parser size.")
        if response.status in {401, 403}:
            raise WriteFailure("permission_denied", "The provider denied this operation.")
        if response.status in {409, 412}:
            raise WriteFailure("conflict", "The provider rejected a stale or conflicting change.")
        if not 200 <= response.status < 300:
            if response.status >= 500 or response.status in {408, 429}:
                raise AmbiguousWrite()
            raise WriteFailure("provider_rejected", f"The provider rejected the request (HTTP {response.status}).")
        if raw:
            return response
        if not response.content:
            return None
        try:
            value = json.loads(response.content)
            return value if private_response else sanitize(value, config)
        except (UnicodeError, ValueError):
            raise AmbiguousWrite("The provider returned an invalid JSON response.") from None

    def read(self, source, url, context, bounds, deadline):
        return self._call(source, context, NativeRequest("GET", url, "", {}, self.headers()), bounds, deadline)

    def headers(self):
        return {"X-Wistia-API-Version": "2026-09"} if self.family == "wistia" else {}

    def prepare(self, source, change, context, bounds, deadline):
        self.authorize(source, change, context)
        if not isinstance(change.key, str) or not change.key or len(change.key) > 200:
            raise ValueError("Each change requires a bounded nonempty key.")
        if change.operation not in {"create", "update", "upload"}:
            raise WriteFailure("unsupported_operation", "Only explicit create/update/upload operations are allowed.")
        files = self._files(change, bounds)
        if self.family == "legistar":
            native, identity_field, revision_field, read_url, lookup = self._legistar(source, change)
        elif self.family == "wistia":
            native, identity_field, revision_field, read_url, lookup = self._wistia(source, change, files)
        else:
            native, identity_field, revision_field, read_url, lookup = self._laserfiche(source, change, files)
        if "MatterAttachmentBinary" in native.body and len(base64.b64decode(
            native.body["MatterAttachmentBinary"])) > bounds.transfer_bytes:
            raise ValueError("The attachment exceeds the configured transfer byte limit.")
        before = None
        is_update = change.operation == "update"
        needs_before = is_update or change.entity == "document_pages"
        if needs_before:
            before = self.read_before(source, change, read_url, context, bounds, deadline)
            if not isinstance(before, dict):
                raise ValueError("The existing provider resource could not be read.")
        expected = change.expected_version
        supplied = before.get(revision_field) if before else None
        if expected is not None and expected != supplied:
            raise WriteFailure("conflict", "The supplied expected version differs from provider readback.")
        if self.family == "legistar" and is_update:
            schema = LEGISTAR[change.entity][0]
            # PUT's full native model must retain existing documented values.
            combined = {k: v for k, v in before.items() if k in schema}
            combined.update(native.body)
            for required in LEGISTAR[change.entity][3]:
                if combined.get(required) is None:
                    raise ValueError(f"{required} is required by the native update model.")
            native = NativeRequest(native.method, native.url, native.content_type, combined, native.headers)
        after = deepcopy(before or {})
        after.update(deepcopy(native.body))
        if change.entity == "caption_edits" and change.fields["expected_version"] != supplied:
            raise WriteFailure("conflict", "The caption expected_version differs from the active provider version.")
        return {
            "change": asdict(change), "native": native.public_dict(), "before": before, "after": after,
            "before_fingerprint": canonical_hash(before), "expected_version": supplied,
            "revision_field": revision_field, "identity_field": identity_field,
            "read_url": read_url, "reconcile": lookup,
            "conflict_semantics": "provider_version" if change.entity == "caption_edits"
            else "preflight_read_compare_not_atomic_upstream_cas",
        }

    def _files(self, change, bounds):
        files, size = [], 0
        for part in change.files:
            if not isinstance(part, dict) or set(part) != {"part", "filename", "content_type", "reference"}:
                raise ValueError("A prepared file requires part, filename, content_type and an immutable reference.")
            for key in ("part", "filename", "content_type"):
                if not isinstance(part[key], str) or re.search(r'[\r\n"\\/\x00]', part[key]):
                    # MIME types intentionally contain one slash.
                    if key != "content_type" or not re.fullmatch(r"[\w.+-]+/[\w.+-]+", part[key]):
                        raise ValueError("Unsafe multipart file metadata.")
            with self._open_file(part):
                pass
            length = part["reference"]["byte_length"]
            size += length
            if change.operation == "update" and not length:
                raise ValueError("An empty replacement file is not permitted.")
            if size > bounds.transfer_bytes:
                raise ValueError("The submitted files exceed the transfer byte limit.")
            files.append(deepcopy(part))
        return tuple(files)

    def _legistar(self, source, change):
        if change.entity not in LEGISTAR:
            raise WriteFailure("mapping_unverified", "This Legistar entity mapping is not verified.")
        schema, prefix, path, required = LEGISTAR[change.entity]
        if change.files:
            raise ValueError("Legistar JSON attachments use MatterAttachmentBinary, not multipart files.")
        fields = deepcopy(change.fields)
        validate_fields(fields, schema, required=required if change.operation != "update" else ())
        if "{parent}" in path:
            path = path.format(parent=safe_id(change.parent_id))
        root = f"https://webapi.legistar.com/v1/{_legistar_client(source)}/{path}"
        is_update = change.operation == "update"
        identity = prefix + "Id"
        if is_update:
            url = root + "/" + safe_id(change.resource_id)
            if identity in fields and str(fields[identity]) != str(change.resource_id):
                raise ValueError("The native body ID does not match the target resource.")
            fields[identity] = int(change.resource_id)
        else:
            if change.resource_id is not None or identity in fields:
                raise ValueError("A create cannot reuse an existing resource identifier.")
            url = root
            fields.setdefault(prefix + "Guid", str(uuid.uuid4()))
        if change.entity == "event_item":
            if "EventItemEventId" in fields and str(fields["EventItemEventId"]) != str(change.parent_id):
                raise ValueError("EventItemEventId does not match the parent Event.")
            fields.setdefault("EventItemEventId", int(change.parent_id))
        if change.entity in {"vote", "roll_call"}:
            parent_field = prefix + "EventItemId"
            if parent_field in fields and str(fields[parent_field]) != str(change.parent_id):
                raise ValueError(f"{parent_field} does not match the parent EventItem.")
            fields.setdefault(parent_field, int(change.parent_id))
        if change.entity == "matter_text":
            if str(fields.get("MatterTextMatterId", change.parent_id)) != str(change.parent_id):
                raise ValueError("MatterTextMatterId does not match the parent Matter.")
            fields.setdefault("MatterTextMatterId", int(change.parent_id))
        if change.entity == "matter_history":
            if "MatterHistoryEventId" in fields and str(fields["MatterHistoryEventId"]) != str(change.meeting_id):
                raise ValueError("MatterHistoryEventId must match the authorized meeting relationship.")
        lookup = {"url": root, "field": prefix + "Guid", "value": fields.get(prefix + "Guid"),
                  "id_field": identity} if not is_update else None
        return (NativeRequest("PUT" if is_update else "POST", url, "application/json", fields, {}),
                identity, prefix + "RowVersion", url if is_update else root, lookup)

    def _wistia(self, source, change, files):
        root = "https://api.wistia.com/modern"
        fields = deepcopy(change.fields)
        entity, op = change.entity, change.operation
        read_url, lookup, revision = None, None, "updated"
        if entity == "media" and op == "update":
            validate_fields(fields, _fields(strings="name new_still_media_id description", arrays="tags",
                                           objects="custom_metadata"))
            if "tags" in fields and any(not isinstance(i, str) for i in fields["tags"]):
                raise ValueError("Media tags must be strings.")
            url, method, content_type = root + "/medias/" + safe_id(change.resource_id), "PUT", "application/json"
            read_url = url
        elif entity == "media" and op in {"create", "upload"}:
            validate_fields(fields, _fields(strings="project_id name description url", integers="contact_id",
                                           booleans="low_priority"))
            if fields.get("name") and len(fields["name"]) > 255:
                raise ValueError("The upload name exceeds the documented 255-character limit.")
            if files:
                if len(files) != 1 or files[0]["part"] != "file" or "url" in fields or "low_priority" in fields:
                    raise ValueError("Wistia file upload requires exactly one file part and no URL/low_priority.")
                content_type = "multipart/form-data"
            else:
                if "url" not in fields:
                    raise ValueError("Media upload requires a file or a public URL.")
                _public_url(fields["url"])
                content_type = "application/x-www-form-urlencoded"
            url, method = "https://upload.wistia.com/", "POST"
        elif entity == "media_import" and op == "create":
            validate_fields(fields, _fields(strings="url folder_id"), required=("url",))
            _public_url(fields["url"])
            url, method, content_type = root + "/medias/import_url", "POST", "application/json"
        elif entity in {"caption", "caption_edits"}:
            media = safe_id(change.parent_id)
            url = root + "/medias/" + media + "/captions"
            language = change.language or fields.get("language")
            if change.language and "language" in fields and change.language != fields["language"]:
                raise ValueError("The approved caption language conflicts with the native body language.")
            if language and not re.fullmatch(r"[a-z]{3}" if entity == "caption" else r"[A-Za-z]{2,3}(?:-[A-Za-z]+)?",
                                              language):
                raise ValueError("Caption create/update language uses a three-letter ISO 639-2 code.")
            if entity == "caption":
                validate_fields(fields, _fields(strings="caption_file language"),
                                required=() if files else ("caption_file",))
                if op == "update":
                    if not language or "language" in fields:
                        raise ValueError("Caption update requires path language, not body language.")
                    url += "/" + language
                elif op != "create":
                    raise ValueError("Caption operation must be create or update.")
                elif language:
                    fields["language"] = language
                if files and (len(files) != 1 or files[0]["part"] != "caption_file" or "caption_file" in fields):
                    raise ValueError("Supply one caption_file text field or file, not both.")
                method, content_type = ("PUT" if op == "update" else "POST"), (
                    "multipart/form-data" if files else "application/json"
                )
                if language:
                    read_url = root + "/medias/" + media + "/captions/" + language
                    lookup = {"url": read_url, "caption": fields.get("caption_file")}
            else:
                if op != "update" or not language:
                    raise ValueError("Caption edits require update and a target language.")
                validate_fields(fields, _fields(integers="expected_version", arrays="edits"),
                                required=("expected_version", "edits"))
                if not 1 <= len(fields["edits"]) <= 20:
                    raise ValueError("Caption edit batches contain between 1 and 20 corrections.")
                for edit in fields["edits"]:
                    validate_fields(edit, _fields(strings="target_text replacement_text",
                                                 integers="start_ms end_ms"),
                                    required=("target_text", "replacement_text"))
                    if ("start_ms" in edit) != ("end_ms" in edit):
                        raise ValueError("Caption time window requires paired inclusive start_ms/end_ms.")
                    if "start_ms" in edit and edit["start_ms"] > edit["end_ms"]:
                        raise ValueError("Caption time window is reversed.")
                read_url = url + "/" + language
                url = read_url + "/edits"
                method, content_type, revision = "POST", "application/json", "version"
        elif entity == "media_tags" and op == "update":
            validate_fields(fields, _fields(arrays="hashed_ids tag_names"), required=("hashed_ids", "tag_names"))
            if any(not isinstance(i, str) for key in fields for i in fields[key]):
                raise ValueError("Tag target IDs and tag names must be strings.")
            if not fields["hashed_ids"] or not fields["tag_names"]:
                raise ValueError("A tag update requires explicit media IDs and tag names.")
            for identity in fields["hashed_ids"]:
                safe_id(identity)
            url, method, content_type = root + "/taggings/bulk_create", "POST", "application/json"
            # The batch is read back per explicit media ID, never against account-wide data.
            read_url = root + "/medias/" + safe_id(fields["hashed_ids"][0])
        else:
            raise WriteFailure("mapping_unverified", "This Wistia entity/operation has no verified mapping.")
        if files and content_type != "multipart/form-data":
            raise ValueError("This operation does not support file parts.")
        headers = self.headers() if url.startswith(root) else {}
        return (NativeRequest(method, url, content_type, fields, headers, files),
                "hashed_id", revision, read_url, lookup)

    def _laserfiche(self, source, change, files):
        root = f"https://api.laserfiche.com/repository/v2/Repositories/{safe_id(_laserfiche_repository(source))}/Entries/"
        fields = deepcopy(change.fields)
        entity, op = change.entity, change.operation
        schema = _fields(strings="name", booleans="autoRename importAsElectronicDocument generateImagePagesText",
                         objects="pdfOptions metadata")
        if entity in {"document", "document_large"}:
            validate_fields(fields, schema, required=("name",) if op != "update" else ())
            if op == "update":
                url, method = root + safe_id(change.resource_id) + "/Document", "PATCH"
                if not files and not fields.get("metadata"):
                    raise ValueError("A document update requires file, imageFiles, or metadata.")
            else:
                url, method = root + safe_id(change.parent_id) + "/Folder/Import", "POST"
            if any(p["part"] not in {"file", "imageFiles"} for p in files):
                raise ValueError("Document import/update supports file and imageFiles parts only.")
            if sum(p["part"] == "file" for p in files) > 1:
                raise ValueError("Only one electronic file part may be submitted.")
            images = [p for p in files if p["part"] == "imageFiles"]
            if len(images) > 10 or sum(p["reference"]["byte_length"] for p in images) > 100_000_000:
                raise ValueError("Laserfiche imageFiles permits at most 10 files and 100 MB aggregate.")
            if any(p["content_type"] not in {"image/tiff", "image/jpeg", "image/png"} for p in images):
                raise ValueError("Laserfiche imageFiles permits TIFF, JPG and PNG only.")
            electronic = [p for p in files if p["part"] == "file"]
            if (images and electronic and electronic[0]["content_type"].startswith("image/")
                    and not fields.get("importAsElectronicDocument", False)):
                raise ValueError("Image file conversion and explicit imageFiles cannot both create pages.")
            if entity == "document" and sum(p["reference"]["byte_length"] for p in files) > 100_000_000:
                raise ValueError("Use the documented large-document operation above the 100 MB simple limit.")
            if entity == "document_large" and (len(files) != 1 or files[0]["part"] != "file"):
                raise ValueError("Large-document submission requires one explicit electronic file.")
            metadata = fields.get("metadata", {})
            validate_fields(metadata, _fields(strings="templateName", arrays="fields tags links"))
            for item in metadata.get("fields", []):
                validate_fields(item, _fields(strings="name", arrays="values"), required=("name", "values"))
            if any(not isinstance(t, str) for t in metadata.get("tags", [])):
                raise ValueError("Metadata tags must be strings.")
            for link in metadata.get("links", []):
                validate_fields(link, _fields(integers="linkDefinitionId otherEntryId", booleans="isSource",
                                             objects="customProperties"),
                                required=("linkDefinitionId", "otherEntryId", "isSource"))
            validate_fields(fields.get("pdfOptions", {}), _fields(
                booleans="generatePages generateText keepPdfAfterImport", strings="generatePagesImageType"))
        elif entity in {"document_pages", "document_page"}:
            if entity == "document_pages":
                validate_fields(fields, _fields(arrays="textPages"))
                if not fields.get("textPages") and not files:
                    raise ValueError("An empty page replacement/delete is prohibited.")
                if any(not isinstance(t, str) for t in fields.get("textPages", [])):
                    raise ValueError("textPages must contain strings.")
                if any(p["part"] != "imageFiles" for p in files):
                    raise ValueError("Page creation/replacement uses imageFiles parts.")
                url = root + safe_id(change.resource_id) + "/Document/Pages"
                method = "PUT" if op == "update" else "POST"
            else:
                if op != "update" or type(change.page_number) is not int or change.page_number < 1:
                    raise ValueError("Single-page update requires a positive page_number.")
                validate_fields(fields, _fields(strings="text"))
                if not fields and not files:
                    raise ValueError("Supply page text or imageFile.")
                if any(p["part"] != "imageFile" for p in files) or len(files) > 1:
                    raise ValueError("Single-page update accepts one imageFile.")
                url = root + safe_id(change.resource_id) + "/Document/Pages/" + str(change.page_number)
                method = "PUT"
        else:
            raise WriteFailure("mapping_unverified", "This Laserfiche document operation has no verified mapping.")
        read_url = root + safe_id(change.resource_id) if op == "update" or entity == "document_pages" else None
        return (NativeRequest(method, url, "multipart/form-data", fields, {}, files),
                "id", "lastModifiedTime", read_url, None)

    def read_before(self, source, change, url, context, bounds, deadline):
        if change.entity == "media_tags":
            return {"media": [self.read(source, "https://api.wistia.com/modern/medias/" + safe_id(i),
                                        context, bounds, deadline) for i in change.fields["hashed_ids"]]}
        value = self.read(source, url, context, bounds, deadline)
        if self.family == "laserfiche":
            value = self.document_readback(source, value, change, context, bounds, deadline)
        return value

    def document_readback(self, source, entry, change, context, bounds, deadline):
        if not isinstance(entry, dict) or "id" not in entry:
            raise AmbiguousWrite("The repository readback did not identify a document entry.")
        entry = deepcopy(entry)
        root = (f"https://api.laserfiche.com/repository/v2/Repositories/{safe_id(_laserfiche_repository(source))}"
                f"/Entries/{safe_id(entry['id'])}")
        metadata = change.fields.get("metadata", {})
        for field, suffix in (("fields", "Fields"), ("tags", "Tags"), ("links", "Links")):
            if field in metadata:
                values = self.read(source, root + "/" + suffix, context, bounds, deadline)
                if not isinstance(values, dict) or "@odata.nextLink" in values:
                    raise AmbiguousWrite("Repository metadata readback is incomplete.")
                entry.setdefault("_metadata", {})[field] = values.get("value", [])
        if "templateName" in metadata:
            entry.setdefault("_metadata", {})["templateName"] = entry.get("templateName")
        if change.files and any(p["part"] == "file" for p in change.files):
            exported = self._call(
                source, context, NativeRequest("POST", root + "/Export", "application/json", {"part": "Edoc"}, {}),
                bounds, deadline, private_response=True,
            )
            if not isinstance(exported, dict) or not isinstance(exported.get("value"), str):
                raise AmbiguousWrite("The repository export did not supply an electronic-document readback.")
            content = self._signed_transfer(exported["value"], None, "GET", bounds, deadline, context=context).content
            entry["_file_sha256"] = hashlib.sha256(content).hexdigest()
        if change.entity == "document_page":
            page_url = root + "/Document/Pages/" + str(change.page_number)
            if "text" in change.fields:
                entry["_page_text"] = self.read(source, page_url + "/Text", context, bounds, deadline).get("text")
            if change.files:
                response = self._call(source, context, NativeRequest(
                    "GET", page_url + "/Image", "", {}, {"Accept": "application/octet-stream"}),
                    bounds, deadline, raw=True)
                entry["_page_image_sha256"] = hashlib.sha256(response.content).hexdigest()
        if change.entity == "document_pages":
            # Capture all supplied text pages on an existing document for exact conflict checks/readback.
            entry["_text_pages"] = []
            if entry.get("pageCount", 0) > bounds.max_records:
                raise ValueError("Page readback exceeds max_records; choose a more specific page update.")
            for number in range(1, entry.get("pageCount", 0) + 1):
                value = self.read(source, root + f"/Document/Pages/{number}/Text", context, bounds, deadline)
                entry["_text_pages"].append(value.get("text"))
        if any(p["part"] == "imageFiles" for p in change.files):
            page_count = entry.get("pageCount", 0)
            if page_count > bounds.max_records:
                raise ValueError("Image-page readback exceeds max_records.")
            entry["_image_pages_sha256"] = []
            for number in range(1, page_count + 1):
                response = self._call(source, context, NativeRequest(
                    "GET", root + f"/Document/Pages/{number}/Image", "", {},
                    {"Accept": "application/octet-stream"}), bounds, deadline, raw=True)
                entry["_image_pages_sha256"].append(hashlib.sha256(response.content).hexdigest())
        return entry

    def _signed_transfer(self, url, body, method, bounds, deadline, *, context=None):
        """Ephemeral provider-issued URLs never receive provider Authorization headers."""
        parsed = urlsplit(url)
        if context is not None and context.check_cancelled():
            raise WriteCancelled()
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise AmbiguousWrite("The provider issued an unsafe transfer URL.")
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise AmbiguousWrite("The transfer deadline expired.")
        try:
            response = self.transport.send(url, method=method, body=body, headers={},
                                           byte_limit=bounds.transfer_bytes,
                                           deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite("The provider transfer outcome could not be confirmed.") from None
        if (not isinstance(response, WriteResponse) or response.status != 200
                or len(response.content) > bounds.transfer_bytes):
            raise AmbiguousWrite("The provider transfer response could not be confirmed.")
        return response

    def document_matches(self, prepared, readback):
        change, fields = prepared["change"], prepared["native"]["body"]
        metadata = fields.get("metadata", {})
        actual = readback.get("_metadata", {})
        if "templateName" in metadata and actual.get("templateName") != metadata["templateName"]:
            return False
        if "fields" in metadata:
            by_name = {f.get("name"): f for f in actual.get("fields", [])}
            if any(by_name.get(f["name"], {}).get("values") != f["values"] for f in metadata["fields"]):
                return False
        if "tags" in metadata and not set(metadata["tags"]).issubset({
            t.get("name") for t in actual.get("tags", []) if isinstance(t, dict)
        }):
            return False
        if "links" in metadata:
            for link in metadata["links"]:
                if not any(
                    row.get("linkDefinitionId") == link["linkDefinitionId"]
                    and row.get("targetId" if link["isSource"] else "sourceId") == link["otherEntryId"]
                    and row.get("customProperties", {}) == link.get("customProperties", {})
                    for row in actual.get("links", [])
                ):
                    return False
        for file in prepared["native"]["files"]:
            digest = file["reference"]["sha256"]
            if file["part"] == "file" and readback.get("_file_sha256") != digest:
                return False
            if file["part"] == "imageFile" and readback.get("_page_image_sha256") != digest:
                return False
            if file["part"] == "imageFiles":
                submitted = [p["reference"]["sha256"]
                             for p in prepared["native"]["files"] if p["part"] == "imageFiles"]
                if readback.get("_image_pages_sha256", [])[-len(submitted):] != submitted:
                    return False
        if change["entity"] == "document_page":
            return "text" not in fields or fields["text"] == readback.get("_page_text")
        if change["entity"] == "document_pages":
            expected = fields.get("textPages", [])
            if change["operation"] != "update":
                expected = (prepared["before"] or {}).get("_text_pages", []) + expected
            return expected == readback.get("_text_pages")
        return "name" not in fields or fields.get("autoRename") is True or fields["name"] == readback.get("name")

    def large_document(self, source, prepared, context, bounds, deadline, *, persist=None):
        native = NativeRequest(**prepared["native"])
        file = native.files[0]
        data = self._open_file(file)
        chunk_size = 8 * 1024 * 1024
        count = max(1, (file["reference"]["byte_length"] + chunk_size - 1) // chunk_size)
        root = f"https://api.laserfiche.com/repository/v2/Repositories/{safe_id(_laserfiche_repository(source))}"
        upload_id, etags = None, []
        # The official guide obtains signed URLs in batches; URLs remain memory-only.
        for offset in range(0, count, 5):
            request = {"startingPartNumber": offset + 1, "numberOfParts": min(5, count - offset)}
            if upload_id is None:
                request.update(fileName=file["filename"], mimeType=file["content_type"])
            else:
                request["uploadId"] = upload_id
            result = self._call(source, context, NativeRequest(
                "POST", root + "/Entries/CreateMultipartUploadUrls", "application/json", request, {}),
                bounds, deadline, private_response=True)
            upload_id = result.get("uploadId")
            urls = result.get("urls", [])
            if not upload_id or len(urls) != request["numberOfParts"]:
                raise AmbiguousWrite("The repository did not return the requested upload parts.")
            if persist:
                if persist({"upload_id": upload_id, "part_etags": list(etags), "parts_total": count}):
                    raise WriteCancelled()
            for index, url in enumerate(urls, offset):
                response = self._signed_transfer(url, data.read(chunk_size), "PUT", bounds, deadline, context=context)
                etag = response.headers.get("etag") or response.headers.get("ETag")
                if not etag:
                    raise AmbiguousWrite("The repository upload part did not return an ETag.")
                etags.append(etag)
                if persist:
                    if persist({"upload_id": upload_id, "part_etags": list(etags), "parts_total": count}):
                        raise WriteCancelled()
        data.close()
        fields = {**native.body, "uploadId": upload_id, "partETags": etags}
        change = prepared["change"]
        path = ("/Entries/" + safe_id(change["resource_id"]) + "/Document/UpdateUploadedParts"
                if change["operation"] == "update" else
                "/Entries/" + safe_id(change["parent_id"]) + "/Folder/ImportUploadedParts")
        result = self._call(source, context, NativeRequest("POST", root + path, "application/json", fields, {}),
                            bounds, deadline)
        task_id = result.get("taskId") if isinstance(result, dict) else None
        if not task_id:
            raise AmbiguousWrite("The repository did not return its asynchronous task reference.")
        return {"state": "pending", "task_id": task_id, "upload_id": upload_id, "part_etags": etags,
                "resource_id": change.get("resource_id")}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        if prepared["before"] is not None:
            now = self.read_before(source, change, prepared["read_url"], context, bounds, deadline)
            if canonical_hash(now) != prepared["before_fingerprint"]:
                raise WriteFailure("conflict", "Provider state changed after this exact plan was prepared.")
        native = NativeRequest(**prepared["native"])
        if change.entity == "document_large":
            return self.large_document(source, prepared, context, bounds, deadline, persist=persist)
        response = self._call(source, context, native, bounds, deadline)
        if change.entity in {"media_import", "media_tags"}:
            # Queued does not mean complete. Persist the job reference for receipt polling.
            if not isinstance(response, dict) or not isinstance(response.get("background_job_status"), dict):
                raise AmbiguousWrite("The provider did not return its documented background job reference.")
            return {"state": "pending", "provider_response": response, "resource_id": None,
                    "job": response["background_job_status"]}
        identity = (response or {}).get(prepared["identity_field"]) if isinstance(response, dict) else None
        if identity is None:
            identity = change.resource_id
        if self.family == "wistia" and change.entity in {"caption", "caption_edits"}:
            identity = f"{change.parent_id}:{change.language or change.fields.get('language') or 'detected'}"
            read_url = prepared["read_url"]
        elif identity is not None:
            if self.family == "legistar":
                read_url = native.url if change.operation == "update" else native.url + "/" + safe_id(identity)
            elif self.family == "wistia":
                read_url = "https://api.wistia.com/modern/medias/" + safe_id(identity)
            else:
                read_url = (f"https://api.laserfiche.com/repository/v2/Repositories/"
                            f"{safe_id(_laserfiche_repository(source))}/Entries/{safe_id(identity)}")
        else:
            raise AmbiguousWrite("The provider response did not establish the remote resource identity.")
        if read_url is None:
            return {"state": "uncertain", "resource_id": identity,
                    "reason": "No exact caption language readback is available; review required."}
        if persist:
            persist({"resource_id": identity, "read_url": read_url})
        try:
            readback = self.read(source, read_url, context, bounds, deadline)
            if self.family == "laserfiche":
                readback = self.document_readback(source, readback, change, context, bounds, deadline)
            if self.family == "legistar" and "MatterAttachmentBinary" in native.body:
                file_response = self._call(source, context, NativeRequest("GET", read_url + "/File", "", {},
                                                                         {"Accept": "application/octet-stream"}),
                                           bounds, deadline, raw=True)
                readback["MatterAttachmentBinary"] = base64.b64encode(file_response.content).decode()
        except (WriteFailure, ValueError, TypeError):
            return {"state": "uncertain", "resource_id": identity,
                    "reason": "The mutation returned success but exact readback could not complete."}
        if change.entity == "caption_edits" and isinstance(response, dict):
            readback["_edit_confirmation"] = response
        if not self.matches(prepared, readback):
            return {"state": "uncertain", "resource_id": identity, "readback": readback,
                    "reason": "The remote readback does not confirm every submitted field."}
        return {"state": "succeeded", "resource_id": identity, "readback": readback,
                "provider_revision": readback.get(prepared["revision_field"]) if isinstance(readback, dict) else None}

    def matches(self, prepared, readback):
        if not isinstance(readback, dict):
            return False
        change = prepared["change"]
        if change["entity"] == "caption_edits":
            confirmation = readback.get("_edit_confirmation", {})
            return (confirmation.get("applied") is True
                    and confirmation.get("version", {}).get("from") == change["fields"]["expected_version"]
                    and confirmation.get("version", {}).get("to") == readback.get("version"))
        if change["entity"] == "caption":
            expected = change["fields"].get("caption_file")
            if expected is None and prepared["native"]["files"]:
                expected = self._file_bytes(prepared["native"]["files"][0]).decode()
            return readback.get("text") == expected or readback.get("caption_file") == expected
        fields = prepared["native"]["body"]
        if self.family == "laserfiche":
            return self.document_matches(prepared, readback)
        if self.family == "wistia" and change["entity"] == "media" and change["operation"] != "update":
            fields = {k: v for k, v in fields.items() if k in {"name", "description"}}
        for key, value in fields.items():
            if key.endswith(("RowVersion", "LastModifiedUtc")):
                continue
            actual = readback.get(key)
            if key == "tags" and isinstance(actual, list):
                actual = [v.get("name") if isinstance(v, dict) else v for v in actual]
            if actual != value:
                return False
        return True

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        """Read only. Never resend a possibly accepted mutation."""
        lookup = prepared.get("reconcile")
        identity = item.get("resource_id")
        if item.get("task_id") and self.family == "laserfiche":
            root = f"https://api.laserfiche.com/repository/v2/Repositories/{safe_id(_laserfiche_repository(source))}"
            response = self.read(source, root + "/Tasks?" + urlencode({"taskIds": item["task_id"]}),
                                 context, bounds, deadline)
            tasks = response.get("value", []) if isinstance(response, dict) else []
            if len(tasks) != 1 or tasks[0].get("id") != item["task_id"]:
                return {"state": "uncertain", "reason": "The exact repository task is unavailable."}
            task = tasks[0]
            if task.get("errors"):
                return {"state": "failed", "task": task, "reason": "The repository task reported errors."}
            if task.get("status") != "Completed":
                return {"state": "pending", "task": task}
            identity = task.get("result", {}).get("entryId")
            if identity is not None:
                result = self.read(source, root + "/Entries/" + safe_id(identity), context, bounds, deadline)
                change = WriteChange.from_dict(prepared["change"])
                result = self.document_readback(source, result, change, context, bounds, deadline)
                if self.matches(prepared, result):
                    return {"state": "succeeded", "resource_id": identity, "readback": result,
                            "provider_revision": result.get("lastModifiedTime"), "task": task}
            return {"state": "uncertain", "task": task, "reason": "Task completion needs exact document readback."}
        if item.get("job"):
            job = item["job"]
            job_id = job.get("hashed_id") or job.get("id")
            result = self.read(source, "https://api.wistia.com/modern/background_job_status/"
                               + safe_id(job_id), context, bounds, deadline)
            status = result.get("background_job_status", {})
            if status.get("status") == "failed":
                return {"state": "failed", "reason": "The provider background job failed.", "job": status}
            if status.get("status") == "finished" and prepared["change"]["entity"] == "media_tags":
                readback = self.read_before(source, WriteChange.from_dict(prepared["change"]), None,
                                            context, bounds, deadline)
                names = set(prepared["change"]["fields"]["tag_names"])
                if all(names.issubset({t["name"] if isinstance(t, dict) else t for t in media.get("tags", [])})
                       for media in readback["media"]):
                    return {"state": "succeeded", "job": status, "readback": readback,
                            "resource_ids": prepared["change"]["fields"]["hashed_ids"]}
            if status.get("status") == "finished" and prepared["change"]["entity"] == "media_import":
                results = status.get("object", {}).get("results", [])
                created = [r for r in results if r.get("status") == "succeeded"
                           and r.get("operation") == "create" and r.get("resource_type") == "media" and r.get("id")]
                if len(created) == 1:
                    value = self.read(source, "https://api.wistia.com/modern/medias/" + safe_id(created[0]["id"]),
                                      context, bounds, deadline)
                    return {"state": "succeeded", "job": status, "resource_id": created[0]["id"], "readback": value}
            return {"state": "pending" if status.get("status") in {"queued", "started"} else "uncertain",
                    "job": status, "reason": "Job status retained; exact resource readback still required."}
        if self.family == "legistar" and lookup and lookup.get("value"):
            term = lookup["value"].replace("'", "''")
            url = lookup["url"] + "?" + urlencode({
                "$filter": f"{lookup['field']} eq '{term}'", "$top": 2,
            })
            result = self.read(source, url, context, bounds, deadline)
            if isinstance(result, list) and len(result) == 1 and self.matches(prepared, result[0]):
                return {"state": "succeeded", "resource_id": result[0][lookup["id_field"]],
                        "readback": result[0], "reconciled": True,
                        "provider_revision": result[0].get(prepared["revision_field"])}
        if identity is not None and item.get("read_url"):
            result = self.read(source, item["read_url"], context, bounds, deadline)
            if self.family == "laserfiche":
                result = self.document_readback(source, result, WriteChange.from_dict(prepared["change"]),
                                                context, bounds, deadline)
            if self.matches(prepared, result):
                return {"state": "succeeded", "resource_id": identity, "readback": result, "reconciled": True}
        if prepared["change"]["operation"] == "update" or (lookup and lookup.get("caption") is not None):
            result = self.read_before(source, WriteChange.from_dict(prepared["change"]), prepared["read_url"],
                                      context, bounds, deadline)
            if self.matches(prepared, result):
                return {"state": "succeeded", "resource_id": identity or prepared["change"].get("resource_id"),
                        "readback": result, "reconciled": True}
        return {"state": "uncertain", "resource_id": identity,
                "reason": "Readback cannot uniquely reconcile the original intent; do not repeat create."}


def default_adapters(transport=None):
    from .providers.essential_write import EssentialWriteAdapter
    return {**{name: WriteAdapter(name, transport)
               for name in ("legistar", "wistia", "laserfiche", "laserfiche-weblink")},
            "municode-meetings": EssentialWriteAdapter(transport)}
