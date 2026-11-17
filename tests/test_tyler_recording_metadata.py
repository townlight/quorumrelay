"""Vendor-supplied player metadata survives persistence without a media GET."""

import base64
import json

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers.tyler_public import recordings
from test_provider_discovery import FakeTransport, request
from test_tyler_liberty import BASE, CAPTURE, SOURCE


def test_captured_player_link_persists_reopens_exports_and_refuses_byte_transfer(tmp_path):
    transport = FakeTransport(lambda *_: CAPTURE)
    database = tmp_path / 'recordings.sqlite'
    owner = create_engine(provider_transport=transport, storage=SQLiteStorage(database))
    req = request('tyler-meeting-manager', SOURCE, options={'calendar_api_base': BASE, 'meeting_type_ids': []})
    req['bounds'] = {'date_from': '2026-10-01', 'date_to': '2026-10-31'}
    result = owner.execute('discover', req)
    record = result.data['records'][0]
    player = record['normalized']['recordings'][0]
    assert player == {'external_id': record['original']['videoId'], 'kind': 'video', 'media_type': 'video',
                      'url': 'https://www.youtube.com/watch?v=' + record['original']['videoId'],
                      'availability': 'supplied_player_link', 'source_status': 'linked'}
    assert any(r['relation'] == 'recording' and r['value'] == player for r in record['relationships'])
    bundle = result.data['bundles'][0]
    assert owner.execute('import_bundle', {'bundle': bundle, 'persist': True}).status == 'completed'
    owner = create_engine(provider_transport=transport, storage=SQLiteStorage(database))
    fetched = owner.fetch_attachment(Source.from_dict(req['source']), record, kind='recordings')
    assert fetched.status == 'unsupported', fetched.public_dict()
    assert fetched.data['recording'] == player and fetched.data['attachment'] is None
    assert fetched.coverage['recording_bytes'] == 'not_implemented'
    assert len(transport.calls) == 1  # The calendar POST only; never open a player page as media bytes.
    exported = owner.execute('export', {'bundle': bundle, 'format': 'zip'})
    imported = create_engine().execute('import_bundle', {'format': 'zip'},
                                      content=base64.b64decode(exported.data['content_base64']))
    assert imported.status == 'completed', imported.public_dict()
    restored = imported.data['bundle']['records'][0]
    assert restored['normalized']['recordings'] == [player]
    assert restored['original'] == record['original']


@pytest.mark.parametrize('status', ['', 'NA', 'private', 'delete', 'rejected', None, 3])
def test_unavailable_video_status_never_advertises_player(status):
    raw = json.loads(CAPTURE)[0]
    raw['videoStatus'] = status
    assert recordings(raw) == []


@pytest.mark.parametrize('value', ['', '../other', 'x&v=foreign', 'line\nbreak', None])
def test_malformed_video_id_does_not_become_a_player_url(value):
    raw = json.loads(CAPTURE)[0]
    raw['videoId'] = value
    assert recordings(raw) == []


def test_cancelled_video_retains_raw_id_without_advertising_player():
    raw = json.loads(CAPTURE)[0]
    identity = raw['videoId']
    raw['canceled'] = True
    assert recordings(raw) == [] and raw['videoId'] == identity
