'''Synthetic MinuteTraq MeetingUpdate create/update wire tests. No real network.'''
import base64
import os
import shutil
import subprocess
from pathlib import Path
from time import monotonic
import xml.etree.ElementTree as ET

import pytest

from quorumrelay import Engine, OperationContext, Source
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import WriteChange, default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from civic_data_connectors.providers import iqm2_soap, iqm2_meeting_write

URL = 'https://test.iqm2.com/MinuteTraqService/Data_1_0.asmx'
NS = iqm2_meeting_write._meeting_namespace(Source('iqm2', URL, input_format=iqm2_meeting_write.FORMAT, options={'minutetraq_agency': 'City of Test'}))
VERSION = '8.11.3.1452015'
CONNECTION_ID = '0123456789ABCDEF'
AUTH = ('Basic:clerk@City of Test:' + 'a' * 32 + ':' + CONNECTION_ID + ':M-127.0.0.1:' + 'MinuteTraq:' + VERSION + ':.NET 4.8')

SCHEMA_XML = (
    '<xs:schema id=\'DB_1_0\' targetNamespace=\'' + iqm2_soap.DB_NS + '\' '
    'xmlns:mstns=\'' + iqm2_soap.DB_NS + '\' xmlns=\'' + iqm2_soap.DB_NS + '\' '
    'xmlns:xs=\'http://www.w3.org/2001/XMLSchema\' '
    'xmlns:msdata=\'urn:schemas-microsoft-com:xml-msdata\' '
    'attributeFormDefault=\'qualified\' elementFormDefault=\'qualified\'>'
    '<xs:element name=\'DB_1_0\' msdata:IsDataSet=\'true\' msdata:UseCurrentLocale=\'true\'>'
    '<xs:complexType><xs:choice minOccurs=\'0\' maxOccurs=\'unbounded\'>'
    '<xs:element name=\'Meeting\'><xs:complexType><xs:sequence>'
    '<xs:element name=\'MeetingID\' type=\'xs:int\' msdata:ReadOnly=\'true\' msdata:AutoIncrement=\'true\' msdata:AutoIncrementSeed=\'-1\' msdata:AutoIncrementStep=\'-1\'/>'
    '<xs:element name=\'MeetingDate\' type=\'xs:dateTime\'/>'
    '<xs:element name=\'ResolutionDueDate\' type=\'xs:dateTime\'/>'
    '<xs:element name=\'MeetingTypeID\' type=\'xs:int\'/>'
    '<xs:element name=\'MeetingLocationID\' type=\'xs:int\'/>'
    '<xs:element name=\'MeetingStatusID\' type=\'xs:unsignedByte\' default=\'10\'/>'
    '<xs:element name=\'DepartmentID\' type=\'xs:int\' minOccurs=\'0\'/>'
    '<xs:element name=\'TimestampStart\' type=\'xs:dateTime\' minOccurs=\'0\' nillable=\'true\'/>'
    '<xs:element name=\'TimestampStartDelta\' type=\'xs:int\' minOccurs=\'0\' default=\'0\'/>'
    '<xs:element name=\'UnknownMeeting\' type=\'xs:string\' minOccurs=\'0\'/>'
    '</xs:sequence></xs:complexType></xs:element>'
    '<xs:element name=\'UnknownRow\'><xs:complexType><xs:sequence>'
    '<xs:element name=\'UnknownID\' type=\'xs:int\'/>'
    '<xs:element name=\'Payload\' type=\'xs:string\' minOccurs=\'0\'/>'
    '</xs:sequence></xs:complexType></xs:element>'
    '</xs:choice></xs:complexType>'
    '<xs:key name=\'MeetingKey\' msdata:PrimaryKey=\'true\'>'
    '<xs:selector xpath=\'.//mstns:Meeting\'/><xs:field xpath=\'mstns:MeetingID\'/>'
    '</xs:key></xs:element></xs:schema>'
)


def source():
    return Source('iqm2', URL, namespace=NS, input_format=iqm2_meeting_write.FORMAT, options={'minutetraq_agency': 'City of Test'})


def context(permissions=None, meeting_ids=None, department_ids=None, meeting_type_ids=None, meeting_location_ids=None):
    if permissions is None:
        permissions = ['meeting:create', 'meeting:update']
    if meeting_ids is None:
        meeting_ids = [501, 7001]
    if department_ids is None:
        department_ids = [2]
    if meeting_type_ids is None:
        meeting_type_ids = [3]
    if meeting_location_ids is None:
        meeting_location_ids = [4]
    config = {'tenant': 'test-client', 'origin': 'https://test.iqm2.com', 'agency': 'City of Test', 'allowed_namespaces': [NS], 'authorization_header': AUTH, 'client_version': VERSION, 'permissions': permissions, 'meeting_ids': meeting_ids, 'department_ids': department_ids, 'meeting_type_ids': meeting_type_ids, 'meeting_location_ids': meeting_location_ids}
    return OperationContext(principal='editor', client_id='test', tenant='test-client', authorization=frozenset({'write:plan', 'write:commit'}), allowed_namespaces=frozenset({NS}), credentials={'iqm2': config})


class State:
    def __init__(self, meeting_id=501):
        self.meeting_id = meeting_id
        self.next_create_id = 7001
        self.meeting_date = '2026-11-17T09:00:00'
        self.resolution_due_date = '2026-11-17T09:00:00'
        self.meeting_type_id = 3
        self.meeting_location_id = 4
        self.meeting_status_id = 10
        self.department_id = 2
        self.timestamp_start = '2026-11-17T17:00:00-07:00'
        self.timestamp_start_delta = 0
        self.unknown_meeting = 'keep-meeting-unknown'
        self.unknown_row = 'keep-unknown-row'


def _local(tag):
    if tag.startswith('{'):
        return tag.split('}', 1)[1]
    return tag


def _read_xml(state):
    return ('<?xml version=\'1.0\' encoding=\'utf-8\'?>'
            '<soap:Envelope xmlns:soap=\'' + iqm2_soap.SOAP_NS + '\'>'
            '<soap:Body><MeetingGetResponse xmlns=\'' + iqm2_soap.SERVICE_NS + '\'>'
            '<MeetingGetResult>' + SCHEMA_XML +
            '<diffgr:diffgram xmlns:diffgr=\'' + iqm2_soap.DIFFGR_NS + '\' xmlns:msdata=\'urn:schemas-microsoft-com:xml-msdata\'>'
            '<DB_1_0 xmlns=\'' + iqm2_soap.DB_NS + '\'>'
            '<Meeting diffgr:id=\'Meeting1\'>'
            '<MeetingID>' + str(state.meeting_id) + '</MeetingID>'
            '<MeetingDate>' + state.meeting_date + '</MeetingDate>'
            '<ResolutionDueDate>' + state.resolution_due_date + '</ResolutionDueDate>'
            '<MeetingTypeID>' + str(state.meeting_type_id) + '</MeetingTypeID>'
            '<MeetingLocationID>' + str(state.meeting_location_id) + '</MeetingLocationID>'
            '<MeetingStatusID>' + str(state.meeting_status_id) + '</MeetingStatusID>'
            '<DepartmentID>' + str(state.department_id) + '</DepartmentID>'
            '<TimestampStart>' + state.timestamp_start + '</TimestampStart>'
            '<TimestampStartDelta>' + str(state.timestamp_start_delta) + '</TimestampStartDelta>'
            '<UnknownMeeting>' + state.unknown_meeting + '</UnknownMeeting>'
            '</Meeting>'
            '<UnknownRow diffgr:id=\'UnknownRow1\'><UnknownID>1</UnknownID><Payload>' + state.unknown_row + '</Payload></UnknownRow>'
            '</DB_1_0></diffgr:diffgram></MeetingGetResult></MeetingGetResponse></soap:Body></soap:Envelope>').encode('utf-8')


def _update_ack_xml(meeting_id):
    return ('<?xml version=\'1.0\' encoding=\'utf-8\'?>'
            '<soap:Envelope xmlns:soap=\'' + iqm2_soap.SOAP_NS + '\'>'
            '<soap:Body><MeetingUpdateResponse xmlns=\'' + iqm2_soap.SERVICE_NS + '\'>'
            '<MeetingUpdateResult>'
            '<diffgr:diffgram xmlns:diffgr=\'' + iqm2_soap.DIFFGR_NS + '\'>'
            '<DB_1_0 xmlns=\'' + iqm2_soap.DB_NS + '\'>'
            '<Meeting><MeetingID>' + str(meeting_id) + '</MeetingID></Meeting>'
            '</DB_1_0></diffgr:diffgram>'
            '</MeetingUpdateResult></MeetingUpdateResponse></soap:Body></soap:Envelope>').encode('utf-8')


def _apply_update_xml(state, body):
    root = ET.fromstring(body)
    data_root = None
    for element in root.iter():
        if _local(element.tag) == 'DB_1_0':
            data_root = element
            break
    if data_root is None:
        raise AssertionError('Update request omitted DB_1_0')
    for row in list(data_root):
        if _local(row.tag) != 'Meeting':
            continue
        changes = row.attrib.get('{' + iqm2_soap.DIFFGR_NS + '}hasChanges')
        fields = {}
        for child in row:
            fields[_local(child.tag)] = child
        if 'MeetingID' in fields:
            text = (fields['MeetingID'].text or '').strip()
            if changes == 'inserted' and text == '-1':
                state.meeting_id = state.next_create_id
            elif text:
                state.meeting_id = int(text)
        mapping = {'MeetingDate': 'meeting_date', 'ResolutionDueDate': 'resolution_due_date', 'MeetingTypeID': 'meeting_type_id', 'MeetingLocationID': 'meeting_location_id', 'MeetingStatusID': 'meeting_status_id', 'DepartmentID': 'department_id', 'TimestampStartDelta': 'timestamp_start_delta', 'UnknownMeeting': 'unknown_meeting'}
        for field, attr in mapping.items():
            if field not in fields:
                continue
            child = fields[field]
            if child.attrib.get('{' + iqm2_soap.XSI_NS + '}nil') == 'true':
                continue
            text = child.text if child.text is not None else ''
            if field in {'MeetingDate', 'ResolutionDueDate', 'TimestampStart', 'UnknownMeeting'}:
                setattr(state, attr, text)
            else:
                setattr(state, attr, int(text))
        if 'TimestampStart' in fields:
            child = fields['TimestampStart']
            if child.attrib.get('{' + iqm2_soap.XSI_NS + '}nil') != 'true':
                state.timestamp_start = child.text if child.text is not None else ''


class XmlResponse(WriteResponse):
    def __init__(self, status, content, content_type='text/xml'):
        super().__init__(status, content)
        object.__setattr__(self, 'headers', {'Content-Type': content_type})


class Vendor:
    mock = True

    def __init__(self, state):
        self.state = state
        self.calls = []
        self.fault = None
        self.read_override = None
        self.read_content_type = 'text/xml'
        self.after_update = lambda: None

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert url == URL
        assert headers['Authorization'] == AUTH
        assert headers['MinuteTraqVersion'] == VERSION
        action = headers['SOAPAction']
        self.calls.append((action, body))
        if '/MeetingGet' in action:
            if self.fault == 'read_fail':
                raise TimeoutError()
            content = self.read_override if self.read_override is not None else _read_xml(self.state)
            return XmlResponse(200, content, self.read_content_type)
        if '/MeetingUpdate' in action:
            if self.fault == 'denied':
                return XmlResponse(403, b'')
            if self.fault == 'server_error':
                return XmlResponse(500, b'')
            if self.fault == 'soap_fault':
                return XmlResponse(200, ('<soap:Envelope xmlns:soap=\'http://schemas.xmlsoap.org/soap/envelope/\'><soap:Body><soap:Fault><faultstring>boom</faultstring></soap:Fault></soap:Body></soap:Envelope>').encode())
            _apply_update_xml(self.state, body)
            self.after_update()
            if self.fault == 'timeout':
                raise TimeoutError()
            if self.fault == 'bad_reply':
                return XmlResponse(200, b'not xml')
            if self.fault == 'wrong_ack':
                return XmlResponse(200, _read_xml(self.state))
            return XmlResponse(200, _update_ack_xml(self.state.meeting_id))
        raise AssertionError('Unexpected SOAPAction ' + action)


def setup(tmp_path, state=None):
    state = state or State()
    vendor = Vendor(state)
    caller = context()
    db_path = tmp_path / 'write.sqlite'
    engine = Engine(storage=SQLiteStorage(db_path))
    register(engine, default_adapters(vendor))
    return engine, caller, vendor, state, db_path


def change(operation='update', resource_id='501', fields=None, **overrides):
    base_fields = {'meeting_date': '2026-11-17T10:00:00', 'resolution_due_date': '2026-11-17T09:00:00', 'meeting_type_id': 3, 'meeting_location_id': 4, 'meeting_status_id': 10, 'department_id': 2, 'meeting_get': {'date_from': '2026-11-01T00:00:00', 'date_to': '2026-12-01T00:00:00', 'meeting_status': None, 'department_id': 2}}
    if fields:
        base_fields.update(fields)
    value = {'key': 'edit', 'entity': 'meeting', 'operation': operation, 'fields': base_fields}
    if operation == 'update':
        value['resource_id'] = resource_id
    value.update(overrides)
    return value


def plan(engine, caller, value=None):
    result = engine.execute('plan_write', {'source': source().public_dict(), 'changes': [value or change()]}, context=caller)
    assert result.status == 'completed', result.public_dict()
    return {key: result.data[key] for key in ('plan_id', 'plan_hash')}, result


def _update_bodies(vendor):
    return [body for action, body in vendor.calls if 'MeetingUpdate' in action]


class _Bounds:
    def __init__(self, max_records=100):
        self.max_records = max_records
        self.parser_bytes = 1000000
        self.transfer_bytes = 1000000


def test_create_readback_through_coordinator(tmp_path):
    engine, caller, vendor, state, _ = setup(tmp_path)
    approval, _ = plan(engine, caller, change('create'))
    result = engine.execute('commit_write', approval, context=caller)
    assert result.status == 'completed', result.public_dict()
    assert state.meeting_id == 7001
    assert state.meeting_date == '2026-11-17T10:00:00'
    bodies = _update_bodies(vendor)
    assert len(bodies) == 1
    root = ET.fromstring(bodies[0])
    data_root = next(element for element in root.iter() if _local(element.tag) == 'DB_1_0')
    rows = [element for element in list(data_root) if _local(element.tag) == 'Meeting']
    assert len(rows) == 1
    row = rows[0]
    assert row.attrib.get('{' + iqm2_soap.DIFFGR_NS + '}hasChanges') == 'inserted'
    assert row.find('{' + iqm2_soap.DB_NS + '}TimestampStart') is None
    delta = row.find('{' + iqm2_soap.DB_NS + '}TimestampStartDelta')
    assert delta is not None and delta.text == '0'


def test_update_before_current_protection_and_changed_row_only(tmp_path):
    engine, caller, vendor, state, _ = setup(tmp_path)
    approval, _ = plan(engine, caller)
    result = engine.execute('commit_write', approval, context=caller)
    assert result.status == 'completed', result.public_dict()
    assert state.meeting_date == '2026-11-17T10:00:00'
    assert state.unknown_meeting == 'keep-meeting-unknown'
    assert state.unknown_row == 'keep-unknown-row'
    body = _update_bodies(vendor)[0]
    root = ET.fromstring(body)
    data_root = next(element for element in root.iter() if _local(element.tag) == 'DB_1_0')
    assert not any(_local(element.tag) == 'UnknownRow' for element in root.iter())
    meeting_rows = [element for element in list(data_root) if _local(element.tag) == 'Meeting']
    changed_rows = [row for row in meeting_rows if row.attrib.get('{' + iqm2_soap.DIFFGR_NS + '}hasChanges') == 'modified']
    assert len(changed_rows) == 1
    timestamp = changed_rows[0].find('{' + iqm2_soap.DB_NS + '}TimestampStart')
    assert timestamp is not None and timestamp.text == '2026-11-17T17:00:00-07:00'


def test_lost_ack_create_unknown_id_no_resend(tmp_path):
    engine, caller, vendor, state, db_path = setup(tmp_path)
    approval, _ = plan(engine, caller, change('create'))
    vendor.fault = 'timeout'
    first = engine.execute('commit_write', approval, context=caller)
    assert first.data['items'][0]['state'] == 'uncertain'
    assert len(_update_bodies(vendor)) == 1
    vendor.fault = None
    reopened = Engine(storage=SQLiteStorage(db_path))
    register(reopened, default_adapters(vendor))
    second = reopened.execute('commit_write', approval, context=caller)
    assert second.status == 'partial', second.public_dict()
    assert second.data['items'][0]['state'] == 'uncertain'
    assert len(_update_bodies(vendor)) == 1


def test_known_id_cancel_persisted_then_reconciles(tmp_path):
    engine, caller, vendor, state, db_path = setup(tmp_path)
    approval, _ = plan(engine, caller, change('create'))
    vendor.after_update = caller.cancellation.set
    first = engine.execute('commit_write', approval, context=caller)
    assert first.data['items'][0]['state'] == 'uncertain'
    assert first.data['items'][0]['resource_id'] == '7001'
    assert len(_update_bodies(vendor)) == 1
    caller.cancellation.clear()
    vendor.after_update = lambda: None
    reopened = Engine(storage=SQLiteStorage(db_path))
    register(reopened, default_adapters(vendor))
    second = reopened.execute('commit_write', approval, context=caller)
    assert second.status == 'completed', second.public_dict()
    assert second.data['items'][0]['state'] == 'succeeded'
    assert len(_update_bodies(vendor)) == 1


def test_update_uncertain_readback_resume_without_resend(tmp_path):
    engine, caller, vendor, state, _ = setup(tmp_path)
    approval, _ = plan(engine, caller)
    vendor.fault = 'timeout'
    first = engine.execute('commit_write', approval, context=caller)
    assert first.data['items'][0]['state'] == 'uncertain'
    assert first.data['items'][0]['resource_id'] == '501'
    assert len(_update_bodies(vendor)) == 1
    vendor.fault = None
    second = engine.execute('commit_write', approval, context=caller)
    assert second.status == 'completed', second.public_dict()
    assert second.data['items'][0]['state'] == 'succeeded'
    assert len(_update_bodies(vendor)) == 1


@pytest.mark.parametrize('case', ['permissions', 'meeting_ids', 'department_ids', 'meeting_type_ids', 'meeting_location_ids', 'unknown_fields', 'typed_bool'])
def test_rejected_scope_never_calls_provider(tmp_path, case):
    engine, caller, vendor, state, _ = setup(tmp_path)
    value = change()
    if case == 'permissions':
        caller.credentials['iqm2']['permissions'] = []
    elif case == 'meeting_ids':
        caller.credentials['iqm2']['meeting_ids'] = []
    elif case == 'department_ids':
        caller.credentials['iqm2']['department_ids'] = [999]
    elif case == 'meeting_type_ids':
        caller.credentials['iqm2']['meeting_type_ids'] = [999]
    elif case == 'meeting_location_ids':
        caller.credentials['iqm2']['meeting_location_ids'] = [999]
    elif case == 'unknown_fields':
        value['fields']['extra'] = 'x'
    else:
        value['fields']['meeting_type_id'] = True
    result = engine.execute('plan_write', {'source': source().public_dict(), 'changes': [value]}, context=caller)
    assert result.status == 'failed', result.public_dict()
    assert not vendor.calls


@pytest.mark.parametrize('fields', [None, {'timestamp_start': '2026-11-17T17:00:00-07:00'}, {'timestamp_start_delta': -5}])
def test_optional_timestamp_fields_are_independently_optional(tmp_path, fields):
    engine, caller, vendor, state, _ = setup(tmp_path)
    approval, _ = plan(engine, caller, change(fields=fields))
    result = engine.execute('commit_write', approval, context=caller)
    assert result.status == 'completed', result.public_dict()
    assert len(_update_bodies(vendor)) == 1


def test_canonical_local_datetime_strips_native_offset_without_utc_conversion():
    assert iqm2_meeting_write._canonical_local_datetime('2026-11-17T17:00:00-07:00') == '2026-11-17T17:00:00'


def test_meeting_fingerprint_rejects_non_element_root():
    with pytest.raises(ValueError):
        iqm2_meeting_write._meeting_fingerprint('<schema/>', [], [])


def test_replace_meeting_row_returns_dataset_root():
    root = ET.fromstring('<DB_1_0 xmlns=\'' + iqm2_soap.DB_NS + '\'><Meeting><MeetingID>501</MeetingID></Meeting><UnknownRow><UnknownID>1</UnknownID></UnknownRow></DB_1_0>')
    replacement = ET.fromstring('<Meeting xmlns=\'' + iqm2_soap.DB_NS + '\'><MeetingID>501</MeetingID><MeetingDate>2026-11-17T10:00:00</MeetingDate></Meeting>')
    updated = iqm2_meeting_write._replace_meeting_row(root, replacement)
    assert updated.tag == '{' + iqm2_soap.DB_NS + '}DB_1_0'
    assert any(row.tag == '{' + iqm2_soap.DB_NS + '}UnknownRow' for row in list(updated))


def test_mime_guard_rejects_non_xml_read(tmp_path):
    engine, caller, vendor, state, _ = setup(tmp_path)
    vendor.read_content_type = 'text/plain'
    result = engine.execute('plan_write', {'source': source().public_dict(), 'changes': [change()]}, context=caller)
    assert result.status == 'failed', result.public_dict()
    assert not _update_bodies(vendor)


def test_timestamp_start_delta_int32_guard_on_read(tmp_path):
    engine, caller, vendor, state, _ = setup(tmp_path)
    vendor.read_override = _read_xml(state).replace(b'<TimestampStartDelta>0</TimestampStartDelta>', b'<TimestampStartDelta>2147483648</TimestampStartDelta>')
    result = engine.execute('plan_write', {'source': source().public_dict(), 'changes': [change()]}, context=caller)
    assert result.status == 'failed', result.public_dict()
    assert not _update_bodies(vendor)


def test_ack_rejects_dirty_or_multiple_meeting_rows():
    dirty = ('<soap:Envelope xmlns:soap=\'' + iqm2_soap.SOAP_NS + '\'><soap:Body><MeetingUpdateResponse xmlns=\'' + iqm2_soap.SERVICE_NS + '\'><MeetingUpdateResult><diffgr:diffgram xmlns:diffgr=\'' + iqm2_soap.DIFFGR_NS + '\'><DB_1_0 xmlns=\'' + iqm2_soap.DB_NS + '\'><Meeting diffgr:hasChanges=\'modified\'><MeetingID>501</MeetingID></Meeting></DB_1_0></diffgr:diffgram></MeetingUpdateResult></MeetingUpdateResponse></soap:Body></soap:Envelope>').encode()
    with pytest.raises(ValueError):
        iqm2_meeting_write._parse_meeting_update_ack(dirty)


def _powershell():
    exe = shutil.which('powershell.exe') or shutil.which('powershell') or shutil.which('pwsh')
    if not exe:
        if os.name == 'nt':
            pytest.fail('PowerShell is required for the independent .NET fixture on Windows.')
        pytest.skip('PowerShell is not available for independent .NET validation.')
    return exe


def test_actual_adapter_requests_validated_by_windows_fixture(tmp_path):
    script = Path(__file__).resolve().parent / 'fixtures' / 'iqm2' / 'meeting-wire-fixture.ps1'
    assert script.exists()
    exe = _powershell()
    generated = subprocess.run([exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-OutDir', str(tmp_path)], capture_output=True, text=True)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    baseline = (tmp_path / 'minutetraq-meeting-baseline-get-response.xml').read_bytes()
    vendor = Vendor(State())
    vendor.read_override = baseline
    adapter = iqm2_meeting_write.IQM2MeetingWriteAdapter(vendor)
    caller = context()
    prepared_update = adapter.prepare(source(), WriteChange.from_dict(change()), caller, _Bounds(), monotonic() + 5)
    update_path = tmp_path / 'actual-meeting-update-request.xml'
    update_path.write_bytes(base64.b64decode(prepared_update['native']['body_base64']))
    validated_update = subprocess.run([exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-OutDir', str(tmp_path), '-ValidateUpdate', str(update_path)], capture_output=True, text=True)
    assert validated_update.returncode == 0, validated_update.stdout + validated_update.stderr
    prepared_create = adapter.prepare(source(), WriteChange.from_dict(change('create')), caller, _Bounds(), monotonic() + 5)
    create_path = tmp_path / 'actual-meeting-create-request.xml'
    create_path.write_bytes(base64.b64decode(prepared_create['native']['body_base64']))
    validated_create = subprocess.run([exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-OutDir', str(tmp_path), '-ValidateCreate', str(create_path)], capture_output=True, text=True)
    assert validated_create.returncode == 0, validated_create.stdout + validated_create.stderr
