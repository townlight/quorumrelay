"""Exact archived agenda response; selected-parent request is synthetic, not live."""

import base64
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers.contracts import Response

FIXTURES = Path(__file__).parent / 'fixtures/boarddocs-public'
SOURCE = Source('boarddocs', 'https://go.boarddocs.com/oh/columbus/Board.nsf/Public',
                options={'boarddocs_committee_id': 'explicit-fixture-committee'})
MEETING = 'DQ3VPX80F260'


class Network:
    def __init__(self):
        self.calls = []
        self.raw = (FIXTURES / 'columbus-agenda.html').read_bytes()
        self.status, self.changed, self.cancel = 200, False, None

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert url == 'https://go.boarddocs.com/oh/columbus/Board.nsf/BD-GetAgenda?open'
        assert kwargs['method'] == 'POST' and kwargs['allow_redirects'] is False
        assert parse_qs(kwargs['body'].decode()) == {'id': [MEETING], 'current_committee_id': ['explicit-fixture-committee']}
        assert kwargs['allowed_origins'] == ('https://go.boarddocs.com',)
        if self.cancel:
            self.cancel.cancellation.set()
        return Response(url + '/changed' if self.changed else url, self.raw, 'text/html', self.status)


def setup(tmp_path):
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'agenda.sqlite'), provider_transport=network)
    parent = engine.normalize(SOURCE, (FIXTURES / 'columbus-meeting.html').read_bytes(),
                              input_format='boarddocs-public-meeting-html')
    assert parent.status == 'completed', parent.public_dict()
    assert parent.data['records'][0]['identity']['external_id'] == MEETING
    assert engine.execute('import_bundle', {'bundle': parent.data, 'persist': True}).status == 'completed'
    assert not network.calls
    return engine, network


@pytest.mark.parametrize('kind,count', [('agenda_item', 123), ('agenda_section', 28)])
def test_archived_outline_native_ids_selected_parent_sqlite_search_and_exact_zip(tmp_path, kind, count):
    engine, network = setup(tmp_path)
    result = engine.fetch_related(SOURCE, MEETING, kind, bounds=Bounds(max_records=200))
    assert result.status == 'partial' and not result.errors, result.public_dict()
    bundle = result.data
    assert len(bundle['records']) == count and len(network.calls) == 1
    record = bundle['records'][0]
    assert record['identity']['parent']['external_id'] == MEETING
    assert record['normalized']['parent_section_availability'] == 'not_asserted_by_native_ID_in_response'
    assert record['normalized']['documents'] == []
    assert result.coverage['catalog_complete'] is False
    assert result.coverage['meeting_binding'].endswith('not_response_asserted')
    for _ in range(2):
        assert engine.execute('import_bundle', {'bundle': bundle, 'persist': True}).status == 'completed'
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'agenda.sqlite'))
    found = reopened.execute('search', {'query': {'terms': ['Quorum' if kind == 'agenda_item' else 'Convene']}})
    assert found.data['hits']
    archive = reopened.execute('export', {'bundle': bundle, 'format': 'zip'})
    restored = read_bundle(base64.b64decode(archive.data['content_base64']), format='zip')
    assert restored == bundle
    assert base64.b64decode(restored['capture']['content_base64']) == network.raw


def test_record_cap_is_explicit_and_does_not_invent_upstream_paging(tmp_path):
    engine, network = setup(tmp_path)
    result = engine.fetch_related(SOURCE, MEETING, 'agenda_item', bounds=Bounds(max_records=2))
    assert not result.errors and len(result.data['records']) == 2
    assert result.coverage['record_limit_reached'] is True
    assert result.coverage['matching_records_in_response'] == 123
    assert not result.coverage.get('checkpoint') and len(network.calls) == 1


@pytest.mark.parametrize('fault', ['absent_parent', 'wrong_scope', 'record_type', 'checkpoint'])
def test_current_selected_parent_and_bounds_required_before_network(tmp_path, fault):
    engine, network = setup(tmp_path)
    parent, kind, context, bounds = MEETING, 'agenda_item', OperationContext(), Bounds()
    if fault == 'absent_parent':
        parent = 'UNSTORED'
    elif fault == 'wrong_scope':
        context = OperationContext(principal='other')
    elif fault == 'record_type':
        kind = 'vote'
    else:
        bounds = Bounds(checkpoint='unrecognized')
    result = engine.fetch_related(SOURCE, parent, kind, context=context, bounds=bounds)
    assert result.status == 'failed', result.public_dict()
    assert not network.calls


@pytest.mark.parametrize('fault', ['denied', 'redirect', 'not_outline', 'duplicate', 'id_mismatch', 'cancel'])
def test_denial_changed_shape_identity_and_cancellation_retain_no_fabricated_items(tmp_path, fault):
    engine, network = setup(tmp_path)
    context = OperationContext()
    if fault == 'denied':
        network.status = 403
    elif fault == 'redirect':
        network.changed = True
    elif fault == 'not_outline':
        network.raw = b'<html><title>Sign in</title></html>'
    elif fault == 'duplicate':
        network.raw += b'<li class="item public" id="DQ3VPZ80F262" unique="DQ3VPZ80F262"><span class="title">Repeated</span></li>'
    elif fault == 'id_mismatch':
        network.raw = network.raw.replace(b'id="DQ3VPZ80F262"', b'id="WRONG"', 1)
    else:
        network.cancel = context
    result = engine.fetch_related(SOURCE, MEETING, 'agenda_item', context=context)
    assert result.status in {'failed', 'partial', 'cancelled'}, result.public_dict()
    assert result.data is None or not result.data['records']
    if fault == 'cancel':
        assert result.status == 'cancelled'
    else:
        assert result.errors


def test_private_or_template_ancestor_cannot_surface_items(tmp_path):
    engine, network = setup(tmp_path)
    network.raw += b'<div class="private"><li class="item public" id="SECRET" unique="SECRET"><span class="title">Hidden</span></li></div>'
    network.raw += b'<template><li class="item public" id="TEMPLATE" unique="TEMPLATE"><span class="title">Hidden</span></li></template>'
    result = engine.fetch_related(SOURCE, MEETING, 'agenda_item', bounds=Bounds(max_records=200))
    assert not result.errors and len(result.data['records']) == 123
    assert not {'SECRET', 'TEMPLATE'} & {r['identity']['external_id'] for r in result.data['records']}
