from urllib.parse import parse_qs
import base64
import json

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.providers.discovery import _checkpoint

SOURCE = Source('civicplus-agenda-center', 'https://www.effinghamcounty.org/AgendaCenter', input_format='agenda-center-html')
CONTROL = b'''<a href="javascript:changeYear(2024, 3, 'a1')">2024</a>'''
ROOT = b'<table><tr><td><a href="/AgendaCenter/ViewFile/Agenda/_01022025-10">Commission Meeting</a></td></tr></table>' + CONTROL
YEAR = b'<table><tr><td><a href="/AgendaCenter/ViewFile/Agenda/_01022024-9">Commission Meeting</a></td></tr></table>'


class Transport:
    def __init__(self):
        self.calls = []
        self.root = ROOT

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url == SOURCE.url:
            return Response(url, self.root, 'text/html')
        assert url == SOURCE.url + '/UpdateCategoryList'
        assert kwargs['method'] == 'POST'
        assert parse_qs(kwargs['body'].decode(), keep_blank_values=True) == {
            'year': ['2024'], 'catID': ['3'], 'startDate': [''], 'endDate': [''], 'term': [''], 'prevVersionScreen': ['false']}
        return Response(url, YEAR, 'text/html')


def test_agenda_center_published_year_control_resumes_and_filters_calendar_dates():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute('discover', {'source': SOURCE.public_dict(), 'bounds': {'max_pages': 1, 'date_from':'2024-01-01','date_to':'2024-12-31'}})
    assert first.data['records'] == [] and first.coverage['checkpoint']
    second = engine.execute('discover', {'source': SOURCE.public_dict(), 'bounds': {'checkpoint':first.coverage['checkpoint'],'date_from':'2024-01-01','date_to':'2024-12-31'}})
    assert [r['identity']['external_id'] for r in second.data['records']] == ['9']
    assert second.coverage['catalog_complete'] is False and second.status == 'partial'
    assert len(transport.calls) == 3


def test_agenda_center_control_forgery_and_no_published_year_fail_closed():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute('discover', {'source':SOURCE.public_dict(),'bounds':{'max_pages':1}})
    state = json.loads(base64.urlsafe_b64decode(first.coverage['checkpoint']))
    state['queue'][0]['fields']['catID'] = '999'
    token = _checkpoint(state['binding'],state['queue'],state['seen'])
    refused = engine.execute('discover', {'source':SOURCE.public_dict(),'bounds':{'checkpoint':token}})
    assert refused.status == 'failed'
    assert all(call[1].get('method','GET') == 'GET' for call in transport.calls)
    transport.root = ROOT.replace(CONTROL,b'')
    refused = engine.execute('discover', {'source':SOURCE.public_dict(),'bounds':{'checkpoint':first.coverage['checkpoint']}})
    assert refused.status == 'failed'
