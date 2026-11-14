"""Observed Akron v25 JSON-in-HTML model; synthetic faults, no browser/network."""

import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from quorumrelay import OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers.onbase import listing_rows, search_model


SOURCE = Source('onbase', 'https://onlinedocs.akronohio.gov/OnBaseAgendaOnline/')
MODEL = json.loads((Path(__file__).parents[1] /
    'docs/capabilities/evidence/onbase-search-model/search-model.json').read_text())


def page(model):
    return ('<script>showSearchResults(new SearchResults(' + json.dumps(model) +
            '));</script>').encode()


def test_observed_model_preserves_native_identity_dates_flags_and_declared_document_links():
    rows = listing_rows(SOURCE, page(MODEL))
    assert len(rows) == 3
    normalized, raw, kind = rows[0]
    assert kind == 'meeting' and normalized['external_id'] == '704'
    assert normalized['meeting_date'] == '2026-10-26'
    assert normalized['source_start'] == '2026-10-26T18:30:00-04:00'
    assert raw == MODEL['Meetings'][0]
    assert normalized['recordings'] == []  # null Media does not invent video.
    assert normalized['documents'][0]['url'].endswith('documentType=1&meetingId=704')
    assert '%2F' not in normalized['documents'][0]['url'].split('/DownloadFile/')[1]
    assert search_model(page(MODEL))['NoMoreResults'] is False


def test_model_is_data_only_and_ignores_markup_outside_scripts():
    raw = b'<div>showSearchResults(new SearchResults({bad syntax</div>' + page(MODEL)
    assert len(listing_rows(SOURCE, raw)) == 3
    assert search_model(b'<p>showSearchResults(new SearchResults({}))</p>') is None
    assert listing_rows(SOURCE, page({**MODEL, 'Meetings': []})) == []


@pytest.mark.parametrize('fault', ['duplicate', 'invalid_id', 'boolean_id', 'bad_date',
    'unsafe_document', 'missing_document', 'provider_error', 'ambiguous'])
def test_model_rejects_ambiguous_identity_invalid_data_and_reported_errors(fault):
    model = deepcopy(MODEL)
    if fault == 'duplicate':
        model['Meetings'].append(deepcopy(model['Meetings'][0]))
    elif fault == 'invalid_id':
        model['Meetings'][0]['ID'] = '../42'
    elif fault == 'boolean_id':
        model['Meetings'][0]['ID'] = True
    elif fault == 'bad_date':
        model['Meetings'][0]['Time'] = 'not-a-date'
    elif fault == 'unsafe_document':
        model['Meetings'][0]['AgendaUniqueName'] = '../other'
    elif fault == 'missing_document':
        model['Meetings'][0]['AgendaUniqueName'] = None
    elif fault == 'provider_error':
        model['ErrorOccurred'] = True
    raw = page(model) * (2 if fault == 'ambiguous' else 1)
    with pytest.raises(ValueError):
        listing_rows(SOURCE, raw)


def test_model_packet_code_is_client_declared_six_and_unknown_fields_survive():
    model = deepcopy(MODEL)
    row = model['Meetings'][0]
    row.update(IsMinutesPacketAvailable=True, MinutesPacketUniqueName='minutes packet',
               FutureField={'empty': [], 'zero': 0})
    normalized, original, _ = listing_rows(SOURCE, page(model))[0]
    packet = next(d for d in normalized['documents'] if d['kind'] == 'minutes_packet')
    assert packet['url'].endswith('minutes%20packet.pdf?documentType=6&meetingId=704&isAttachment=true')
    assert original['FutureField'] == row['FutureField']


def test_model_actual_sqlite_import_retry_reopen_search_and_zip(tmp_path):
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'owner.sqlite'))
    result = owner.normalize(SOURCE, page(MODEL), input_format='onbase-public-listing-html')
    assert result.status == 'completed', result.public_dict()
    request = {'result': result.public_dict(), 'persist': True}
    assert owner.execute('import_bundle', request).status == 'completed'
    assert all(c['outcome'] == 'unchanged' for c in owner.execute('import_bundle', request).data['changes'])
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'owner.sqlite'))
    hits = reopened.execute('search', {'query': {'phrases': ['October 26, 2026']}})
    assert {h['identity']['external_id'] for h in hits.data['hits']} == {'704'}
    exported = reopened.execute('export', {'bundle': result.data, 'format': 'zip'})
    destination = create_engine(storage=SQLiteStorage(tmp_path / 'destination.sqlite'))
    restored = destination.execute('import_bundle', {'format': 'zip', 'persist': True},
        content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed', restored.public_dict()
    originals = {item.value['identity']['external_id']: item.value['original']
                 for item in destination.storage.list('records', scope=OperationContext().scope)}
    assert originals['704'] == MODEL['Meetings'][0]


def test_public_window_get_resumes_without_duplicate_and_keeps_truncation_honest():
    calls = []

    class Transport:
        def request(self, url, **kwargs):
            calls.append((url, kwargs))
            assert kwargs['allow_redirects'] is False
            return Response(url, page(MODEL), 'text/html')

    engine = create_engine(provider_transport=Transport())
    request = {'source': SOURCE.public_dict(), 'bounds': {
        'date_from': '2026-10-01', 'date_to': '2026-10-31', 'max_records': 1}}
    first = engine.execute('discover', request)
    assert first.status == 'partial' and len(first.data['records']) == 1
    assert first.coverage['catalog_complete'] is False
    assert calls[0][0].endswith('dropid=11&dropsv=10%2F01%2F2026&dropev=10%2F31%2F2026')
    ids = [r['identity']['external_id'] for r in first.data['records']]
    while first.coverage['checkpoint']:
        request['bounds']['checkpoint'] = first.coverage['checkpoint']
        first = engine.execute('discover', request)
        ids.extend(r['identity']['external_id'] for r in first.data['records'])
    assert ids == ['704', '703', '702']
    assert len(calls) == 3  # Same response/offset, no undocumented server pagination.


@pytest.mark.parametrize('failure', ['redirect', 'oversized', 'changed_resume'])
def test_window_failures_and_transfer_ceiling_cannot_appear_as_complete_empty(failure):
    responses = 0

    class Transport:
        def request(self, url, **kwargs):
            nonlocal responses
            responses += 1
            assert kwargs['byte_limit'] == 10000
            model = deepcopy(MODEL)
            if failure == 'changed_resume' and responses > 1:
                model['Meetings'][0]['Name'] += ' changed'
            content = b'x' * 10001 if failure == 'oversized' else page(model)
            return Response(url + '&unexpected=redirect' if failure == 'redirect' else url,
                            content, 'text/html', 302 if failure == 'redirect' else 200)

    engine = create_engine(provider_transport=Transport())
    request = {'source': SOURCE.public_dict(), 'bounds': {'date_from': '2026-10-01',
        'date_to': '2026-10-31', 'max_records': 1, 'parser_bytes': 20000, 'transfer_bytes': 10000}}
    result = engine.execute('discover', request)
    if failure == 'changed_resume':
        request['bounds']['checkpoint'] = result.coverage['checkpoint']
        result = engine.execute('discover', request)
    assert result.status == 'failed', result.public_dict()
    assert result.errors and not result.data['records']
