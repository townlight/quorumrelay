"""Pinned legacy Boardable agenda sibling reorder, with exact tree readback."""

from copy import deepcopy
from dataclasses import asdict
import json
import re
from time import monotonic
from urllib.parse import urlsplit
from uuid import uuid4

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure, sanitize
from ..write_transport import WriteResponse


def _native_id(value):
    if type(value) is not int or not 0 < value < 10 ** 19:
        raise ValueError("A bounded positive native agenda ID is required.")
    return value


class BoardableWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__("boardable", transport)

    def credentials(self, source, context):
        config = context.credentials.get(self.provider)
        parsed = urlsplit(source.url)
        if (not isinstance(config, dict) or config.get("tenant") != context.tenant or not context.tenant
                or config.get("org_url") != source.url or config.get("legacy_agenda_editor") is not True
                or parsed.scheme != "https" or parsed.netloc != "app.boardable.com" or parsed.query or parsed.fragment
                or not re.fullmatch(r"/(?:[A-Za-z0-9_-]{1,128}/){1,5}", parsed.path)
                or not source.namespace or source.namespace not in config.get("allowed_namespaces", ())
                or (context.allowed_namespaces is not None and source.namespace not in context.allowed_namespaces)):
            raise WriteFailure("permission_denied", "An exact trusted legacy Boardable organization and tenant binding is required.")
        for key in ("session_cookie", "csrf_token"):
            value = config.get(key)
            if (not isinstance(value, str) or not value or len(value) > 16384
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                raise WriteFailure("credentials_required", "Trusted Boardable session and CSRF values are required.")
        if not re.fullmatch(r"[A-Za-z0-9_-]+=[^;,\s]+(?:; [A-Za-z0-9_-]+=[^;,\s]+)*", config["session_cookie"]):
            raise WriteFailure("credentials_required", "The supplied Boardable session cookie is not a safe header.")
        return config

    def validate_source(self, source, context):
        if source.provider != self.provider or source.options:
            raise ValueError("Only the explicit legacy Boardable organization source without options is supported.")
        self.credentials(source, context)

    def authorize(self, source, change, context):
        self.validate_source(source, context)
        config = self.credentials(source, context)
        creating = change.entity == 'item' and change.operation == 'create'
        if (change.entity not in {"agenda_order", "item"} or (change.operation != "update" and not creating) or change.files
                or (not creating and change.parent_id is not None)
                or (creating and (change.resource_id is not None or type(change.parent_id) is not int
                                  or not 0 <= change.parent_id < 10 ** 19
                                  or change.language is not None or change.page_number is not None))
                or (change.entity == "agenda_order" and change.resource_id != change.meeting_id)
                or not isinstance(change.meeting_id, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", change.meeting_id)):
            raise WriteFailure("mapping_unverified", "Only legacy sibling reorder, text edits and explicitly parented item creation are mapped.")
        if change.entity == "item" and not creating:
            config = self.credentials(source, context)
            if "onedrive_access_token" not in config or config["onedrive_access_token"] is not None:
                raise WriteFailure("mapping_unverified", "Item edits require an explicit null OneDrive runtime token; cloud imports are not mapped.")
        meeting = change.meeting_id
        expected = source.url + "meetings/" + meeting
        urls = config.get("meeting_urls")
        if (f"{change.entity}:{change.operation}" not in config.get("permissions", ()) or meeting not in config.get("meeting_ids", ())
                or not isinstance(urls, dict) or urls.get(meeting) != expected):
            raise WriteFailure("permission_denied", "The native meeting URL or reorder permission is outside current policy.")

    def _request(self, source, change, context, bounds, deadline, *, agenda=None, item_id=None, item_fields=None,
                 create_fields=None):
        self.authorize(source, change, context)
        if context.check_cancelled():
            raise WriteCancelled()
        config = self.credentials(source, context)
        base = config["meeting_urls"][change.meeting_id] + "/agenda/"
        url = base + ("list?list_type=nested&version=edit" if agenda is None else "reorder")
        headers = {"Accept": "application/json", "Cookie": config["session_cookie"],
                   "X-Requested-With": "XMLHttpRequest"}
        if item_id is not None:
            url = source.url + "agenda/" + str(item_id)
        body = None
        if create_fields is not None:
            url = base.rstrip('/')
            headers.update({"Content-Type": "application/json", "X-CSRF-TOKEN": config["csrf_token"]})
            body = json.dumps(create_fields, separators=(',', ':')).encode('utf-8')
            if len(body) > min(bounds.parser_bytes, bounds.transfer_bytes):
                raise ValueError('The new item exceeds request byte bounds.')
        if agenda is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-TOKEN": config["csrf_token"]})
            body = json.dumps({"agenda": agenda}, separators=(",", ":")).encode("utf-8")
            if len(body) > min(bounds.parser_bytes, bounds.transfer_bytes):
                raise ValueError("The agenda reorder exceeds request byte bounds.")
        if item_fields is not None:
            url = base + "update"
            boundary = "quorumrelay" + uuid4().hex
            headers.update({"Content-Type": "multipart/form-data; boundary=" + boundary,
                            "X-CSRF-TOKEN": config["csrf_token"]})
            parts = []
            for key, value in item_fields:
                parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n'
                              + str(value) + "\r\n").encode("utf-8"))
            body = b"".join(parts) + f"--{boundary}--\r\n".encode()
            if len(body) > min(bounds.parser_bytes, bounds.transfer_bytes):
                raise ValueError("The item edit exceeds request byte bounds.")
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise WriteFailure("deadline_exceeded", "The Boardable operation deadline expired.")
        response_limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        try:
            response = self.transport.send(url, method="GET" if body is None else "POST", body=body,
                headers=headers, byte_limit=response_limit, deadline_seconds=seconds)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite() from None
        if not isinstance(response, WriteResponse) or len(response.content) > response_limit:
            raise AmbiguousWrite("Invalid or oversized Boardable response.")
        if response.status in {401, 403}:
            raise WriteFailure("permission_denied", "Boardable denied the operation.")
        if response.status in {409, 412}:
            raise WriteFailure("conflict", "Boardable rejected a conflicting change.")
        if not 200 <= response.status < 300:
            raise AmbiguousWrite("Boardable did not return a confirmed success response.")
        if body is not None and create_fields is None:
            return None
        if create_fields is None and context.check_cancelled():
            raise WriteCancelled()
        if create_fields is None and monotonic() >= deadline:
            raise WriteFailure("deadline_exceeded", "The Boardable read exceeded its operation deadline.")
        try:
            value = json.loads(response.content)
        except (ValueError, UnicodeError):
            raise ValueError("The edit-list readback is not JSON.") from None
        if sanitize(value, config) != value:
            raise ValueError("Credential-bearing Boardable readback cannot be saved.")
        if create_fields is not None:
            if (not isinstance(value, dict) or type(value.get('parent_agenda_id')) is not int
                    or value['parent_agenda_id'] != change.parent_id or value.get('text') != change.fields['text']):
                raise AmbiguousWrite('The created item response does not confirm the requested fields.')
            try:
                _native_id(value.get('id'))
            except ValueError:
                raise AmbiguousWrite('The created item response lacks its native identity.') from None
        elif item_id is not None:
            if (not isinstance(value, dict) or not isinstance(value.get("agenda_item"), dict)
                    or value["agenda_item"].get("id") != item_id):
                raise ValueError("The native item readback has the wrong identity or shape.")
        else:
            self._flatten(value, bounds)
        return value

    @staticmethod
    def _flatten(tree, bounds):
        flat, seen = [], set()

        def walk(rows, parent=0, depth=0):
            if not isinstance(rows, list) or depth > min(64, bounds.max_records):
                raise ValueError("The native agenda is not a bounded nested list.")
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("The native agenda contains a non-object item.")
                identity = _native_id(row.get("id"))
                if identity in seen or len(seen) >= bounds.max_records:
                    raise ValueError("The agenda repeats an identity or exceeds record bounds.")
                seen.add(identity)
                if "parent_agenda_id" in row and (type(row["parent_agenda_id"]) is not int or row["parent_agenda_id"] != parent):
                    raise ValueError("The native parent field conflicts with the supplied tree.")
                flat.append({"id": identity, "parent_agenda_id": parent})
                if row.get("agenda") is not None:
                    walk(row["agenda"], identity, depth + 1)
        walk(tree)
        return flat

    def prepare(self, source, change, context, bounds, deadline):
        self.authorize(source, change, context)
        if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
            raise ValueError("A bounded change key is required.")
        if change.operation == 'create':
            if (not isinstance(change.fields, dict) or set(change.fields) != {'text'}
                    or not isinstance(change.fields['text'], str) or not change.fields['text'].strip()):
                raise ValueError('New legacy agenda items accept only nonempty text.')
            before = self._request(source, change, context, bounds, deadline)
            flat = self._flatten(before, bounds)
            if len(flat) >= bounds.max_records or (change.parent_id and change.parent_id not in {r['id'] for r in flat}):
                raise ValueError('The selected parent is absent or the agenda has reached record bounds.')
            if change.parent_id:
                pending = list(before)
                while pending:
                    row = pending.pop()
                    if row['id'] == change.parent_id and not isinstance(row.get('agenda'), list):
                        raise ValueError('The selected parent lacks the child array consumed by the legacy client.')
                    pending.extend(row.get('agenda') or [])
            fingerprint = canonical_hash(before)
            if change.expected_version is not None and change.expected_version != fingerprint:
                raise WriteFailure('conflict', 'The expected agenda differs from readback.')
            body = {'text': change.fields['text'], 'parent_id': change.parent_id, 'date': ''}
            if len(json.dumps(body).encode('utf-8')) > min(bounds.parser_bytes, bounds.transfer_bytes):
                raise ValueError('The new item exceeds request bounds.')
            return {'change': asdict(change), 'before': before, 'before_fingerprint': fingerprint,
                    'conflict_semantics': 'preflight_compare_not_atomic_upstream_cas',
                    'native': {'method': 'POST', 'url': source.url + 'meetings/' + change.meeting_id + '/agenda',
                               'headers': {}, 'body': body}}
        if change.entity == "item":
            return self._prepare_item(source, change, context, bounds, deadline)
        if not isinstance(change.fields, dict) or set(change.fields) != {"agenda_item_ids"}:
            raise ValueError("Supply only the complete desired native agenda_item_ids preorder.")
        order = change.fields["agenda_item_ids"]
        if not isinstance(order, list) or not 0 < len(order) <= bounds.max_records:
            raise ValueError("A nonempty bounded desired order is required.")
        order = [_native_id(i) for i in order]
        if len(order) != len(set(order)):
            raise ValueError("The desired order repeats an item.")
        before = self._request(source, change, context, bounds, deadline)
        flat = self._flatten(before, bounds)
        if set(order) != {r["id"] for r in flat}:
            raise ValueError("Reorder must preserve every existing native agenda item.")
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected agenda differs from readback.")
        after, ranks = deepcopy(before), {identity: n for n, identity in enumerate(order)}

        def sort(rows):
            rows.sort(key=lambda r: ranks[r["id"]])
            for row in rows:
                if row.get("agenda") is not None:
                    sort(row["agenda"])
        sort(after)
        native = self._flatten(after, bounds)
        if [r["id"] for r in native] != order:
            raise ValueError("Only sibling reorder is supported; parent relationships must stay unchanged.")
        return {"change": asdict(change), "before": before, "after": after,
                "before_fingerprint": fingerprint, "conflict_semantics": "preflight_compare_not_atomic_upstream_cas",
                "native": {"method": "POST", "url": source.url + "meetings/" + change.meeting_id + "/agenda/reorder",
                           "headers": {}, "body": {"agenda": native}}}

    def _item_snapshot(self, source, change, context, bounds, deadline):
        if not isinstance(change.resource_id, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", change.resource_id):
            raise ValueError("A positive native item ID is required.")
        identity = int(change.resource_id)
        tree = self._request(source, change, context, bounds, deadline)
        if identity not in {r["id"] for r in self._flatten(tree, bounds)}:
            raise WriteFailure("permission_denied", "The selected item is not in the authorized meeting edit-list.")
        detail = self._request(source, change, context, bounds, deadline, item_id=identity)
        return {"tree": tree, "detail": detail}

    def _prepare_item(self, source, change, context, bounds, deadline):
        if (not isinstance(change.fields, dict) or not change.fields
                or not set(change.fields) <= {"text", "description"}
                or any(not isinstance(v, str) for v in change.fields.values())
                or ("text" in change.fields and not change.fields["text"].strip())):
            raise ValueError("Supply text and/or description strings only; item text must be nonempty.")
        before = self._item_snapshot(source, change, context, bounds, deadline)
        item = before["detail"]["agenda_item"]
        if (not isinstance(item.get("text"), str) or not isinstance(item.get("description"), str)
                or type(item.get("is_private")) is not int or item["is_private"] not in {0, 1}
                or type(item.get("duration")) is not int or not 0 <= item["duration"] <= 100000
                or not isinstance(item.get("people_responsible"), list) or not isinstance(item.get("uploads"), list)):
            raise ValueError("The item lacks the complete editable field snapshot.")
        people = [_native_id(r.get("id")) if isinstance(r, dict) else _native_id(None)
                  for r in item["people_responsible"]]
        uploads = [_native_id(r.get("id")) if isinstance(r, dict) else _native_id(None) for r in item["uploads"]]
        if len(set(people)) != len(people) or len(set(uploads)) != len(uploads):
            raise ValueError("The item repeats a responsible person or attachment ID.")
        after = deepcopy(before)
        after["detail"]["agenda_item"].update(change.fields)

        def edit(rows):
            for row in rows:
                if row["id"] == int(change.resource_id):
                    for key, value in change.fields.items():
                        if key in row:
                            row[key] = value
                if row.get("agenda") is not None:
                    edit(row["agenda"])
        edit(after["tree"])
        fingerprint = canonical_hash(before)
        if change.expected_version is not None and change.expected_version != fingerprint:
            raise WriteFailure("conflict", "The expected item differs from readback.")
        desired = after["detail"]["agenda_item"]
        fields = [("id", item["id"]), *[(key, desired[key]) for key in ("text", "description", "is_private")],
                  ("original_token", "null"), ("duration", item["duration"])]
        fields += [("people_responsible[]", identity) for identity in people]
        for index, identity in enumerate(uploads):
            fields += [(f"attachments[{index}][type]", "attachment"), (f"attachments[{index}][attachment_id]", identity)]
        return {"change": asdict(change), "before": before, "after": after, "before_fingerprint": fingerprint,
                "conflict_semantics": "preflight_compare_not_atomic_upstream_cas",
                "native": {"method": "POST", "url": source.url + "meetings/" + change.meeting_id + "/agenda/update",
                           "headers": {}, "body": fields}}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared["change"])
        if change.operation == 'create':
            now = self._request(source, change, context, bounds, deadline)
            if canonical_hash(now) != prepared['before_fingerprint']:
                raise WriteFailure('conflict', 'The agenda changed after planning.')
            if persist and persist({'resource_id': None}):
                raise WriteCancelled()
            reply = self._request(source, change, context, bounds, deadline, create_fields=prepared['native']['body'])
            identity = str(reply['id'])
            cancelled = persist({'resource_id': identity}) if persist else context.check_cancelled()
            if cancelled or monotonic() >= deadline:
                raise AmbiguousWrite('Creation returned a native identity; readback remains unconfirmed.')
            try:
                return self.reconcile(source, prepared, {'resource_id': identity}, context, bounds, deadline)
            except (WriteCancelled, WriteFailure):
                raise AmbiguousWrite('Creation was sent before readback could be confirmed.') from None
        now = (self._item_snapshot(source, change, context, bounds, deadline) if change.entity == "item"
               else self._request(source, change, context, bounds, deadline))
        if canonical_hash(now) != prepared["before_fingerprint"]:
            raise WriteFailure("conflict", "The agenda changed after planning.")
        if persist and persist({"resource_id": change.resource_id}):
            raise WriteCancelled()
        if change.entity == "item":
            self._request(source, change, context, bounds, deadline, item_fields=prepared["native"]["body"])
        else:
            self._request(source, change, context, bounds, deadline, agenda=self._flatten(prepared["after"], bounds))
        try:
            return self.reconcile(source, prepared, {}, context, bounds, deadline)
        except (WriteCancelled, WriteFailure):
            raise AmbiguousWrite('The mutation was sent before readback could be confirmed.') from None

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared["change"])
        if change.operation == 'create':
            value = self._request(source, change, context, bounds, deadline)
            identity = item.get('resource_id')
            if not isinstance(identity, str) or not re.fullmatch(r'[1-9][0-9]{0,18}', identity):
                return {'state': 'uncertain', 'readback': value, 'reconciled': True,
                        'reason': 'Created native identity was not confirmed; no title matching or POST replay.'}
            before_ids = {r['id'] for r in self._flatten(prepared['before'], bounds)}
            remaining = deepcopy(value)
            selected = []

            def remove(rows, parent=0):
                for row in list(rows):
                    if row['id'] == int(identity):
                        selected.append((row, parent))
                        rows.remove(row)
                    elif row.get('agenda') is not None:
                        remove(row['agenda'], row['id'])
            remove(remaining)
            match = (int(identity) not in before_ids and len(selected) == 1
                     and selected[0][1] == change.parent_id
                     and selected[0][0].get('parent_agenda_id') == change.parent_id
                     and selected[0][0].get('text') == change.fields['text']
                     and not selected[0][0].get('agenda')
                     and canonical_hash(remaining) == prepared['before_fingerprint'])
            return {'state': 'succeeded' if match else 'uncertain', 'resource_id': identity,
                    'readback': value, 'reconciled': True}
        value = (self._item_snapshot(source, change, context, bounds, deadline) if change.entity == "item"
                 else self._request(source, change, context, bounds, deadline))
        return {"state": "succeeded" if canonical_hash(value) == canonical_hash(prepared["after"]) else "uncertain",
                "resource_id": change.resource_id, "readback": value, "reconciled": True}
