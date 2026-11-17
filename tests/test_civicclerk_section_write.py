"""Synthetic public coordinator tests against the pinned CivicClerk contract."""
from dataclasses import replace
import json
from urllib.parse import urlsplit

from civic_data_connectors import Engine, OperationContext
from civic_data_connectors.storage import SQLiteStorage
from civic_data_connectors.write_adapters import default_adapters
from civic_data_connectors.write_transport import WriteResponse
from civic_data_connectors.writes import register

ORIGIN = 'https://fishersin.api.civicclerk.com'
NAMESPACE = '//fishersin.api.civicclerk.com'
SOURCE = {'provider': 'civicplus-select', 'url': ORIGIN + '/v1/Events', 'namespace': NAMESPACE}


class Vendor:
    mock = True

    def __init__(self):
        self.rows = {}
        self.calls = []
        self.mismatch = False
        self.omit_text = False
        self.event = {'id': 7, 'agendaId': 91}
        self.change_parent_on_post = False

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert headers['Authorization'] == 'Bearer private-test-token'
        assert urlsplit(url).hostname == 'fishersin.api.civicclerk.com' and deadline_seconds > 0
        self.calls.append((method, url, json.loads(body) if body else None))
        if method == 'GET' and urlsplit(url).path == '/v1/Events/7':
            return WriteResponse(200, json.dumps(self.event).encode())
        if method == 'POST':
            value = {'id': 41, **json.loads(body)}
            self.rows[41] = value
            if self.change_parent_on_post:
                self.event['agendaId'] = 92
            return WriteResponse(201, json.dumps(value).encode())
        if method == 'PUT':
            self.rows[41].update(json.loads(body))
            return WriteResponse(204, b'')
        value = dict(self.rows[41])
        if self.mismatch:
            value['sectionName'] = 'Different'
        if self.omit_text:
            value.pop('sectionText', None)
        return WriteResponse(200, json.dumps(value).encode())


def setup(tmp_path):
    network = Vendor()
    context = OperationContext(principal='editor', client_id='fixture', tenant='newsroom',
        authorization=frozenset({'write:plan', 'write:commit'}), allowed_namespaces=frozenset({NAMESPACE}),
        credentials={'civicplus-select': {'token': 'private-test-token', 'tenant': 'newsroom', 'origin': ORIGIN,
            'allowed_namespaces': [NAMESPACE], 'permissions': ['agenda_section:create', 'agenda_section:update'],
            'parent_ids': ['91'], 'meeting_ids': ['7'], 'resource_ids': ['41']}})
    engine = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(engine, default_adapters(network))
    return engine, context, network


def plan(engine, context, change):
    result = engine.execute('plan_write', {'source': SOURCE, 'changes': [change]}, context=context)
    assert result.status == 'completed', result.public_dict()
    return {k: result.data[k] for k in ('plan_id', 'plan_hash')}


def change(operation, **fields):
    return {'key': operation, 'entity': 'agenda_section', 'operation': operation,
            'parent_id': 91, 'meeting_id': '7', 'fields': fields,
            **({'resource_id': 41} if operation == 'update' else {})}


def test_create_update_204_readback_receipt_and_replay(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context, change('create', sectionName='Budget', sectionText='Initial text'))
    assert len(network.calls) == 1 and network.calls[0][0] == 'GET'
    created = engine.execute('commit_write', approval, context=context)
    assert created.status == 'completed', created.public_dict()
    post = next(call for call in network.calls if call[0] == 'POST')
    assert post[2] == {'agendaId': 91, 'sectionName': 'Budget', 'sectionText': 'Initial text'}
    assert created.data['items'][0]['readback']['agendaId'] == 91
    receipt = engine.execute('receipt', {'plan_id': approval['plan_id']}, context=context)
    assert receipt.status == 'completed' and 'private-test-token' not in json.dumps(receipt.public_dict())
    calls = list(network.calls)
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(network))
    assert reopened.execute('commit_write', approval, context=context).status == 'completed'
    assert network.calls == calls
    approval = plan(reopened, context, change('update', sectionName='Updated'))
    result = reopened.execute('commit_write', approval, context=context)
    assert result.status == 'completed', result.public_dict()
    put = next(call for call in network.calls if call[0] == 'PUT')
    assert put[2] == {'sectionName': 'Updated', 'sectionText': 'Initial text'}
    assert result.data['items'][0]['readback']['agendaId'] == 91
    assert network.calls[-1][0] == 'GET'


def test_mismatch_uncertain_and_no_duplicate_create(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context, change('create', sectionName='Budget'))
    network.mismatch = True
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'partial' and result.data['items'][0]['state'] == 'uncertain'
    assert engine.execute('commit_write', approval, context=context).status == 'partial'
    assert sum(method == 'POST' for method, _, _ in network.calls) == 1


def test_update_conflict_and_parent_scope_fail_closed(tmp_path):
    engine, context, network = setup(tmp_path)
    network.rows[41] = {'id': 41, 'agendaId': 91, 'sectionName': 'Old', 'sectionText': 'Keep'}
    approval = plan(engine, context, change('update', sectionText='New'))
    network.rows[41]['sectionName'] = 'Changed independently'
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'failed' and not any(call[0] == 'PUT' for call in network.calls)
    wrong = change('update', sectionName='Other')
    wrong['parent_id'] = 92
    assert engine.execute('plan_write', {'source': SOURCE, 'changes': [wrong]}, context=context).status == 'failed'
    invalid = change('update', sectionName='Other', agendaId=92)
    assert engine.execute('plan_write', {'source': SOURCE, 'changes': [invalid]}, context=context).status == 'failed'


def test_denied_namespace_and_credential_origin_before_network(tmp_path):
    engine, context, network = setup(tmp_path)
    denied = replace(context, allowed_namespaces=frozenset())
    assert engine.execute('plan_write', {'source': SOURCE, 'changes': [change('create', sectionName='x')]},
                          context=denied).status == 'failed'
    config = {**context.credentials['civicplus-select'], 'origin': 'https://other.api.civicclerk.com'}
    denied = replace(context, credentials={'civicplus-select': config})
    assert engine.execute('plan_write', {'source': SOURCE, 'changes': [change('create', sectionName='x')]},
                          context=denied).status == 'failed'
    assert not network.calls


def test_missing_text_readback_cannot_confirm_null_or_preserve_update(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context, change('create', sectionName='Budget', sectionText=None))
    network.omit_text = True
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'partial' and result.data['items'][0]['state'] == 'uncertain'
    before = len(network.calls)
    result = engine.execute('plan_write', {'source': SOURCE,
        'changes': [change('update', sectionName='Changed')]}, context=context)
    assert result.status == 'failed' and not any(call[0] == 'PUT' for call in network.calls[before:])


def test_wrong_event_parent_or_identity_rejected_during_plan(tmp_path):
    engine, context, network = setup(tmp_path)
    invalid = change('create', sectionName='x')
    invalid['meeting_id'] = 'not-a-native-id'
    assert engine.execute('plan_write', {'source': SOURCE, 'changes': [invalid]}, context=context).status == 'failed'
    assert not network.calls
    for event in ({'id': 7, 'agendaId': 92}, {'id': 8, 'agendaId': 91}, {'id': True, 'agendaId': 91}):
        network.event = event
        result = engine.execute('plan_write', {'source': SOURCE,
            'changes': [change('create', sectionName='x')]}, context=context)
        assert result.status == 'failed'
    assert all(method == 'GET' for method, _, _ in network.calls)


def test_parent_changed_after_plan_prevents_create_and_update(tmp_path):
    engine, context, network = setup(tmp_path)
    network.rows[41] = {'id': 41, 'agendaId': 91, 'sectionName': 'Old', 'sectionText': 'Keep'}
    for operation in ('create', 'update'):
        network.event['agendaId'] = 91
        approval = plan(engine, context, change(operation, sectionName='New'))
        network.event['agendaId'] = 92
        result = engine.execute('commit_write', approval, context=context)
        assert result.status == 'failed'
    assert all(method == 'GET' for method, _, _ in network.calls)


def test_parent_changed_after_create_remains_uncertain_without_duplicate(tmp_path):
    engine, context, network = setup(tmp_path)
    approval = plan(engine, context, change('create', sectionName='Budget'))
    network.change_parent_on_post = True
    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'partial' and result.data['items'][0]['state'] == 'uncertain'
    assert engine.execute('commit_write', approval, context=context).status == 'partial'
    assert sum(method == 'POST' for method, _, _ in network.calls) == 1
