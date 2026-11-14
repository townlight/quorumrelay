"""CivicClerk Event-supplied published files use the matching tenant API."""
import base64
from copy import deepcopy
import json

import pytest

from civic_data_connectors import OperationContext, Source, create_engine
from civic_data_connectors.engine import source_identity_key
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.storage import SQLiteStorage

PORTAL = 'https://fishersin.portal.civicclerk.com'
API = 'https://fishersin.api.civicclerk.com'
SOURCE = Source('civicplus-select', PORTAL + '/event/7')
EVENT = {'id': 7, 'agendaId': 0, 'eventName': 'Council meeting', 'startDateTime': '2026-10-01T18:00:00',
         'isPublished': 'Published', 'isDeleted': False,
         'publishedFiles': [{'fileId': 300, 'type': 'Agenda', 'name': 'Agenda'}]}
CONTENT = json.dumps({'value': [EVENT]}).encode()
FILE_URL = API + '/v1/Meetings/GetMeetingFileStream(fileId=300,plainText=false)'
PDF = b'%PDF-1.7\nsynthetic\n%%EOF'


class Network:
    def __init__(self):
        self.calls = []

    def request(self, url, **options):
        self.calls.append((url, options))
        if url.startswith(API + '/v1/Events'):
            return Response(url, CONTENT, 'application/json')
        assert url == FILE_URL and options.get('allow_redirects') is False
        return Response(url, PDF, 'application/pdf')


def setup(tmp_path, *, legacy=False):
    network = Network()
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'events.sqlite'), provider_transport=network)
    if legacy:
        result = owner.normalize(SOURCE, CONTENT, input_format='civicplus-events-json')
        bundle = result.data
    else:
        result = owner.execute('discover', {'source': SOURCE.public_dict(),
            'bounds': {'date_from': '2026-10-01', 'date_to': '2026-10-01'}})
        bundle = result.data['bundles'][0]
    assert owner.execute('import_bundle', {'bundle': bundle, 'persist': True}).status == 'completed'
    return create_engine(storage=SQLiteStorage(tmp_path / 'events.sqlite'), provider_transport=network), network, bundle


@pytest.mark.parametrize('legacy', [False, True])
def test_event_file_from_discovery_or_legacy_storage(tmp_path, legacy):
    owner, network, bundle = setup(tmp_path, legacy=legacy)
    record = bundle['records'][0]
    expected = (PORTAL if legacy else API) + '/v1/Meetings/GetMeetingFileStream(fileId=300,plainText=false)'
    assert record['normalized']['documents'][0]['url'] == expected
    key = source_identity_key(record['identity'])
    stored = owner.storage.get('records', key, scope=OperationContext().scope)
    before = len(network.calls)
    result = owner.fetch_attachment(SOURCE, record)
    assert result.status == 'completed', result.public_dict()
    assert base64.b64decode(result.data['attachment']['content_base64']) == PDF
    assert len(network.calls) == before + 1 and network.calls[-1][0] == FILE_URL
    assert owner.storage.get('records', key, scope=OperationContext().scope) == stored
    exported = owner.execute('export', {'bundle': bundle, 'format': 'zip'})
    dest = create_engine(storage=SQLiteStorage(tmp_path / 'other.sqlite'))
    restored = dest.execute('import_bundle', {'format': 'zip', 'persist': True},
                            content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed' and restored.data['bundle']['records'][0]['original'] == EVENT


@pytest.mark.parametrize('mutation', ['file_id', 'url', 'raw_file', 'source', 'event_id'])
def test_tampered_event_file_fails_before_network(tmp_path, mutation):
    owner, network, bundle = setup(tmp_path)
    record = bundle['records'][0]
    scope = OperationContext().scope
    key = source_identity_key(record['identity'])
    stored = owner.storage.get('records', key, scope=scope)
    value = deepcopy(stored.value)
    row = value['record'] if 'record' in value else value
    if mutation == 'file_id':
        row['normalized']['documents'][0]['external_id'] = '301'
    elif mutation == 'url':
        row['normalized']['documents'][0]['url'] = API + '/v1/Meetings/GetMeetingFileStream(fileId=301,plainText=false)'
    elif mutation == 'raw_file':
        row['original']['publishedFiles'][0]['fileId'] = 301
    elif mutation == 'source':
        row['source_url'] = PORTAL + '/other'
    else:
        row['original']['id'] = 8
    owner.storage.put('records', key, value, scope=scope, expected_version=stored.version)
    before = len(network.calls)
    assert owner.fetch_attachment(SOURCE, record).status == 'failed'
    assert len(network.calls) == before


@pytest.mark.parametrize('source_url', ['http://fishersin.portal.civicclerk.com/event/7',
                                         'https://fishersin.portal.civicclerk.com:443/event/7'])
def test_legacy_portal_scheme_and_port_resolve_to_https_api(tmp_path, source_url):
    network = Network()
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'legacy.sqlite'), provider_transport=network)
    source = Source('civicplus-select', source_url)
    result = owner.normalize(source, CONTENT, input_format='civicplus-events-json')
    assert owner.execute('import_bundle', {'bundle': result.data, 'persist': True}).status == 'completed'
    fetched = owner.fetch_attachment(source, result.data['records'][0])
    assert fetched.status == 'completed', fetched.public_dict()
    assert network.calls[-1][0] == FILE_URL
