"""Vendor-linked production routes; synthetic responses, never live account calls."""

import json

import pytest

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import default_adapters
from test_account_apis import MEETING, context, structure

PRODUCTION = 'https://meetings.municode.com'


class Network:
    mock = True

    def __init__(self):
        self.value = {'meetingStructure': structure()}
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert url.startswith(PRODUCTION + '/PublicApi/meeting')
        assert kwargs['allowed_origins'] == (PRODUCTION,) and kwargs['allow_redirects'] is False
        assert kwargs['headers']['Authorization'] == 'Bearer synthetic-long-bearer'
        return Response(url, json.dumps(self.value).encode(), 'application/json')

    def send(self, *args, **kwargs):
        raise AssertionError('No production write is mapped.')


def caller():
    result = context('municode-meetings')
    result.credentials['municode-meetings']['origin'] = PRODUCTION
    return result


@pytest.mark.parametrize('resource,path', [('meeting', '/PublicApi/meeting/'),
    ('item', '/PublicApi/meeting/item/'), ('multimedia', '/PublicApi/meeting/multimedia/')])
def test_production_read_uses_exact_vendor_published_route(resource, path):
    network = Network()
    engine = create_engine(provider_transport=network)
    source = Source('municode-meetings', PRODUCTION, namespace='account-a')
    result = engine.execute('fetch', {'source': source.public_dict(),
        'api_resource': resource, 'external_id': MEETING}, context=caller())
    assert result.status == 'partial', result.public_dict()
    assert network.calls[0][0] == PRODUCTION + path + MEETING
    if resource != 'multimedia':
        assert result.data['records'] == [] and result.coverage['schema_mapping'].startswith('unverified')
    assert 'synthetic-long-bearer' not in json.dumps(result.public_dict())


@pytest.mark.parametrize('target,credentials', [(PRODUCTION, context),
    ('https://meetingsgov.devmunicode.com', lambda _: caller())])
def test_development_and_production_credentials_are_not_interchangeable(target, credentials):
    network = Network()
    source = Source('municode-meetings', target, namespace='account-a')
    result = create_engine(provider_transport=network).execute('fetch', {'source': source.public_dict(),
        'api_resource': 'meeting', 'external_id': MEETING}, context=credentials('municode-meetings'))
    assert result.status == 'failed' and not network.calls


def test_production_collection_is_explicit_offset_raw_partial_without_inferred_pagination():
    network = Network()
    filters = {'Words': '', 'ArchivedState': 0, 'MeetingTypeIds': [],
               'CreatedMeetingFromDate': {'Day': -1, 'Month': -1, 'Year': -1},
               'CreatedMeetingToDate': {'Day': -1, 'Month': -1, 'Year': -1}}
    result = create_engine(provider_transport=network).execute('fetch', {'source': {
        'provider': 'municode-meetings', 'url': PRODUCTION, 'namespace': 'account-a'},
        'api_resource': 'collection', 'offset': 0, 'filters': filters}, context=caller())
    assert result.status == 'partial' and result.data['records'] == [], result.public_dict()
    assert len(network.calls) == 1 and network.calls[0][0] == PRODUCTION + '/PublicApi/meeting/collection/0'
    assert network.calls[0][1]['method'] == 'POST'
    assert json.loads(network.calls[0][1]['body']) == filters


@pytest.mark.parametrize('target', ['http://meetings.municode.com', 'https://meetings.municode.com:443',
                                   'https://meetings.municode.com.evil.example'])
def test_unlisted_origin_does_not_receive_credentials(target):
    network = Network()
    result = create_engine(provider_transport=network).execute('fetch', {'source': {
        'provider': 'municode-meetings', 'url': target, 'namespace': 'account-a'},
        'api_resource': 'meeting', 'external_id': MEETING}, context=caller())
    assert result.status == 'failed' and not network.calls


def test_production_multimedia_write_is_unmapped_before_network(tmp_path):
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'production.sqlite'),
                           write_adapters=default_adapters(network))
    source = {'provider': 'municode-meetings', 'url': PRODUCTION, 'namespace': 'account-a'}
    change = {'key': 'production', 'entity': 'meeting_multimedia', 'operation': 'update',
              'resource_id': MEETING, 'meeting_id': MEETING,
              'fields': {'AudioVideoDetails': {'AudioVideoUrl': 'https://example.org/approved.mp4'}}}
    owner = caller()
    planned = engine.execute('plan_write', {'source': source, 'changes': [change]}, context=owner)
    assert planned.status == 'failed', planned.public_dict()
    assert any(error.code == 'mapping_unverified' for error in planned.errors)
    assert not network.calls
