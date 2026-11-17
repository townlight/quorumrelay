"""Documented task/results/context contracts with synthetic transport and real storage."""

import base64
import hashlib
import json
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from test_repository_discovery import BASE, NAMESPACE, context, entry

ROOT = BASE.split('/Entries/', 1)[0]
TASK_ID = 'synthetic-search-task-71'
TASK_URL = ROOT + '/Tasks?taskIds=' + TASK_ID
RESULT_URL = ROOT + '/Searches/' + TASK_ID + '/Results'


def hit(number, text='The park funding was approved.', **extra):
    return {'hitNumber': number, 'hitType': 'PageContent', 'pageNumber': 3,
            'context': text, 'unknown': [False, None], **extra}


class SearchTransport:
    def __init__(self, *, malformed=None, on_poll=None, cleanup_status='Cancelled'):
        self.calls, self.stopped = [], False
        self.malformed, self.on_poll, self.cleanup_status = malformed, on_poll, cleanup_status
        self.rows = [{**entry(71), 'rowNumber': 1}, {**entry(72), 'rowNumber': 2}]
        self.contexts = {1: [hit(1), hit(2, 'Other supplied park text.')],
                         2: [hit(1, 'A park funding proposal remains pending.')]}

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs['allow_redirects'] is False
        assert kwargs['allowed_origins'] == ('https://api.laserfiche.com',)
        assert kwargs['headers']['Authorization'] == 'Bearer secret-read-token'
        assert kwargs['byte_limit'] > 0 and kwargs['deadline_seconds'] > 0
        code = 200
        if url == ROOT + '/Searches/SearchAsync':
            assert kwargs['method'] == 'POST'
            self.command = json.loads(kwargs['body'])['searchCommand']
            block, code = {'taskId': TASK_ID}, 202
            if self.malformed == 'start':
                block = {}
        elif url == TASK_URL:
            if kwargs['method'] == 'DELETE':
                self.stopped = True
                block = {'value': [{'id': TASK_ID, 'taskType': 'SearchEntry', 'result': True}]}
            else:
                if self.on_poll and not self.stopped:
                    self.on_poll()
                row = {'id': TASK_ID, 'taskType': 'SearchEntry',
                       'status': self.cleanup_status if self.stopped else 'Completed', 'errors': [],
                       'result': {'entryId': 0, 'uri': RESULT_URL}}
                if not self.stopped:
                    if self.malformed == 'task_id':
                        row['id'] = 'unowned'
                    elif self.malformed == 'task_type':
                        row['taskType'] = 'DeleteEntry'
                    elif self.malformed == 'result_uri':
                        row['result']['uri'] = RESULT_URL.replace('r-city', 'r-other')
                    elif self.malformed == 'task_error':
                        row['errors'] = [{'detail': 'private-error'}]
                block = {'value': [row]}
        else:
            parsed = urlsplit(url)
            params = parse_qs(parsed.query)
            assert set(params) == {'$skip', '$top', '$count'} and params['$count'] == ['true']
            offset, top = int(params['$skip'][0]), int(params['$top'][0])
            if parsed.path == urlsplit(RESULT_URL).path:
                rows = deepcopy(self.rows)
                if self.malformed == 'parent':
                    rows[0]['parentId'] = 55
                elif self.malformed == 'row_id':
                    rows[0]['rowNumber'] = 0
                elif self.malformed == 'duplicate_entry':
                    rows[1]['id'] = rows[0]['id']
                block = {'value': rows[offset:offset + top], '@odata.count': len(rows), 'unknown_page': True}
                if self.malformed == 'count':
                    block['@odata.count'] = -1
                elif self.malformed == 'echo':
                    block['echo'] = 'secret-read-token'
                elif self.malformed == 'response_url':
                    url += '&foreign=1'
            else:
                row_number = int(parsed.path.split('/')[-2])
                rows = deepcopy(self.contexts[row_number])
                if self.malformed == 'context_page':
                    rows[0]['pageNumber'] = 0
                elif self.malformed == 'context_text':
                    rows[0]['context'] = None
                elif self.malformed == 'duplicate_hit':
                    rows = [hit(1), hit(1)]
                elif self.malformed == 'context_http':
                    code = 403
                block = {'value': rows[offset:offset + top], '@odata.count': len(rows)}
        return Response(url, json.dumps(block).encode(), 'application/json', code)


def request(**changes):
    value = {'native': True, 'source': {'provider': 'laserfiche-weblink', 'url': BASE,
             'options': {'page_size': 1}},
             'query': {'terms': ['park'], 'phrases': ['funding was approved']}}
    value.update(changes)
    return value


def run(transport, *, payload=None, caller=None, storage=None):
    return create_engine(provider_transport=transport, storage=storage).execute(
        'search', payload or request(), context=caller or context())


def test_repository_search_folder_scope_exact_matches_paging_citations_raw_and_cleanup():
    transport = SearchTransport()
    result = run(transport)
    assert result.status == 'partial', result.public_dict()
    assert transport.command == '({LF:Basic~="park",option="DFAN"}) & ({LF:LookIn="54",Subfolders=N})'
    assert len(result.data['hits']) == 1 and len(result.data['records']) == 2
    match = result.data['hits'][0]['matches'][0]
    assert match['page'] == 3 and match['completeness'] == 'partial'
    assert match['citation_url'] == ROOT + '/Entries/71'
    assert result.coverage['result_pages'] == 2 and result.coverage['context_pages'] == 3
    assert result.coverage['result_collection_complete'] and not result.coverage['truncated']
    assert not result.coverage['catalog_complete'] and not result.coverage['full_document_text_searched']
    state = result.coverage['search_task']
    assert state['cancellation_requested'] and state['cancellation_confirmed']
    assert [url for url, call in transport.calls if call['method'] == 'DELETE'] == [TASK_URL]
    assert result.data['records'][0]['original']['unknown'] == {'keep': [False, None]}
    for bundle in result.data['bundles']:
        for capture in [bundle['capture'], *bundle['captures']]:
            raw = base64.b64decode(capture['content_base64'])
            assert hashlib.sha256(raw).hexdigest() == capture['sha256']
            assert json.loads(raw) == capture['original_values']
    assert 'secret-read-token' not in json.dumps(result.public_dict())


def test_repository_search_literal_query_cannot_change_folder_or_options():
    transport = SearchTransport()
    term = 'O\'Leary "x" [*]?~\\ } & {LF:LookIn="999"}'
    result = run(transport, payload=request(query={'terms': [term]}))
    assert result.status == 'partial'
    assert transport.command == ('({LF:Basic~="O\'\'Leary ""x"" \\[\\*\\]\\?\\~\\\\ } & '
                                 '{LF:LookIn=""999""}",option="DFAN"}) & ({LF:LookIn="54",Subfolders=N})')


@pytest.mark.parametrize('malformed', ['start', 'task_id', 'task_type', 'task_error', 'result_uri',
                                       'parent', 'row_id', 'count', 'echo', 'response_url'])
def test_repository_search_invalid_scope_or_contract_never_empty_success(malformed):
    transport = SearchTransport(malformed=malformed)
    result = run(transport)
    assert result.status == 'failed', result.public_dict()
    assert not result.data['hits'] and not result.data['records']
    assert 'secret-read-token' not in json.dumps(result.public_dict())
    assert 'private-error' not in json.dumps(result.public_dict())
    assert all('unowned' not in url and 'r-other' not in url for url, _ in transport.calls)
    if malformed != 'start':
        assert transport.stopped


@pytest.mark.parametrize('malformed', ['context_page', 'context_text', 'context_http', 'duplicate_hit'])
def test_repository_search_context_failure_preserves_metadata_and_partial(malformed):
    transport = SearchTransport(malformed=malformed)
    # One page avoids a duplicate hit only becoming visible on the second page.
    payload = request()
    payload['source']['options']['page_size'] = 100
    result = run(transport, payload=payload)
    assert result.status == 'partial' and len(result.data['records']) == 2
    assert result.coverage['failures'] and transport.stopped
    assert all(record['normalized']['content_availability'] == 'metadata_only' for record in result.data['records'])


def test_repository_search_duplicate_entry_across_pages_retains_only_verified_page():
    result = run(SearchTransport(malformed='duplicate_entry'))
    assert result.status == 'partial' and len(result.data['records']) == 1
    assert not result.coverage['result_collection_complete']


@pytest.mark.parametrize('query', [{'terms': []}, {'terms': ['bad\nvalue']}, {'date_from': '2026-01-01'},
                                  {'record_types': ['meeting']}, {'namespaces': ['other']}])
def test_repository_search_invalid_or_unmapped_query_has_no_network(query):
    transport = SearchTransport()
    assert run(transport, payload=request(query=query)).status in {'failed', 'unsupported'}
    assert not transport.calls


def test_repository_search_credentials_and_namespace_denial_no_network():
    for caller in [OperationContext(), context(allowed_namespaces=('other',))]:
        transport = SearchTransport()
        assert run(transport, caller=caller).status == 'failed'
        assert not transport.calls
    transport = SearchTransport()
    unsupported = request()
    unsupported['source']['url'] = 'https://records.example.org/WebLink/Browse.aspx'
    assert run(transport, payload=unsupported).status == 'unsupported' and not transport.calls


def test_repository_search_record_page_and_api_byte_bounds_cleanup():
    transport = SearchTransport()
    limited = run(transport, payload=request(bounds={'max_records': 1, 'max_pages': 1}))
    assert limited.status == 'partial' and limited.coverage['truncated']
    assert len(limited.data['records']) == 1 and transport.stopped
    assert not limited.coverage['result_collection_complete']
    transport = SearchTransport()
    limited = run(transport, payload=request(bounds={'transfer_bytes': 900}))
    assert limited.status == 'failed' and not limited.data['records']
    assert all(call['byte_limit'] <= 900 for _, call in transport.calls)
    assert limited.coverage['search_task']['cancellation_requested']


def test_repository_search_cancellation_and_unconfirmed_cleanup_are_explicit():
    caller = context()
    transport = SearchTransport(on_poll=caller.cancellation.set, cleanup_status='InProgress')
    result = run(transport, caller=caller)
    assert result.status == 'cancelled' and transport.stopped
    state = result.coverage['search_task']
    assert state['cancellation_accepted'] and not state['cancellation_confirmed']
    assert state['cleanup_unconfirmed'] and state['next_action']
    assert not any('/ContextHits' in url or '/Results?' in url for url, _ in transport.calls)


def test_repository_search_empty_and_metadata_only_results_remain_scoped():
    transport = SearchTransport()
    transport.rows = []
    empty = run(transport)
    assert empty.status == 'partial' and not empty.data['hits']
    assert empty.coverage['result_collection_complete'] and transport.stopped
    transport = SearchTransport()
    transport.contexts = {1: [], 2: []}
    metadata = run(transport, payload=request(query={'terms': ['Budget'], 'record_types': ['document']}))
    assert metadata.status == 'partial' and len(metadata.data['hits']) == 2
    assert all(record['normalized']['content_availability'] == 'metadata_only' for record in metadata.data['records'])


def test_repository_search_http_native_dispatch_and_trusted_credentials():
    from starlette.testclient import TestClient
    from civic_data_connectors.transports.http import create_app
    from civic_data_connectors.transports.runtime import Principal, ServiceConfig

    transport = SearchTransport()
    token = 'synthetic-service-token-for-native-search'
    principal = Principal(credentials={'laserfiche_token': 'secret-read-token'})
    with TestClient(create_app(create_engine(provider_transport=transport),
                    ServiceConfig(tokens={token: principal})), base_url='http://127.0.0.1') as client:
        response = client.post('/v1/operations/search', json=request(), headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == 200
    result = response.json()
    assert result['status'] == 'partial' and len(result['data']['hits']) == 1, result
    assert result['coverage']['native_search'] and result['coverage']['search_task']['cancellation_confirmed']
    assert 'secret-read-token' not in response.text


def test_repository_search_persistence_reopen_and_zip_preserve_excerpts_and_raw(tmp_path):
    result = run(SearchTransport())
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'records.sqlite'))
    imported = owner.execute('import_bundle', {'result': result.public_dict(), 'persist': True})
    assert imported.status == 'partial' and imported.data['persisted'], imported.public_dict()
    assert all(owner.storage.get('captures', capture['sha256'], scope=context().scope) is not None
               for capture in result.data['captures'])
    repeated = owner.execute('import_bundle', {'result': result.public_dict(), 'persist': True})
    assert all(change['outcome'] == 'unchanged' for change in repeated.data['changes'])
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'records.sqlite'))
    found = reopened.execute('search', {'query': request()['query']})
    assert found.status == 'partial' and len(found.data['hits']) == 1, found.public_dict()
    assert found.data['hits'][0]['identity']['namespace'] == NAMESPACE
    # Export the import's combined bundle, including every page/context capture.
    bundle = imported.data['bundle']
    exported = reopened.execute('export', {'bundle': bundle, 'format': 'zip'})
    assert exported.status == 'completed', exported.public_dict()
    destination = create_engine(storage=SQLiteStorage(tmp_path / 'destination.sqlite'))
    restored = destination.execute('import_bundle', {'format': 'zip', 'persist': True},
                                  content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed', restored.public_dict()
    assert len(restored.data['bundle']['captures']) == len(bundle['captures'])
    for capture in restored.data['bundle']['captures']:
        with destination.storage.open_capture(capture['storage_reference'], scope=context().scope) as stream:
            assert hashlib.sha256(stream.read()).hexdigest() == capture['sha256']
    again = destination.execute('search', {'query': request()['query']})
    assert again.data['hits'][0]['matches'] == found.data['hits'][0]['matches']
