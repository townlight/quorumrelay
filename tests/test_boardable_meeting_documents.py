'''Actual Engine/SQLite tests for Boardable native meeting-document uploads.'''

import base64
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import hashlib
import json
import os
from pathlib import Path
from time import monotonic
from urllib.parse import quote

import pytest

from quorumrelay import Engine, OperationContext
from quorumrelay.models import Bounds, Source
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import WriteCancelled, WriteFailure, default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from civic_data_connectors.providers.boardable_meeting_documents import BoardableMeetingDocumentsWriteAdapter
from civic_data_connectors.providers.boardable_write import BoardableWriteAdapter

ORG = 'https://app.boardable.com/quorumrelay-evaluation/'
NS = 'boardable:46098'
MEETING = '526577'
MEETING_URL = ORG + 'meetings/0e58cf-quorumrelay-contract-fixture-revised'
OLD_ID = 684953
NEW_ID = 684954
OLD_SLUG = 'b838c2db'
NEW_SLUG = 'c39cc980'
OWNER = 403839
ORGANIZATION = 46098
OLD_FILENAME = 'quorumrelay-document-center-evaluation.txt'
NEW_FILENAME = 'quorumrelay-meeting-attachment-api-fixture.txt'
PINNED_HASH = '785229e6354d8899d43e6c9bc083204360c51593717c738aca05c00dcc513ab5'


def _evidence_path(name):
    roots = []
    repo_root = os.environ.get('QUORUMRELAY_REPO_ROOT')
    if repo_root:
        roots.append(Path(repo_root))
    evidence_root = os.environ.get('BOARDABLE_MEETING_DOCUMENTS_EVIDENCE_ROOT')
    if evidence_root:
        roots.append(Path(evidence_root))
    here = Path(__file__).resolve().parent
    roots.extend([here, *here.parents])
    relative = Path('docs') / 'capabilities' / 'evidence' / 'boardable-meeting-documents' / name
    for root in roots:
        candidate = root / relative
        if candidate.is_file():
            return candidate
        direct = root / name
        if direct.is_file():
            return direct
    raise FileNotFoundError(name)


def pinned_payload():
    return _evidence_path('quorumrelay-meeting-attachment-api-fixture.txt').read_bytes()
ATTACHABLE = 'App' + chr(92) + 'Boardable' + chr(92) + 'Meetings' + chr(92) + 'Meeting'
UUIDABLE = 'App' + chr(92) + 'Boardable' + chr(92) + 'Attachments' + chr(92) + 'Attachment'
SOURCE = {'provider': 'boardable', 'url': ORG, 'namespace': NS}


def _meeting():
    return {
        'id': 526577, 'organization_id': 46098, 'owner_id': 403839,
        'title': 'QuorumRelay Contract Fixture Revised',
        'description': '<p>Synthetic integration fixture edited.</p>',
        'location': 'QuorumRelay integration evaluation',
        'start': '2026-11-17T03:00:00.000000Z', 'end': '2026-11-17T04:00:00.000000Z',
        'timezone': 'America/New_York',
        'datesTimezone': [{'date': '11/16/2026', 'from': '10:00 pm', 'to': '11:00 pm',
                           'id': 526577, 'timezone': 'America/New_York'}],
        'slug': '0e58cf-quorumrelay-contract-fixture-revised', 'url': MEETING_URL,
        'remote_option': 'no_remote', 'remote_url': None, 'remote_url_description': None,
        'disable_remote_rsvp': 0, 'minutes_type': 'free_form',
        'public_member_dashboard': 0, 'public_page': 0, 'published': False,
        'published_level': 0, 'published_at': None, 'minutes_published': 0,
        'materials_published_status': None, 'published_materials_status': None,
        'agenda_live_version': None, 'agenda_draft_version': 'native-draft-preserved',
        'agenda_last_published_at': None, 'enable_recording': 0, 'enable_transcription': 0,
        'enable_ai_summary': 0, 'series_id': 0, 'recurrence_id': None,
        'alternative_dates': None, 'additional_dates': [], 'video_conference_enabled': False,
        'starred_public_page': 0, 'notify': [403839], 'group_id': None, 'group': None,
        'members': [{'id': 403839, 'pivot': {'meeting_id': 526577, 'user_id': 403839,
                                            'rsvp': '', 'attendance': '', 'collaborator': 0,
                                            'is_voter': 1, 'token': 'secret-token'},
                     'email': 'secret@example.test', 'profile': {'email': 'secret@example.test'}}],
        'groups': [], 'guests': [], 'guest_members': [],
        'created_at': '2026-11-16T21:53:54.000000Z', 'updated_at': '2026-11-16T21:54:16.000000Z',
        'formattedMeetingTime': {'datetime': 'display only'}, 'timeUntilStart': 'display only',
        'meetingHasStarted': False, 'name': 'QuorumRelay Contract Fixture Revised',
        'blurb': 'display only', 'active_until': 'display only', 'videoLink': None,
    }


def _download(identity, filename):
    return ORG + 'attachments/uploads/download/' + str(identity) + '/' + quote(filename, safe='')


def _canonical(identity, filename, size, folder_id=0, order=0, owner=OWNER, org=ORGANIZATION,
               meeting=526577, attached_type='computer', document_id=0, pdf_status=None):
    pdf = None
    if pdf_status is not None:
        pdf = {'id': 3937287, 'status': pdf_status, 'isConverted': pdf_status == 'converted',
               'pdfable_id': identity, 'pdfable_type': UUIDABLE,
               'url': ORG + 'pdfs/3937287/' + filename + 'pdf',
               'thumbUrl': ORG + 'pdfs/3937287/' + filename + 'pdf/thumb'}
    return {
        'id': identity, 'attachable_id': meeting, 'attachable_type': ATTACHABLE,
        'organization_id': org, 'owner_id': owner, 'folder_id': folder_id,
        'attached_type': attached_type, 'document_id': document_id,
        'filename': filename, 'mime_type': 'text/plain', 'file_size': size,
        'downloadUrl': _download(identity, filename), 'url': _download(identity, filename),
        'file': str(identity) + '--fixture.txt', 'order': order,
        'created_at': '2026-11-16T23:55:32.000000Z', 'updated_at': '2026-11-16T23:55:32.000000Z',
        'pdf': pdf, 'iconUrl': ORG + 'icon.svg', 'bareIconUrl': '/img/icons/doc_center/bare-file.svg',
    }


def _list_row(identity, filename, size, slug, order=0, pdf_status=None):
    pdf = None
    if pdf_status is not None:
        pdf = {'id': 3937287, 'status': pdf_status, 'isConverted': pdf_status == 'converted',
               'pdfable_id': identity, 'pdfable_type': UUIDABLE}
    return {
        'id': identity, 'filename': filename, 'file_size': size,
        'downloadUrl': _download(identity, filename), 'url': _download(identity, filename),
        'uuid': {'uuid': 'fixture-uuid-' + str(identity), 'uuidable_id': identity,
                 'uuidable_type': UUIDABLE, 'short_slug': slug,
                 'created_at': '2026-11-16T23:55:32.000000Z',
                 'updated_at': '2026-11-16T23:55:32.000000Z',
                 'hex': 'fixturehex' + str(identity)},
        'order': order, 'pdf': pdf, 'created_at': '2026-11-16T23:55:32.000000Z',
        'updated_at': '2026-11-16T23:55:32.000000Z', 'iconUrl': ORG + 'icon.svg',
    }


def _detail_row(identity, filename, size, slug, pdf_status=None, owner=OWNER, org=ORGANIZATION,
                meeting=526577, folder_id=0, attached_type='computer', document_id=0):
    row = _canonical(identity, filename, size, folder_id=folder_id, owner=owner, org=org,
                     meeting=meeting, attached_type=attached_type, document_id=document_id,
                     pdf_status=pdf_status)
    row['uuid'] = {'uuid': 'fixture-uuid-' + str(identity), 'uuidable_id': identity,
                   'uuidable_type': UUIDABLE, 'short_slug': slug,
                   'created_at': '2026-11-16T23:55:32.000000Z',
                   'updated_at': '2026-11-16T23:55:32.000000Z',
                   'hex': 'fixturehex' + str(identity)}
    row['webUrl'] = _download(identity, filename)
    return row


class Vendor:
    mock = True

    def __init__(self):
        self.calls = []
        self.upload_count = 0
        self.faults = set()
        self.after_mutation = None
        self.old_filename = OLD_FILENAME
        self.payload = pinned_payload()
        self.payload_hash = hashlib.sha256(self.payload).hexdigest()
        self.old_bytes = (b'old' * 40)[:118]
        self.attachments = [self._canonical(OLD_ID, self.old_filename, len(self.old_bytes), 0, pdf_status='converted')]
        self.root = [self._list_row(OLD_ID, self.old_filename, len(self.old_bytes), OLD_SLUG, 0, 'converted')]
        self.folders = []
        self.details = {OLD_ID: _detail_row(OLD_ID, self.old_filename, len(self.old_bytes), OLD_SLUG, 'converted')}
        self.bytes = {OLD_ID: self.old_bytes, NEW_ID: self.payload}

    def _canonical(self, identity, filename, size, order, pdf_status=None):
        return _canonical(identity, filename, size, folder_id=0, order=order, pdf_status=pdf_status)

    def _list_row(self, identity, filename, size, slug, order, pdf_status=None):
        return _list_row(identity, filename, size, slug, order, pdf_status)

    def _add(self, filename, data, identity):
        slug = OLD_SLUG if identity == OLD_ID else NEW_SLUG
        self.attachments.append(_canonical(identity, filename, len(data), 0, 1, pdf_status=None))
        self.root.append(_list_row(identity, filename, len(data), slug, 1, None))
        self.details[identity] = _detail_row(identity, filename, len(data), slug, None)
        self.bytes[identity] = data

    def _parse(self, body, content_type):
        message = BytesParser(policy=default).parsebytes(
            ('Content-Type: ' + content_type + chr(13) + chr(10) + chr(13) + chr(10)).encode() + body
        )
        fields = {}
        files = []
        for part in message.iter_parts():
            name = part.get_param('name', header='Content-Disposition')
            filename = part.get_filename()
            payload = part.get_payload(decode=True)
            if filename is not None:
                files.append({'name': name, 'filename': filename,
                              'content_type': part.get_content_type(), 'data': payload})
            else:
                fields[name] = payload.decode('utf-8')
        return fields, files

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert deadline_seconds > 0
        assert 'Authorization' not in headers
        self.calls.append((method, url, body, headers))
        if method == 'GET' and url == MEETING_URL + '?format=json':
            meeting = _meeting()
            if 'meeting_unknown_after' in self.faults and self.upload_count:
                meeting['new_business_field'] = 'changed-after-upload'
            if 'extra_member' in self.faults:
                meeting['members'].append({'id': 999, 'pivot': {'meeting_id': 526577, 'user_id': 999}})
            if 'group' in self.faults:
                meeting['groups'].append({'id': 7, 'name': 'Group'})
            if 'guest' in self.faults:
                meeting['guests'].append({'id': 8})
            if 'series' in self.faults:
                meeting['series_id'] = 1
            if 'public' in self.faults:
                meeting['public_page'] = 1
            resource = {'id': 526577, 'url': MEETING_URL, 'owner_id': OWNER,
                        'can': {'edit': True, 'view': True}, 'attachments': deepcopy(self.attachments),
                        'published_level': 0}
            return WriteResponse(200, json.dumps({'meeting': meeting, 'meeting_resource': resource}).encode())
        if method == 'POST' and url == ORG + 'attachment-list':
            request = json.loads(body)
            assert request == {'attachable_id': 526577, 'attachable_type': 'meeting', 'folder': 'root'}
            items = deepcopy(self.root)
            if 'list_missing_new' in self.faults and self.upload_count:
                items = [row for row in items if row['id'] != NEW_ID]
            if 'list_duplicate_new' in self.faults and any(row['id'] == NEW_ID for row in items):
                items.append(deepcopy(next(row for row in items if row['id'] == NEW_ID)))
            envelope = {'items': items, 'folders': deepcopy(self.folders), 'current_folder': None,
                        'breadcrumbs': [{'label': 'All files', 'slug': ''}]}
            if 'root_deep' in self.faults:
                deep = {}
                for _ in range(80):
                    deep = {'x': deep}
                envelope['deep'] = deep
            if 'root_missing_current' in self.faults:
                envelope.pop('current_folder')
            if 'root_current_folder' in self.faults:
                envelope['current_folder'] = {'id': 1, 'name': 'Nested'}
            return WriteResponse(200, json.dumps(envelope).encode())
        if method == 'POST' and url == ORG + 'attachments/upload':
            fields, files = self._parse(body, headers['Content-Type'])
            self.upload_count += 1
            assert set(fields) == {'attachments[0][type]', 'attachable_type', 'attachable_id', 'folder_id', 'original_token'}
            assert fields['attachments[0][type]'] == 'upload'
            assert fields['attachable_type'] == 'meeting'
            assert fields['attachable_id'] == MEETING
            assert fields['folder_id'] == '0'
            assert fields['original_token'] == 'undefined'
            assert len(files) == 1 and files[0]['name'] == 'attachments[0][file]'
            assert files[0]['filename'] == NEW_FILENAME
            assert files[0]['content_type'] == 'text/plain'
            assert files[0]['data'] == self.payload
            if 'timeout_before' in self.faults:
                raise TimeoutError()
            if 'no_mutation' in self.faults:
                return WriteResponse(200, b'')
            self._add(NEW_FILENAME, self.payload, NEW_ID)
            if 'double_mutation' in self.faults:
                self._add(NEW_FILENAME, self.payload, NEW_ID + 1)
            if self.after_mutation:
                self.after_mutation()
            if 'timeout_after' in self.faults:
                raise TimeoutError()
            if 'remote_500_after' in self.faults:
                return WriteResponse(500, b'')
            return WriteResponse(200, b'')
        if method == 'GET' and url.startswith(ORG + 'documents/'):
            slug = url[len(ORG + 'documents/'):].split('/')[0]
            rows = [row for row in self.details.values() if row.get('uuid', {}).get('short_slug') == slug]
            if not rows:
                return WriteResponse(404)
            detail = deepcopy(rows[0])
            if 'detail_500' in self.faults:
                return WriteResponse(500)
            if 'detail_404' in self.faults:
                return WriteResponse(404)
            if 'detail_org' in self.faults:
                detail['organization_id'] = 999
            if 'detail_owner' in self.faults:
                detail['owner_id'] = 999
            if 'detail_meeting' in self.faults:
                detail['attachable_id'] = 999
            if 'detail_uuid' in self.faults:
                detail['uuid']['short_slug'] = 'badsafe'
            if 'detail_download_evil' in self.faults:
                detail['downloadUrl'] = 'https://evil.example/attachments/uploads/download/' + str(detail['id']) + '/' + detail['filename']
            if 'detail_download_path' in self.faults:
                detail['downloadUrl'] = ORG + 'attachments/uploads/download/999/' + detail['filename']
            return WriteResponse(200, json.dumps(detail).encode())
        if method == 'GET' and url.startswith(ORG + 'attachments/uploads/download/'):
            tail = url[len(ORG + 'attachments/uploads/download/'):]
            identity = int(tail.split('/', 1)[0])
            if 'download_500' in self.faults:
                return WriteResponse(500)
            if 'download_404' in self.faults:
                return WriteResponse(404)
            if 'download_redirect' in self.faults:
                return WriteResponse(302, b'', headers={'Location': 'https://evil.example/'})
            data = self.bytes.get(identity, b'')
            if 'download_corrupt' in self.faults:
                data = b'corrupt'
            return WriteResponse(200, data)
        raise AssertionError((method, url))


def setup(tmp_path):
    vendor = Vendor()
    context = OperationContext(
        principal='editor', client_id='fixture', tenant='city',
        authorization=frozenset({'write:plan', 'write:commit'}),
        allowed_namespaces=frozenset({NS}),
        credentials={'boardable': {
            'current_meeting_form': True, 'current_meeting_documents': True,
            'tenant': 'city', 'org_url': ORG, 'organization_id': ORGANIZATION,
            'allowed_namespaces': [NS], 'session_cookie': 'boardable_session=secret-session',
            'xsrf_token': 'secret-csrf', 'owner_id': OWNER,
            'permissions': ['meeting_document:upload'],
            'meeting_ids': [MEETING], 'meeting_urls': {MEETING: MEETING_URL},
        }},
    )
    engine = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(engine, default_adapters(vendor))
    return engine, context, vendor


def file_part(data=None, filename=NEW_FILENAME, content_type='text/plain'):
    if data is None:
        data = pinned_payload()
    return {'part': 'file', 'filename': filename, 'content_type': content_type,
            'content_base64': base64.b64encode(data).decode()}


def change(**overrides):
    value = {'key': 'doc', 'entity': 'meeting_document', 'operation': 'upload',
             'meeting_id': MEETING, 'fields': {}, 'files': [file_part()]}
    value.update(overrides)
    return value


def plan(engine, context, body=None, **overrides):
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [body or change(**overrides)]}, context=context)
    assert result.status == 'completed', result.public_dict()
    return {key: result.data[key] for key in ('plan_id', 'plan_hash')}


def test_captured_native_replay_uses_actual_evidence_and_pinned_bytes(tmp_path):
    before = json.loads(_evidence_path('boardable-meeting-document-before.json').read_text(encoding='utf-8'))
    after = json.loads(_evidence_path('boardable-meeting-document-after.json').read_text(encoding='utf-8'))
    second = json.loads(_evidence_path('boardable-meeting-document-second-upload.json').read_text(encoding='utf-8'))
    payload = pinned_payload()
    assert len(payload) == 141
    assert hashlib.sha256(payload).hexdigest() == PINNED_HASH
    detail = after['attachment']['body']
    assert detail['id'] == NEW_ID
    assert detail['uuid']['uuidable_id'] == NEW_ID
    assert detail['uuid']['uuidable_type'] == UUIDABLE
    upload_request = next(row for row in second if row['request']['url'].endswith('/attachments/upload'))
    assert upload_request['response']['status'] == 200
    assert upload_request['response']['body'] == ''

    class CapturedVendor:
        mock = True

        def __init__(self):
            self.upload_count = 0
            self.uploaded = False
            self.calls = []

        def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
            self.calls.append((method, url, body, headers))
            assert deadline_seconds > 0
            assert 'Authorization' not in headers
            if method == 'GET' and url == MEETING_URL + '?format=json':
                source = after if self.uploaded else before
                return WriteResponse(200, json.dumps(source['meeting']['body']).encode())
            if method == 'POST' and url == ORG + 'attachment-list':
                assert json.loads(body) == {'attachable_id': 526577, 'attachable_type': 'meeting', 'folder': 'root'}
                source = after if self.uploaded else before
                return WriteResponse(200, json.dumps(source['list']['body']).encode())
            if method == 'POST' and url == ORG + 'attachments/upload':
                message = BytesParser(policy=default).parsebytes(
                    ('Content-Type: ' + headers['Content-Type'] + chr(13) + chr(10) + chr(13) + chr(10)).encode() + body
                )
                fields = {}
                files = []
                for part in message.iter_parts():
                    name = part.get_param('name', header='Content-Disposition')
                    filename = part.get_filename()
                    data = part.get_payload(decode=True)
                    if filename is not None:
                        files.append((name, filename, part.get_content_type(), data))
                    else:
                        fields[name] = data.decode('utf-8')
                assert fields == {
                    'attachments[0][type]': 'upload',
                    'attachable_type': 'meeting',
                    'attachable_id': '526577',
                    'folder_id': '0',
                    'original_token': 'undefined',
                }
                assert files == [('attachments[0][file]', NEW_FILENAME, 'text/plain', payload)]
                self.upload_count += 1
                self.uploaded = True
                return WriteResponse(200, b'')
            if method == 'GET' and url == ORG + 'documents/' + NEW_SLUG + '/data':
                return WriteResponse(200, json.dumps(detail).encode())
            if method == 'GET' and url == detail['downloadUrl']:
                return WriteResponse(200, payload)
            raise AssertionError((method, url))

    vendor = CapturedVendor()
    context = OperationContext(
        principal='editor', client_id='fixture', tenant='city',
        authorization=frozenset({'write:plan', 'write:commit'}),
        allowed_namespaces=frozenset({NS}),
        credentials={'boardable': {
            'current_meeting_form': True, 'current_meeting_documents': True,
            'tenant': 'city', 'org_url': ORG, 'organization_id': ORGANIZATION,
            'allowed_namespaces': [NS], 'session_cookie': 'boardable_session=secret-session',
            'xsrf_token': 'secret-csrf', 'owner_id': OWNER,
            'permissions': ['meeting_document:upload'],
            'meeting_ids': [MEETING], 'meeting_urls': {MEETING: MEETING_URL},
        }},
    )
    engine = Engine(storage=SQLiteStorage(tmp_path / 'captured.sqlite'))
    register(engine, default_adapters(vendor))
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'completed', result.public_dict()
    item = result.data['items'][0]
    assert item['state'] == 'succeeded'
    assert item['resource_id'] == '684954'
    assert item['receipt']['original'] == {'sha256': PINNED_HASH, 'size': 141}
    assert item['receipt']['association']['attachable_id'] == 526577
    assert vendor.upload_count == 1
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'captured.sqlite'))
    register(reopened, default_adapters(vendor))
    again = reopened.execute('commit_write', approval, context=context)
    assert again.status == 'completed', again.public_dict()
    assert vendor.upload_count == 1


def test_upload_exact_request_success_receipt_and_restart_no_replay(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    assert vendor.upload_count == 0
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'completed', result.public_dict()
    item = result.data['items'][0]
    assert item['state'] == 'succeeded'
    assert item['resource_id'] == str(NEW_ID)
    assert item['receipt']['original']['sha256'] == vendor.payload_hash
    assert item['receipt']['original']['size'] == 141
    assert item['receipt']['association']['attachable_id'] == 526577
    assert item['receipt']['association']['organization_id'] == ORGANIZATION
    assert item['receipt']['association']['owner_id'] == OWNER
    assert vendor.upload_count == 1
    assert 'secret-session' not in json.dumps(result.public_dict())
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(vendor))
    again = reopened.execute('commit_write', approval, context=context)
    assert again.status == 'completed', again.public_dict()
    assert vendor.upload_count == 1


def test_existing_duplicate_filename_does_not_skip_new_upload(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.old_filename = NEW_FILENAME
    vendor.attachments = [vendor._canonical(OLD_ID, NEW_FILENAME, len(vendor.old_bytes), 0, pdf_status='converted')]
    vendor.root = [vendor._list_row(OLD_ID, NEW_FILENAME, len(vendor.old_bytes), OLD_SLUG, 0, 'converted')]
    vendor.details[OLD_ID] = _detail_row(OLD_ID, NEW_FILENAME, len(vendor.old_bytes), OLD_SLUG, 'converted')
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'completed', result.public_dict()
    assert result.data['items'][0]['resource_id'] == str(NEW_ID)
    assert vendor.upload_count == 1


def test_old_record_or_meeting_change_conflicts_before_upload(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    vendor.root[0]['order'] = 99
    result = engine.execute('commit_write', approval, context=context)
    assert result.data['items'][0]['state'] == 'conflict'
    assert vendor.upload_count == 0


def test_expected_version_mismatch_fails_before_upload(tmp_path):
    engine, context, vendor = setup(tmp_path)
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change(expected_version='wrong')]}, context=context)
    assert result.status == 'failed'
    assert vendor.upload_count == 0


@pytest.mark.parametrize('fault', ['no_mutation', 'double_mutation'])
def test_zero_or_multiple_new_ids_after_upload_stays_uncertain(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add(fault)
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    assert result.data['items'][0]['state'] == 'uncertain'
    assert vendor.upload_count == 1
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(vendor))
    again = reopened.execute('commit_write', approval, context=context)
    assert again.data['items'][0]['state'] == 'uncertain'
    assert vendor.upload_count == 1


@pytest.mark.parametrize('fault', ['list_missing_new', 'list_duplicate_new', 'detail_org', 'detail_owner',
                                   'detail_meeting', 'detail_uuid', 'detail_download_evil',
                                   'detail_download_path'])
def test_duplicate_missing_foreign_or_uuid_detail_mismatch_is_uncertain(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add(fault)
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    assert result.data['items'][0]['state'] == 'uncertain', result.public_dict()
    assert vendor.upload_count == 1
    assert not any(call[1].startswith('https://evil.example') for call in vendor.calls)
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(vendor))
    again = reopened.execute('commit_write', approval, context=context)
    assert again.data['items'][0]['state'] == 'uncertain'
    assert vendor.upload_count == 1


@pytest.mark.parametrize('fault', ['detail_500', 'detail_404', 'download_500', 'download_404', 'download_corrupt', 'download_redirect'])
def test_detail_or_original_failure_retains_id_and_recovers_readonly(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add(fault)
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    item = result.data['items'][0]
    assert item['state'] == 'uncertain'
    assert item['resource_id'] == str(NEW_ID)
    assert vendor.upload_count == 1
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(vendor))
    again = reopened.execute('commit_write', approval, context=context)
    assert again.status == 'completed', again.public_dict()
    assert again.data['items'][0]['state'] == 'succeeded'
    assert vendor.upload_count == 1


def test_pending_pdf_with_valid_original_bytes_succeeds(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    def pending():
        vendor.details[NEW_ID]['pdf'] = {'status': 'processing', 'isConverted': False,
                                         'pdfable_id': NEW_ID, 'pdfable_type': UUIDABLE}
    vendor.after_mutation = pending
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'completed', result.public_dict()
    assert vendor.upload_count == 1


def test_unsafe_filename_mime_and_transfer_bounds_fail_before_upload(tmp_path):
    engine, context, vendor = setup(tmp_path)
    bad_name = change(files=[file_part(filename='../escape.txt')])
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [bad_name]}, context=context)
    assert result.status == 'failed'
    bad_mime = change(files=[file_part(content_type='text/plain' + chr(13) + chr(10) + 'X-Bad: yes')])
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [bad_mime]}, context=context)
    assert result.status == 'failed'
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change()],
                                           'bounds': {'transfer_bytes': 100}}, context=context)
    assert result.status == 'failed'
    assert vendor.upload_count == 0


@pytest.mark.parametrize('mutation', ['missing_permission', 'meeting_not_allowed', 'owner_mismatch'])
def test_narrowed_grants_block_planning(tmp_path, mutation):
    engine, context, vendor = setup(tmp_path)
    if mutation == 'missing_permission':
        context.credentials['boardable']['permissions'] = []
    elif mutation == 'meeting_not_allowed':
        context.credentials['boardable']['meeting_ids'] = ['999']
    else:
        context.credentials['boardable']['owner_id'] = 999
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change()]}, context=context)
    assert result.status == 'failed'
    assert vendor.upload_count == 0


def test_mode_exclusivity_and_existing_routes_unaffected(tmp_path):
    engine, context, vendor = setup(tmp_path)
    source = Source(**SOURCE)
    wrapper = BoardableWriteAdapter(vendor)
    assert wrapper._is_meeting_documents(source, context) is True
    context.credentials['boardable'].pop('current_meeting_form')
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change()]}, context=context)
    assert result.status == 'failed'
    context.credentials['boardable']['current_meeting_form'] = True
    context.credentials['boardable']['legacy_agenda_editor'] = True
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change()]}, context=context)
    assert result.status == 'failed'
    context.credentials['boardable'].pop('legacy_agenda_editor')
    context.credentials['boardable']['current_agenda_builder'] = True
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change()]}, context=context)
    assert result.status == 'failed'
    context.credentials['boardable'].pop('current_agenda_builder')
    context.credentials['boardable']['current_meeting_series'] = True
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change()]}, context=context)
    assert result.status == 'failed'
    context.credentials['boardable'].pop('current_meeting_series')
    context.credentials['boardable']['current_meeting_documents'] = False
    assert wrapper._is_meeting_documents(source, context) is False
    assert wrapper._is_meeting_form(source, context) is True
    assert vendor.upload_count == 0


def _prepared_from_plan(engine, context, approval):
    stored = engine.storage.get('write_plans', approval['plan_id'], scope=context.scope)
    plan = stored.value['plan']
    return plan['changes'][0], Bounds(**plan['bounds']), Source(**plan['source'])


def test_forged_prepared_route_or_parts_do_not_upload(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    prepared, bounds, source = _prepared_from_plan(engine, context, approval)
    adapter = BoardableMeetingDocumentsWriteAdapter(vendor).bind_files(engine, context)
    prepared['native']['url'] = 'https://evil.example/upload'
    with pytest.raises(WriteFailure):
        adapter.apply(source, prepared, context, bounds, monotonic() + bounds.deadline_seconds)
    assert vendor.upload_count == 0


def test_cancellation_after_outbound_marker_sends_nothing(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    prepared, bounds, source = _prepared_from_plan(engine, context, approval)
    adapter = BoardableMeetingDocumentsWriteAdapter(vendor).bind_files(engine, context)
    def persist(step):
        return bool(step.get('outbound_started'))
    with pytest.raises(WriteCancelled):
        adapter.apply(source, prepared, context, bounds, monotonic() + bounds.deadline_seconds, persist=persist)
    assert vendor.upload_count == 0


def test_cancellation_after_candidate_identity_persisted_restart_recovers_without_replay(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    vendor.after_mutation = context.cancellation.set
    result = engine.execute('commit_write', approval, context=context)
    item = result.data['items'][0]
    assert item['state'] == 'uncertain'
    assert item['resource_id'] == str(NEW_ID)
    assert vendor.upload_count == 1
    context.cancellation.clear()
    vendor.after_mutation = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(vendor))
    again = reopened.execute('commit_write', approval, context=context)
    assert again.status == 'completed', again.public_dict()
    assert vendor.upload_count == 1


def test_timeout_after_upload_then_sqlite_restart_readonly_recovery(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add('timeout_after')
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    assert result.data['items'][0]['state'] == 'uncertain'
    assert vendor.upload_count == 1
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(vendor))
    again = reopened.execute('commit_write', approval, context=context)
    assert again.status == 'completed', again.public_dict()
    assert again.data['items'][0]['state'] == 'succeeded'
    assert vendor.upload_count == 1


def test_remote_500_after_upload_then_readonly_recovery(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add('remote_500_after')
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    assert result.data['items'][0]['state'] == 'uncertain'
    assert vendor.upload_count == 1
    vendor.faults.clear()
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(vendor))
    again = reopened.execute('commit_write', approval, context=context)
    assert again.status == 'completed', again.public_dict()
    assert vendor.upload_count == 1


def test_source_options_body_input_format_and_invalid_fields_rejected(tmp_path):
    engine, context, vendor = setup(tmp_path)
    for source in (
        {**SOURCE, 'options': {'x': 1}},
        {**SOURCE, 'body': 'not allowed'},
        {**SOURCE, 'input_format': 'json'},
    ):
        result = engine.execute('plan_write', {'source': source, 'changes': [change()]}, context=context)
        assert result.status == 'failed'
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change(fields={'title': 'x'})]}, context=context)
    assert result.status == 'failed'
    assert vendor.upload_count == 0


def test_narrowed_grant_after_planning_blocks_commit(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    context.credentials['boardable']['permissions'] = []
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'failed'
    assert vendor.upload_count == 0


@pytest.mark.parametrize('fault', ['extra_member', 'group', 'guest', 'series', 'public'])
def test_owner_only_private_scope_guards_block_planning(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add(fault)
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change()]}, context=context)
    assert result.status == 'failed'
    assert vendor.upload_count == 0


@pytest.mark.parametrize('fault', ['root_missing_current', 'root_current_folder'])
def test_root_envelope_must_be_exact_root(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    vendor.faults.add(fault)
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change()]}, context=context)
    assert result.status == 'failed'
    assert vendor.upload_count == 0


def test_folder_metadata_change_after_upload_is_uncertain_with_id(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.folders = [{'id': 10, 'name': 'Original'}]

    def mutate():
        vendor.folders[0]['name'] = 'Changed'

    vendor.after_mutation = mutate
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    item = result.data['items'][0]
    assert item['state'] == 'uncertain'
    assert item['resource_id'] == str(NEW_ID)
    assert vendor.upload_count == 1
    vendor.after_mutation = None
    vendor.folders[0]['name'] = 'Original'
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(vendor))
    again = reopened.execute('commit_write', approval, context=context)
    assert again.status == 'completed', again.public_dict()
    assert vendor.upload_count == 1


@pytest.mark.parametrize('mode', ['zero', 'multiple'])
def test_persisted_candidate_requires_exact_delta_on_recovery(tmp_path, mode):
    engine, context, vendor = setup(tmp_path)

    def old_change():
        vendor.root[0]['order'] = 99

    vendor.after_mutation = old_change
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    item = result.data['items'][0]
    assert item['state'] == 'uncertain'
    assert item['resource_id'] == str(NEW_ID)
    if mode == 'zero':
        vendor.attachments = [row for row in vendor.attachments if row['id'] != NEW_ID]
        vendor.root = [row for row in vendor.root if row['id'] != NEW_ID]
    else:
        vendor._add('second.txt', b'second', NEW_ID + 1)
    vendor.after_mutation = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(vendor))
    again = reopened.execute('commit_write', approval, context=context)
    assert again.data['items'][0]['state'] == 'uncertain'
    assert again.data['items'][0]['resource_id'] == str(NEW_ID)
    assert vendor.upload_count == 1


def test_nonroot_existing_attachment_is_preserved_and_not_equated_with_root(tmp_path):
    engine, context, vendor = setup(tmp_path)
    vendor.attachments.append(_canonical(999, 'nested.txt', 10, folder_id=5, order=1))
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'completed', result.public_dict()
    assert result.data['items'][0]['resource_id'] == str(NEW_ID)
    assert vendor.upload_count == 1


@pytest.mark.parametrize('method,field', [
    ('apply', 'before'), ('apply', 'native'),
    ('reconcile', 'before'), ('reconcile', 'native'),
])
def test_forged_before_or_native_parts_in_apply_and_reconcile_rejected(tmp_path, method, field):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    prepared, bounds, source = _prepared_from_plan(engine, context, approval)
    adapter = BoardableMeetingDocumentsWriteAdapter(vendor).bind_files(engine, context)
    if field == 'before':
        prepared['before']['meeting']['title'] = 'forged'
    else:
        prepared['native']['multipart'][0]['name'] = 'forged'
    if method == 'apply':
        with pytest.raises(WriteFailure):
            adapter.apply(source, prepared, context, bounds, monotonic() + bounds.deadline_seconds)
    else:
        outcome = adapter.reconcile(source, prepared, {}, context, bounds, monotonic() + bounds.deadline_seconds)
        assert outcome['state'] == 'uncertain'
    assert vendor.upload_count == 0


def test_new_canonical_uuid_mismatch_root_is_uncertain_with_id(tmp_path):
    engine, context, vendor = setup(tmp_path)
    def mutate():
        row = next(row for row in vendor.attachments if row['id'] == NEW_ID)
        row['uuid'] = {**vendor.root[-1]['uuid'], 'short_slug': 'deadbeef'}
    vendor.after_mutation = mutate
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    item = result.data['items'][0]
    assert item['state'] == 'uncertain'
    assert item['resource_id'] == str(NEW_ID)
    assert vendor.upload_count == 1


@pytest.mark.parametrize('fault', ['unknown_meeting', 'old_canonical'])
def test_post_upload_business_or_old_canonical_change_is_uncertain_with_id(tmp_path, fault):
    engine, context, vendor = setup(tmp_path)
    if fault == 'unknown_meeting':
        vendor.faults.add('meeting_unknown_after')
    else:
        def mutate():
            vendor.attachments[0]['order'] = 99
        vendor.after_mutation = mutate
    approval = plan(engine, context)
    result = engine.execute('commit_write', approval, context=context)
    item = result.data['items'][0]
    assert item['state'] == 'uncertain'
    assert item['resource_id'] == str(NEW_ID)
    assert vendor.upload_count == 1


@pytest.mark.parametrize('mutation', ['canonical_org', 'canonical_uuid', 'canonical_uuid_id',
                                      'canonical_uuid_type', 'list_uuid'])
def test_malformed_or_foreign_canonical_identity_rejected_before_upload(tmp_path, mutation):
    engine, context, vendor = setup(tmp_path)
    if mutation == 'canonical_org':
        vendor.attachments[0]['organization_id'] = 999
    elif mutation == 'canonical_uuid':
        vendor.attachments[0]['uuid'] = {
            'uuidable_id': OLD_ID, 'uuidable_type': UUIDABLE, 'short_slug': 'badsafe',
        }
    elif mutation == 'canonical_uuid_id':
        vendor.attachments[0]['uuid'] = {
            'uuidable_id': OLD_ID + 1, 'uuidable_type': UUIDABLE, 'short_slug': OLD_SLUG,
        }
    elif mutation == 'canonical_uuid_type':
        vendor.attachments[0]['uuid'] = {
            'uuidable_id': OLD_ID, 'uuidable_type': 'WrongType', 'short_slug': OLD_SLUG,
        }
    else:
        vendor.root[0]['uuid']['uuidable_id'] = 999
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change()]}, context=context)
    assert result.status == 'failed'
    assert vendor.upload_count == 0


def test_planning_bounds_max_records_and_json_depth_fail_before_upload(tmp_path):
    engine, context, vendor = setup(tmp_path)
    result = engine.execute('plan_write', {
        'source': SOURCE,
        'changes': [change(), change(key='doc2')],
        'bounds': {'max_records': 1},
    }, context=context)
    assert result.status == 'failed'
    vendor.faults.add('root_deep')
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change()]}, context=context)
    assert result.status == 'failed'
    assert vendor.upload_count == 0


def test_serialized_prepared_size_too_small_fails_apply_before_mutation(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    prepared, bounds, source = _prepared_from_plan(engine, context, approval)
    adapter = BoardableMeetingDocumentsWriteAdapter(vendor).bind_files(engine, context)
    tiny = Bounds(parser_bytes=1, transfer_bytes=bounds.transfer_bytes,
                  deadline_seconds=bounds.deadline_seconds)
    with pytest.raises((WriteFailure, ValueError)):
        adapter.apply(source, prepared, context, tiny, monotonic() + tiny.deadline_seconds)
    assert vendor.upload_count == 0


def test_durable_plan_excludes_raw_file_and_session_secrets_and_is_scope_bound(tmp_path):
    engine, context, vendor = setup(tmp_path)
    approval = plan(engine, context)
    stored = engine.storage.get('write_plans', approval['plan_id'], scope=context.scope)
    serialized = json.dumps(stored.value, sort_keys=True)
    assert 'content_base64' not in serialized
    assert 'secret-session' not in serialized
    assert 'secret-csrf' not in serialized
    other = OperationContext(
        principal='other', client_id='fixture', tenant='city',
        authorization=frozenset({'write:plan', 'write:commit'}),
        allowed_namespaces=frozenset({NS}),
        credentials=deepcopy(context.credentials),
    )
    denied = engine.execute('commit_write', approval, context=other)
    assert denied.status == 'failed'
    assert vendor.upload_count == 0
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'completed', result.public_dict()
    public = json.dumps(result.public_dict(), sort_keys=True)
    assert 'content_base64' not in public
    assert 'secret-session' not in public
    assert 'secret-csrf' not in public
    assert vendor.upload_count == 1
