"""Captured meeting-packet wrapper, with synthetic readback and PDF bytes."""

import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from quorumrelay import create_engine
from quorumrelay.providers.contracts import Response
from test_onbase_documents import PDF
from test_onbase_listing import HTML, SOURCE

WRAPPER = (Path(__file__).parents[1] / 'docs/capabilities/evidence/onbase-packet/wrapper.html').read_bytes()
NAME = 'Commission_on_Aging_Well_3825_Agenda_Packet_11_12_2026_8_30_00_AM.pdf'


class Transport:
    def __init__(self, citation, code, failure=None):
        self.citation, self.code, self.failure = citation, code, failure
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append(url)
        assert kwargs['allow_redirects'] is False
        assert kwargs['byte_limit'] > 0 and kwargs['deadline_seconds'] > 0
        assert kwargs['allowed_origins'] == ('https://agendas.fitchburgwi.gov',)
        if url == self.citation:
            wrapper = WRAPPER.replace(b'g_documentType = 5;', f'g_documentType = {self.code};'.encode())
            for key, value in {'ItemId': 9, 'PublishId': 8}.items():
                if self.failure == 'wrapper_' + key:
                    wrapper = wrapper.replace(f'g_document{key} = 0;'.encode(), f'g_document{key} = {value};'.encode())
            if self.failure == 'wrapper_attachment':
                wrapper = wrapper.replace(b'g_documentIsAttachment = true;', b'g_documentIsAttachment = false;')
            return Response(url, wrapper, 'text/html')
        query = parse_qs(urlsplit(url).query)
        assert query == {'meetingId': ['3825'], 'itemId': ['0'], 'publishId': ['0'],
                         'isSection': ['false'], 'documentType': [str(self.code)]}
        if '/InvokeDownloadAttachment/' in url:
            assert kwargs['method'] == 'POST' and kwargs['body'] == b''
            data = {'DocumentName': NAME, 'MeetingId': 3825, 'ItemId': 0,
                    'PublishId': 0, 'DocumentType': self.code, 'IsSection': False}
            if self.failure in {'MeetingId', 'ItemId', 'PublishId', 'DocumentType'}:
                data[self.failure] += 1
            return Response(url, json.dumps(data).encode(), 'application/json')
        assert '/ViewDocument/' in url and kwargs['method'] == 'GET'
        return Response(url, PDF, 'application/pdf')


def fetch(code, monkeypatch, failure=None):
    from civic_data_connectors.providers import onbase_documents
    monkeypatch.setattr(onbase_documents, '_wait', lambda context, deadline: None)
    link = (f'<a href="/OnBaseAgendaOnline/Documents/Downloadfile/{NAME}?documentType={code}'
            '&amp;meetingId=3825&amp;isAttachment=True">Packet</a>').encode()
    content = HTML.split(b'<a href="/OnBaseAgendaOnline/Documents/')[0] + link + b'</td></tr></table>'
    record = create_engine().execute('discover', {'source': SOURCE.public_dict()}, content=content).data['records'][0]
    transport = Transport(record['normalized']['documents'][0]['url'], code, failure)
    owner = create_engine(provider_transport=transport)
    return owner.fetch_attachment(SOURCE, record, capture=content), transport


@pytest.mark.parametrize('code', [5, 6])
def test_packet_uses_supplied_attachment_branch_with_zero_item_and_publish(monkeypatch, code):
    # Type 5 uses captured wrapper constants; type 6 is a labeled enum-shaped variation.
    result, transport = fetch(code, monkeypatch)
    assert result.status == 'completed', result.public_dict()
    assert base64.b64decode(result.data['attachment']['content_base64']) == PDF
    assert result.data['attachment']['resolution']['document_type'] == code
    assert len(transport.calls) == 3
    assert result.data['record']['normalized']['documents'][0]['kind'] == ('packet' if code == 5 else 'minutes_packet')


@pytest.mark.parametrize('failure', ['wrapper_ItemId', 'wrapper_PublishId', 'wrapper_attachment',
                                    'MeetingId', 'ItemId', 'PublishId', 'DocumentType'])
def test_packet_rejects_changed_wrapper_or_readback_without_file_get(monkeypatch, failure):
    result, transport = fetch(5, monkeypatch, failure)
    assert result.status == 'partial', result.public_dict()
    assert result.data['attachment'] is None
    assert not any('/ViewDocument/' in url for url in transport.calls)
