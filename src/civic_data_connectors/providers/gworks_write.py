"""Pinned development FrontDesk saves through durable plan/commit/readback."""

from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime, timezone
import json
import re
from time import monotonic

from ..engine import canonical_hash
from ..models import Source
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure, sanitize
from ..write_transport import WriteResponse
from . import gworks_editor, gworks_media_write

ROOT = gworks_editor.ORIGIN + "/cms/secure/city/meeting/"
PREFIX = "cms_meeting."


def _id(value):
    if type(value) not in {int, str} or not re.fullmatch(r"[1-9][0-9]{0,18}", str(value)):
        raise ValueError("A positive native meeting ID is required.")
    return str(value)


def _instant(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00(?:Z|[+-]\d{2}:\d{2})", value):
        raise ValueError("Supply an ISO meeting time with an explicit offset and whole minutes.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not 2000 <= parsed.year <= 2050:
        raise ValueError("Meeting date is outside the editor's documented range.")
    return parsed


def _sections(value, before, maximum):
    if not isinstance(value, list) or not value or len(value) < len(before):
        raise ValueError("Supply all sections in order; existing sections cannot be removed.")
    result, count = deepcopy(before), 0
    for i, section in enumerate(value):
        if (not isinstance(section, dict) or set(section) != {"title", "items"}
                or not isinstance(section["title"], str) or not section["title"].strip()
                or not isinstance(section["items"], list)):
            raise ValueError("Sections require title and ordered items.")
        if i == len(result):
            result.append({"type": "section", "title": section["title"], "items": []})
        target = result[i]
        if (not isinstance(target, dict) or not isinstance(target.get("items"), list)
                or len(section["items"]) < len(target["items"])):
            raise ValueError("Existing items cannot be removed.")
        target["title"] = section["title"]
        for j, item in enumerate(section["items"]):
            if (not isinstance(item, dict) or set(item) != {"value", "minute"}
                    or any(not isinstance(v, str) for v in item.values())):
                raise ValueError("Items require agenda value and minute strings.")
            if j == len(target["items"]):
                target["items"].append({"type": "agenda-item", "value": "", "minute": "", "files": []})
            target["items"][j].update(item)
        count += 1 + len(target["items"])
        if count > maximum:
            raise ValueError("Sections and items exceed record bounds.")
    return result


def _comparable(value):
    result = deepcopy(value)
    result.pop(PREFIX + "mod_ts", None)
    # Equivalent explicit offsets represent the same meeting instant.
    key = PREFIX + "meeting_ts"
    if key in result:
        result[key] = _instant(result[key]).astimezone(timezone.utc).isoformat()
    key = PREFIX + "category_ref_type_id"
    if key in result:
        result[key] = str(result[key])
    return result


class GWorksWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__("gworks", transport)

    def credentials(self, source, context):
        config = context.credentials.get(self.provider)
        city = source.options.get("gworks_city_id")
        namespace = f"//api.dev.gworks.cloud/city/{city}/cms"
        if (source.provider != self.provider or source.url != ROOT
                or set(source.options) != {"gworks_city_id"} or source.body
                or source.input_format is not None or source.namespace != namespace
                or not isinstance(city, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", city)
                or not isinstance(config, dict) or not context.tenant
                or config.get("tenant") != context.tenant or config.get("city_id") != city
                or config.get("origin") != gworks_editor.ORIGIN
                or not isinstance(config.get("allowed_namespaces"), (list, tuple, set, frozenset))
                or namespace not in config["allowed_namespaces"]
                or (context.allowed_namespaces is not None and namespace not in context.allowed_namespaces)):
            raise WriteFailure("permission_denied", "Exact development-origin, tenant and city authorization is required.")
        token = config.get("token")
        if (not isinstance(token, str) or not token or len(token) > 16384
                or any(ord(c) <= 32 or ord(c) == 127 for c in token)):
            raise WriteFailure("credentials_required", "A safe trusted Bearer credential is required.")
        return config

    def validate_source(self, source, context):
        self.credentials(source, context)

    def authorize(self, source, change, context):
        config = self.credentials(source, context)
        if gworks_media_write.is_media_change(change):
            gworks_media_write.authorize(self, source, change, context)
            return
        if (change.entity != "meeting" or change.operation not in {"create", "update"} or change.files
                or any(v is not None for v in (change.parent_id, change.meeting_id, change.language, change.page_number))):
            raise WriteFailure("mapping_unverified", "Only meeting create/update with existing file preservation is mapped.")
        permissions = config.get("permissions")
        if not isinstance(permissions, (list, tuple, set, frozenset)) or "meeting:" + change.operation not in permissions:
            raise WriteFailure("permission_denied", "This meeting operation is outside current policy.")
        if change.operation == "create":
            if change.resource_id is not None or change.expected_version is not None:
                raise ValueError("Creation cannot select an existing resource or revision.")
        else:
            identity = _id(change.resource_id)
            ids = config.get("meeting_ids")
            if not isinstance(ids, (list, tuple, set, frozenset)) or identity not in ids:
                raise WriteFailure("permission_denied", "The selected meeting is outside current policy.")
        publication = change.fields.get("publication") if isinstance(change.fields, dict) else None
        if publication in {"agenda", "minutes"} and "meeting:publish_" + publication not in permissions:
            raise WriteFailure("permission_denied", "Publication requires its own current permission.")

    def _request(self, source, change, context, bounds, deadline, *, identity=None, body=None):
        self.authorize(source, change, context)
        if context.check_cancelled():
            raise WriteCancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure("deadline_exceeded", "The write deadline expired.")
        config = self.credentials(source, context)
        identity = _id(identity) if identity is not None else None
        url = ROOT + (identity or "")
        method = "GET" if body is None else "POST" if identity is None else "PUT"
        if body is None and identity is None:
            raise ValueError("Detail read requires an exact ID.")
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        encoded = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode() if body is not None else None
        if encoded is not None and len(encoded) > limit:
            raise ValueError("The native request exceeds byte bounds.")
        try:
            response = self.transport.send(url, method=method, body=encoded, headers={
                "Authorization": "Bearer " + config["token"], "Accept": "application/json",
                **({"Content-Type": "application/json"} if encoded is not None else {})},
                byte_limit=limit, deadline_seconds=remaining)
        except (OSError, RuntimeError, ValueError):
            raise AmbiguousWrite() from None
        if not isinstance(response, WriteResponse) or len(response.content) > limit:
            raise AmbiguousWrite("Invalid or oversized provider response.")
        if response.status in {401, 403}:
            raise WriteFailure("permission_denied", "The provider denied this operation.")
        if response.status in {409, 412}:
            raise WriteFailure("conflict", "The provider rejected a conflicting save.")
        if not 200 <= response.status < 300:
            raise AmbiguousWrite()
        try:
            value = json.loads(response.content)
            returned = _id(value.get(PREFIX + "id"))
            if identity is not None and returned != identity:
                raise ValueError("Wrong returned identity.")
            if sanitize(value, config) != value:
                raise ValueError("Credential-bearing response.")
            if body is None:
                detail = Source("gworks", url, namespace=source.namespace, input_format=gworks_editor.FORMAT,
                                options=source.options)
                gworks_editor.parse_bundle(detail, source.namespace, response.content)
        except (ValueError, TypeError, AttributeError):
            raise AmbiguousWrite("The response has no verified native meeting identity/shape.") from None
        if body is None:
            if context.check_cancelled():
                raise WriteCancelled()
            if monotonic() >= deadline:
                raise WriteFailure("deadline_exceeded", "Detail read exceeded the deadline.")
        # A successful save ID must reach durable storage even if cancellation
        # occurred during the send; apply checks cancellation after persisting it.
        return value

    def prepare(self, source, change, context, bounds, deadline):
        if gworks_media_write.is_media_change(change):
            return gworks_media_write.prepare(self, source, change, context, bounds, deadline)
        self.authorize(source, change, context)
        if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
            raise ValueError("A bounded change key is required.")
        fields = change.fields
        allowed = {"title", "location", "scheduled_start", "category_ref_type_id", "sections", "publication", "published_on"}
        if not isinstance(fields, dict) or not fields or set(fields) - allowed:
            raise ValueError("Unsupported meeting fields.")
        creating = change.operation == "create"
        required = {"title", "location", "scheduled_start", "category_ref_type_id", "sections", "publication"}
        if creating and not required <= set(fields):
            raise ValueError("Creation requires explicit meeting fields, sections and publication choice.")
        publication = fields.get("publication", "preserve")
        if publication not in ({"draft", "agenda"} if creating else {"preserve", "agenda", "minutes"}):
            raise ValueError("Select draft/agenda for create or preserve/agenda/minutes for update.")
        if ("published_on" in fields) != (publication in {"agenda", "minutes"}):
            raise ValueError("Explicit publication date is required only for publication.")
        if publication in {"agenda", "minutes"}:
            day = fields["published_on"]
            if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
                raise ValueError("Publication date must be an ISO local date.")
        before = None if creating else self._request(source, change, context, bounds, deadline, identity=change.resource_id)
        expected = {} if creating else deepcopy(before)
        if before is not None and change.expected_version is not None and change.expected_version != canonical_hash(before):
            raise WriteFailure("conflict", "The meeting differs from the expected snapshot.")
        for field in ("title", "location"):
            value = fields.get(field, expected.get(PREFIX + field))
            if not isinstance(value, str) or value != value.strip() or not 4 <= len(value) <= 256:
                raise ValueError("Title and location must be trimmed strings of 4 to 256 characters.")
            expected[PREFIX + field] = value
        category = fields.get("category_ref_type_id", expected.get(PREFIX + "category_ref_type_id"))
        _id(category)
        expected[PREFIX + "category_ref_type_id"] = category
        timestamp = fields.get("scheduled_start", expected.get(PREFIX + "meeting_ts"))
        instant = _instant(timestamp)
        expected[PREFIX + "meeting_ts"] = instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        previous_sections = [] if creating else before[PREFIX + "data"]
        projection = [{"title": s["title"], "items": [{"value": i["value"], "minute": i["minute"]}
                       for i in s["items"]]} for s in previous_sections]
        sections = _sections(fields.get("sections", projection), previous_sections, bounds.max_records)
        expected[PREFIX + "data"] = sections
        if creating:
            expected.update({PREFIX + "files": [], PREFIX + "template_fl": False,
                             PREFIX + "archived_fl": False, PREFIX + "agenda_published_fl": False,
                             PREFIX + "minutes_published_fl": False, PREFIX + "agenda_published_dt": None,
                             PREFIX + "minutes_published_dt": None})
        for field in ("template_fl", "archived_fl", "agenda_published_fl", "minutes_published_fl"):
            if type(expected.get(PREFIX + field)) is not bool:
                raise ValueError("The snapshot must include every template/archive/publication flag.")
        if publication == "agenda":
            expected.update({PREFIX + "archived_fl": False, PREFIX + "agenda_published_fl": True,
                             PREFIX + "agenda_published_dt": fields["published_on"]})
        elif publication == "minutes":
            if not expected[PREFIX + "agenda_published_fl"]:
                raise ValueError("Publish the agenda before publishing minutes, as the editor requires.")
            expected.update({PREFIX + "minutes_published_fl": True,
                             PREFIX + "minutes_published_dt": fields["published_on"]})
        body = {PREFIX + field: expected[PREFIX + field] for field in ("title", "location")}
        body.update({PREFIX + "category_ref_type_id": str(category),
                     PREFIX + "date": instant.date().isoformat(), PREFIX + "time": instant.strftime("%H:%M"),
                     PREFIX + "meeting_ts": expected[PREFIX + "meeting_ts"],
                     PREFIX + "data": json.dumps(sections, ensure_ascii=False, separators=(",", ":")),
                     PREFIX + "files": json.dumps(expected[PREFIX + "files"], ensure_ascii=False, separators=(",", ":")),
                     PREFIX + "section_count": len(sections)})
        if expected[PREFIX + "template_fl"]:
            body[PREFIX + "template_fl"] = "true"  # Checkbox has no boolean value-type.
        if creating:
            # Explicit false flags use the same boolean fields the editor's
            # archive action writes; no implicit publication defaults are relied on.
            for field in ("archived_fl", "agenda_published_fl", "minutes_published_fl",
                          "agenda_published_dt", "minutes_published_dt"):
                body[PREFIX + field] = expected[PREFIX + field]
        elif publication == "agenda":
            for field in ("archived_fl", "agenda_published_fl", "agenda_published_dt"):
                body[PREFIX + field] = expected[PREFIX + field]
        elif publication == "minutes":
            for field in ("minutes_published_fl", "minutes_published_dt"):
                body[PREFIX + field] = expected[PREFIX + field]
        if PREFIX + "section_count" in expected:
            expected[PREFIX + "section_count"] = len(sections)
        if len(json.dumps(body, ensure_ascii=False).encode()) > min(bounds.parser_bytes, bounds.transfer_bytes):
            raise ValueError("The native save exceeds request bounds.")
        return {"change": asdict(change), "before": before, "expected": expected,
                "before_fingerprint": canonical_hash(before) if before is not None else None,
                "conflict_semantics": "preflight_compare_not_atomic_upstream_cas",
                "effects": {"publication": publication, "existing_files_preserved": True,
                            "environment": "development"},
                "native": {"method": "POST" if creating else "PUT",
                           "url": ROOT + ("" if creating else _id(change.resource_id)),
                           "body": body, "headers": {}}}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        if gworks_media_write.is_media_change(change):
            return gworks_media_write.apply(self, source, prepared, context, bounds, deadline, persist=persist)
        if change.operation == "update":
            current = self._request(source, change, context, bounds, deadline, identity=change.resource_id)
            if canonical_hash(current) != prepared["before_fingerprint"]:
                raise WriteFailure("conflict", "The meeting changed after planning.")
        if persist and persist({"resource_id": change.resource_id}):
            raise WriteCancelled()
        reply = self._request(source, change, context, bounds, deadline, identity=change.resource_id,
                              body=prepared["native"]["body"])
        identity = _id(reply[PREFIX + "id"])
        cancelled = persist({"resource_id": identity}) if persist else context.check_cancelled()
        if cancelled or monotonic() >= deadline:
            raise AmbiguousWrite("Save returned an ID; readback remains unconfirmed.")
        try:
            return self.reconcile(source, prepared, {"resource_id": identity}, context, bounds, deadline)
        except (WriteFailure, ValueError):
            raise AmbiguousWrite("Save was sent before readback completed.") from None

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        if gworks_media_write.is_media_change(change):
            return gworks_media_write.reconcile(self, source, prepared, item, context, bounds, deadline)
        identity = item.get("resource_id") if change.operation == "create" else change.resource_id
        if identity is None:
            return {"state": "uncertain", "reason": "No confirmed new ID; no title matching or create replay.",
                    "reconciled": True}
        identity = _id(identity)
        value = self._request(source, change, context, bounds, deadline, identity=identity)
        expected, actual = _comparable(prepared["expected"]), _comparable(value)
        if change.operation == "create":
            match = all(key in actual and actual[key] == val for key, val in expected.items())
        else:
            match = actual == expected
        return {"state": "succeeded" if match else "uncertain", "resource_id": identity,
                "readback": value, "reconciled": True}

