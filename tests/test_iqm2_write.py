'''Synthetic MinuteTraq AgendaUpdate/MinutesUpdate wire tests. No real network.'''
import base64
import codecs
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from time import monotonic
import xml.etree.ElementTree as ET

import pytest

from quorumrelay import Engine, OperationContext, Source
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import WriteChange, WriteFailure, default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from civic_data_connectors.providers import iqm2_soap, iqm2_write

URL = 'https://test.iqm2.com/MinuteTraqService/Data_1_0.asmx'
NS = iqm2_soap.namespace(Source('iqm2', URL, input_format=iqm2_soap.FORMAT,
    options={'minutetraq_agency': 'City of Test', 'meeting_id': 501,
             'document_id': 77, 'document_kind': 'agenda'}))
VERSION = '8.11.3.1452015'
CONNECTION_ID = '0123456789ABCDEF'
AUTH = ('Basic:clerk@City of Test:' + 'a' * 32 + ':' + CONNECTION_ID + ':M-127.0.0.1:'
        'MinuteTraq:' + VERSION + ':.NET 4.8')

SCHEMA_XML = (
    '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
    'xmlns:mstns="' + iqm2_soap.DB_NS + '" '
    'xmlns:msdata="urn:schemas-microsoft-com:xml-msdata" id="DB_1_0">'
    '<xs:element name="DB_1_0">'
    '<xs:complexType><xs:sequence>'
    '<xs:element name="Agenda" minOccurs="0" maxOccurs="unbounded">'
    '<xs:complexType><xs:sequence>'
    '<xs:element name="AgendaID" type="xs:int"/>'
    '<xs:element name="MeetingID" type="xs:int"/>'
    '<xs:element name="Updated" type="xs:dateTime"/>'
    '<xs:any minOccurs="0" maxOccurs="unbounded" processContents="lax"/>'
    '</xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="AgendaItem" minOccurs="0" maxOccurs="unbounded">'
    '<xs:complexType><xs:sequence>'
    '<xs:element name="AgendaItemID" type="xs:long"/>'
    '<xs:element name="AgendaID" type="xs:int"/>'
    '<xs:element name="Sort" type="xs:short" minOccurs="0"/>'
    '<xs:element name="Title" type="xs:string" minOccurs="0" nillable="true"/>'
    '<xs:any minOccurs="0" maxOccurs="unbounded" processContents="lax"/>'
    '</xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="Minutes" minOccurs="0" maxOccurs="unbounded">'
    '<xs:complexType><xs:sequence>'
    '<xs:element name="MinutesID" type="xs:int"/>'
    '<xs:element name="MeetingID" type="xs:int"/>'
    '<xs:element name="Updated" type="xs:dateTime"/>'
    '<xs:any minOccurs="0" maxOccurs="unbounded" processContents="lax"/>'
    '</xs:sequence></xs:complexType></xs:element>'
    '<xs:element name="MinutesItem" minOccurs="0" maxOccurs="unbounded">'
    '<xs:complexType><xs:sequence>'
    '<xs:element name="MinutesItemID" type="xs:long"/>'
    '<xs:element name="MinutesID" type="xs:int"/>'
    '<xs:element name="Sort" type="xs:short" minOccurs="0"/>'
    '<xs:element name="Title" type="xs:string" minOccurs="0" nillable="true"/>'
    '<xs:any minOccurs="0" maxOccurs="unbounded" processContents="lax"/>'
    '</xs:sequence></xs:complexType></xs:element>'
    '</xs:sequence></xs:complexType>'
    '<xs:key name="AgendaKey"><xs:selector xpath=".//mstns:Agenda"/>'
    '<xs:field xpath="mstns:AgendaID"/></xs:key>'
    '<xs:key name="MinutesKey"><xs:selector xpath=".//mstns:Minutes"/>'
    '<xs:field xpath="mstns:MinutesID"/></xs:key>'
    '</xs:element>'
    '</xs:schema>'
)


def source(kind='agenda'):
    document_id = 77 if kind == 'agenda' else 88
    return Source('iqm2', URL, namespace=NS, input_format=iqm2_soap.FORMAT,
                  options={'minutetraq_agency': 'City of Test', 'meeting_id': 501,
                           'document_id': document_id, 'document_kind': kind})


def context(kind='agenda', permissions=None, item_ids=None):
    document_id = 77 if kind == 'agenda' else 88
    if permissions is None:
        permissions = [kind + '_item:update_title']
    if item_ids is None:
        item_ids = ['9001', '9002']
    config = {
        'tenant': 'test-client',
        'origin': 'https://test.iqm2.com',
        'agency': 'City of Test',
        'allowed_namespaces': [NS],
        'meeting_ids': [501],
        'document_ids': [document_id],
        'document_kind': kind,
        'authorization_header': AUTH,
        'client_version': VERSION,
        'permissions': permissions,
        'item_ids': item_ids,
    }
    return OperationContext(
        principal='editor', client_id='test', tenant='test-client',
        authorization=frozenset({'write:plan', 'write:commit'}),
        allowed_namespaces=frozenset({NS}), credentials={'iqm2': config})


class State:
    def __init__(self, kind='agenda'):
        self.kind = kind
        self.meeting_id = 501
        self.document_id = 77 if kind == 'agenda' else 88
        self.updated = '2026-11-17T17:00:00Z'
        self.parent_unknown = 'keep-parent'
        self.meeting_unknown = 'keep-meeting'
        self.omit_null_titles = False
        self.items = {
            '9001': {'title': 'Bridge repair', 'sort': 1, 'unknown': 'keep-item'},
            '9002': {'title': 'Sidewalk', 'sort': 2, 'unknown': 'keep-item-2'},
        }


def _local(tag):
    if tag.startswith('{'):
        return tag.split('}', 1)[1]
    return tag


def _read_xml(state):
    kind = state.kind
    parent_tag = 'Agenda' if kind == 'agenda' else 'Minutes'
    item_tag = 'AgendaItem' if kind == 'agenda' else 'MinutesItem'
    id_field = 'AgendaID' if kind == 'agenda' else 'MinutesID'
    item_id_field = 'AgendaItemID' if kind == 'agenda' else 'MinutesItemID'
    response = 'AgendaGetResponse' if kind == 'agenda' else 'MinutesGetResponse'
    result = 'AgendaGetResult' if kind == 'agenda' else 'MinutesGetResult'
    item_rows = []
    for item_id, item in state.items.items():
        if item['title'] is None:
            if state.omit_null_titles:
                title = ''
            else:
                title = ("<Title xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' "
                         "xsi:nil='true'/>")
        else:
            title = '<Title>' + item['title'] + '</Title>'
        item_rows.append(
            '<' + item_tag + ' diffgr:id="' + item_tag + item_id + '">'
            '<' + item_id_field + '>' + item_id + '</' + item_id_field + '>'
            '<' + id_field + '>' + str(state.document_id) + '</' + id_field + '>'
            '<Sort>' + str(item['sort']) + '</Sort>' + title +
            '<UnknownItem>' + item['unknown'] + '</UnknownItem>'
            '</' + item_tag + '>')
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="' + iqm2_soap.SOAP_NS + '">'
        '<soap:Body>'
        '<' + response + ' xmlns="' + iqm2_soap.SERVICE_NS + '">'
        '<' + result + '>'
        + SCHEMA_XML +
        '<diffgr:diffgram xmlns:diffgr="' + iqm2_soap.DIFFGR_NS + '" '
        'xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">'
        '<DB_1_0 xmlns="' + iqm2_soap.DB_NS + '">'
        '<Meeting diffgr:id="Meeting1"><MeetingID>501</MeetingID>'
        '<UnknownMeeting>' + state.meeting_unknown + '</UnknownMeeting></Meeting>'
        '<' + parent_tag + ' diffgr:id="' + parent_tag + '1">'
        '<' + id_field + '>' + str(state.document_id) + '</' + id_field + '>'
        '<MeetingID>501</MeetingID>'
        '<Updated>' + state.updated + '</Updated>'
        '<UnknownParent>' + state.parent_unknown + '</UnknownParent>'
        '</' + parent_tag + '>' + ''.join(item_rows) +
        '</DB_1_0>'
        '</diffgr:diffgram>'
        '</' + result + '>'
        '</' + response + '>'
        '</soap:Body>'
        '</soap:Envelope>'
    ).encode('utf-8')


def _update_ack_xml(kind):
    method = 'AgendaUpdate' if kind == 'agenda' else 'MinutesUpdate'
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="' + iqm2_soap.SOAP_NS + '">'
        '<soap:Body>'
        '<' + method + 'Response xmlns="' + iqm2_soap.SERVICE_NS + '">'
        '<' + method + 'Result>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" id="DB_1_0"/>'
        '<diffgr:diffgram xmlns:diffgr="' + iqm2_soap.DIFFGR_NS + '">'
        '<DB_1_0 xmlns="' + iqm2_soap.DB_NS + '"/>'
        '</diffgr:diffgram>'
        '</' + method + 'Result>'
        '</' + method + 'Response>'
        '</soap:Body>'
        '</soap:Envelope>'
    ).encode('utf-8')


def _apply_update_xml(state, body):
    root = ET.fromstring(body)
    data_root = None
    for element in root.iter():
        if _local(element.tag) == 'DB_1_0':
            data_root = element
            break
    if data_root is None:
        raise AssertionError('Update request omitted DB_1_0')
    parent_tag = 'Agenda' if state.kind == 'agenda' else 'Minutes'
    item_tag = 'AgendaItem' if state.kind == 'agenda' else 'MinutesItem'
    id_field = 'AgendaID' if state.kind == 'agenda' else 'MinutesID'
    item_id_field = 'AgendaItemID' if state.kind == 'agenda' else 'MinutesItemID'
    for row in list(data_root):
        local = _local(row.tag)
        if local == parent_tag:
            for child in row:
                if _local(child.tag) == id_field:
                    assert child.text.strip() == str(state.document_id)
                if _local(child.tag) == 'Updated':
                    state.updated = child.text
        elif local == item_tag:
            item_id = None
            title = None
            title_is_nil = False
            for child in row:
                if _local(child.tag) == item_id_field:
                    item_id = child.text.strip()
                if _local(child.tag) == 'Title':
                    title_is_nil = child.attrib.get('{' + iqm2_soap.XSI_NS + '}nil') == 'true'
                    title = None if title_is_nil else (child.text if child.text is not None else '')
            assert item_id in state.items
            state.items[item_id]['title'] = title


class Vendor:
    mock = True

    def __init__(self, state):
        self.state = state
        self.calls = []
        self.fault = None
        self.read_override = None
        self.after_update = lambda: None

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert url == URL
        assert headers['Authorization'] == AUTH
        assert headers['MinuteTraqVersion'] == VERSION
        action = headers['SOAPAction']
        self.calls.append((action, body))
        if '/AgendaGet"' in action or '/MinutesGet"' in action:
            if self.fault == 'read_fail':
                raise TimeoutError()
            if self.read_override is not None:
                return WriteResponse(200, self.read_override)
            return WriteResponse(200, _read_xml(self.state))
        if '/AgendaUpdate"' in action or '/MinutesUpdate"' in action:
            if self.fault == 'denied':
                return WriteResponse(403)
            if self.fault == 'server_error':
                return WriteResponse(500)
            if self.fault == 'soap_fault':
                return WriteResponse(200, (
                    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
                    '<soap:Body><soap:Fault><faultstring>boom</faultstring></soap:Fault>'
                    '</soap:Body></soap:Envelope>').encode())
            _apply_update_xml(self.state, body)
            self.after_update()
            if self.fault == 'timeout':
                raise TimeoutError()
            if self.fault == 'bad_reply':
                return WriteResponse(200, b'not xml')
            if self.fault == 'wrong_ack':
                return WriteResponse(200, _read_xml(self.state))
            return WriteResponse(200, _update_ack_xml(self.state.kind))
        raise AssertionError('Unexpected SOAPAction ' + action)


def setup(tmp_path, kind='agenda', state=None):
    state = state or State(kind)
    vendor = Vendor(state)
    caller = context(kind)
    engine = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(engine, default_adapters(vendor))
    return engine, caller, vendor, state


def change(kind='agenda', items=None, **fields):
    document_id = 77 if kind == 'agenda' else 88
    value = {
        'key': 'edit',
        'entity': kind,
        'operation': 'update',
        'resource_id': str(document_id),
        'fields': {
            'updated': '2026-11-17T18:00:00Z',
            'items': items or [{'item_id': '9001', 'title': 'New bridge'}],
            'minutetraq_file_since': '2026-11-17T00:00:00',
            'minutetraq_public_file_since': '2026-11-17T00:00:00Z',
        },
    }
    value['fields'].update(fields)
    return value


def plan(engine, caller, kind='agenda', value=None):
    result = engine.execute('plan_write', {
        'source': source(kind).public_dict(),
        'changes': [value or change(kind)],
    }, context=caller)
    assert result.status == 'completed', result.public_dict()
    return {key: result.data[key] for key in ('plan_id', 'plan_hash')}, result


def _update_bodies(vendor):
    return [body for action, body in vendor.calls if 'Update"' in action]


def test_agenda_update_serializes_exact_diffgram_and_preserves_protected(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    approval, plan_result = plan(engine, caller)
    assert len(vendor.calls) == 1 and 'AgendaGet"' in vendor.calls[0][0]
    assert 'a' * 32 not in json.dumps(plan_result.public_dict())
    result = engine.execute('commit_write', approval, context=caller)
    assert result.status == 'completed', result.public_dict()
    bodies = _update_bodies(vendor)
    assert len(bodies) == 1
    body = bodies[0]
    text = body.decode('utf-8')
    assert '<AgendaUpdate xmlns="' + iqm2_soap.SERVICE_NS + '">' in text
    assert '<ds' in text and '<xs:schema' in text and '<diffgr:diffgram' in text
    assert '<Agenda ' in text and '<AgendaItem ' in text
    assert not re.search(r'<Meeting(?:\s|/|>)', text)
    assert '<AgendaItemID>9002</AgendaItemID>' not in text
    assert '<Updated>2026-11-17T18:00:00Z</Updated>' in text
    assert '<Title>New bridge</Title>' in text
    assert '<UnknownParent>keep-parent</UnknownParent>' in text
    assert '<UnknownItem>keep-item</UnknownItem>' in text
    assert 'xmlns:mstns="' + iqm2_soap.DB_NS + '"' in text
    assert 'xpath=".//mstns:Agenda"' in text
    assert text.count('diffgr:hasChanges="modified"') == 2
    root = ET.fromstring(body)
    before = next(element for element in root.iter()
                  if element.tag == '{' + iqm2_soap.DIFFGR_NS + '}before')
    before_agenda_rows = [row for row in before if row.tag == '{' + iqm2_soap.DB_NS + '}Agenda']
    assert len(before_agenda_rows) == 1
    before_agenda = before_agenda_rows[0]
    assert next(child for child in before_agenda
                if child.tag == '{' + iqm2_soap.DB_NS + '}Updated').text == '2026-11-17T17:00:00Z'
    before_item_rows = [row for row in before if row.tag == '{' + iqm2_soap.DB_NS + '}AgendaItem']
    assert len(before_item_rows) == 1
    before_item = before_item_rows[0]
    assert next(child for child in before_item
                if child.tag == '{' + iqm2_soap.DB_NS + '}Title').text == 'Bridge repair'
    assert state.items['9001']['title'] == 'New bridge'
    assert state.items['9002']['title'] == 'Sidewalk'
    assert state.parent_unknown == 'keep-parent'
    assert state.meeting_unknown == 'keep-meeting'
    assert 'a' * 32 not in json.dumps(result.public_dict())


def test_minutes_update_uses_minutesupdate_and_document_id(tmp_path):
    engine, caller, vendor, state = setup(tmp_path, kind='minutes')
    approval, _ = plan(engine, caller, kind='minutes', value=change('minutes'))
    result = engine.execute('commit_write', approval, context=caller)
    assert result.status == 'completed', result.public_dict()
    bodies = _update_bodies(vendor)
    assert len(bodies) == 1
    text = bodies[0].decode('utf-8')
    assert '<MinutesUpdate xmlns="' + iqm2_soap.SERVICE_NS + '">' in text
    assert '<MinutesID>88</MinutesID>' in text
    assert '<MinutesItemID>9001</MinutesItemID>' in text
    assert '<Agenda' not in text
    assert state.items['9001']['title'] == 'New bridge'


def test_preflight_conflict_prevents_update(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    approval, _ = plan(engine, caller)
    state.items['9001']['title'] = 'Other editor'
    result = engine.execute('commit_write', approval, context=caller)
    assert result.status == 'failed', result.public_dict()
    assert not _update_bodies(vendor)


def test_restart_after_lost_ack_server_applied_reconciles_without_replay(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    approval, _ = plan(engine, caller)
    vendor.fault = 'timeout'
    first = engine.execute('commit_write', approval, context=caller)
    assert first.data['items'][0]['state'] == 'uncertain'
    assert first.data['items'][0]['resource_id'] == '77'
    assert len(_update_bodies(vendor)) == 1
    vendor.fault = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'write.sqlite'))
    register(reopened, default_adapters(vendor))
    second = reopened.execute('commit_write', approval, context=caller)
    assert second.status == 'completed', second.public_dict()
    assert len(_update_bodies(vendor)) == 1


def test_cancel_after_send_keeps_id_then_reconciles(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    approval, _ = plan(engine, caller)
    vendor.after_update = caller.cancellation.set
    first = engine.execute('commit_write', approval, context=caller)
    assert first.data['items'][0]['state'] == 'uncertain'
    assert first.data['items'][0]['resource_id'] == '77'
    assert len(_update_bodies(vendor)) == 1
    caller.cancellation.clear()
    vendor.after_update = lambda: None
    second = engine.execute('commit_write', approval, context=caller)
    assert second.status == 'completed', second.public_dict()
    assert len(_update_bodies(vendor)) == 1


@pytest.mark.parametrize('case', ['permissions', 'item_ids', 'document_kind'])
def test_rejected_scope_never_calls_provider(tmp_path, case):
    engine, caller, vendor, state = setup(tmp_path)
    if case == 'permissions':
        caller.credentials['iqm2']['permissions'] = []
    elif case == 'item_ids':
        caller.credentials['iqm2']['item_ids'] = []
    else:
        caller.credentials['iqm2']['document_kind'] = 'minutes'
    result = engine.execute('plan_write', {
        'source': source().public_dict(), 'changes': [change()]}, context=caller)
    assert result.status == 'failed', result.public_dict()
    assert not vendor.calls


@pytest.mark.parametrize('mutate', [
    lambda value: value['fields'].update({'arbitrary': 'x'}),
    lambda value: value['fields']['items'][0].update({'extra': 'x'}),
    lambda value: value['fields']['items'][0].update({'title': 'bad\x01'}),
    lambda value: value['fields']['items'][0].update({'item_id': True}),
    lambda value: value['fields']['items'][0].update({'item_id': -1}),
    lambda value: value['fields']['items'].append({'item_id': '9001', 'title': 'duplicate'}),
    lambda value: value.update({'resource_id': '78'}),
    lambda value: value.update({'parent_id': '9001'}),
    lambda value: value.update({'files': [{'part': 'x'}]}),
    lambda value: value.update({'entity': 'minutes'}),
])
def test_invalid_change_never_calls_provider(tmp_path, mutate):
    engine, caller, vendor, state = setup(tmp_path)
    value = change()
    mutate(value)
    result = engine.execute('plan_write', {
        'source': source().public_dict(), 'changes': [value]}, context=caller)
    assert result.status == 'failed', result.public_dict()
    assert not vendor.calls


def test_native_item_id_mismatch_reads_but_never_updates(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    caller.credentials['iqm2']['item_ids'] = ['9001', '9002', '9999']
    value = change(items=[{'item_id': '9999', 'title': 'Missing'}])
    result = engine.execute('plan_write', {
        'source': source().public_dict(), 'changes': [value]}, context=caller)
    assert result.status == 'failed', result.public_dict()
    assert len(vendor.calls) == 1 and 'AgendaGet"' in vendor.calls[0][0]
    assert not _update_bodies(vendor)


def test_explicit_null_title_uses_xsi_nil_and_reads_back(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    approval, _ = plan(engine, caller, value=change(items=[{'item_id': '9001', 'title': None}]))
    result = engine.execute('commit_write', approval, context=caller)
    assert result.status == 'completed', result.public_dict()
    body = _update_bodies(vendor)[0]
    root = ET.fromstring(body)
    item = next(element for element in root.iter() if _local(element.tag) == 'AgendaItem')
    title = next(child for child in item if _local(child.tag) == 'Title')
    assert title.attrib.get('{' + iqm2_soap.XSI_NS + '}nil') == 'true'
    assert title.text is None
    assert not list(title)
    assert state.items['9001']['title'] is None


def test_null_title_omitted_readback_reconciles_without_replay(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    approval, _ = plan(engine, caller, value=change(items=[{'item_id': '9001', 'title': None}]))
    vendor.fault = 'timeout'
    first = engine.execute('commit_write', approval, context=caller)
    assert first.data['items'][0]['state'] == 'uncertain'
    assert len(_update_bodies(vendor)) == 1
    body = _update_bodies(vendor)[0]
    root = ET.fromstring(body)
    before = next(element for element in root.iter()
                  if element.tag == '{' + iqm2_soap.DIFFGR_NS + '}before')
    before_item = next(row for row in before if row.tag == '{' + iqm2_soap.DB_NS + '}AgendaItem')
    assert next(child for child in before_item
                if child.tag == '{' + iqm2_soap.DB_NS + '}Title').text == 'Bridge repair'
    state.omit_null_titles = True
    vendor.fault = None
    second = engine.execute('commit_write', approval, context=caller)
    assert second.status == 'completed', second.public_dict()
    assert second.data['items'][0]['state'] == 'succeeded'
    assert len(_update_bodies(vendor)) == 1
    assert state.items['9001']['title'] is None


def test_malformed_updated_readback_remains_uncertain_without_replay(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    approval, _ = plan(engine, caller)
    vendor.after_update = lambda: state.__setattr__('updated', 'not-a-date')
    first = engine.execute('commit_write', approval, context=caller)
    assert first.data['items'][0]['state'] == 'uncertain'
    assert len(_update_bodies(vendor)) == 1
    second = engine.execute('commit_write', approval, context=caller)
    assert second.data['items'][0]['state'] == 'uncertain'
    assert len(_update_bodies(vendor)) == 1


def test_unsupported_updated_datetime_mode_fails_before_update_send(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    needle = b'<xs:element name="Updated" type="xs:dateTime"/>'
    read = _read_xml(state)
    assert needle in read
    vendor.read_override = read.replace(
        needle,
        b'<xs:element name="Updated" type="xs:dateTime" msdata:DateTimeMode="Local"/>',
        1)
    result = engine.execute('plan_write', {
        'source': source().public_dict(), 'changes': [change()]}, context=caller)
    assert result.status == 'failed', result.public_dict()
    assert not _update_bodies(vendor)


def test_schema_detection_requires_xs_namespace_and_datetime_type():
    foreign_child = (
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:f="urn:foreign">'
        '<xs:element name="Agenda"><f:element name="Updated" type="xs:dateTime"/></xs:element>'
        '</xs:schema>')
    with pytest.raises(ValueError):
        iqm2_write._validate_updated_datetime_mode(foreign_child, 'agenda')
    wrong_type = (
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="Agenda"><xs:element name="Updated" type="xs:string"/></xs:element>'
        '</xs:schema>')
    with pytest.raises(ValueError):
        iqm2_write._validate_updated_datetime_mode(wrong_type, 'agenda')
    valid = (
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="Agenda"><xs:element name="Updated" type="xs:dateTime"/></xs:element>'
        '</xs:schema>')
    iqm2_write._validate_updated_datetime_mode(valid, 'agenda')


@pytest.mark.parametrize('fault', ['server_error', 'soap_fault'])
def test_unapplied_uncertain_update_never_resends(tmp_path, fault):
    engine, caller, vendor, state = setup(tmp_path)
    approval, _ = plan(engine, caller)
    vendor.fault = fault
    first = engine.execute('commit_write', approval, context=caller)
    assert first.data['items'][0]['state'] == 'uncertain', first.public_dict()
    assert len(_update_bodies(vendor)) == 1
    vendor.fault = None
    second = engine.execute('commit_write', approval, context=caller)
    assert second.data['items'][0]['state'] == 'uncertain'
    assert len(_update_bodies(vendor)) == 1


@pytest.mark.parametrize('fault', ['bad_reply', 'wrong_ack'])
def test_applied_update_with_invalid_ack_reconciles_without_replay(tmp_path, fault):
    engine, caller, vendor, state = setup(tmp_path)
    approval, _ = plan(engine, caller)
    vendor.fault = fault
    first = engine.execute('commit_write', approval, context=caller)
    assert first.data['items'][0]['state'] == 'uncertain', first.public_dict()
    assert len(_update_bodies(vendor)) == 1
    vendor.fault = None
    second = engine.execute('commit_write', approval, context=caller)
    assert second.status == 'completed', second.public_dict()
    assert len(_update_bodies(vendor)) == 1


def test_dirty_read_snapshot_is_rejected(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    clean = _read_xml(state)
    dirty = clean.replace(
        b'</diffgr:diffgram>',
        b'<diffgr:before><Agenda diffgr:id="Agenda1"/></diffgr:before></diffgr:diffgram>')
    vendor.read_override = dirty
    result = engine.execute('plan_write', {
        'source': source().public_dict(), 'changes': [change()]}, context=caller)
    assert result.status == 'failed', result.public_dict()
    assert not _update_bodies(vendor)


def test_element_repr_preserves_leaf_whitespace_and_empty():
    space = ET.fromstring('<Title xmlns="' + iqm2_soap.DB_NS + '"> </Title>')
    empty = ET.fromstring('<Title xmlns="' + iqm2_soap.DB_NS + '"/>')
    assert iqm2_write._element_repr(space)['text'] == ' '
    assert iqm2_write._element_repr(empty)['text'] is None
    assert iqm2_write._element_repr(space) != iqm2_write._element_repr(empty)


def test_foreign_namespace_updated_is_not_native():
    row = ET.fromstring(
        '<Agenda xmlns="' + iqm2_soap.DB_NS + '" xmlns:f="urn:foreign">'
        '<f:Updated>foreign</f:Updated><f:Title>foreign title</f:Title></Agenda>')
    iqm2_write._set_field(row, 'Updated', '2026-11-17T18:00:00Z')
    iqm2_write._set_field(row, 'Title', 'native title', allow_nil=True)
    foreign_updated = next(child for child in row if child.tag == '{urn:foreign}Updated')
    native_updated = next(child for child in row if child.tag == '{' + iqm2_soap.DB_NS + '}Updated')
    foreign_title = next(child for child in row if child.tag == '{urn:foreign}Title')
    native_title = next(child for child in row if child.tag == '{' + iqm2_soap.DB_NS + '}Title')
    assert foreign_updated.text == 'foreign'
    assert native_updated.text == '2026-11-17T18:00:00Z'
    assert foreign_title.text == 'foreign title'
    assert native_title.text == 'native title'


def test_schema_raw_preserves_ancestor_namespace_binding():
    content = (
        '<?xml version="1.0"?>'
        '<soap:Envelope xmlns:soap="' + iqm2_soap.SOAP_NS + '">'
        '<soap:Body>'
        '<AgendaGetResponse xmlns="' + iqm2_soap.SERVICE_NS + '" '
        'xmlns:mstns="' + iqm2_soap.DB_NS + '">'
        '<AgendaGetResult>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="DB_1_0"><xs:key name="K">'
        '<xs:selector xpath=".//mstns:Agenda"/>'
        '<xs:field xpath="mstns:AgendaID"/>'
        '</xs:key></xs:element>'
        '</xs:schema>'
        '</AgendaGetResult>'
        '</AgendaGetResponse>'
        '</soap:Body>'
        '</soap:Envelope>'
    ).encode('utf-8')
    raw, namespaces = iqm2_write._extract_raw_schema(content)
    assert ('mstns', iqm2_soap.DB_NS) in namespaces
    body = iqm2_write._build_request_body('AgendaUpdate', raw, namespaces, [], [])
    text = body.decode('utf-8')
    assert 'xmlns:mstns="' + iqm2_soap.DB_NS + '"' in text
    assert 'xpath=".//mstns:Agenda"' in text


@pytest.mark.parametrize('encoding,bom', [
    ('utf-16-le', codecs.BOM_UTF16_LE),
    ('utf-16-be', codecs.BOM_UTF16_BE),
])
def test_schema_raw_utf16_nested_namespace_shadowing(encoding, bom):
    schema = (
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="DB_1_0"><xs:key name="K">'
        '<xs:selector xpath=".//mstns:Agenda"/>'
        '<xs:field xpath="mstns:AgendaID"/>'
        '</xs:key></xs:element></xs:schema>')
    text = (
        '<?xml version="1.0" encoding="utf-16"?>'
        '<soap:Envelope xmlns:soap="' + iqm2_soap.SOAP_NS + '">'
        '<soap:Body>'
        '<AgendaGetResponse xmlns="' + iqm2_soap.SERVICE_NS + '">'
        '<AgendaGetResult xmlns="urn:inner" xmlns:mstns="urn:shadow">'
        + schema +
        '</AgendaGetResult>'
        '</AgendaGetResponse>'
        '</soap:Body>'
        '</soap:Envelope>')
    content = bom + text.encode(encoding)
    raw, namespaces = iqm2_write._extract_raw_schema(content)
    assert ('mstns', 'urn:shadow') in namespaces
    assert ('', 'urn:inner') in namespaces
    assert 'xmlns:mstns="urn:shadow"' in raw
    assert 'xmlns="urn:inner"' in raw
    ET.fromstring(raw)
    body = iqm2_write._build_request_body('AgendaUpdate', raw, namespaces, [], [])
    ET.fromstring(body)


def test_self_closing_schema_does_not_swallow_next_tag():
    content = (
        '<?xml version="1.0"?>'
        '<soap:Envelope xmlns:soap="' + iqm2_soap.SOAP_NS + '">'
        '<soap:Body>'
        '<AgendaGetResponse xmlns="' + iqm2_soap.SERVICE_NS + '">'
        '<AgendaGetResult>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" id="DB_1_0"/>'
        '<diffgr:diffgram xmlns:diffgr="' + iqm2_soap.DIFFGR_NS + '">'
        '<DB_1_0 xmlns="' + iqm2_soap.DB_NS + '"/>'
        '</diffgr:diffgram>'
        '</AgendaGetResult>'
        '</AgendaGetResponse>'
        '</soap:Body>'
        '</soap:Envelope>').encode('utf-8')
    raw, namespaces = iqm2_write._extract_raw_schema(content)
    assert '<diffgr' not in raw
    assert raw.rstrip().endswith('/>')
    ET.fromstring(raw)
    body = iqm2_write._build_request_body('AgendaUpdate', raw, namespaces, [], [])
    ET.fromstring(body)


def test_readback_whitespace_mismatch_is_uncertain(tmp_path):
    engine, caller, vendor, state = setup(tmp_path)
    approval, _ = plan(engine, caller)
    vendor.after_update = lambda: state.items['9001'].update(title='New bridge ')
    result = engine.execute('commit_write', approval, context=caller)
    assert result.status == 'partial', result.public_dict()
    assert result.data['items'][0]['state'] == 'uncertain'
    assert len(_update_bodies(vendor)) == 1


def test_readback_same_wallclock_representation_succeeds(tmp_path):
    state = State()
    state.updated = '2026-11-17T17:00:00-07:00'
    engine, caller, vendor, state = setup(tmp_path, state=state)
    approval, _ = plan(engine, caller)
    vendor.after_update = lambda: state.__setattr__(
        'updated', '2026-11-17T18:00:00.0000000-07:00')
    result = engine.execute('commit_write', approval, context=caller)
    assert result.status == 'completed', result.public_dict()
    assert result.data['items'][0]['state'] == 'succeeded'


def test_readback_changed_wallclock_remains_uncertain(tmp_path):
    state = State()
    state.updated = '2026-11-17T17:00:00-07:00'
    engine, caller, vendor, state = setup(tmp_path, state=state)
    approval, _ = plan(engine, caller)
    vendor.after_update = lambda: state.__setattr__(
        'updated', '2026-11-17T19:00:00-07:00')
    result = engine.execute('commit_write', approval, context=caller)
    assert result.status == 'partial', result.public_dict()
    assert result.data['items'][0]['state'] == 'uncertain'


def _powershell():
    exe = (shutil.which('powershell.exe') or shutil.which('powershell')
           or shutil.which('pwsh'))
    if not exe:
        if os.name == 'nt':
            pytest.fail('PowerShell is required for the independent .NET fixture on Windows.')
        pytest.skip('PowerShell is not available for independent .NET validation.')
    return exe


def test_outbound_request_validated_by_windows_fixture(tmp_path):
    script = Path(__file__).resolve().parent / 'fixtures' / 'iqm2' / 'dataset-wire-fixture.ps1'
    assert script.exists()
    exe = _powershell()
    generated = subprocess.run(
        [exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
         '-OutDir', str(tmp_path)],
        capture_output=True, text=True)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    baseline = (tmp_path / 'minutetraq-baseline-get-response.xml').read_bytes()
    vendor = Vendor(State())
    vendor.read_override = baseline
    adapter = iqm2_write.IQM2WriteAdapter(vendor)
    caller = context()
    prepared = adapter.prepare(
        source(), WriteChange.from_dict(change()), caller, _Bounds(), monotonic() + 5)
    request_path = tmp_path / 'actual-adapter-request.xml'
    request_path.write_bytes(base64.b64decode(prepared['native']['body_base64']))
    completed = subprocess.run(
        [exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
         '-OutDir', str(tmp_path), '-ValidateRequest', str(request_path)],
        capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert 'Validated outbound MinuteTraq ds' in completed.stdout


class _Bounds:
    def __init__(self, max_records=100):
        self.max_records = max_records
        self.parser_bytes = 1000000
        self.transfer_bytes = 1000000


def test_record_bound_enforced_before_any_write(tmp_path):
    vendor = Vendor(State())
    adapter = iqm2_write.IQM2WriteAdapter(vendor)
    caller = context()
    binding = adapter.credentials(source(), caller)
    thresholds = {
        'minutetraq_file_since': '2026-11-17T00:00:00',
        'minutetraq_public_file_since': '2026-11-17T00:00:00Z',
    }
    with pytest.raises(ValueError):
        adapter._read_current(
            source(), binding, thresholds, caller, _Bounds(max_records=1), monotonic() + 5)
    assert not _update_bodies(vendor)


def test_late_deadline_prevents_read_and_write(tmp_path):
    vendor = Vendor(State())
    adapter = iqm2_write.IQM2WriteAdapter(vendor)
    caller = context()
    binding = adapter.credentials(source(), caller)
    thresholds = {
        'minutetraq_file_since': '2026-11-17T00:00:00',
        'minutetraq_public_file_since': '2026-11-17T00:00:00Z',
    }
    with pytest.raises(WriteFailure):
        adapter._read_current(source(), binding, thresholds, caller, _Bounds(), monotonic() - 1)
    assert not vendor.calls
