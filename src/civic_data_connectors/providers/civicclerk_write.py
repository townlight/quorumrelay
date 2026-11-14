"""Documented CivicClerk section create/update with exact scoped readback."""
from copy import deepcopy
from dataclasses import asdict
import json
from urllib.parse import urlsplit

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, NativeRequest, WriteAdapter, WriteCancelled, WriteChange, WriteFailure, sanitize
from .contracts import _origin
from .discovery import _api_source
from .identification import validate_source


def _id(value):
    if type(value) is int and 0 < value <= 2147483647:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal() and str(int(value)) == value:
        number = int(value)
        if 0 < number <= 2147483647:
            return number
    raise ValueError('A positive bounded native section or agenda ID is required.')


class CivicClerkWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__('civicplus-select', transport)

    def validate_source(self, source, context):
        if source.provider != self.provider or source.options or not context.tenant or urlsplit(source.url).scheme != 'https':
            raise ValueError('A CivicClerk write requires an exact source without options and a trusted tenant.')
        validate_source(source, context)
        config = self.credentials(source, context)
        if config.get('tenant') != context.tenant or config.get('origin') != _origin(_api_source(source)):
            raise WriteFailure('permission_denied', 'The credential tenant and API origin must match the source.')
        if not isinstance(config.get('token'), str):
            raise WriteFailure('credentials_required', 'A server-side CivicClerk token is required.')

    def authorize(self, source, change, context):
        self.validate_source(source, context)
        config = self.credentials(source, context)
        if change.entity != 'agenda_section' or change.operation not in {'create', 'update'} or change.files:
            raise WriteFailure('mapping_unverified', 'Only documented agenda section create/update is mapped.')
        parent = _id(change.parent_id)
        meeting = _id(change.meeting_id)
        if (f'agenda_section:{change.operation}' not in config.get('permissions', ())
                or str(parent) not in config.get('parent_ids', ())
                or str(meeting) not in config.get('meeting_ids', ())):
            raise WriteFailure('permission_denied', 'Section parent or meeting is outside trusted source policy.')
        if change.operation == 'update':
            resource = _id(change.resource_id)
            if str(resource) not in config.get('resource_ids', ()):
                raise WriteFailure('permission_denied', 'Section identity is outside trusted source policy.')
        elif change.resource_id is not None:
            raise ValueError('Create cannot select an existing section ID.')

    def _root(self, source):
        return _api_source(source).removesuffix('/Events') + '/Sections'

    def _verify_meeting_parent(self, source, change, parent, context, bounds, deadline):
        meeting = _id(change.meeting_id)
        value = self.read(source, _api_source(source) + '/' + str(meeting), context, bounds, deadline)
        if (not isinstance(value, dict) or type(value.get('id')) is not int or value['id'] != meeting
                or type(value.get('agendaId')) is not int or value['agendaId'] != parent):
            raise WriteFailure('conflict', 'The event does not identify the selected agenda parent.')

    def _read(self, source, identity, parent, context, bounds, deadline):
        value = self.read(source, self._root(source) + '/' + str(identity), context, bounds, deadline)
        if (not isinstance(value, dict) or type(value.get('id')) is not int or value['id'] != identity
                or type(value.get('agendaId')) is not int or value['agendaId'] != parent
                or not isinstance(value.get('sectionName'), str)
                or ('sectionText' in value and value['sectionText'] is not None
                    and not isinstance(value['sectionText'], str))):
            raise ValueError('Section readback does not match its selected identity and agenda parent.')
        return value

    def prepare(self, source, change, context, bounds, deadline):
        self.authorize(source, change, context)
        if not isinstance(change.key, str) or not change.key or len(change.key) > 200:
            raise ValueError('Each change requires a bounded key.')
        fields = change.fields
        if not isinstance(fields, dict) or not fields or set(fields) - {'sectionName', 'sectionText'}:
            raise ValueError('Use only documented sectionName and sectionText fields.')
        if ('sectionName' in fields and (not isinstance(fields['sectionName'], str) or not fields['sectionName'])):
            raise ValueError('sectionName must be a nonempty string.')
        if 'sectionText' in fields and fields['sectionText'] is not None and not isinstance(fields['sectionText'], str):
            raise ValueError('sectionText must be a string or null.')
        parent = _id(change.parent_id)
        self._verify_meeting_parent(source, change, parent, context, bounds, deadline)
        before, resource = None, None
        if change.operation == 'update':
            resource = _id(change.resource_id)
            before = self._read(source, resource, parent, context, bounds, deadline)
            if change.expected_version is not None and change.expected_version != canonical_hash(before):
                raise WriteFailure('conflict', 'The expected section hash differs from current readback.')
            if 'sectionText' not in before and 'sectionText' not in fields:
                raise ValueError('The omitted sectionText cannot be preserved without current readback.')
            body = {'sectionName': before['sectionName']}
            if 'sectionText' in before:
                body['sectionText'] = before['sectionText']
            body.update(deepcopy(fields))
            url = self._root(source) + '/' + str(resource)
        else:
            if not fields.get('sectionName') or change.expected_version is not None:
                raise ValueError('Create requires sectionName and no expected version.')
            body = {**deepcopy(fields), 'agendaId': parent}
            url = self._root(source)
        if len(json.dumps(body, ensure_ascii=False).encode()) > min(bounds.parser_bytes, bounds.transfer_bytes):
            raise ValueError('The section request exceeds its configured byte bounds.')
        native = NativeRequest('PUT' if before is not None else 'POST', url, 'application/json', body, {})
        return {'change': asdict(change), 'native': native.public_dict(), 'before': before,
                'before_fingerprint': canonical_hash(before), 'parent': parent, 'resource_id': resource,
                'expected_fields': {k: deepcopy(v) for k, v in body.items() if k != 'agendaId'},
                'conflict_semantics': 'preflight_read_compare_not_atomic_upstream_cas'}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        change = WriteChange.from_dict(prepared['change'])
        self.authorize(source, change, context)
        self._verify_meeting_parent(source, change, prepared['parent'], context, bounds, deadline)
        identity = prepared['resource_id']
        if identity is not None:
            before = self._read(source, identity, prepared['parent'], context, bounds, deadline)
            if canonical_hash(before) != prepared['before_fingerprint']:
                raise WriteFailure('conflict', 'Provider state changed after the exact plan was prepared.')
            if persist and persist({'resource_id': identity}):
                raise WriteCancelled()
        response = self._call(source, context, NativeRequest(**prepared['native']), bounds, deadline, raw=True)
        if change.operation == 'create':
            if response.status != 201 or len(response.content) > bounds.parser_bytes:
                raise AmbiguousWrite('Create did not return its documented identity response.')
            try:
                value = sanitize(json.loads(response.content), self.credentials(source, context))
                identity = _id(value['id'])
            except (ValueError, TypeError, KeyError):
                raise AmbiguousWrite('Create did not return a valid section ID.') from None
            if persist and persist({'resource_id': identity}):
                return {'state': 'uncertain', 'resource_id': identity,
                        'reason': 'Cancelled after create; exact readback remains required.'}
        elif response.status not in {200, 204}:
            raise AmbiguousWrite('Update did not return a documented success status.')
        return self.reconcile(source, prepared, {'resource_id': identity}, context, bounds, deadline)

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        change = WriteChange.from_dict(prepared['change'])
        self.authorize(source, change, context)
        identity = item.get('resource_id')
        if identity is None:
            return {'state': 'uncertain', 'reason': 'No section ID was returned; do not repeat create.'}
        try:
            identity = _id(identity)
            self._verify_meeting_parent(source, change, prepared['parent'], context, bounds, deadline)
            value = self._read(source, identity, prepared['parent'], context, bounds, deadline)
        except (WriteFailure, ValueError, TypeError):
            return {'state': 'uncertain', 'resource_id': identity, 'reason': 'Exact section readback was unavailable.'}
        if any(key not in value or value[key] != expected for key, expected in prepared['expected_fields'].items()):
            return {'state': 'uncertain', 'resource_id': identity, 'readback': value,
                    'reason': 'Section readback differs from the approved fields.'}
        return {'state': 'succeeded', 'resource_id': identity, 'readback': value, 'provider_revision': None}
