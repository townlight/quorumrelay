'''Synthetic MinuteTraq M2 recording upload tests and independent .NET wire proof.'''
import base64
import hashlib
import io
import os
import shutil
import subprocess
from pathlib import Path
from time import monotonic
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, urlsplit

import pytest

from quorumrelay import Engine, OperationContext, Source
from quorumrelay.storage import SQLiteStorage
from quorumrelay.write_adapters import WriteChange, default_adapters
from quorumrelay.write_transport import WriteResponse
from quorumrelay.writes import register
from civic_data_connectors.providers import iqm2_soap, iqm2_media_write as media
from civic_data_connectors.write_files import stage_write_file

URL = 'https://test.iqm2.com/MinuteTraqService/Data_1_0.asmx'
NS = '//test.iqm2.com/MinuteTraqService/agency/City%20of%20Test'
VERSION = '8.11.3.1452015'
CONNECTION_ID = '0123456789ABCDEF'
AUTH = ('Basic:clerk@City of Test:' + 'a' * 32 + ':' + CONNECTION_ID + ':M-127.0.0.1:' + 'MinuteTraq:' + VERSION + ':.NET 4.8')
BIGFILE_SCHEMA = ('<xs:schema id="DB_1_0" targetNamespace="' + iqm2_soap.DB_NS + '" '
                  'xmlns:mstns="' + iqm2_soap.DB_NS + '" xmlns="' + iqm2_soap.DB_NS + '" '
                  'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                  'xmlns:msdata="urn:schemas-microsoft-com:xml-msdata" '
                  'attributeFormDefault="qualified" elementFormDefault="qualified">'
                  '<xs:element name="DB_1_0" msdata:IsDataSet="true" msdata:UseCurrentLocale="true">'
                  '<xs:complexType><xs:choice minOccurs="0" maxOccurs="unbounded">'
                  '<xs:element name="BigFile"><xs:complexType><xs:sequence>'
                  '<xs:element name="FileType" type="xs:int"/>'
                  '<xs:element name="ID" type="xs:long"/>'
                  '<xs:element name="FileUpdated" type="xs:dateTime" minOccurs="0" nillable="true" msdata:DateTimeMode="UnspecifiedLocal"/>'
                  '<xs:element name="FileData" type="xs:base64Binary" minOccurs="0" nillable="true"/>'
                  '<xs:element name="FileSize" type="xs:long" minOccurs="0" nillable="true"/>'
                  '<xs:element name="FileFormat" type="xs:string" minOccurs="0" nillable="true"/>'
                  '</xs:sequence></xs:complexType></xs:element>'
                  '</xs:choice></xs:complexType></xs:element></xs:schema>')


def source():
    return Source('iqm2', URL, namespace=NS, input_format=media.FORMAT,
                  options={'minutetraq_agency': 'City of Test', 'meeting_id': 7001})


def context(permissions=None, meeting_ids=None, media_ids=None, file_handle=None, bigfiles_enabled=True):
    if permissions is None:
        permissions = ['recording:upload']
    if meeting_ids is None:
        meeting_ids = [7001]
    if media_ids is None:
        media_ids = [501]
    config = {'tenant': 'test-client', 'origin': 'https://test.iqm2.com', 'agency': 'City of Test',
              'allowed_namespaces': [NS], 'authorization_header': AUTH, 'client_version': VERSION,
              'permissions': permissions, 'meeting_ids': meeting_ids, 'media_ids': media_ids}
    if bigfiles_enabled is not None:
        config['bigfiles_enabled'] = bigfiles_enabled
    return OperationContext(principal='editor', client_id='test', tenant='test-client',
                            authorization=frozenset({'write:plan', 'write:commit'}),
                            allowed_namespaces=frozenset({NS}), credentials={'iqm2': config})


def _local(tag):
    if tag.startswith('{'):
        return tag.split('}', 1)[1]
    return tag


def _child_text(row, name):
    for child in row:
        if _local(child.tag) == name:
            return child.text or ''
    return ''


def _media_schema(extra=''):
    if not extra:
        return media._MEDIA_SCHEMA_XML
    return media._MEDIA_SCHEMA_XML.replace('</xs:sequence>', extra + '</xs:sequence>')


def _row_xml(state, media_id, meeting_id, values, unknown=''):
    return ('<Media diffgr:id="Media' + str(media_id) + '">'
            '<MediaID>' + str(media_id) + '</MediaID>'
            '<MeetingID>' + str(meeting_id) + '</MeetingID>'
            '<MediaEventID>0</MediaEventID>'
            '<MediaStatusID>' + str(values.get('MediaStatusID', 100)) + '</MediaStatusID>'
            '<FileFormat>' + values.get('FileFormat', 'mp4') + '</FileFormat>'
            '<FileSize>' + str(values.get('FileSize', 0)) + '</FileSize>'
            '<FileData>' + values.get('FileData', '') + '</FileData>'
            '<Started>' + values.get('Started', '2026-11-17T18:00:00') + '</Started>'
            '<Duration>0</Duration>'
            '<Published>' + values.get('Published', '2026-11-17T18:00:00') + '</Published>'
            '<Created>2026-11-17T18:00:00</Created>'
            '<CreatedUserID>1</CreatedUserID>'
            '<Updated>2026-11-17T18:00:00</Updated>'
            '<UpdatedUserID>1</UpdatedUserID>' + unknown + '</Media>')


def _media_get_response(media_id, meeting_id, values, unknown=''):
    schema = _media_schema(unknown)
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="' + iqm2_soap.SOAP_NS + '">'
            '<soap:Body><MediaGetResponse xmlns="' + iqm2_soap.SERVICE_NS + '">'
            '<MediaGetResult>' + schema +
            '<diffgr:diffgram xmlns:diffgr="' + iqm2_soap.DIFFGR_NS + '" xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">'
            '<DB_1_0 xmlns="' + iqm2_soap.DB_NS + '">' + _row_xml(None, media_id, meeting_id, values, unknown) +
            '</DB_1_0></diffgr:diffgram></MediaGetResult></MediaGetResponse></soap:Body></soap:Envelope>').encode('utf-8')


def _bigfile_info_response(identity, file_size=None, file_updated=None):
    size_xml = ''
    if file_size is not None:
        size_xml = '<FileSize>' + str(file_size) + '</FileSize>'
    updated_xml = ''
    if file_updated is not None:
        updated_xml = '<FileUpdated>' + file_updated + '</FileUpdated>'
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="' + iqm2_soap.SOAP_NS + '">'
            '<soap:Body><BigFileGetUploadInfoResponse xmlns="' + iqm2_soap.SERVICE_NS + '">'
            '<BigFileGetUploadInfoResult>' + BIGFILE_SCHEMA +
            '<diffgr:diffgram xmlns:diffgr="' + iqm2_soap.DIFFGR_NS + '">'
            '<DB_1_0 xmlns="' + iqm2_soap.DB_NS + '">'
            '<BigFile><FileType>11</FileType><ID>' + str(identity) + '</ID>' + updated_xml + size_xml +
            '</BigFile></DB_1_0></diffgr:diffgram>'
            '</BigFileGetUploadInfoResult></BigFileGetUploadInfoResponse></soap:Body></soap:Envelope>').encode('utf-8')


def _ack(method, media_id):
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="' + iqm2_soap.SOAP_NS + '">'
            '<soap:Body><' + method + 'Response xmlns="' + iqm2_soap.SERVICE_NS + '">'
            '<' + method + 'Result><diffgr:diffgram xmlns:diffgr="' + iqm2_soap.DIFFGR_NS + '">'
            '<DB_1_0 xmlns="' + iqm2_soap.DB_NS + '"><Media><MediaID>' + str(media_id) +
            '</MediaID></Media></DB_1_0></diffgr:diffgram></' + method + 'Result>'
            '</' + method + 'Response></soap:Body></soap:Envelope>').encode('utf-8')


def _bigfile_ack():
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="' + iqm2_soap.SOAP_NS + '">'
            '<soap:Body><BigFileAppendResponse xmlns="' + iqm2_soap.SERVICE_NS + '">'
            '<BigFileAppendResult><diffgr:diffgram xmlns:diffgr="' + iqm2_soap.DIFFGR_NS + '">'
            '<DB_1_0 xmlns="' + iqm2_soap.DB_NS + '"><BigFile><FileType>11</FileType><ID>-1</ID></BigFile>'
            '</DB_1_0></diffgr:diffgram></BigFileAppendResult>'
            '</BigFileAppendResponse></soap:Body></soap:Envelope>').encode('utf-8')


class XmlResponse(WriteResponse):
    def __init__(self, status, content, content_type='text/xml'):
        super().__init__(status, content)
        object.__setattr__(self, 'headers', {'Content-Type': content_type})


class Vendor:
    mock = True

    def __init__(self):
        self.media = {}
        self.media_unknown = {}
        self.upload_bytes = {}
        self.staging_bytes = {}
        self.next_media_id = 9001
        self.calls = []
        self.append_calls = 0
        self.update_calls = 0
        self.fault_append_after_apply = False
        self.fault_append_before_apply = False
        self.fault_update_after_apply = False
        self.corrupt_download = False
        self.partial_upload = None
        self.after_media_ack = None

    def _find_media(self, media_id):
        return self.media.get(str(media_id))

    def _parse_body(self, body):
        return ET.fromstring(body)

    def _parse_media_update(self, body):
        root = self._parse_body(body)
        data_root = next(element for element in root.iter() if _local(element.tag) == 'DB_1_0')
        rows = [element for element in list(data_root) if _local(element.tag) == 'Media']
        if len(rows) != 1:
            raise AssertionError('expected one MediaUpdate row')
        row = rows[0]
        values = {}
        for child in row:
            values[_local(child.tag)] = child.text or ''
        return values

    def _parse_append(self, body):
        root = self._parse_body(body)
        data_root = next(element for element in root.iter() if _local(element.tag) == 'DB_1_0')
        rows = [element for element in list(data_root) if _local(element.tag) == 'BigFile']
        if len(rows) != 1:
            raise AssertionError('expected one BigFileAppend row')
        row = rows[0]
        file_type = int(_child_text(row, 'FileType'))
        identity = _child_text(row, 'ID')
        chunk = base64.b64decode(_child_text(row, 'FileData'))
        return file_type, identity, chunk

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        assert deadline_seconds > 0
        self.calls.append((method, url, body, headers))
        if url == URL:
            assert headers['Authorization'] == AUTH
            assert headers['MinuteTraqVersion'] == VERSION
            action = headers['SOAPAction']
            if '/MediaGet' in action:
                root = self._parse_body(body)
                media_id = next(element.text for element in root.iter() if _local(element.tag) == 'MediaID')
                row = self._find_media(media_id)
                if row is None:
                    return XmlResponse(500, b'')
                return XmlResponse(200, _media_get_response(
                    int(media_id), 7001, row, self.media_unknown.get(str(media_id), '')))
            if '/BigFileGetUploadInfo' in action:
                root = self._parse_body(body)
                identity = next(element.text for element in root.iter() if _local(element.tag) == 'ID')
                partial = self.partial_upload or {}
                if partial:
                    return XmlResponse(200, _bigfile_info_response(
                        identity, partial.get('file_size'), partial.get('file_updated')))
                staged = self.staging_bytes.get(identity)
                return XmlResponse(200, _bigfile_info_response(
                    identity, len(staged) if staged else None))
            if '/BigFileAppend' in action:
                self.append_calls += 1
                file_type, identity, chunk = self._parse_append(body)
                assert file_type == 11
                if self.fault_append_before_apply:
                    raise TimeoutError()
                self.staging_bytes.setdefault(identity, bytearray()).extend(chunk)
                if self.fault_append_after_apply:
                    raise TimeoutError()
                return XmlResponse(200, _bigfile_ack())
            if '/MediaUpdate' in action:
                self.update_calls += 1
                values = self._parse_media_update(body)
                given_id = values.get('MediaID', '-1')
                if given_id == '-1':
                    media_id = self.next_media_id
                    self.next_media_id += 1
                    self.media[str(media_id)] = dict(values, MediaID=str(media_id))
                    self.upload_bytes[str(media_id)] = self.staging_bytes.pop('-1', bytearray())
                else:
                    media_id = int(given_id)
                    existing = dict(self.media[str(media_id)])
                    existing.update(values)
                    self.media[str(media_id)] = existing
                    staged = self.staging_bytes.pop(str(media_id), None)
                    if staged is not None:
                        self.upload_bytes[str(media_id)] = staged
                if self.fault_update_after_apply:
                    raise TimeoutError()
                content = _ack('MediaUpdate', media_id)
                if self.after_media_ack:
                    self.after_media_ack()
                return XmlResponse(200, content)
            raise AssertionError('unexpected SOAPAction ' + action)
        parsed = urlsplit(url)
        assert parsed.path == '/Citizens/FileOpen.aspx'
        query = dict(parse_qsl(parsed.query))
        assert query['Type'] == '11'
        assert query['Inline'] == 'true'
        assert query['IsMinuteTraqRequest'] == 'true'
        assert query['AgencyName'] == 'City of Test'
        assert headers['Authorization'] == AUTH
        assert headers['User-Agent'] == 'MinuteTraq'
        data = bytes(self.upload_bytes.get(query['ID'], b''))
        if self.corrupt_download:
            data = data[:-1] + bytes([(data[-1] + 1) % 256]) if data else b'x'
        return WriteResponse(200, data)


def setup(tmp_path):
    vendor = Vendor()
    caller = context()
    engine = Engine(storage=SQLiteStorage(tmp_path / 'media.sqlite'))
    register(engine, default_adapters(vendor))
    return engine, caller, vendor


def file_part(data, filename='recording.mp4'):
    return {'part': 'file', 'filename': filename, 'content_type': 'video/mp4',
            'content_base64': base64.b64encode(data).decode()}


def _stage_file(engine, caller, data, filename='recording.mp4'):
    return stage_write_file(engine, io.BytesIO(data), context=caller,
                            filename=filename, content_type='video/mp4')


def change(data, media_id=None, published='2026-11-17T18:00:00'):
    value = {'key': 'upload', 'entity': 'recording', 'operation': 'upload',
             'fields': {'published': published}, 'files': [file_part(data)]}
    if media_id is not None:
        value['resource_id'] = str(media_id)
    return value


def plan(engine, caller, value):
    result = engine.execute('plan_write', {'source': source().public_dict(), 'changes': [value]}, context=caller)
    assert result.status == 'completed', result.public_dict()
    return {key: result.data[key] for key in ('plan_id', 'plan_hash')}, result


def commit(engine, caller, approval):
    return engine.execute('commit_write', approval, context=caller)


def test_new_recording_multichunk_upload_and_hash_readback(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    data = bytes(range(256)) * 4300
    approval, planned = plan(engine, caller, change(data))
    prepared = planned.data['plan']['changes'][0]
    assert prepared['published'] == '2026-11-17T18:00:00'
    assert prepared['file']['sha256'] == hashlib.sha256(data).hexdigest()
    assert prepared['chunks_total'] == 3
    result = commit(engine, caller, approval)
    assert result.status == 'completed', result.public_dict()
    assert result.data['items'][0]['resource_id'] == '9001'
    assert bytes(vendor.upload_bytes['9001']) == data
    assert vendor.append_calls == 3
    assert vendor.update_calls == 1
    receipt = engine.execute('receipt', {'plan_id': approval['plan_id']}, context=caller)
    assert receipt.status == 'completed', receipt.public_dict()


def test_public_engine_file_handle_and_base64_roundtrip(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    data = b'public engine file handle and base64'
    approval, planned = plan(engine, caller, change(data))
    prepared = planned.data['plan']['changes'][0]
    assert prepared['file']['byte_length'] == len(data)
    assert prepared['file']['sha256'] == hashlib.sha256(data).hexdigest()
    result = commit(engine, caller, approval)
    assert result.status == 'completed', result.public_dict()
    assert bytes(vendor.upload_bytes['9001']) == data

    handle_data = b'public engine file handle upload'
    handle = _stage_file(engine, caller, handle_data)
    value = {'key': 'upload-handle', 'entity': 'recording', 'operation': 'upload',
             'fields': {'published': '2026-11-17T18:00:00'},
             'files': [{'part': 'file', 'filename': 'recording.mp4',
                        'content_type': 'video/mp4', 'file_handle': handle}]}
    handle_approval, handle_planned = plan(engine, caller, value)
    handle_prepared = handle_planned.data['plan']['changes'][0]
    assert handle_prepared['file']['byte_length'] == len(handle_data)
    assert handle_prepared['file']['sha256'] == hashlib.sha256(handle_data).hexdigest()
    handle_result = commit(engine, caller, handle_approval)
    assert handle_result.status == 'completed', handle_result.public_dict()
    assert handle_result.data['items'][0]['resource_id'] == '9002'
    assert bytes(vendor.upload_bytes['9002']) == handle_data


def test_existing_replacement_preserves_unknown_and_parent(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    old = b'old recording'
    vendor.media['501'] = {'MediaID': '501', 'MeetingID': '7001', 'MediaEventID': '0',
                           'MediaStatusID': '100', 'FileFormat': 'mp4',
                           'FileSize': str(len(old)), 'FileData': base64.b64encode(b'~~BIGFILE~~old.mp4').decode(),
                           'Started': '2026-11-16T18:00:00', 'Duration': '0',
                           'Published': '2026-11-16T18:00:00'}
    vendor.media_unknown['501'] = '<UnknownMedia>keep-unknown</UnknownMedia>'
    vendor.upload_bytes['501'] = bytearray(old)
    data = b'replacement bytes' * 100
    approval, _ = plan(engine, caller, change(data, media_id=501))
    result = commit(engine, caller, approval)
    assert result.status == 'completed', result.public_dict()
    assert result.data['items'][0]['resource_id'] == '501'
    assert vendor.media['501']['MeetingID'] == '7001'
    assert vendor.media['501']['UnknownMedia'] == 'keep-unknown'
    assert bytes(vendor.upload_bytes['501']) == data


def test_nonempty_preexisting_staging_rejected_before_mutation(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    vendor.partial_upload = {'file_size': 123, 'file_updated': '2026-11-17T17:00:00'}
    result = engine.execute('plan_write', {
        'source': source().public_dict(), 'changes': [change(b'data')]
    }, context=caller)
    assert result.status == 'failed', result.public_dict()
    assert vendor.append_calls == 0
    assert vendor.update_calls == 0


def test_lost_append_ack_uncertain_and_no_replay_across_reopen(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    approval, _ = plan(engine, caller, change(b'a' * 600000))
    vendor.fault_append_after_apply = True
    first = commit(engine, caller, approval)
    assert first.data['items'][0]['state'] == 'uncertain'
    assert vendor.append_calls == 1
    assert vendor.update_calls == 0
    vendor.fault_append_after_apply = False
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'media.sqlite'))
    register(reopened, default_adapters(vendor))
    second = commit(reopened, caller, approval)
    assert second.data['items'][0]['state'] == 'uncertain'
    assert vendor.append_calls == 1
    assert vendor.update_calls == 0


def test_cancellation_after_metadata_ack_persists_id_and_reconciles_without_replay(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    data = b'metadata ack then cancel'
    approval, _ = plan(engine, caller, change(data))
    vendor.after_media_ack = caller.cancellation.set
    first = commit(engine, caller, approval)
    assert first.data['items'][0]['state'] == 'uncertain'
    assert first.data['items'][0]['resource_id'] == '9001'
    assert vendor.update_calls == 1
    caller.cancellation.clear()
    vendor.after_media_ack = None
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'media.sqlite'))
    register(reopened, default_adapters(vendor))
    second = commit(reopened, caller, approval)
    assert second.status == 'completed', second.public_dict()
    assert second.data['items'][0]['state'] == 'succeeded'
    assert vendor.update_calls == 1


def test_wrong_download_hash_is_uncertain_then_reconciles_without_replay(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    data = b'original file hash proof' * 40
    approval, _ = plan(engine, caller, change(data))
    vendor.corrupt_download = True
    first = commit(engine, caller, approval)
    assert first.data['items'][0]['state'] == 'uncertain'
    assert first.data['items'][0]['resource_id'] == '9001'
    assert vendor.update_calls == 1
    vendor.corrupt_download = False
    reopened = Engine(storage=SQLiteStorage(tmp_path / 'media.sqlite'))
    register(reopened, default_adapters(vendor))
    second = commit(reopened, caller, approval)
    assert second.status == 'completed', second.public_dict()
    assert second.data['items'][0]['state'] == 'succeeded'
    assert vendor.update_calls == 1


def test_credentials_and_bounds_fail_before_mutation(tmp_path):
    engine, caller, vendor = setup(tmp_path)
    caller.credentials['iqm2']['permissions'] = []
    result = engine.execute('plan_write', {
        'source': source().public_dict(), 'changes': [change(b'data')]
    }, context=caller)
    assert result.status == 'failed'
    assert vendor.append_calls == 0 and vendor.update_calls == 0
    caller = context()
    small = {'source': source().public_dict(), 'changes': [change(b'x' * 100)],
             'bounds': {'transfer_bytes': 10, 'parser_bytes': 10000, 'max_records': 100}}
    result = engine.execute('plan_write', small, context=caller)
    assert result.status == 'failed'
    assert vendor.append_calls == 0 and vendor.update_calls == 0


def test_bigfiles_configuration_required_before_network(tmp_path):
    for value in (False, None):
        vendor = Vendor()
        engine = Engine(storage=SQLiteStorage(tmp_path / f'media-{value}.sqlite'))
        register(engine, default_adapters(vendor))
        caller = context(bigfiles_enabled=value)
        result = engine.execute('plan_write', {
            'source': source().public_dict(), 'changes': [change(b'data')]
        }, context=caller)
        assert result.status == 'failed', result.public_dict()
        assert vendor.calls == []
        assert vendor.append_calls == 0 and vendor.update_calls == 0


def _powershell():
    exe = shutil.which('powershell.exe') or shutil.which('powershell') or shutil.which('pwsh')
    if not exe:
        if os.name == 'nt':
            pytest.fail('PowerShell is required for the independent .NET fixture on Windows.')
        pytest.skip('PowerShell is not available for independent .NET validation.')
    return exe


def test_actual_adapter_requests_validated_by_windows_fixture(tmp_path):
    script = Path(__file__).resolve().parent / 'fixtures' / 'iqm2' / 'media-wire-fixture.ps1'
    assert script.exists()
    exe = _powershell()
    generated = subprocess.run([exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                                '-OutDir', str(tmp_path)], capture_output=True, text=True)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    upload_info_path = tmp_path / 'minutetraq-media-bigfile-upload-info.xml'
    upload_info_content = upload_info_path.read_bytes()
    upload_info = media._parse_bigfile_upload_info_response(upload_info_content, '-1')
    append_body = media._build_bigfile_append_body(upload_info, b'a' * 512000)
    append_path = tmp_path / 'actual-bigfile-append.xml'
    append_path.write_bytes(append_body)
    validated = subprocess.run([exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                                '-OutDir', str(tmp_path), '-ValidateBigFileAppend', str(append_path)],
                               capture_output=True, text=True)
    assert validated.returncode == 0, validated.stdout + validated.stderr
    vendor = Vendor()
    adapter = media.IQM2MediaWriteAdapter(vendor)
    caller = context()
    data = b'b' * 1000
    value = WriteChange.from_dict({
        'key': 'upload', 'entity': 'recording', 'operation': 'upload',
        'fields': {'published': '2026-11-17T18:00:00'},
        'files': [{'part': 'file', 'filename': 'recording.mp4', 'content_type': 'video/mp4',
                   'reference': {'byte_length': len(data), 'sha256': hashlib.sha256(data).hexdigest()}}],
    })
    prepared = adapter.prepare(source(), value, caller, type('B', (), {
        'max_records': 100, 'parser_bytes': 2000000, 'transfer_bytes': 2000000})(), monotonic() + 5)
    new_path = tmp_path / 'actual-media-update-new.xml'
    new_path.write_bytes(base64.b64decode(prepared['native']['body_base64']))
    validated_new = subprocess.run([exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                                    '-OutDir', str(tmp_path), '-ValidateMediaUpdateNew', str(new_path)],
                                   capture_output=True, text=True)
    assert validated_new.returncode == 0, validated_new.stdout + validated_new.stderr
