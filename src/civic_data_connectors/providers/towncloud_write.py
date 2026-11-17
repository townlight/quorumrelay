"""Existing TownCloud item draft text only, from the pinned public client."""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import re
from time import monotonic
from urllib.parse import urlencode, urlsplit

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure, sanitize
from ..write_transport import WriteResponse


def _id(value):
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value)


class TownCloudWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__("towncloud", transport)

    def credentials(self, source, context):
        config = context.credentials.get(self.provider)
        url = urlsplit(source.url)
        if (not isinstance(config, dict) or not context.tenant or config.get("tenant") != context.tenant
                or config.get("site_url") != source.url or url.scheme != "https" or url.netloc != "towncloud.io"
                or not re.fullmatch(r"/go/[A-Za-z0-9_-]{1,128}", url.path) or url.query or url.fragment
                or source.namespace != "//towncloud.io" + url.path
                or source.namespace not in config.get("allowed_namespaces", ())
                or (context.allowed_namespaces is not None and source.namespace not in context.allowed_namespaces)):
            raise WriteFailure("permission_denied", "An exact trusted TownCloud tenant, site and namespace binding is required.")
        for key in ("session_cookie", "csrf_token"):
            value = config.get(key)
            if (not isinstance(value, str) or not value or len(value) > 16384
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                raise WriteFailure("credentials_required", "Trusted TownCloud session and CSRF values are required.")
        if not re.fullmatch(r"[A-Za-z0-9_-]+=[^;,\s]+(?:; [A-Za-z0-9_-]+=[^;,\s]+)*", config["session_cookie"]):
            raise WriteFailure("credentials_required", "The TownCloud session cookie is not a safe header.")
        return config

    def validate_source(self, source, context):
        if source.provider != self.provider or source.options:
            raise ValueError("Use an exact TownCloud site source without options.")
        self.credentials(source, context)

    def authorize(self, source, change, context):
        self.validate_source(source, context)
        config = self.credentials(source, context)
        if (change.entity != "item_draft" or change.operation != "update" or change.files
                or change.parent_id is not None or not _id(change.meeting_id) or not _id(change.resource_id)
                or not isinstance(change.fields, dict)
                or set(change.fields) != {"content_type", "field_name", "draft_content"}
                or change.fields["content_type"] not in {"Meetings::Item", "Meetings::SectionHeader"}
                or change.fields["field_name"] not in {"heading", "subheading", "text", "minutes"}
                or not isinstance(change.fields["draft_content"], str)):
            raise WriteFailure("mapping_unverified", "Only one existing item/section draft text field is mapped.")
        if change.fields["content_type"] == "Meetings::SectionHeader" and change.fields["field_name"] not in {"heading", "text"}:
            raise WriteFailure("mapping_unverified", "Only section heading and text drafts are declared by the client.")
        bindings = config.get("content_bindings", {})
        bound = bindings.get(change.meeting_id, {}) if isinstance(bindings, dict) else {}
        allowed = bound.get(change.fields["content_type"], ()) if isinstance(bound, dict) else ()
        if ("item_draft:update" not in config.get("permissions", ()) or change.resource_id not in allowed):
            raise WriteFailure("permission_denied", "The native agenda/content identity is outside current application policy.")

    def _request(self, source, change, context, bounds, deadline, *, body=None):
        self.authorize(source, change, context)
        if context.check_cancelled():
            raise WriteCancelled()
        config = self.credentials(source, context)
        url = source.url + "/drafts"
        headers = {"Accept": "application/json", "Cookie": config["session_cookie"],
                   "X-Requested-With": "XMLHttpRequest"}
        if body is None:
            url += "?" + urlencode({"agenda_id": change.meeting_id})
        else:
            headers.update({"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                            "X-CSRF-Token": config["csrf_token"]})
            body = urlencode(body).encode("utf-8")
            if len(body) > min(bounds.parser_bytes, bounds.transfer_bytes):
                raise ValueError("The draft text exceeds the configured request bounds.")
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise WriteFailure("deadline_exceeded", "The TownCloud operation deadline expired.")
        response_limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        try:
            response = self.transport.send(url, method="GET" if body is None else "POST", body=body,
                headers=headers, byte_limit=response_limit, deadline_seconds=seconds)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite() from None
        if not isinstance(response, WriteResponse) or len(response.content) > response_limit:
            raise AmbiguousWrite("Invalid or oversized TownCloud response.")
        if response.status in {401, 403}:
            raise WriteFailure("permission_denied", "TownCloud denied the operation.")
        if response.status in {409, 412}:
            raise WriteFailure("conflict", "TownCloud rejected a conflicting change.")
        if not 200 <= response.status < 300:
            raise AmbiguousWrite("TownCloud did not return confirmed success.")
        if body is not None:
            return None
        if context.check_cancelled():
            raise WriteCancelled()
        if monotonic() >= deadline:
            raise WriteFailure("deadline_exceeded", "The TownCloud draft read exceeded its deadline.")
        try:
            value = json.loads(response.content)
        except (ValueError, UnicodeError):
            raise ValueError("The draft readback is not JSON.") from None
        if sanitize(value, config) != value:
            raise ValueError("Credential-bearing TownCloud readback cannot be persisted.")
        if not isinstance(value, dict) or not isinstance(value.get("drafts"), list) or len(value["drafts"]) > bounds.max_records:
            raise ValueError("A bounded draft array is required; no paging or truncation is inferred.")
        seen = set()
        for row in value["drafts"]:
            if (not isinstance(row, dict) or not _id(str(row.get("content_id")))
                    or not isinstance(row.get("content_type"), str) or not isinstance(row.get("field_name"), str)
                    or not isinstance(row.get("draft_content"), str)):
                raise ValueError("A draft row lacks its declared content identity or text.")
            key = (row["content_type"], str(row["content_id"]), row["field_name"])
            if key in seen:
                raise ValueError("Draft readback contains ambiguous content/field identities.")
            seen.add(key)
        return value

    @staticmethod
    def _selected(snapshot, change):
        matches = [r for r in snapshot["drafts"] if r["content_type"] == change.fields["content_type"]
                   and str(r["content_id"]) == change.resource_id and r["field_name"] == change.fields["field_name"]]
        if len(matches) != 1 or matches[0].get("expired") is not False:
            raise ValueError("Select one existing, explicitly unexpired native item draft; new/expired drafts are not mapped.")
        return matches[0]

    def prepare(self, source, change, context, bounds, deadline):
        before = self._request(source, change, context, bounds, deadline)
        self._selected(before, change)
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected draft snapshot differs from readback.")
        after = deepcopy(before)
        self._selected(after, change)["draft_content"] = change.fields["draft_content"]
        data = {"draft[agenda_id]": change.meeting_id, "draft[content_type]": change.fields["content_type"],
                "draft[content_id]": change.resource_id, "draft[field_name]": change.fields["field_name"],
                "draft[draft_content]": change.fields["draft_content"],
                "client_timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")}
        if len(urlencode(data).encode()) > min(bounds.parser_bytes, bounds.transfer_bytes):
            raise ValueError("The draft text exceeds request bounds.")
        return {"change": asdict(change), "before": before, "after": after, "before_fingerprint": fingerprint,
                "conflict_semantics": "preflight_compare_not_atomic_upstream_cas",
                "native": {"method": "POST", "url": source.url + "/drafts", "headers": {}, "body": data}}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        current = self._request(source, change, context, bounds, deadline)
        if canonical_hash(current) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "The agenda drafts changed after planning.")
        if persist and persist({"resource_id": change.resource_id}):
            raise WriteCancelled()
        self._request(source, change, context, bounds, deadline, body=prepared["native"]["body"])
        return self.reconcile(source, prepared, {}, context, bounds, deadline)

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        readback = self._request(source, change, context, bounds, deadline)
        selected = self._selected(readback, change)
        comparable = deepcopy(readback)
        expected = deepcopy(prepared["after"])
        # The client explicitly displays updated_at; only the selected draft's
        # update timestamp is allowed to vary. All other fields remain exact.
        self._selected(comparable, change).pop("updated_at", None)
        self._selected(expected, change).pop("updated_at", None)
        matched = canonical_hash(comparable) == canonical_hash(expected)
        return {"state": "succeeded" if matched else "uncertain", "resource_id": change.resource_id,
                "readback": readback, "reconciled": True,
                "effective_state": "saved_unpublished_draft" if matched else "unconfirmed",
                "native_content_id": str(selected["content_id"])}
