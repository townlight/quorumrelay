"""Assigned metadata values: bounded vendor contracts, real import/search/export."""

import base64
import hashlib
import json
from copy import deepcopy

import pytest

from quorumrelay import Bounds, Source, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from test_repository_discovery import BASE, RepositoryTransport, context, entry
from test_repository_fetch import ENTRY_URL
from test_repository_search import ROOT, SearchTransport, request as search_request
from test_repository_text import PageTransport

FIELDS = ENTRY_URL + '/Fields'
NEXT = FIELDS + '?$skiptoken=next'


def field(identity=1, name='Topic', values=None):
    return {'id': identity, 'name': name, 'fieldType': 'String', 'isMultiValue': True,
            'hasMoreValues': False, 'values': ['park funding', 'second supplied value'] if values is None else values,
            'unknown': {'preserve': [False, None]}}


class FieldTransport(PageTransport):
    def __init__(self, *, malformed=None, on_field=None):
        super().__init__()
        self.pages[FIELDS] = {'value': [field()], '@odata.count': 2, '@odata.nextLink': NEXT}
        self.pages[NEXT] = {'value': [field(2, 'Empty', [''])], '@odata.count': 2}
        self.malformed, self.on_field = malformed, on_field

    def request(self, url, **kwargs):
        if url in {FIELDS, NEXT}:
            if self.on_field:
                self.on_field()
            if self.malformed == 'echo':
                self.pages[url]['echo'] = 'secret-read-token'
            if self.malformed == 'timeout':
                self.calls.append((url, kwargs))
                raise TimeoutError('private transport detail')
            result = super().request(url, **kwargs)
            if self.malformed == 'url':
                return Response(result.url.replace('/71/', '/72/'), result.content, result.content_type)
            return result
        return super().request(url, **kwargs)


def source(option=True):
    return Source('laserfiche-weblink', BASE, options={'repository_include_fields': option})


def fetch(transport, **kwargs):
    return create_engine(provider_transport=transport).fetch_record(source(), '71',
                context=kwargs.pop('context', context()), **kwargs)


def test_repository_fields_multivalue_raw_identity_search_reopen_and_zip(tmp_path):
    transport = FieldTransport()
    result = fetch(transport)
    assert result.status == 'completed', result.public_dict()
    record = result.data['records'][0]
    assert record['original'] == entry(71)  # Supplementary fields never rewrite GetEntry bytes.
    assert record['normalized']['repository_fields'] == [field(), field(2, 'Empty', [''])]
    assert result.coverage['field_metadata'][0]['complete']
    proof = record['extensions']['repository_field_provenance']
    assert proof[0]['field_index'] == 0 and proof[0]['capture_sha256'] == result.data['captures'][0]['sha256']
    assert proof[1]['field_index'] == 1 and proof[1]['capture_sha256'] == result.data['captures'][1]['sha256']
    assert proof[0]['citation_url'] == ENTRY_URL and proof[0]['retrieval_url'] == FIELDS
    assert record['relationships'][0]['identity']['external_id'] == '54'
    assert 'meeting_date' not in record['normalized']
    for capture in result.data['captures']:
        raw = base64.b64decode(capture['content_base64'])
        assert hashlib.sha256(raw).hexdigest() == capture['sha256']
        assert json.loads(raw) == capture['original_values']
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'fields.sqlite'))
    imported = owner.execute('import_bundle', {'result': result.public_dict(), 'persist': True})
    assert imported.status == 'completed' and imported.data['persisted']
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'fields.sqlite'))
    found = reopened.execute('search', {'query': {'phrases': ['second supplied value']}})
    assert len(found.data['hits']) == 1, found.public_dict()
    assert found.data['hits'][0]['matches'][0]['field'].startswith('normalized.repository_fields')
    export = reopened.execute('export', {'bundle': result.data, 'format': 'zip'})
    assert export.status == 'completed', export.public_dict()
    destination = create_engine(storage=SQLiteStorage(tmp_path / 'destination.sqlite'))
    restored = destination.execute('import_bundle', {'format': 'zip', 'persist': True},
                                  content=base64.b64decode(export.data['content_base64']))
    assert restored.status == 'completed', restored.public_dict()
    assert restored.data['bundle']['records'][0]['normalized'] == record['normalized']
    for capture in restored.data['bundle']['captures']:
        with destination.storage.open_capture(capture['storage_reference'], scope=context().scope) as stream:
            assert hashlib.sha256(stream.read()).hexdigest() == capture['sha256']
    changed = FieldTransport()
    changed.pages[FIELDS]['value'][0]['values'][1] = 'changed supplied value'
    revision = fetch(changed)
    assert revision.data['records'][0]['identity'] == record['identity']
    assert revision.data['records'][0]['normalized_sha256'] != record['normalized_sha256']


@pytest.mark.parametrize('malformed', ['foreign', 'cycle', 'duplicate', 'bad_values', 'bad_count',
                                       'unknown_completeness', 'more_values', 'echo', 'url', 'timeout', 'http'])
def test_repository_fields_partial_failure_retains_metadata_and_obtained_values(malformed):
    transport = FieldTransport(malformed=malformed)
    if malformed == 'foreign':
        transport.pages[NEXT]['@odata.nextLink'] = FIELDS.replace('/71/', '/72/')
    elif malformed == 'cycle':
        transport.pages[NEXT]['@odata.nextLink'] = FIELDS
    elif malformed == 'duplicate':
        transport.pages[NEXT]['value'] = [field(1, 'Another name')]
    elif malformed == 'bad_values':
        transport.pages[NEXT]['value'][0]['values'] = [5]
    elif malformed == 'bad_count':
        transport.pages[NEXT]['@odata.count'] = 3
    elif malformed == 'unknown_completeness':
        del transport.pages[NEXT]['value'][0]['hasMoreValues']
    elif malformed == 'more_values':
        transport.pages[NEXT]['value'][0]['hasMoreValues'] = True
    elif malformed == 'http':
        transport.statuses[NEXT] = 403
    result = fetch(transport)
    assert result.status == 'partial', result.public_dict()
    assert result.data['records'][0]['identity']['external_id'] == '71'
    assert result.data['records'][0]['original'] == entry(71)
    assert not result.coverage['field_metadata'][0]['complete']
    assert result.coverage['failures']
    assert 'secret-read-token' not in json.dumps(result.public_dict())
    assert 'private transport detail' not in json.dumps(result.public_dict())
    assert all('/72/Fields' not in url for url, _ in transport.calls)


def test_repository_fields_absent_empty_and_null_remain_distinct():
    transport = FieldTransport()
    rows = [field(1, 'Null'), field(2, 'Absent'), field(3, 'Empty', [])]
    rows[0]['values'] = None
    del rows[1]['values']
    transport.pages[FIELDS] = {'value': rows, '@odata.count': 3}
    result = fetch(transport)
    assert result.status == 'completed', result.public_dict()
    assert result.data['records'][0]['normalized']['repository_fields'] == rows


@pytest.mark.parametrize('option', [1, 'true', None])
def test_repository_fields_option_requires_boolean_before_network(option):
    transport = FieldTransport()
    result = create_engine(provider_transport=transport).fetch_record(source(option), '71', context=context())
    assert result.status == 'failed' and not transport.calls


def test_repository_fields_bounds_cancel_and_default_no_extra_network():
    default = FieldTransport()
    result = create_engine(provider_transport=default).fetch_record(Source('laserfiche-weblink', BASE), '71', context=context())
    assert result.status == 'completed' and [url for url, _ in default.calls] == [ENTRY_URL]
    limited = fetch(FieldTransport(), bounds=Bounds(max_records=1, max_pages=1))
    assert limited.status == 'partial' and limited.coverage['field_metadata'][0]['truncated']
    caller = context()
    cancelled = fetch(FieldTransport(on_field=caller.cancellation.set), context=caller)
    assert cancelled.status == 'cancelled' and cancelled.data['records'][0]['identity']['external_id'] == '71'
    tiny = FieldTransport()
    limited = fetch(tiny, bounds=Bounds(transfer_bytes=1))
    assert limited.status == 'partial' and not limited.coverage['field_metadata'][0]['complete']
    assert len([url for url, _ in tiny.calls if url in {FIELDS, NEXT}]) == 1


def test_repository_fields_and_page_text_share_captures_partial_and_supplementary_budget():
    transport = FieldTransport()
    result = fetch(transport, include_text=True)
    assert result.status == 'completed', result.public_dict()
    assert result.coverage['field_metadata'][0]['complete'] and result.coverage['text_complete']
    assert len(result.data['captures']) == 6
    assert result.data['records'][0]['normalized']['repository_fields'][0]['values'][1] == 'second supplied value'
    # A field failure must remain partial when subsequent page text succeeds.
    transport = FieldTransport()
    transport.statuses[NEXT] = 403
    partial = fetch(transport, include_text=True)
    assert partial.status == 'partial' and partial.coverage['failures']
    transport = FieldTransport(malformed='timeout')
    result = fetch(transport, include_text=True)
    assert result.status == 'partial'
    assert not any('/Document/Pages' in url for url, _ in transport.calls)


def test_repository_fields_discovery_saved_capture_and_native_search():
    class DiscoveryFields(RepositoryTransport):
        def request(self, url, **kwargs):
            if '/Fields' in url:
                self.calls.append((url, kwargs))
                block = {'value': [field()], '@odata.count': 1}
                return Response(url, json.dumps(block).encode(), 'application/json')
            return super().request(url, **kwargs)
    transport = DiscoveryFields()
    result = create_engine(provider_transport=transport).discover(source(), context=context())
    assert result.status == 'completed' and len(result.coverage['field_metadata']) == 2, result.public_dict()
    assert all(row['normalized']['repository_fields'] == [field()] for row in result.data['records'])
    assert len(result.data['captures']) == 2
    raw = json.dumps({'value': [entry(71)]}).encode()
    transport = DiscoveryFields()
    saved = create_engine(provider_transport=transport).execute('discover', {'source': source().public_dict()},
                                                               content=raw, context=context())
    assert saved.status == 'completed' and not transport.calls
    assert saved.data['records'][0]['normalized']['repository_fields'] == entry(71)['fields']
    class SearchFields(SearchTransport):
        def request(self, url, **kwargs):
            if url.startswith(ROOT + '/Entries/') and '/Fields' in url:
                self.calls.append((url, kwargs))
                return Response(url, json.dumps({'value': [field()], '@odata.count': 1}).encode(), 'application/json')
            return super().request(url, **kwargs)
    transport = SearchFields()
    payload = deepcopy(search_request(query={'phrases': ['second supplied value']}))
    payload['source']['options']['repository_include_fields'] = True
    result = create_engine(provider_transport=transport).execute('search', payload, context=context())
    assert result.status == 'partial' and len(result.data['hits']) == 2, result.public_dict()
    assert len(result.coverage['field_metadata']) == 2 and transport.stopped
    assert len(result.data['captures']) == 5


def test_repository_fields_discovery_later_page_failure_keeps_supplemental_captures(tmp_path):
    class LaterFailure(RepositoryTransport):
        def request(self, url, **kwargs):
            if url == BASE + '?$skiptoken=opaque':
                self.calls.append((url, kwargs))
                return Response(url, b'{}', 'application/json', 403)
            if url == FIELDS:
                self.calls.append((url, kwargs))
                return Response(url, json.dumps({'value': [field()]}).encode(), 'application/json')
            return super().request(url, **kwargs)
    result = create_engine(provider_transport=LaterFailure()).discover(source(), context=context())
    assert result.status == 'partial' and len(result.data['captures']) == 1, result.public_dict()
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'partial.sqlite'))
    imported = owner.execute('import_bundle', {'result': result.public_dict(), 'persist': True})
    assert imported.status == 'partial' and imported.data['persisted'], imported.public_dict()
    assert owner.storage.get('captures', result.data['captures'][0]['sha256'], scope=context().scope) is not None


def test_repository_discovery_rejects_token_echo_before_capture_or_field_requests():
    transport = RepositoryTransport()
    transport.pages[BASE]['echo'] = 'secret-read-token'
    result = create_engine(provider_transport=transport).discover(source(), context=context())
    assert result.status == 'failed' and result.data is None
    assert 'secret-read-token' not in json.dumps(result.public_dict())
    assert len(transport.calls) == 1
