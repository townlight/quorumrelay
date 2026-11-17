import base64
from copy import deepcopy
import json

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle


SOURCE = 'https://libertycountytxapp.meetingmanager.tylerapp.com/392259prod/tylermm/calendar/'
BASE = 'https://libertycountytxapp.meetingmanager.tylerapp.com/tylermmcalendar392259prod/'


def request():
    return {'native': True, 'source': {'provider': 'tyler-meeting-manager', 'url': SOURCE,
             'options': {'calendar_api_base': BASE}},
            'query': {'terms': ['water'], 'record_types': ['agenda_item'],
                      'date_from': '2026-01-01', 'date_to': '2026-12-31'}}


def row(identity=81):
    return {'agendaItemId': identity, 'itemTitle': 'Water mains', 'description': '<p>Water budget café</p>',
            'outcomeDescription': '<p>Motion passed</p><script>secret-marker</script>',
            'meetingName': 'Council', 'meetingDate': '2026-11-09T18:00:00', 'meetingType': 'Regular',
            'votingOutcome': 'Passed', 'unknown': [False, None]}


class Transport:
    def __init__(self):
        self.calls, self.flag, self.fault, self.context = [], True, None, None
        self.data = {'searchResults': [row()], 'totalElements': 1}

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs['allow_redirects'] is False
        if self.context:
            self.context.cancellation.set()
        if self.fault == 'timeout':
            raise TimeoutError()
        if url.endswith('feature-flags'):
            return Response(url, json.dumps({'agenda-item-outcome': self.flag}).encode(), 'application/json',
                            404 if self.fault == 'flag404' else 200)
        assert url == BASE + 'meetingCalendarSearch/agenda-items/search'
        payload = json.loads(kwargs['body'])
        assert payload == {'searchKeyword': 'water', 'pageNo': payload['pageNo'], 'pageSize': payload['pageSize'],
                           'startDate': '01/01/2026', 'endDate': '12/31/2026',
                           'meetingTypeIds': [-1], 'votingOutcomes': []}
        body = json.dumps(self.data).encode()
        if self.fault == 'oversize':
            body = b'x' * (kwargs['byte_limit'] + 1)
        return Response(url + '/redirect' if self.fault == 'redirect' else url, body, 'application/json',
                        403 if self.fault == 'denied' else 200)


def test_declared_request_native_item_identity_visible_text_and_neutral_workflow(tmp_path):
    transport = Transport()
    database = tmp_path / 'items.sqlite'
    engine = create_engine(storage=SQLiteStorage(database), provider_transport=transport)
    result = engine.execute('search', request())
    assert result.status == 'partial', result.public_dict()
    assert len(result.data['hits']) == 1
    bundle = result.data['bundle']
    record = bundle['records'][0]
    assert record['identity']['record_type'] == 'agenda_item' and record['identity']['external_id'] == '81'
    assert record['identity']['parent'] is None
    assert record['normalized']['meeting_external_id'] is None
    assert record['normalized']['meeting_date'] == '2026-11-09'
    assert record['normalized']['voting_outcome'] == 'Passed'
    assert 'secret-marker' not in record['normalized']['outcome_description']
    assert record['original']['unknown'] == [False, None]
    assert len(bundle['captures']) == 2
    for _ in range(2):
        assert engine.execute('import_bundle', {'bundle': bundle, 'persist': True}).status == 'completed'
    reopened = create_engine(storage=SQLiteStorage(database))
    found = reopened.execute('search', {'query': {'terms': ['café'], 'record_types': ['agenda_item']}})
    assert len(found.data['hits']) == 1 and found.coverage['incomplete_text'] is True
    exported = engine.execute('export', {'bundle': bundle, 'format': 'zip'})
    assert read_bundle(base64.b64decode(exported.data['content_base64']), format='zip') == bundle


def test_explicit_feature_false_or_unknown_is_not_a_successful_empty_search():
    for flag in (False, None):
        transport = Transport()
        transport.flag = flag
        result = create_engine(provider_transport=transport).execute('search', request())
        assert result.status == 'partial' and result.errors[0].code == 'provider_feature_not_enabled'
        assert len(transport.calls) == 1 and 'hits' not in result.data
        assert result.data['bundle']['capture']['content_base64']


@pytest.mark.parametrize('fault', ['timeout', 'flag404', 'redirect', 'denied', 'oversize', 'cancel',
                                  'shape', 'duplicate', 'id', 'date', 'total'])
def test_failed_or_cancelled_native_requests_are_not_zero_hit_acceptance(fault):
    transport, context = Transport(), OperationContext()
    if fault == 'cancel':
        transport.context = context
    elif fault == 'shape':
        transport.data['searchResults'] = {}
    elif fault == 'duplicate':
        transport.data = {'searchResults': [row(), row()], 'totalElements': 2}
    elif fault == 'id':
        transport.data['searchResults'][0]['agendaItemId'] = True
    elif fault == 'date':
        transport.data['searchResults'][0]['meetingDate'] = None
    elif fault == 'total':
        transport.data['totalElements'] = 0
    else:
        transport.fault = fault
    result = create_engine(provider_transport=transport).execute('search', request(), context=context)
    assert result.status == ('cancelled' if fault == 'cancel' else 'failed'), result.public_dict()


def test_page_resume_and_query_binding_are_separate_from_meeting_search():
    transport = Transport()
    transport.data['totalElements'] = 2
    engine = create_engine(provider_transport=transport)
    req = request()
    req['bounds'] = {'max_records': 1}
    first = engine.execute('search', req)
    token = first.coverage['checkpoint']
    assert token
    transport.data['searchResults'] = [row(82)]
    req['bounds']['checkpoint'] = token
    second = engine.execute('search', req)
    assert second.data['hits'][0]['record']['identity']['external_id'] == '82'
    assert second.coverage['checkpoint'] is None
    before = len(transport.calls)
    req['query']['record_types'] = ['meeting']
    assert engine.execute('search', req).status == 'failed'
    assert len(transport.calls) == before


@pytest.mark.parametrize('kind', [['meeting', 'agenda_item'], ['document'], ['transcript']])
def test_other_or_mixed_types_are_rejected_before_network(kind):
    transport = Transport()
    req = request()
    req['query']['record_types'] = kind
    assert create_engine(provider_transport=transport).execute('search', req).status == 'failed'
    assert not transport.calls


def test_exact_phrase_matching_filters_broad_candidates():
    transport = Transport()
    transport.data['searchResults'] += [deepcopy(row(82))]
    transport.data['totalElements'] = 2
    transport.data['searchResults'][1]['description'] = 'Watershed budget'
    req = request()
    req['query']['phrases'] = ['water budget']
    result = create_engine(provider_transport=transport).execute('search', req)
    assert len(result.data['hits']) == 1, result.public_dict()


def test_non_iso_supplied_date_remains_explicitly_unknown():
    transport = Transport()
    transport.data['searchResults'][0]['meetingDate'] = 'unqualified vendor display date'
    result = create_engine(provider_transport=transport).execute('search', request())
    assert len(result.data['hits']) == 1 and result.status == 'partial', result.public_dict()
    assert result.data['bundle']['records'][0]['normalized']['meeting_date'] is None
    assert any(f['reason'] == 'unknown_date' for f in result.coverage['failures'])


@pytest.mark.parametrize('selection', [[0], [-1, 2], [2, 2]])
def test_invalid_item_meeting_type_selection_stops_before_network(selection):
    transport = Transport()
    req = request()
    req['source']['options']['meeting_type_ids'] = selection
    assert create_engine(provider_transport=transport).execute('search', req).status == 'failed'
    assert not transport.calls
