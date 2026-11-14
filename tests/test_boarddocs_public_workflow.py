"""Opt-in public BoardDocs flow; third-party-source-shaped synthetic responses."""

import base64
from copy import deepcopy
import json

import pytest

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from test_boarddocs_public_helpers import DETAIL, SOURCE


ROWS = [{'unique': 'C55TD0000001', 'numberdate': '20261112', 'unid': 'NATIVE1',
         'name': 'Board of Trustees'},
        {'unique': 'C55TD0000002', 'numberdate': '20261113', 'unid': 'NATIVE2',
         'name': 'Special Meeting'}]


class Transport:
    def __init__(self):
        self.calls = []
        self.listing = json.dumps(ROWS).encode()
        self.detail = DETAIL
        self.status = 200

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs['allow_redirects'] is False
        assert kwargs['method'] == 'POST'
        body = self.listing if 'BD-GetMeetingsList' in url else self.detail
        return Response(url, body, 'application/json' if body == self.listing else 'text/html', self.status)


def request():
    return {'source': SOURCE.public_dict(), 'bounds': {'date_from': '2026-11-01',
        'date_to': '2026-11-30', 'max_records': 1}}


def test_optin_listing_preserves_raw_and_resumes_at_record_without_server_paging():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    req = request()
    first = engine.execute('discover', req)
    assert first.status == 'partial', first.public_dict()
    assert first.data['records'][0]['normalized']['title'] == 'Board of Trustees'
    assert first.data['records'][0]['original'] == ROWS[0]
    assert first.coverage['catalog_complete'] is False
    assert first.coverage['checkpoint']
    req['bounds']['checkpoint'] = first.coverage['checkpoint']
    second = engine.execute('discover', req)
    assert [r['identity']['external_id'] for r in second.data['records']] == ['C55TD0000002']
    assert second.coverage['checkpoint'] is None
    assert transport.calls[0][0].endswith('/mi/grand/Board.nsf/BD-GetMeetingsList?open')
    assert b'current_committee_id=C55TD0000001' == transport.calls[0][1]['body']


@pytest.mark.parametrize('fault', ['denied', 'changed', 'committee', 'transfer'])
def test_failures_do_not_trigger_bypass_or_silently_complete(fault):
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    req = request()
    if fault == 'denied':
        transport.status = 403
    elif fault == 'transfer':
        req['bounds']['transfer_bytes'] = 1
    if fault in {'changed', 'committee'}:
        first = engine.execute('discover', req)
        req['bounds']['checkpoint'] = first.coverage['checkpoint']
        if fault == 'changed':
            transport.listing = json.dumps([*ROWS, {**ROWS[0], 'unique': 'NEW'}]).encode()
        else:
            req['source']['options']['boarddocs_committee_id'] = 'OTHER'
    result = engine.execute('discover', req)
    assert result.status == 'failed', result.public_dict()
    assert result.errors
    if fault == 'denied':
        assert len(transport.calls) == 1
    if fault == 'committee':
        assert len(transport.calls) == 1  # Binding rejected before another request.


def test_selected_detail_is_stored_identity_bound_and_survives_reopen_search_zip(tmp_path):
    transport = Transport()
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'records.sqlite'), provider_transport=transport)
    assert engine.fetch_record(SOURCE, ROWS[0]['unique']).status == 'failed'
    assert not transport.calls
    discovered = engine.execute('discover', request())
    assert engine.execute('import_bundle', {'bundle': discovered.data['bundles'][0], 'persist': True}).status == 'completed'
    detailed = engine.fetch_record(SOURCE, ROWS[0]['unique'])
    assert detailed.status == 'partial', detailed.public_dict()
    assert detailed.data['records'][0]['identity'] == discovered.data['records'][0]['identity']
    assert detailed.data['records'][0]['normalized']['documents'] == []
    assert detailed.data['records'][0]['normalized']['source_public_file_links']
    assert engine.execute('import_bundle', {'result': detailed.public_dict(), 'persist': True}).status == 'partial'
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'records.sqlite'), provider_transport=transport)
    hits = reopened.execute('search', {'query': {'terms': ['Budget']}})
    assert {h['identity']['external_id'] for h in hits.data['hits']} == {ROWS[0]['unique']}
    assert reopened.fetch_record(SOURCE, ROWS[0]['unique']).status == 'partial'
    exported = reopened.execute('export', {'bundle': detailed.data, 'format': 'zip'})
    destination = create_engine(storage=SQLiteStorage(tmp_path / 'destination.sqlite'))
    restored = destination.execute('import_bundle', {'format': 'zip', 'persist': True},
                                   content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed', restored.public_dict()
    assert destination.execute('search', {'query': {'terms': ['Budget']}}).data['hits']


def test_selected_detail_wrong_date_retains_capture_and_keeps_stored_record(tmp_path):
    transport = Transport()
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'records.sqlite'), provider_transport=transport)
    result = engine.execute('discover', request())
    engine.execute('import_bundle', {'bundle': result.data['bundles'][0], 'persist': True})
    transport.detail = DETAIL.replace(b'November 12, 2026', b'November 11, 2026')
    detailed = engine.fetch_record(SOURCE, ROWS[0]['unique'])
    assert detailed.status == 'partial' and detailed.errors
    assert detailed.data['capture']['content_base64'] == base64.b64encode(transport.detail).decode()
    assert detailed.data['records'] == []
    stored = list(engine.storage.list('records', scope=OperationContext().scope))[0].value
    assert stored['original'] == ROWS[0]


def test_source_without_explicit_committee_keeps_original_saved_pdf_path():
    transport = Transport()
    source = Source('boarddocs', SOURCE.url)
    result = create_engine(provider_transport=transport).execute('discover', {'source': source.public_dict()})
    assert result.status != 'completed' and not transport.calls


def test_unrecognized_source_and_parser_hook_cannot_open_other_hosts():
    transport = Transport()
    source = deepcopy(SOURCE.public_dict())
    source['url'] = 'https://example.com/mi/grand/Board.nsf/Public'
    result = create_engine(provider_transport=transport).execute('discover', {'source': source})
    assert result.status == 'failed' and not transport.calls
