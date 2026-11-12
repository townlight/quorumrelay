from urllib.parse import parse_qs

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.providers.discovery import _checkpoint, _resume

SOURCE = Source('suiteone-media', 'https://vermilionoh.suiteonemedia.com/', input_format='suiteone-archive-html')
CONTROL = b'''<a href="#" class="older_meetings_click" data-yearFrom="2025" data-groupId="8" data-uniqueId="BoardofZoningAppeals" data-categoryId="32" data-groupName="Board of Zoning Appeals">Older Meetings</a>'''


def row(identity, day):
    return (f'<table><tr><td><a href="/event/?id={identity}" title="Navigate to Board Meeting">Board Meeting</a></td><td>{day} | 7:00 PM</td>'
            f'<td><a href="/event/GetAgendaFile/Agenda?aid={identity}">Agenda</a></td></tr></table>').encode()


ROOT = row('1412', 'Nov 10, 2026') + CONTROL
OLDER = row('1412', 'Nov 10, 2026') + row('1100', 'Nov 10, 2025')


class Transport:
    def __init__(self, root=ROOT):
        self.root = root
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url == SOURCE.url:
            return Response(url, self.root, 'text/html')
        assert url == SOURCE.url + 'Home/GetRecentEventsGroup' and kwargs['method'] == 'POST'
        fields = parse_qs(kwargs['body'].decode())
        assert fields['groupId'] == ['8'] and fields['yearFrom'] == ['2025']
        assert fields['psize'] == ['10'] and fields['page'] == ['0']
        return Response(url, OLDER, 'text/html')


def test_suiteone_public_group_traversal_deduplicates_and_resumes():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    request = {'source': SOURCE.public_dict(), 'bounds': {'max_pages': 1}}
    first = engine.execute('discover', request)
    assert [r['identity']['external_id'] for r in first.data['records']] == ['1412']
    token = first.coverage['checkpoint']
    second = engine.execute('discover', {'source': SOURCE.public_dict(), 'bounds': {'checkpoint': token}})
    assert [r['identity']['external_id'] for r in second.data['records']] == ['1100']
    assert second.status == 'partial' and second.coverage['catalog_complete'] is False
    assert len(transport.calls) == 3  # root, revalidated root, one published POST


def test_suiteone_forged_or_removed_public_group_never_posts():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    first = engine.execute('discover', {'source': SOURCE.public_dict(), 'bounds': {'max_pages': 1}})
    import base64
    import json
    state = json.loads(base64.urlsafe_b64decode(first.coverage['checkpoint']))
    state['queue'][0]['fields']['groupId'] = '999'
    token = _checkpoint(state['binding'], state['queue'], state['seen'])
    result = engine.execute('discover', {'source': SOURCE.public_dict(), 'bounds': {'checkpoint': token}})
    assert result.status == 'failed' and all(x[1].get('method', 'GET') == 'GET' for x in transport.calls)
    _resume(token, state['binding'])
    transport.root = row('1412', 'Nov 10, 2026')
    result = engine.execute('discover', {'source': SOURCE.public_dict(), 'bounds': {'checkpoint': first.coverage['checkpoint']}})
    assert result.status == 'failed'
