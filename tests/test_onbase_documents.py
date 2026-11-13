"""Replay the actual vendor download wrapper with synthetic prepared/file responses."""

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from test_onbase_listing import HTML, SOURCE

ROOT = 'https://agendas.fitchburgwi.gov/OnBaseAgendaOnline'
CITATION = ROOT + '/Documents/Downloadfile/Agenda.pdf?documentType=1&meetingId=3825'
WRAPPER = (Path(__file__).parents[1] / 'docs/capabilities/evidence/onbase-download/wrapper.html').read_bytes()
NAME = 'Commission_on_Aging_Well_3825_Agenda_11_12_2026_8_30_00_AM.pdf'
PDF = b'%PDF-1.7\nsynthetic prepared meeting document\n%%EOF'
COOKIE = 'synthetic-private-session-value'


class Transport:
    def __init__(self, wrapper=WRAPPER, malformed=None, on_prepare=None):
        self.wrapper, self.malformed, self.on_prepare = wrapper, malformed, on_prepare
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs.get('allow_redirects') is False
        assert kwargs['byte_limit'] > 0 and kwargs['deadline_seconds'] > 0
        if url == CITATION:
            assert kwargs.get('method', 'GET') == 'GET'
            if self.malformed == 'direct_pdf':
                return Response(url, PDF, 'application/pdf')
            return Response(url, self.wrapper, 'text/html', set_cookie_headers=(
                'ASP.NET_SessionId=' + COOKIE + '; Path=/OnBaseAgendaOnline; Secure; HttpOnly',))
        assert kwargs['allowed_origins'] == ('https://agendas.fitchburgwi.gov',)
        assert kwargs['headers']['Cookie'] == 'ASP.NET_SessionId=' + COOKIE
        assert 'Authorization' not in kwargs['headers']
        query = parse_qs(urlsplit(url).query)
        if '/InvokeDownloadMeetingDocument/' in url:
            assert kwargs['method'] == 'POST' and kwargs['body'] == b''
            assert query == {'meetingId': ['3825'], 'documentType': ['1']}
            data = {'DocumentName': NAME, 'MeetingId': 3825, 'DocumentType': 1,
                    'ItemId': 0, 'PublishId': 0, 'IsSection': False, 'unknown': [False, None]}
            if self.malformed in {'MeetingId', 'DocumentType', 'ItemId', 'PublishId'}:
                data[self.malformed] += 1
            elif self.malformed == 'IsSection':
                data['IsSection'] = True
            elif self.malformed == 'DocumentName':
                data['DocumentName'] = '../foreign.pdf'
            elif self.malformed == 'echo':
                data['unknown'] = COOKIE
            elif self.malformed == 'json':
                return Response(url, b'not json', 'application/json')
            elif self.malformed == 'post_http':
                return Response(url, b'{}', 'application/json', 403)
            elif self.malformed == 'post_url':
                return Response(url.replace('3825', '9999'), json.dumps(data).encode(), 'application/json')
            if self.on_prepare:
                self.on_prepare()
            return Response(url, json.dumps(data).encode(), 'application/json')
        assert '/Documents/ViewDocument/' in url and kwargs['method'] == 'GET'
        assert query == {'meetingId': ['3825'], 'documentType': ['1'], 'itemId': ['0'],
                         'publishId': ['0'], 'isSection': ['false']}
        if self.malformed == 'view_html':
            return Response(url, b'<html>Not ready</html>', 'text/html')
        if self.malformed == 'view_url':
            return Response(url.replace('3825', '9999'), PDF, 'application/pdf')
        return Response(url, PDF, 'application/pdf')


@pytest.fixture(autouse=True)
def skip_browser_delay(monkeypatch):
    # Synthetic preparation is immediate; production follows the wrapper's 1s wait.
    from civic_data_connectors.providers import onbase_documents
    monkeypatch.setattr(onbase_documents, '_wait', lambda context, deadline: None)


def fetch(transport, **kwargs):
    owner = create_engine(provider_transport=transport)
    record = owner.execute('discover', {'source': SOURCE.public_dict()}, content=HTML).data['records'][0]
    return owner.fetch_attachment(SOURCE, record, capture=HTML, **kwargs)


def test_onbase_wrapper_post_view_exact_capture_hash_citation_and_zip(tmp_path):
    transport = Transport()
    result = fetch(transport)
    assert result.status == 'completed', result.public_dict()
    attachment = result.data['attachment']
    assert base64.b64decode(attachment['content_base64']) == PDF
    assert attachment['citation_url'] == CITATION and attachment['text_availability'] == 'not_extracted'
    assert len(transport.calls) == 3 and attachment['resolution']['requests'] == 3
    assert COOKIE not in json.dumps(result.public_dict())
    captures = result.data['captures']
    assert len(captures) == 2 and base64.b64decode(captures[0]['content_base64']) == WRAPPER
    assert captures[1]['original_values']['unknown'] == [False, None]
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'documents.sqlite'))
    imported = owner.execute('import_bundle', {'bundle': result.data['bundle'], 'persist': True})
    assert imported.status == 'completed' and imported.data['persisted'], imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'documents.sqlite'))
    assert all(reopened.storage.get('captures', capture['sha256'], scope=OperationContext().scope) is not None
               for capture in captures)
    exported = reopened.execute('export', {'bundle': result.data['bundle'], 'format': 'zip'})
    assert exported.status == 'completed', exported.public_dict()
    destination = create_engine(storage=SQLiteStorage(tmp_path / 'destination.sqlite'))
    restored = destination.execute('import_bundle', {'format': 'zip', 'persist': True},
                                  content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed', restored.public_dict()
    for capture in restored.data['bundle']['captures']:
        with destination.storage.open_capture(capture['storage_reference'], scope=OperationContext().scope) as stream:
            assert hashlib.sha256(stream.read()).hexdigest() == capture['sha256']


@pytest.mark.parametrize('malformed', ['MeetingId', 'DocumentType', 'ItemId', 'PublishId', 'IsSection',
                                       'DocumentName', 'echo', 'json', 'post_http', 'post_url', 'view_html', 'view_url'])
def test_onbase_wrong_preparation_or_file_is_partial_without_cross_document_download(malformed):
    transport = Transport(malformed=malformed)
    result = fetch(transport)
    assert result.status == 'partial' and result.data['attachment'] is None, result.public_dict()
    assert result.data['record']['identity']['external_id'] == '3825'
    assert COOKIE not in json.dumps(result.public_dict())
    assert all('9999' not in url and 'foreign' not in url for url, _ in transport.calls)
    if malformed.startswith('view_'):
        assert len(result.data['captures']) == 2
    else:
        assert len(transport.calls) == 2


@pytest.mark.parametrize('old,new', [(b'g_documentMeetingId = 3825', b'g_documentMeetingId = 9999'),
    (b'g_documentType = 1', b'g_documentType = 2'),
    (b'g_documentIsAttachment = false', b'g_documentIsAttachment = true'),
    (b'/Documents/InvokeDownloadMeetingDocument/', b'/Documents/UnverifiedRoute/'),
    (b"g_documentName = '", b"g_documentName = '../"),
    (b"g_documentStreamId = ''", b"g_documentStreamId = 'existing-stream'")])
def test_onbase_changed_wrapper_does_not_invent_or_invoke_routes(old, new):
    assert old in WRAPPER
    transport = Transport(wrapper=WRAPPER.replace(old, new))
    result = fetch(transport)
    assert result.status == 'partial' and len(transport.calls) == 1


def test_onbase_direct_pdf_still_works_without_wrapper_protocol():
    transport = Transport(malformed='direct_pdf')
    result = fetch(transport)
    assert result.status == 'completed' and len(transport.calls) == 1
    assert 'resolution' not in result.data['attachment']


def test_onbase_wrapper_bounds_cancel_and_partial_captures():
    for bounds in [Bounds(max_pages=2), Bounds(transfer_bytes=len(WRAPPER))]:
        transport = Transport()
        result = fetch(transport, bounds=bounds)
        assert result.status == 'partial' and len(transport.calls) == 1
    transport = Transport()
    tiny_parser = fetch(transport, bounds=Bounds(parser_bytes=10))
    # The original listing capture is rejected before any network request.
    assert tiny_parser.status == 'failed' and not transport.calls
    transport = Transport()
    limited = fetch(transport, bounds=Bounds(transfer_bytes=len(WRAPPER) + 10))
    assert limited.status == 'partial' and len(transport.calls) == 2
    caller = OperationContext()
    transport = Transport(on_prepare=caller.cancellation.set)
    cancelled = fetch(transport, context=caller)
    assert cancelled.status == 'cancelled' and len(transport.calls) == 2
    assert cancelled.data['record']['identity']['external_id'] == '3825'
