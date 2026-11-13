"""Actual captured Agenda Online hierarchy plus synthetic bounded orchestration."""

import base64
import hashlib
import json
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.engine import source_identity_key
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from test_onbase_listing import HTML, SOURCE

DIRECTORY = Path(__file__).parents[1] / 'docs/capabilities/evidence/onbase-detail'
MEETING, AGENDA, ITEM, SECTION = [(DIRECTORY / (name + '.html')).read_bytes()
                                  for name in ('meeting', 'agenda', 'item', 'section')]
ROOT = SOURCE.url.rstrip('/')
MEETING_URL = ROOT + '/Meetings/ViewMeeting?id=3825&doctype=1'
AGENDA_URL = ROOT + '/Meetings/ViewMeetingAgenda?meetingId=3825&type=agenda'
ITEM_URL = ROOT + '/Meetings/ViewMeetingAgendaItem?meetingId=3825&itemId=88173&isSection=false&type=agenda'
SECTION_URL = ROOT + '/Meetings/ViewMeetingAgendaItem?meetingId=3825&itemId=54973&isSection=true&type=agenda'
FORMAT = 'onbase-public-listing-html'


class Transport:
    def __init__(self, *, on_read=None):
        self.calls, self.on_read = [], on_read
        self.pages = {SOURCE.url: HTML, MEETING_URL: MEETING, AGENDA_URL: AGENDA, ITEM_URL: ITEM, SECTION_URL: SECTION}
        self.statuses, self.urls = {}, {}

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs.get('method', 'GET') == 'GET' and kwargs['allow_redirects'] is False
        assert kwargs['allowed_origins'] == ('https://agendas.fitchburgwi.gov',)
        assert kwargs['byte_limit'] > 0 and kwargs['deadline_seconds'] > 0
        assert 'Authorization' not in kwargs.get('headers', {})
        if self.on_read:
            self.on_read(url)
        return Response(self.urls.get(url, url), self.pages[url], 'text/html', self.statuses.get(url, 200))


def fetch(transport, *, related=False, **kwargs):
    owner = create_engine(provider_transport=transport)
    if related:
        return owner.fetch_related(SOURCE, '3825', 'agenda_item', external_id='88173', **kwargs)
    return owner.fetch_record(SOURCE, '3825', **kwargs)


def normalize(url, content):
    return create_engine().normalize(Source('onbase', url), content, input_format=FORMAT)


def test_actual_accessible_agenda_native_sections_items_parent_context_and_raw():
    result = normalize(AGENDA_URL, AGENDA)
    assert result.status == 'completed', result.public_dict()
    records = result.data['records']
    assert len(records) == 12
    meeting = records[0]
    assert meeting['normalized']['title'] == 'Commission on Aging Well'
    assert meeting['normalized']['meeting_date'] == '2026-11-12'
    assert meeting['normalized']['source_start'] == '2026-11-12T08:30:00'
    assert meeting['normalized']['time_zone_status'] == 'unknown' and 'body' not in meeting['normalized']
    assert len(meeting['normalized']['agenda_items']) == 2 and len(meeting['normalized']['agenda_sections']) == 9
    item = next(record for record in records if record['identity']['external_id'] == '88173')
    assert item['identity']['record_type'] == 'agenda_item'
    assert source_identity_key(item['identity']['parent']) == source_identity_key(meeting['identity'])
    assert item['normalized']['parent_section_external_id'] == '54973'
    assert item['relationships'][1]['identity']['external_id'] == '54973'
    assert item['original']['attributes']['onclick'] == 'loadAgendaItem(88173); return false;'
    assert item['text'][0]['provenance']['capture_sha256'] == hashlib.sha256(AGENDA).hexdigest()
    assert base64.b64decode(result.data['capture']['content_base64']) == AGENDA


def test_actual_selected_item_keeps_native_attachment_and_exact_meeting_binding():
    result = normalize(ITEM_URL, ITEM)
    assert result.status == 'completed', result.public_dict()
    item = result.data['records'][0]
    assert item['identity']['external_id'] == '88173' and item['identity']['parent']['external_id'] == '3825'
    document = item['normalized']['documents'][0]
    assert document['external_id'] == '299754' and document['publish_id'] == '97134'
    assert document['agenda_item_external_id'] == '88173'
    assert document['availability'] == 'supplied_locator_not_fetched'
    assert item['text'][0]['citation_url'] == ITEM_URL


def test_fetch_detail_composes_only_supplied_routes_preserves_identity_and_captures():
    transport = Transport()
    transport.pages[SOURCE.url] = HTML.replace(b'</td></tr>',
        b'<a href="/OnBaseAgendaOnline/Meetings/ViewMeeting?id=3825&amp;doctype=1">View Media</a></td></tr>')
    result = fetch(transport)
    assert result.status == 'partial' and not result.errors, result.public_dict()
    assert [url for url, _ in transport.calls] == [SOURCE.url, MEETING_URL, AGENDA_URL]
    assert len(result.data['records']) == 12 and len(result.data['captures']) == 2
    previous = create_engine().execute('discover', {'source': SOURCE.public_dict()},
                                       content=transport.pages[SOURCE.url]).data['records'][0]
    meeting = result.data['records'][0]
    assert meeting['identity'] == previous['identity']
    assert meeting['original']['listing'] == previous['original']
    assert meeting['normalized']['recordings'] == previous['normalized']['recordings']
    assert any(relation['relation'] == 'recording' for relation in meeting['relationships'])
    assert result.data['compatibility']['meetings'] == [meeting['normalized']]
    assert len(meeting['normalized']['documents']) == 3
    assert not result.coverage['catalog_complete'] and not result.coverage['source_complete']


def test_selected_item_requires_current_parent_membership_and_keeps_section_and_text():
    transport = Transport()
    result = fetch(transport, related=True)
    assert result.status == 'partial' and not result.errors, result.public_dict()
    assert len(result.data['records']) == 1 and len(transport.calls) == 4
    item = result.data['records'][0]
    assert item['normalized']['meeting_date'] == '2026-11-12'
    assert item['normalized']['documents'][0]['external_id'] == '299754'
    assert any(relation['relation'] == 'parent_agenda_section' for relation in item['relationships'])
    assert len(result.data['captures']) == 3


def test_detail_persist_reopen_search_and_interchange_keep_native_children_and_captures(tmp_path):
    result = fetch(Transport(), related=True)
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'source.sqlite'))
    imported = owner.execute('import_bundle', {'result': result.public_dict(), 'persist': True})
    assert imported.status == 'partial' and imported.data['persisted'], imported.public_dict()
    repeated = owner.execute('import_bundle', {'result': result.public_dict(), 'persist': True})
    assert repeated.data['changes'][0]['outcome'] == 'unchanged'
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'source.sqlite'))
    found = reopened.execute('search', {'query': {'phrases': ['Draft Minutes']}})
    assert found.status == 'partial' and len(found.data['hits']) == 1, found.public_dict()
    assert any(match.get('citation_url') == ITEM_URL for match in found.data['hits'][0]['matches'])
    exported = reopened.execute('export', {'bundle': result.data, 'format': 'zip'})
    assert exported.status == 'completed', exported.public_dict()
    destination = create_engine(storage=SQLiteStorage(tmp_path / 'destination.sqlite'))
    restored = destination.execute('import_bundle', {'format': 'zip', 'persist': True},
                                  content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed', restored.public_dict()
    assert restored.data['bundle']['records'][0] == result.data['records'][0]
    for capture in [restored.data['bundle']['capture'], *restored.data['bundle']['captures']]:
        with destination.storage.open_capture(capture['storage_reference'], scope=OperationContext().scope) as stream:
            assert hashlib.sha256(stream.read()).hexdigest() == capture['sha256']


@pytest.mark.parametrize('target', [MEETING_URL, AGENDA_URL, ITEM_URL])
def test_later_detail_failure_retains_only_verified_requested_data(target):
    transport = Transport()
    transport.statuses[target] = 403
    result = fetch(transport, related=True)
    assert result.status in {'failed', 'partial'} and result.errors, result.public_dict()
    assert all(record['identity']['record_type'] == 'agenda_item' for record in result.data['records'])
    assert all(record['identity']['external_id'] == '88173' for record in result.data['records'])
    if target == ITEM_URL:
        assert result.status == 'partial' and result.data['records'][0]['normalized']['content_availability'] == 'supplied_title_only'


@pytest.mark.parametrize('mutation', ['meeting', 'template', 'item_missing', 'wrong_title', 'foreign_attachment', 'response_url'])
def test_wrong_context_never_follows_foreign_or_unsupplied_item(mutation):
    transport = Transport()
    if mutation == 'meeting':
        transport.pages[MEETING_URL] = MEETING.replace(b'meetingId=3825', b'meetingId=9999')
    elif mutation == 'template':
        transport.pages[MEETING_URL] = MEETING.replace(b'/Meetings/ViewMeetingAgendaItem?', b'/Meetings/Unverified?')
    elif mutation == 'item_missing':
        transport.pages[AGENDA_URL] = AGENDA.replace(b'loadAgendaItem(88173)', b'loadAgendaItem(99999)')
    elif mutation == 'wrong_title':
        transport.pages[ITEM_URL] = ITEM.replace(b'Draft Minutes', b'Foreign Item')
    elif mutation == 'foreign_attachment':
        transport.pages[ITEM_URL] = ITEM.replace(b'meetingId=3825', b'meetingId=9999')
    elif mutation == 'response_url':
        transport.urls[AGENDA_URL] = AGENDA_URL.replace('3825', '9999')
    result = fetch(transport, related=True)
    assert result.status in {'failed', 'partial'} and result.errors, result.public_dict()
    assert not any('9999' in url for url, _ in transport.calls)
    if mutation == 'item_missing':
        assert ITEM_URL not in [url for url, _ in transport.calls]
    if result.data:
        assert not any('Foreign Item' == record['normalized']['title'] for record in result.data['records'])


def test_bounds_and_cancel_preserve_partial_and_limit_network():
    transport = Transport()
    limited = fetch(transport, bounds=Bounds(max_records=1))
    assert limited.status == 'partial' and len(limited.data['records']) == 1 and limited.coverage['truncated']
    transport = Transport()
    limited = fetch(transport, bounds=Bounds(max_pages=2))
    assert limited.status == 'partial' and len(transport.calls) == 2 and limited.coverage['truncated']
    caller = OperationContext()
    transport = Transport(on_read=lambda url: caller.cancellation.set() if url == MEETING_URL else None)
    cancelled = fetch(transport, context=caller)
    assert cancelled.status == 'cancelled' and len(transport.calls) == 2
    transport = Transport()
    budget = len(HTML) + len(MEETING) + 1
    limited = fetch(transport, bounds=Bounds(parser_bytes=budget))
    assert limited.status == 'partial' and len(transport.calls) == 3
    assert transport.calls[-1][1]['byte_limit'] == 1


def test_section_collection_and_absent_meeting():
    owner = create_engine(provider_transport=Transport())
    sections = owner.fetch_related(SOURCE, '3825', 'agenda_section')
    assert sections.status == 'partial' and len(sections.data['records']) == 9
    transport = Transport()
    missing = create_engine(provider_transport=transport).fetch_record(SOURCE, '9999')
    assert missing.status == 'failed' and missing.data is None


def test_http_parent_selector_and_native_child_result_contract():
    from starlette.testclient import TestClient
    from civic_data_connectors.transports.http import create_app
    from civic_data_connectors.transports.runtime import ServiceConfig
    transport = Transport()
    with TestClient(create_app(create_engine(provider_transport=transport), ServiceConfig()),
                    base_url='http://127.0.0.1') as client:
        response = client.post('/v1/operations/fetch', json={'source': SOURCE.public_dict(),
            'parent_id': '3825', 'record_type': 'agenda_item', 'external_id': '88173'})
    assert response.status_code == 200
    result = response.json()
    assert result['status'] == 'partial' and result['data']['records'][0]['identity']['parent']['external_id'] == '3825', result
    assert json.loads(json.dumps(result)) == result


def test_selected_section_capture_membership_and_storage_roundtrip(tmp_path):
    parsed = normalize(SECTION_URL, SECTION)
    assert parsed.status == 'completed', parsed.public_dict()
    section = parsed.data['records'][0]
    assert section['identity']['record_type'] == 'agenda_section'
    assert section['identity']['external_id'] == '54973'
    assert section['identity']['parent']['external_id'] == '3825'
    assert section['normalized']['title'] == 'Approval Of Minutes'
    assert section['normalized']['documents'] == []
    assert base64.b64decode(parsed.data['capture']['content_base64']) == SECTION
    assert parsed.data['capture']['sha256'] == '68c0fe67270a2cc774e49f517975e12b2d035b495e122be87d253c25c89eeafb'
    transport = Transport()
    result = create_engine(provider_transport=transport).fetch_related(
        SOURCE, '3825', 'agenda_section', external_id='54973')
    assert result.status == 'partial' and not result.errors, result.public_dict()
    assert [url for url, _ in transport.calls] == [SOURCE.url, MEETING_URL, AGENDA_URL, SECTION_URL]
    section = result.data['records'][0]
    assert section['identity'] == parsed.data['records'][0]['identity']
    assert section['normalized']['meeting_date'] == '2026-11-12'
    assert section['normalized']['content_availability'] == 'selected_rendered_section'
    assert section['text'][0]['citation_url'] == SECTION_URL
    assert len(result.data['captures']) == 3
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'source.sqlite'))
    imported = owner.execute('import_bundle', {'result': result.public_dict(), 'persist': True})
    assert imported.data['persisted'], imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'source.sqlite'))
    stored = reopened.storage.get('records', source_identity_key(section['identity']), scope=OperationContext().scope)
    assert stored and stored.value['identity'] == section['identity']
    exported = reopened.execute('export', {'bundle': result.data, 'format': 'zip'})
    destination = create_engine(storage=SQLiteStorage(tmp_path / 'destination.sqlite'))
    restored = destination.execute('import_bundle', {'format': 'zip', 'persist': True},
                                  content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed', restored.public_dict()
    assert restored.data['bundle']['records'][0] == section
    for capture in [restored.data['bundle']['capture'], *restored.data['bundle']['captures']]:
        with destination.storage.open_capture(capture['storage_reference'], scope=OperationContext().scope) as stream:
            assert hashlib.sha256(stream.read()).hexdigest() == capture['sha256']


@pytest.mark.parametrize('mutation', ['absent', 'opposite_kind', 'title', 'context', 'attachment', 'http'])
def test_selected_section_rejects_unverified_detail_and_retains_membership(mutation):
    transport = Transport()
    if mutation == 'absent':
        transport.pages[AGENDA_URL] = AGENDA.replace(b'loadAgendaSection(54973)', b'loadAgendaSection(99999)')
    elif mutation == 'opposite_kind':
        transport.pages[AGENDA_URL] = AGENDA.replace(b'loadAgendaSection(54973)', b'loadAgendaItem(54973)')
    elif mutation == 'title':
        transport.pages[SECTION_URL] = SECTION.replace(b'Approval Of Minutes', b'Foreign Section')
    elif mutation == 'context':
        transport.urls[SECTION_URL] = SECTION_URL.replace('3825', '9999')
    elif mutation == 'attachment':
        transport.pages[SECTION_URL] = SECTION.replace(b'</section>', b'<a id="lnkAttachment_1" href="/x">x</a></section>')
    elif mutation == 'http':
        transport.statuses[SECTION_URL] = 403
    result = create_engine(provider_transport=transport).fetch_related(
        SOURCE, '3825', 'agenda_section', external_id='54973')
    assert result.errors and result.status in {'partial', 'failed'}, result.public_dict()
    if mutation in {'absent', 'opposite_kind'}:
        assert SECTION_URL not in [url for url, _ in transport.calls]
    else:
        assert result.status == 'partial'
        assert result.data['records'][0]['normalized']['content_availability'] == 'supplied_title_only'
        assert len(result.data['captures']) == 2


def test_selected_section_bounds_and_cancellation():
    transport = Transport()
    result = create_engine(provider_transport=transport).fetch_related(
        SOURCE, '3825', 'agenda_section', external_id='54973', bounds=Bounds(max_pages=3))
    assert result.status == 'partial' and result.coverage['truncated'] and len(transport.calls) == 3
    caller = OperationContext()
    transport = Transport(on_read=lambda url: caller.cancellation.set() if url == SECTION_URL else None)
    result = create_engine(provider_transport=transport).fetch_related(
        SOURCE, '3825', 'agenda_section', external_id='54973', context=caller)
    assert result.status == 'cancelled' and len(transport.calls) == 4
    assert result.data['records'][0]['identity']['external_id'] == '54973'


def test_selected_nested_section_keeps_agenda_parent_relation():
    transport = Transport()
    text = AGENDA.decode('utf-8')
    start = text.index('loadAgendaSection(54972)')
    boundary = text.index('<div class="accessible-section accessible-section-level-1">', start)
    before = text[:boundary]
    closing = before.rfind('</div>')
    text = before[:closing] + before[closing + len('</div>'):] + text[boundary:]
    third = text.index('<div class="accessible-section accessible-section-level-1">',
                       text.index('loadAgendaSection(54973)'))
    text = text[:third] + '</div>' + text[third:]
    transport.pages[AGENDA_URL] = text.encode('utf-8')
    result = create_engine(provider_transport=transport).fetch_related(
        SOURCE, '3825', 'agenda_section', external_id='54973')
    assert result.status == 'partial' and not result.errors, result.public_dict()
    section = result.data['records'][0]
    assert section['normalized']['parent_section_external_id'] == '54972'
    assert any(relation['relation'] == 'parent_agenda_section' and
               relation['identity']['external_id'] == '54972' for relation in section['relationships'])
