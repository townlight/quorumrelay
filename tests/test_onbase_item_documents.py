"""Selected item attachment, with a synthetic replay of the published wrapper."""
import base64
import json
import hashlib
from urllib.parse import parse_qs, urlsplit

import pytest
from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from test_onbase_detail import ITEM, ITEM_URL, FORMAT
from test_onbase_listing import SOURCE
from test_onbase_documents import WRAPPER, NAME, PDF, COOKIE

ITEM_NAME = 'synthetic-item-88173.pdf'
WRAPPED = (WRAPPER.replace(NAME.encode(), ITEM_NAME.encode()).replace(b'g_documentItemId = 0', b'g_documentItemId = 88173')
           .replace(b'g_documentPublishId = 0', b'g_documentPublishId = 97134')
           .replace(b'g_documentIsAttachment = false', b'g_documentIsAttachment = true'))

class Transport:
    def __init__(self, citation, failure=None, wrapper=WRAPPED, cancel=None):
        self.citation, self.failure, self.wrapper, self.cancel = citation, failure, wrapper, cancel
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append(url)
        assert kwargs['allow_redirects'] is False
        if url == self.citation:
            return Response(url, self.wrapper, 'text/html', set_cookie_headers=(
                'ASP.NET_SessionId=' + COOKIE + '; Path=/OnBaseAgendaOnline; Secure; HttpOnly',))
        assert kwargs['headers']['Cookie'] == 'ASP.NET_SessionId=' + COOKIE
        assert kwargs['allowed_origins'] == ('https://agendas.fitchburgwi.gov',)
        query = parse_qs(urlsplit(url).query)
        if '/InvokeDownloadAttachment/' in url:
            assert kwargs['method'] == 'POST' and kwargs['body'] == b''
            assert query == {'meetingId':['3825'], 'itemId':['88173'], 'publishId':['97134'],
                             'isSection':['false'], 'documentType':['1']}
            data = {'DocumentName': ITEM_NAME, 'MeetingId': 3825, 'ItemId': 88173, 'PublishId': 97134,
                    'DocumentType': 1, 'IsSection': False}
            if self.failure in data:
                data[self.failure] = {'DocumentName':'../other.pdf', 'MeetingId':3826, 'ItemId':88174,
                    'PublishId':97135, 'DocumentType':2, 'IsSection':True}[self.failure]
            if self.failure == 'echo':
                data['extra'] = COOKIE
            if self.cancel:
                self.cancel.cancellation.set()
            return Response(url, json.dumps(data).encode(), 'application/json')
        assert '/ViewDocument/' in url
        assert query == {'meetingId':['3825'], 'itemId':['88173'], 'publishId':['97134'],
                         'isSection':['false'], 'documentType':['1']}
        return Response(url, b'not pdf' if self.failure == 'file' else PDF, 'application/pdf')

@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    from civic_data_connectors.providers import onbase_documents
    monkeypatch.setattr(onbase_documents, '_wait', lambda context, deadline: None)

def setup(tmp_path, failure=None, wrapper=WRAPPED, cancel=None):
    bundle = create_engine().normalize(Source('onbase', ITEM_URL), ITEM, input_format=FORMAT).data
    record = bundle['records'][0]
    storage = SQLiteStorage(tmp_path / 'item.sqlite')
    owner = create_engine(storage=storage)
    result = owner.execute('import_bundle', {'bundle': bundle, 'persist': True})
    assert result.status == 'completed', result.public_dict()
    transport = Transport(record['normalized']['documents'][0]['url'], failure, wrapper, cancel)
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'item.sqlite'), provider_transport=transport)
    return owner, record, transport, bundle

def test_item_from_storage_reopen_and_zip(tmp_path):
    owner, record, transport, bundle = setup(tmp_path)
    result = owner.fetch_attachment(SOURCE, record)
    assert result.status == 'completed', result.public_dict()
    assert result.data['record']['identity'] == record['identity']
    attachment = result.data['attachment']
    assert attachment['citation_url'] == transport.citation
    assert base64.b64decode(attachment['content_base64']) == PDF
    assert attachment['resolution']['item_id'] == '88173' and attachment['resolution']['publish_id'] == '97134'
    assert len(transport.calls) == 3 and COOKIE not in json.dumps(result.public_dict())
    bundle['captures'] = result.data['captures']
    saved = owner.execute('import_bundle', {'bundle': bundle, 'persist': True})
    assert saved.status == 'completed', saved.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'item.sqlite'))
    for capture in result.data['captures']:
        stored = reopened.storage.get('captures', capture['sha256'], scope=OperationContext().scope)
        assert stored
        content = base64.b64decode(stored.value['content_base64'])
        assert content == base64.b64decode(capture['content_base64'])
        assert hashlib.sha256(content).hexdigest() == capture['sha256']
    exported = reopened.execute('export', {'bundle': bundle, 'format': 'zip'})
    restored_engine = create_engine(storage=SQLiteStorage(tmp_path / 'other.sqlite'))
    restored = restored_engine.execute(
        'import_bundle', {'format':'zip', 'persist':True}, content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed', restored.public_dict()
    assert restored.data['bundle']['records'][0]['identity'] == record['identity']
    assert len(restored.data['bundle']['captures']) == 2
    restored_engine = create_engine(storage=SQLiteStorage(tmp_path / 'other.sqlite'))
    for capture, expected in zip(restored.data['bundle']['captures'], result.data['captures']):
        with restored_engine.storage.open_capture(capture['storage_reference'], scope=OperationContext().scope) as stream:
            content = stream.read()
        assert content == base64.b64decode(expected['content_base64'])
        assert hashlib.sha256(content).hexdigest() == expected['sha256']

@pytest.mark.parametrize('failure', ['MeetingId','ItemId','PublishId','DocumentType','IsSection','DocumentName','echo','file'])
def test_rejects_mismatched_preparation_and_preserves_verified_captures(tmp_path, failure):
    owner, record, transport, _ = setup(tmp_path, failure)
    result = owner.fetch_attachment(SOURCE, record)
    assert result.status == 'partial' and result.data['attachment'] is None
    assert result.data['record']['identity'] == record['identity']
    assert len(result.data['captures']) == (2 if failure == 'file' else 1)
    assert COOKIE not in json.dumps(result.public_dict())

@pytest.mark.parametrize('old,new', [(b'g_documentMeetingId = 3825',b'g_documentMeetingId = 9999'),
    (b'g_documentItemId = 88173',b'g_documentItemId = 9999'),
    (b'g_documentPublishId = 97134',b'g_documentPublishId = 9999'),
    (b'g_documentIsSection = false',b'g_documentIsSection = true'),
    (b'/Documents/InvokeDownloadAttachment/',b'/Documents/Unverified/'),
    (b'/Documents/ViewDocument/',b'/Documents/UnverifiedView/'),
    (b"g_documentName = '",b"g_documentName = '../")])
def test_rejects_changed_wrapper(tmp_path, old, new):
    owner, record, transport, _ = setup(tmp_path, wrapper=WRAPPED.replace(old,new))
    result = owner.fetch_attachment(SOURCE, record)
    assert result.status == 'partial' and len(transport.calls) == 1

def test_bounds_and_cancellation(tmp_path):
    owner, record, transport, _ = setup(tmp_path)
    result = owner.fetch_attachment(SOURCE, record, bounds=Bounds(max_pages=2))
    assert result.status == 'partial' and len(transport.calls) == 1
    caller = OperationContext()
    owner, record, transport, _ = setup(tmp_path / 'cancel', cancel=caller)
    result = owner.fetch_attachment(SOURCE, record, context=caller)
    assert result.status == 'cancelled' and len(transport.calls) == 2

@pytest.mark.parametrize('change', ['parent','item','publish','type','section','membership','metadata'])
def test_rejects_foreign_selection_before_preparation(tmp_path, change):
    from copy import deepcopy
    from time import monotonic
    from civic_data_connectors.providers.onbase_documents import resolve_document
    owner, record, transport, _ = setup(tmp_path)
    record = deepcopy(record)
    document = record['normalized']['documents'][0]
    url = document['url']
    if change == 'parent':
        record['identity']['parent']['external_id'] = '9999'
    elif change == 'item':
        record['identity']['external_id'] = '9999'
    elif change == 'publish':
        document['publish_id'] = '9999'
    elif change == 'metadata':
        document['agenda_item_external_id'] = '9999'
    elif change == 'membership':
        document['url'] += '&foreign=1'
    elif change == 'type':
        url = url.replace('documentType=1','documentType=2')
        document['url'] = url
    elif change == 'section':
        url = url.replace('isSection=False','isSection=True')
        document['url'] = url
    first = Response(url, WRAPPED, 'text/html')
    with pytest.raises(ValueError):
        resolve_document(SOURCE, url, record, first, Bounds(), OperationContext(), transport, monotonic() + 30)
    assert not transport.calls
