"""Captured public Tyler packet selectors, with synthetic bounded PDF transfers."""

import base64
import json

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers.tyler_public import documents
from test_provider_discovery import FakeTransport, request
from test_tyler_liberty import BASE, CAPTURE, ROOT, SOURCE


@pytest.mark.parametrize('kind,route,identity', [('packet', 'Agenda', '2409'), ('minutes_packet', 'Minutes', '2801')])
def test_captured_posted_enabled_packet_fetch_uses_native_document_id(tmp_path, kind, route, identity):
    pdf = b'%PDF-1.7\nsynthetic Tyler packet\n%%EOF'
    detail = (ROOT / 'docs/capabilities/evidence/tyler-liberty/detail.json').read_bytes()
    transport = FakeTransport(lambda url, *_: CAPTURE if url.endswith('getMeetingInformationByDate')
                              else detail if url.endswith('/getMeeting') else Response(url, pdf, 'application/pdf'))
    engine = create_engine(provider_transport=transport, storage=SQLiteStorage(tmp_path / 'packet.sqlite'))
    req = request('tyler-meeting-manager', SOURCE, options={'calendar_api_base': BASE, 'meeting_type_ids': []})
    req['bounds'] = {'date_from': '2026-10-01', 'date_to': '2026-10-31'}
    found = engine.execute('discover', req)
    record = found.data['records'][0]
    assert not any(d['kind'] in {'packet', 'minutes_packet'} for d in record['normalized']['documents'])
    source = Source.from_dict(req['source'])
    assert engine.execute('import_bundle', {'bundle': found.data['bundles'][0], 'persist': True}).status == 'completed'
    selected_detail = engine.fetch_record(source, record['identity']['external_id'])
    assert selected_detail.status == 'partial', selected_detail.public_dict()
    assert engine.execute('import_bundle', {'bundle': selected_detail.data, 'persist': True}).status == 'completed'
    record = selected_detail.data['records'][0]
    index = next(i for i,d in enumerate(record['normalized']['documents']) if d['kind'] == kind)
    selected = record['normalized']['documents'][index]
    assert selected['url'] == BASE + f'meetingInformation/{route}/true/{identity}'
    result = engine.fetch_attachment(source, record, index=index)
    assert result.status == 'completed', result.public_dict()
    assert base64.b64decode(result.data['attachment']['content_base64']) == pdf
    assert transport.calls[-1][0] == selected['url']
    assert transport.calls[-1][1]['allow_redirects'] is False


@pytest.mark.parametrize('field,value', [('agendaPacketEnabled', False), ('agendaPacketEnabled', 1),
                                        ('agendaStatus', 0), ('meetingAgendaId', True)])
def test_unposted_disabled_or_malformed_agenda_packet_is_not_advertised(field, value):
    raw = json.loads(CAPTURE)[0]
    raw['agendaPacketEnabled'] = True
    raw[field] = value
    source = Source('tyler-meeting-manager', SOURCE, options={'calendar_api_base': BASE})
    assert not any(d['kind'] == 'packet' for d in documents(source, raw))
