"""Synthetic CivicClerk Select detail and published-file contract checks."""
import base64
from copy import deepcopy
import hashlib
import json

from civic_data_connectors import Bounds, OperationContext, Source, create_engine
from civic_data_connectors.engine import source_identity_key
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.storage import SQLiteStorage

ORIGIN = 'https://fishersin.api.civicclerk.com'
SOURCE = Source('civicplus-select', ORIGIN + '/v1/Events')
EVENT = {'id': 7, 'agendaId': 91, 'eventName': 'Council budget', 'startDateTime': '2026-10-01T18:00:00',
         'isPublished': 'Published', 'isDeleted': False, 'unknown': {'retained': True}}
DETAIL = {'id': 91, 'items': [{'id': 36, 'agendaObjectItemName': 'Budget item', 'parentId': 0}],
          'publishedFiles': [{'id': 77, 'fileId': 300, 'name': 'Budget agenda', 'type': 'Agenda',
                              'unknown': ['preserved']}], 'unknown': 'detail'}
PDF = b'%PDF-1.7\nsynthetic\n%%EOF'


class Network:
    def __init__(self):
        self.calls = []
        self.detail = DETAIL
        self.file = PDF
        self.context = None

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs.get('allow_redirects') is False
        if url.endswith('/Meetings/91'):
            if self.context:
                self.context.cancellation.set()
            return Response(url, self.detail if isinstance(self.detail, bytes) else json.dumps(self.detail).encode(),
                            'application/json')
        assert url == ORIGIN + '/v1/Meetings/GetMeetingFileStream(fileId=300,plainText=false)'
        if self.context:
            self.context.cancellation.set()
        return Response(url, self.file, 'application/pdf')


def setup(tmp_path):
    network = Network()
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'source.sqlite'), provider_transport=network)
    normalized = owner.normalize(SOURCE, json.dumps({'value': [EVENT]}).encode(), input_format='civicplus-events-json')
    assert normalized.status == 'completed', normalized.public_dict()
    assert owner.execute('import_bundle', {'bundle': normalized.data, 'persist': True}).status == 'completed'
    return create_engine(storage=SQLiteStorage(tmp_path / 'source.sqlite'), provider_transport=network), network


def test_detail_scoped_file_search_reopen_and_zip(tmp_path):
    owner, network = setup(tmp_path)
    result = owner.fetch_record(SOURCE, '7')
    assert result.status == 'partial', result.public_dict()
    record = result.data['records'][0]
    assert record['identity']['external_id'] == '7' and record['normalized']['agenda_id'] == '91'
    assert record['original']['event'] == EVENT and record['original']['meeting'] == DETAIL
    assert record['normalized']['agenda_items'][0]['external_id'] == '36'
    assert owner.execute('import_bundle', {'bundle': result.data, 'persist': True}).status == 'completed'
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'source.sqlite'), provider_transport=network)
    assert reopened.fetch_record(SOURCE, '7').status == 'partial'
    attachment = reopened.fetch_attachment(SOURCE, record)
    assert attachment.status == 'completed', attachment.public_dict()
    assert base64.b64decode(attachment.data['attachment']['content_base64']) == PDF
    found = reopened.execute('search', {'query': {'phrases': ['Council budget']}})
    assert found.status == 'partial' and found.data['hits']
    exported = reopened.execute('export', {'bundle': result.data, 'format': 'zip'})
    destination = create_engine(storage=SQLiteStorage(tmp_path / 'other.sqlite'))
    restored = destination.execute(
        'import_bundle', {'format': 'zip', 'persist': True}, content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed'
    assert restored.data['bundle']['capture']['sha256'] == result.data['capture']['sha256']
    assert restored.data['bundle']['records'][0]['original']['meeting'] == DETAIL
    capture = restored.data['bundle']['capture']
    with destination.storage.open_capture(capture['storage_reference'], scope=OperationContext().scope) as stream:
        assert stream.read() == json.dumps(DETAIL).encode()


def test_detail_mismatch_failure_retains_verified_bytes_and_no_file(tmp_path):
    owner, network = setup(tmp_path)
    network.detail = {**DETAIL, 'id': 92}
    result = owner.fetch_record(SOURCE, '7')
    assert result.status == 'partial' and len(network.calls) == 1
    data = base64.b64decode(result.data['captures'][0]['content_base64'])
    assert hashlib.sha256(data).hexdigest() == result.data['captures'][0]['sha256']
    assert json.loads(data)['id'] == 92
    network.detail = b'{broken'
    assert owner.fetch_record(SOURCE, '7').status == 'partial'


def test_detail_cancellation_and_byte_limit(tmp_path):
    owner, network = setup(tmp_path)
    caller = OperationContext()
    network.context = caller
    result = owner.fetch_record(SOURCE, '7', context=caller)
    assert result.status == 'cancelled' and len(result.data['captures']) == 1
    network.context = None
    result = owner.fetch_record(SOURCE, '7', bounds=Bounds(parser_bytes=8))
    assert result.status == 'failed' and network.calls[-1][1]['byte_limit'] == 8


def test_requires_existing_matching_event_and_source(tmp_path):
    owner, network = setup(tmp_path)
    assert owner.fetch_record(SOURCE, '91').status == 'failed'
    assert not network.calls
    other = Source('civicplus-select', ORIGIN + '/other')
    assert owner.fetch_record(other, '7').status == 'failed'
    assert not network.calls


def test_stored_file_spoof_is_rejected_before_request(tmp_path):
    owner, network = setup(tmp_path)
    detail = owner.fetch_record(SOURCE, '7')
    assert owner.execute('import_bundle', {'bundle': detail.data, 'persist': True}).status == 'completed'
    record = detail.data['records'][0]
    scope = OperationContext().scope
    key = source_identity_key(record['identity'])
    stored = owner.storage.get('records', key, scope=scope)
    tampered = deepcopy(stored.value)
    target = tampered['record'] if 'record' in tampered else tampered
    target['normalized']['documents'][0]['url'] = ORIGIN + '/v1/Meetings/GetMeetingFileStream(fileId=999,plainText=false)'
    owner.storage.put('records', key, tampered, scope=scope, expected_version=stored.version)
    before = len(network.calls)
    assert owner.fetch_attachment(SOURCE, record).status == 'failed'
    assert len(network.calls) == before


def test_file_cancel_and_transfer_limit(tmp_path):
    owner, network = setup(tmp_path)
    detail = owner.fetch_record(SOURCE, '7')
    assert owner.execute('import_bundle', {'bundle': detail.data, 'persist': True}).status == 'completed'
    record = detail.data['records'][0]
    context = OperationContext()
    network.context = context
    assert owner.fetch_attachment(SOURCE, record, context=context).status == 'cancelled'
    network.context = None
    result = owner.fetch_attachment(SOURCE, record, bounds=Bounds(transfer_bytes=8))
    assert result.status == 'partial' and network.calls[-1][1]['byte_limit'] == 8
