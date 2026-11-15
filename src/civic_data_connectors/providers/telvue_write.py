"""Pinned Connect client reorder, confirmed through documented v2 snapshots.

The application supplies its own authorized session and API credentials. This
adapter neither signs in nor obtains credentials, and never guesses upload URLs.
"""

from copy import deepcopy
from dataclasses import asdict
import json
from collections import Counter
import re
from time import monotonic
from urllib.parse import urlencode

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure, sanitize
from ..write_transport import WriteResponse

ORIGIN = "https://connect.telvue.com"


def _id(value):
    if type(value) is int and 0 < value < 10 ** 19:
        return value
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value):
        return int(value)
    raise ValueError("A bounded positive native playlist or item ID is required.")


class TelVueWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__("telvue", transport)

    def credentials(self, source, context):
        config = context.credentials.get(self.provider)
        if (not isinstance(config, dict) or not context.tenant or config.get("tenant") != context.tenant
                or config.get("origin") != ORIGIN or not source.namespace
                or source.namespace not in config.get("allowed_namespaces", ())
                or (context.allowed_namespaces is not None and source.namespace not in context.allowed_namespaces)):
            raise WriteFailure("permission_denied", "Trusted TelVue tenant, origin and namespace binding is required.")
        for key in ("session_cookie", "csrf_token", "access_key", "secret_passphrase"):
            value = config.get(key)
            if (not isinstance(value, str) or not value or len(value) > 16384
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                raise WriteFailure("credentials_required", "Trusted TelVue session, CSRF and v2 read credentials are required.")
        if not re.fullmatch(r"[A-Za-z0-9_-]+=[^;,\s]+(?:; [A-Za-z0-9_-]+=[^;,\s]+)*", config["session_cookie"]):
            raise WriteFailure("credentials_required", "The supplied TelVue session cookie is not a safe cookie header.")
        return config

    def validate_source(self, source, context):
        if source.provider != self.provider or source.url not in {ORIGIN, ORIGIN + "/"} or source.options:
            raise ValueError("TelVue writes require the exact HTTPS Connect origin without source options.")
        self.credentials(source, context)

    def authorize(self, source, change, context):
        self.validate_source(source, context)
        config = self.credentials(source, context)
        if (change.entity, change.operation) not in {("playlist_order", "update"), ("playlist_membership", "create")} or change.files or change.parent_id is not None:
            raise WriteFailure("mapping_unverified", "Only existing-playlist order updates and media membership additions are mapped.")
        playlist, meeting = str(_id(change.resource_id)), str(_id(change.meeting_id))
        if (f"{change.entity}:{change.operation}" not in config.get("permissions", ())
                or playlist not in config.get("playlist_ids", ()) or meeting not in config.get("meeting_ids", ())):
            raise WriteFailure("permission_denied", "Playlist order or application meeting relationship is outside policy.")
        if change.entity == "playlist_membership":
            ids = change.fields.get("medium_ids") if isinstance(change.fields, dict) else None
            if not isinstance(ids, list) or not all(str(_id(i)) in config.get("medium_ids", ()) for i in ids):
                raise WriteFailure("permission_denied", "Media IDs are outside current trusted application policy.")

    def _request(self, source, context, path, bounds, deadline, *, order=None, medium_ids=None):
        if context.check_cancelled():
            raise WriteCancelled()
        # No arbitrary URL, redirect, HTTP proxy or caller-supplied headers.
        if not re.fullmatch(r"/(?:api/v2/playlists/[1-9][0-9]{0,18}(?:/playlist_items)?\.json|playlists/[1-9][0-9]{0,18}/reorder|bulk/playlists/[1-9][0-9]{0,18}/playlist_items/create)", path):
            raise ValueError("The TelVue operation path is not mapped.")
        config = self.credentials(source, context)
        headers = {"Accept": "application/json"}
        body = None
        mutation = order is not None or medium_ids is not None
        if not mutation:
            headers.update({"CONNECT-ACCESS-KEY": config["access_key"],
                            "CONNECT-SECRET-PASSPHRASE": config["secret_passphrase"]})
        else:
            headers.update({"Cookie": config["session_cookie"], "X-CSRF-Token": config["csrf_token"],
                            "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded"})
            key, values = ("playlist_item[]", order) if order is not None else ("medium_ids[]", medium_ids)
            body = urlencode([(key, str(i)) for i in values]).encode("ascii")
            if len(body) > min(bounds.transfer_bytes, bounds.parser_bytes):
                raise ValueError("The reorder request exceeds configured byte bounds.")
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure("deadline_exceeded", "The TelVue request deadline expired.")
        response_limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        try:
            response = self.transport.send(ORIGIN + path, method="POST" if mutation else "GET",
                body=body, headers=headers, byte_limit=response_limit, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite() from None
        if not isinstance(response, WriteResponse) or len(response.content) > response_limit:
            raise AmbiguousWrite("TelVue returned an invalid or oversized response.")
        if response.status in {401, 403}:
            raise WriteFailure("permission_denied", "TelVue denied the operation.")
        if response.status in {409, 412}:
            raise WriteFailure("conflict", "TelVue rejected the change as conflicting.")
        if not 200 <= response.status < 300:
            raise AmbiguousWrite("TelVue did not return a confirmed success response.")
        if mutation:
            return None  # A successful POST alone does not confirm the order.
        if context.check_cancelled():
            raise WriteCancelled()
        if monotonic() >= deadline:
            raise WriteFailure("deadline_exceeded", "The TelVue read exceeded its operation deadline.")
        try:
            value = json.loads(response.content)
        except (ValueError, UnicodeError):
            raise ValueError("TelVue readback was not JSON.") from None
        if sanitize(value, config) != value:
            raise ValueError("Credential-bearing TelVue readback cannot be persisted.")
        return value

    def _read(self, source, playlist, context, bounds, deadline):
        root = f"/api/v2/playlists/{playlist}"
        metadata = self._request(source, context, root + ".json", bounds, deadline)
        detail = metadata.get("playlist") if isinstance(metadata, dict) else None
        if (not isinstance(detail, dict) or type(detail.get("id")) is not int or detail["id"] != playlist
                or type(detail.get("playables_count")) is not int or not 0 <= detail["playables_count"] <= bounds.max_records):
            raise ValueError("The exact playlist and bounded published playables_count are required.")
        value = self._request(source, context, root + "/playlist_items.json", bounds, deadline)
        rows = value.get("playlist_items") if isinstance(value, dict) else None
        if not isinstance(rows, list) or len(rows) != detail["playables_count"]:
            raise ValueError("The returned playlist items do not cover the declared playlist count.")
        seen, sequences = set(), set()
        for row in rows:
            if (not isinstance(row, dict) or type(row.get("id")) is not int
                    or type(row.get("playlist_id")) is not int or row["playlist_id"] != playlist
                    or type(row.get("sequence_number")) is not int):
                raise ValueError("Playlist readback requires native item, parent and sequence fields.")
            identity = _id(row["id"])
            if identity in seen or row["sequence_number"] in sequences:
                raise ValueError("Playlist identities and sequence positions must be unique.")
            seen.add(identity)
            sequences.add(row["sequence_number"])
        if sequences != set(range(1, len(rows) + 1)):
            raise ValueError("Playlist sequence positions do not cover the declared order.")
        # API array ordering is not assumed; use the explicitly supplied sequence.
        return {"playlist_id": playlist, "playlist_items": sorted(deepcopy(rows), key=lambda r: r["sequence_number"])}

    def prepare(self, source, change, context, bounds, deadline):
        self.authorize(source, change, context)
        if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
            raise ValueError("A bounded change key is required.")
        if change.entity == "playlist_membership":
            return self._prepare_membership(source, change, context, bounds, deadline)
        fields = change.fields
        if not isinstance(fields, dict) or set(fields) != {"playlist_item_ids"}:
            raise ValueError("Supply only the exact desired playlist_item_ids order.")
        order = fields["playlist_item_ids"]
        if not isinstance(order, list) or not 0 < len(order) <= bounds.max_records:
            raise ValueError("The desired order must be a nonempty bounded list.")
        order = [_id(i) for i in order]
        if len(order) != len(set(order)):
            raise ValueError("The desired playlist order repeats an item.")
        playlist = _id(change.resource_id)
        before = self._read(source, playlist, context, bounds, deadline)
        if set(order) != {r["id"] for r in before["playlist_items"]}:
            raise ValueError("Reordering must preserve every supplied playlist item; no additions or removals.")
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected playlist snapshot differs from readback.")
        after = deepcopy(before)
        for row in after["playlist_items"]:
            row["sequence_number"] = order.index(row["id"]) + 1
        after["playlist_items"].sort(key=lambda r: r["sequence_number"])
        return {"change": asdict(change), "native": {"method": "POST", "url": ORIGIN + f"/playlists/{playlist}/reorder",
                "content_type": "application/x-www-form-urlencoded", "body": {"playlist_item[]": order}, "headers": {}},
                "before": before, "after": after, "before_fingerprint": fingerprint,
                "conflict_semantics": "preflight_snapshot_compare_not_atomic_upstream_cas",
                "meeting_relationship": "application_policy_only_not_vendor_meeting_association"}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        playlist = _id(change.resource_id)
        now = self._read(source, playlist, context, bounds, deadline)
        if canonical_hash(now) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "The playlist changed after the exact plan was prepared.")
        if persist and persist({"resource_id": str(playlist)}):
            raise WriteCancelled()
        if change.entity == "playlist_membership":
            self._request(source, context, f"/bulk/playlists/{playlist}/playlist_items/create",
                          bounds, deadline, medium_ids=prepared["after"]["medium_ids"])
        else:
            order = [r["id"] for r in prepared["after"]["playlist_items"]]
            self._request(source, context, f"/playlists/{playlist}/reorder", bounds, deadline, order=order)
        return self.reconcile(source, prepared, {}, context, bounds, deadline)

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        self.authorize(source, change, context)
        value = self._read(source, _id(change.resource_id), context, bounds, deadline)
        confirmed = (self._membership_matches(prepared, value) if change.entity == "playlist_membership"
                     else canonical_hash(value) == canonical_hash(prepared["after"]))
        return {"state": "succeeded" if confirmed else "uncertain",
                "resource_id": str(change.resource_id), "readback": value, "reconciled": True}


    def _prepare_membership(self, source, change, context, bounds, deadline):
        if not isinstance(change.fields, dict) or set(change.fields) != {"medium_ids"}:
            raise ValueError("Supply only the existing medium_ids to add to this playlist.")
        ids = change.fields["medium_ids"]
        if not isinstance(ids, list) or not 0 < len(ids) <= bounds.max_records:
            raise ValueError("A nonempty bounded list of native media IDs is required.")
        ids = [_id(i) for i in ids]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate requested media IDs are not supported.")
        config = self.credentials(source, context)
        if not all(str(i) in config.get("medium_ids", ()) for i in ids):
            raise WriteFailure("permission_denied", "Media IDs are outside trusted application policy.")
        playlist = _id(change.resource_id)
        before = self._read(source, playlist, context, bounds, deadline)
        existing = [row.get("playable") for row in before["playlist_items"]]
        if (any(not isinstance(p, dict) or p.get("type") != "media" or type(p.get("id")) is not int for p in existing)
                or any(p["id"] in ids for p in existing)):
            raise ValueError("Membership additions require an unambiguous media-only snapshot with no requested media already present.")
        if len(existing) + len(ids) > bounds.max_records:
            raise ValueError("The resulting playlist would exceed record bounds.")
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected playlist snapshot differs from readback.")
        return {"change": asdict(change), "before": before,
                "after": {"playlist_id": playlist, "medium_ids": ids}, "before_fingerprint": fingerprint,
                "native": {"method": "POST", "url": ORIGIN + f"/bulk/playlists/{playlist}/playlist_items/create",
                           "content_type": "application/x-www-form-urlencoded", "body": {"medium_ids[]": ids}, "headers": {}},
                "conflict_semantics": "preflight_snapshot_compare_not_atomic_upstream_cas",
                "meeting_relationship": "application_policy_only_not_vendor_meeting_association"}

    @staticmethod
    def _membership_matches(prepared, value):
        old = {r["id"]: r for r in prepared["before"]["playlist_items"]}
        current = {r["id"]: r for r in value["playlist_items"]}
        if not old.keys() <= current.keys():
            return False
        # The native call does not promise insertion order. Preserve all existing
        # fields apart from explicit sequence, and verify every new native item.
        def without_sequence(r):
            return {k: v for k, v in r.items() if k != "sequence_number"}
        if any(canonical_hash(without_sequence(current[i])) != canonical_hash(without_sequence(r)) for i, r in old.items()):
            return False
        added = [r for i, r in current.items() if i not in old]
        media = [r.get("playable") for r in added]
        if any(not isinstance(p, dict) or p.get("type") != "media" or type(p.get("id")) is not int for p in media):
            return False
        return Counter(p["id"] for p in media) == Counter(prepared["after"]["medium_ids"])
