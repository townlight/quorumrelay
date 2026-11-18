"""Production single-field saves from the captured production FrontDesk editor."""
from copy import deepcopy
from datetime import timezone
import json
import re
from time import monotonic
from urllib.parse import urlsplit

from ..write_adapters import AmbiguousWrite, WriteChange, WriteFailure, sanitize
from ..write_transport import WriteResponse
from .gworks_write import GWorksWriteAdapter as DevelopmentAdapter, PREFIX, _id, _comparable, _instant

ORIGIN = "https://api.gworks.cloud"
ROOT = ORIGIN + "/cms/secure/city/meeting/"


class ProductionTitleAdapter(DevelopmentAdapter):
    def credentials(self, source, context):
        config = context.credentials.get("gworks")
        city = source.options.get("gworks_city_id")
        namespace = f"//api.gworks.cloud/city/{city}/cms"
        if (source.provider != "gworks" or source.url != ROOT or source.body
                or source.input_format is not None or set(source.options) != {"gworks_city_id"}
                or not isinstance(city, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", city)
                or source.namespace != namespace or not isinstance(config, dict)
                or not context.tenant or config.get("tenant") != context.tenant
                or config.get("city_id") != city or config.get("origin") != ORIGIN
                or not isinstance(config.get("allowed_namespaces"), (list, tuple, set, frozenset))
                or namespace not in config["allowed_namespaces"]
                or (context.allowed_namespaces is not None and namespace not in context.allowed_namespaces)):
            raise WriteFailure("permission_denied", "Exact production-origin, tenant and city authorization is required.")
        token = config.get("token")
        if (not isinstance(token, str) or not token or len(token) > 16384
                or any(ord(c) <= 32 or ord(c) == 127 for c in token)):
            raise WriteFailure("credentials_required", "A safe trusted Bearer credential is required.")
        return config

    def authorize(self, source, change, context):
        config = self.credentials(source, context)
        if (change.entity != "meeting" or change.operation != "update" or change.files
                or any(v is not None for v in (change.parent_id, change.meeting_id,
                                               change.language, change.page_number))
                or not isinstance(change.fields, dict)
                or set(change.fields) not in ({"title"}, {"location"}, {"scheduled_start"})):
            raise WriteFailure("mapping_unverified", "Production supports only one existing draft meeting title, location or schedule update.")
        identity = _id(change.resource_id)
        ids, permissions = config.get("meeting_ids"), config.get("permissions")
        if (not isinstance(ids, (list, tuple, set, frozenset)) or list(ids) != [identity]
                or not isinstance(permissions, (list, tuple, set, frozenset))
                or "meeting:update" not in permissions):
            raise WriteFailure("permission_denied", "Authorize exactly the selected production meeting and update permission.")
        if "scheduled_start" in change.fields:
            timestamp = change.fields["scheduled_start"]
            instant = _instant(timestamp)
            # Reject unknown offsets and offsets Python could normalize silently.
            if (timestamp.endswith("-00:00")
                    or not re.search(r"(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$", timestamp)):
                raise ValueError("Supply a known, valid explicit meeting offset.")
            _instant(instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))

    @staticmethod
    def _validate(value, identity):
        if (not isinstance(value, dict) or _id(value.get(PREFIX + "id")) != identity
                or not isinstance(value.get(PREFIX + "title"), str)
                or not value[PREFIX + "title"].strip()
                or not isinstance(value.get(PREFIX + "data"), list)
                or not isinstance(value.get(PREFIX + "files"), list)):
            raise ValueError("A matching flattened meeting with native arrays is required.")
        for key in ("agenda_published_fl", "minutes_published_fl", "template_fl", "archived_fl"):
            if type(value.get(PREFIX + key)) is not bool:
                raise ValueError("All draft/template/archive flags must be explicit booleans.")
        for section in value[PREFIX + "data"]:
            if (not isinstance(section, dict) or not isinstance(section.get("title"), str)
                    or not isinstance(section.get("items"), list)):
                raise ValueError("Malformed section.")
            for item in section["items"]:
                if (not isinstance(item, dict) or not isinstance(item.get("value"), str)
                        or not isinstance(item.get("minute"), str)
                        or not isinstance(item.get("files"), list)):
                    raise ValueError("Malformed agenda item.")

    def _request(self, source, change, context, bounds, deadline, *, identity=None, body=None):
        from ..write_adapters import WriteCancelled
        self.authorize(source, change, context)
        if context.check_cancelled():
            raise WriteCancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure("deadline_exceeded", "The write deadline expired.")
        identity = _id(identity)
        config = self.credentials(source, context)
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        encoded = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False,
                                                       separators=(",", ":")).encode()
        if encoded is not None and len(encoded) > limit:
            raise ValueError("The native request exceeds byte bounds.")
        try:
            response = self.transport.send(ROOT + identity, method="GET" if body is None else "PUT",
                body=encoded, headers={"Authorization": "Bearer " + config["token"],
                    "Accept": "application/json", **({"Content-Type": "application/json"} if body is not None else {})},
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
            if _id(value.get(PREFIX + "id")) != identity or sanitize(value, config) != value:
                raise ValueError("Wrong or credential-bearing identity response.")
            if body is None:
                self._validate(value, identity)
        except (ValueError, TypeError, AttributeError):
            raise AmbiguousWrite("The production response has no verified identity/shape.") from None
        if body is None:
            if context.check_cancelled():
                raise WriteCancelled()
            if monotonic() >= deadline:
                raise WriteFailure("deadline_exceeded", "Detail read exceeded the deadline.")
        return value

    def prepare(self, source, change, context, bounds, deadline):
        # Reuse the identical captured form serialization, without production media/create/publication.
        prepared = super().prepare(source, change, context, bounds, deadline)
        before = prepared["before"]
        if (any(before[PREFIX + flag] for flag in ("agenda_published_fl", "minutes_published_fl",
                                                  "archived_fl", "template_fl"))
                or any(before.get(PREFIX + field) is not None for field in
                       ("agenda_published_dt", "minutes_published_dt"))):
            raise WriteFailure("permission_denied", "Production updates require an unambiguous unpublished active meeting.")
        # Full readback preservation uses the same explicit-offset/category equivalence as development.
        expected = deepcopy(before)
        field, value = next(iter(change.fields.items()))
        if field == "scheduled_start":
            # The shared serializer validates explicit-offset whole minutes and
            # projects local date/time to the editor's UTC native timestamp.
            expected[PREFIX + "meeting_ts"] = prepared["expected"][PREFIX + "meeting_ts"]
        else:
            expected[PREFIX + field] = value
        prepared["expected"] = expected
        prepared["native"]["url"] = ROOT + _id(change.resource_id)
        prepared["effects"] = {"environment": "production", "publication": "preserve",
                               "existing_files_preserved": True, "scope": "one_draft_meeting_" + field}
        return prepared

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        identity = _id(change.resource_id)
        value = self._request(source, change, context, bounds, deadline, identity=identity)
        actual, expected = _comparable(value), _comparable(prepared["expected"])
        return {"state": "succeeded" if actual == expected else "uncertain", "resource_id": identity,
                "readback": value, "reconciled": True}


class GWorksWriteAdapter(DevelopmentAdapter):
    """Select exact production routing; the original development adapter stays isolated."""
    def __init__(self, transport=None):
        super().__init__(transport)
        self.production = ProductionTitleAdapter(transport)

    def _selected(self, source):
        return self.production if urlsplit(source.url).netloc == "api.gworks.cloud" else super()

    def credentials(self, source, context):
        return self._selected(source).credentials(source, context)

    def validate_source(self, source, context):
        return self._selected(source).validate_source(source, context)

    def authorize(self, source, change, context):
        return self._selected(source).authorize(source, change, context)

    def prepare(self, source, change, context, bounds, deadline):
        return self._selected(source).prepare(source, change, context, bounds, deadline)

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        return self._selected(source).apply(source, prepared, context, bounds, deadline, persist=persist)

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        return self._selected(source).reconcile(source, prepared, item, context, bounds, deadline)
