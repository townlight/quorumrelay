"""Bounded replay of a captured public Tyler calendar response."""
import base64
import json
from pathlib import Path

import pytest

from civic_data_connectors import Source, create_engine
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.storage import SQLiteStorage
from test_provider_discovery import FakeTransport, make_engine, request

ROOT = Path(__file__).parents[1]
CAPTURE = (ROOT / 'docs/capabilities/evidence/tyler-liberty/calendar.json').read_bytes()
ORIGIN = 'https://libertycountytxapp.meetingmanager.tylerapp.com'
SOURCE = ORIGIN + '/392259prod/tylermm/calendar/'
BASE = ORIGIN + '/tylermmcalendar392259prod/'


def test_observed_empty_type_selection_and_checkpoint_binding():
    engine, transport = make_engine(lambda *args: CAPTURE)
    req = request('tyler-meeting-manager', SOURCE, options={'calendar_api_base': BASE, 'meeting_type_ids': []})
    req['bounds'] = {'date_from': '2026-10-01', 'date_to': '2026-10-31', 'max_records': 1}
    first = engine.execute('discover', req)
    assert first.status == 'partial', first.public_dict()
    assert len(first.data['records']) == 1
    assert json.loads(transport.calls[0][1]['body'])['meetingTypeIds'] == []
    assert first.data['records'][0]['original']['meetingId'] == 3007
    checkpoint = first.coverage['checkpoint']
    assert checkpoint
    req['bounds']['checkpoint'] = checkpoint
    req['source']['options']['meeting_type_ids'] = [-1]
    assert engine.execute('discover', req).status == 'failed'
    assert len(transport.calls) == 1


@pytest.mark.parametrize('selection', [None, [True], ['13'], [-2], [2147483648], list(range(101))])
def test_invalid_type_selection_rejected_before_request(selection):
    engine, transport = make_engine()
    req = request('tyler-meeting-manager', SOURCE,
                  options={'calendar_api_base': BASE, 'meeting_type_ids': selection})
    assert engine.execute('discover', req).status == 'failed'
    assert not transport.calls


def test_captured_discovery_persists_reopens_searches_and_exports(tmp_path):
    transport = FakeTransport(lambda *args: CAPTURE)
    database = tmp_path / 'source.sqlite'
    engine = create_engine(storage=SQLiteStorage(database), provider_transport=transport)
    req = request('tyler-meeting-manager', SOURCE, options={'calendar_api_base': BASE, 'meeting_type_ids': []})
    req['bounds'] = {'date_from': '2026-10-01', 'date_to': '2026-10-31'}
    discovered = engine.execute('discover', req)
    assert discovered.status == 'partial' and len(discovered.data['records']) == 3
    bundle = discovered.data['bundles'][0]
    imported = engine.execute('import_bundle', {'bundle': bundle, 'persist': True})
    assert imported.status == 'completed', imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(database))
    found = reopened.execute('search', {'query': {'phrases': ['County Commissioners Court Regular Meeting']}})
    assert found.status == 'partial' and len(found.data['hits']) == 2
    exported = reopened.execute('export', {'bundle': imported.data['bundle'], 'format': 'zip'})
    restored = create_engine(storage=SQLiteStorage(tmp_path / 'destination.sqlite')).execute(
        'import_bundle', {'format': 'zip', 'persist': True}, content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed' and len(restored.data['bundle']['records']) == 3
    assert restored.data['bundle']['capture']['sha256'] == bundle['capture']['sha256']


def test_selected_document_is_bound_and_requires_pdf(tmp_path):
    pdf = b'%PDF-1.4\nsynthetic test\n%%EOF'
    transport = FakeTransport(lambda url, *_: CAPTURE if url.endswith('getMeetingInformationByDate')
                              else Response(url, pdf, 'application/pdf'))
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'doc.sqlite'), provider_transport=transport)
    req = request('tyler-meeting-manager', SOURCE, options={'calendar_api_base': BASE, 'meeting_type_ids': []})
    req['bounds'] = {'date_from': '2026-10-01', 'date_to': '2026-10-31'}
    found = engine.execute('discover', req)
    record = found.data['records'][0]
    assert record['normalized']['documents'][0]['url'] == BASE + 'meetingInformation/Agenda/false/2409'
    assert engine.execute('import_bundle', {'bundle': found.data['bundles'][0], 'persist': True}).status == 'completed'
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'doc.sqlite'), provider_transport=transport)
    fetched = engine.fetch_attachment(Source.from_dict(req['source']), record)
    assert fetched.status == 'completed', fetched.public_dict()
    assert base64.b64decode(fetched.data['attachment']['content_base64']) == pdf
    assert transport.calls[-1][1]['allow_redirects'] is False
    transport.callback = lambda url, *_: Response(url, b'<html>not a PDF</html>', 'text/html')
    assert engine.fetch_attachment(Source.from_dict(req['source']), record).status == 'partial'


def test_observed_native_search_and_page_binding():
    content = (ROOT / 'docs/capabilities/evidence/tyler-liberty/search.json').read_bytes()
    transport = FakeTransport(lambda *args: content)
    engine = create_engine(provider_transport=transport)
    req = {'native': True, 'source': {'provider': 'tyler-meeting-manager', 'url': SOURCE,
           'options': {'calendar_api_base': BASE, 'meeting_type_ids': []}},
           'query': {'terms': ['court'], 'date_from': '2026-10-01', 'date_to': '2026-10-31'}}
    result = engine.execute('search', req)
    assert result.status == 'partial', result.public_dict()
    assert len(result.data['bundle']['records']) == 3 and result.coverage['provider_total'] == 3
    body = json.loads(transport.calls[0][1]['body'])
    assert body['lastPage'] is False and body['pageNo'] == 1 and body['filter']['meetingTypeIds'] == []
    assert result.data['bundle']['records'][0]['original']['meetingId'] == 3030
    assert result.coverage['catalog_complete'] is False


def test_selected_detail_requires_stored_identity_and_matches_response(tmp_path):
    detail = (ROOT / 'docs/capabilities/evidence/tyler-liberty/detail.json').read_bytes()
    transport = FakeTransport(lambda url, *_: detail if url.endswith('/getMeeting') else CAPTURE)
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'detail.sqlite'), provider_transport=transport)
    req = request('tyler-meeting-manager', SOURCE, options={'calendar_api_base': BASE, 'meeting_type_ids': []})
    req['bounds'] = {'date_from': '2026-10-01', 'date_to': '2026-10-31'}
    source = Source.from_dict(req['source'])
    discovery = engine.execute('discover', req)
    record = discovery.data['records'][0]
    external_id = record['identity']['external_id']
    assert engine.fetch_record(source, external_id).status == 'failed'
    assert engine.execute('import_bundle', {'bundle': discovery.data['bundles'][0], 'persist': True}).status == 'completed'
    result = engine.fetch_record(source, external_id)
    assert result.status == 'partial', result.public_dict()
    assert result.data['records'][0]['original']['meetingId'] == 3007
    assert json.loads(transport.calls[-1][1]['body']) == {'meetingId': 3007, 'recurringId': 3027, 'activity': 'View'}
    modified = json.loads(detail)
    modified['recurringId'] = 999
    transport.callback = lambda *_: json.dumps(modified).encode()
    assert engine.fetch_record(source, external_id).status == 'failed'


def test_search_page_checkpoint_is_bound_to_query_and_size():
    rows = json.loads((ROOT / 'docs/capabilities/evidence/tyler-liberty/search.json').read_bytes())['searchResults']
    def page(_, kwargs, __):
        body = json.loads(kwargs['body'])
        size, number = body['pageSize'], body['pageNo']
        return {'searchResults': rows[(number - 1) * size:number * size], 'totalElements': len(rows)}
    transport = FakeTransport(page)
    engine = create_engine(provider_transport=transport)
    req = {'native': True, 'source': {'provider': 'tyler-meeting-manager', 'url': SOURCE,
           'options': {'calendar_api_base': BASE, 'meeting_type_ids': []}},
           'query': {'terms': ['court'], 'date_from': '2026-10-01', 'date_to': '2026-10-31'},
           'bounds': {'max_records': 1}}
    first = engine.execute('search', req)
    req['bounds']['checkpoint'] = first.coverage['checkpoint']
    second = engine.execute('search', req)
    assert second.status == 'partial' and json.loads(transport.calls[-1][1]['body'])['pageNo'] == 2
    assert first.data['bundle']['records'][0]['identity'] != second.data['bundle']['records'][0]['identity']
    req['bounds']['max_records'] = 2
    assert engine.execute('search', req).status == 'failed'


def test_stored_detail_and_attachment_reject_different_calendar_source(tmp_path):
    detail = (ROOT / 'docs/capabilities/evidence/tyler-liberty/detail.json').read_bytes()
    transport = FakeTransport(lambda url, *_: detail if url.endswith('/getMeeting') else CAPTURE)
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'binding.sqlite'), provider_transport=transport)
    options = {'calendar_api_base': BASE, 'meeting_type_ids': []}
    req = request('tyler-meeting-manager', SOURCE, options=options)
    req['bounds'] = {'date_from': '2026-10-01', 'date_to': '2026-10-31'}
    found = engine.execute('discover', req)
    record = found.data['records'][0]
    assert engine.execute('import_bundle', {'bundle': found.data['bundles'][0], 'persist': True}).status == 'completed'
    foreign_source = Source('tyler-meeting-manager', ORIGIN + '/other/tylermm/calendar/', options=options)
    before = len(transport.calls)
    assert engine.fetch_record(foreign_source, record['identity']['external_id']).status == 'failed'
    assert engine.fetch_attachment(foreign_source, record).status == 'failed'
    assert len(transport.calls) == before
