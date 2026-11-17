'''Scoped MinuteTraq M2 recording upload via immutable staged files and native BigFile/MediaUpdate SOAP.'''
from __future__ import annotations

import base64
import hashlib
import re
from copy import deepcopy
from dataclasses import asdict
from time import monotonic
from urllib.parse import quote, urlencode, urlsplit
import xml.etree.ElementTree as ET

from ..write_adapters import (
    AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure,
)
from ..write_transport import WriteResponse
from . import iqm2_soap, iqm2_write

FORMAT = 'iqm2-minutetraq-media-soap-xml'
FILE_TYPE_MEDIA = 11
CHUNK_SIZE = 512000
MAX_INT32 = 2147483647
MAX_INT64 = 9223372036854775807
SERVICE_NS = iqm2_soap.SERVICE_NS
SOAP_NS = iqm2_soap.SOAP_NS
DIFFGR_NS = iqm2_soap.DIFFGR_NS
DB_NS = iqm2_soap.DB_NS
XSI_NS = iqm2_soap.XSI_NS
XML_SCHEMA_NS = iqm2_write.XML_SCHEMA_NS
MSDATA_NS = iqm2_write.MSDATA_NS
_OPTION_KEYS = {'minutetraq_agency', 'meeting_id'}
_MAX_AGENCY_LENGTH = 128
_MEDIA_EVENT_ID = 0
_MEDIA_ID_FIELD = 'MediaID'
_MEDIA_FIELDS = (
    'MediaID', 'MeetingID', 'MediaEventID', 'MediaStatusID', 'MediaStatusMessage',
    'MediaEncoderID', 'FileFormat', 'FileUpdated', 'FileSize', 'FileData',
    'FileSizeMP4', 'MediaURL', 'MediaURLMP4', 'Started', 'Duration', 'Published',
    'TranscodeStatusID', 'TranscodeID', 'TranscodeFormats', 'TranscodeTimeLeft',
    'TranscodeProgress', 'TranscodeInfo', 'TranscodeStarted', 'TranscodeUpdated',
    'MediaEncoderPresetID', 'LocalVaultStatusID', 'Created', 'CreatedUserID',
    'Updated', 'MediaEncoderStartDelta', 'UpdatedUserID',
)
_DATE_FIELDS = {
    'FileUpdated', 'Started', 'Published', 'TranscodeStarted', 'TranscodeUpdated',
    'Created', 'Updated',
}
_READBACK_IGNORED_FIELDS = {
    'FileUpdated', 'FileSizeMP4', 'MediaURL', 'MediaURLMP4', 'TranscodeStatusID',
    'TranscodeID', 'TranscodeFormats', 'TranscodeTimeLeft', 'TranscodeProgress',
    'TranscodeInfo', 'TranscodeStarted', 'TranscodeUpdated', 'LocalVaultStatusID',
    'Created', 'CreatedUserID', 'Updated', 'UpdatedUserID',
}
_MEDIA_SCHEMA_XML = '''<xs:schema id='DB_1_0' targetNamespace='http://tempuri.org/DB_1_0.xsd' xmlns:mstns='http://tempuri.org/DB_1_0.xsd' xmlns='http://tempuri.org/DB_1_0.xsd' xmlns:xs='http://www.w3.org/2001/XMLSchema' xmlns:msdata='urn:schemas-microsoft-com:xml-msdata' attributeFormDefault='qualified' elementFormDefault='qualified'><xs:element name='DB_1_0' msdata:IsDataSet='true' msdata:UseCurrentLocale='true'><xs:complexType><xs:choice minOccurs='0' maxOccurs='unbounded'><xs:element name='Media'><xs:complexType><xs:sequence><xs:element name='MediaID' type='xs:int' msdata:ReadOnly='true' msdata:AutoIncrement='true' msdata:AutoIncrementSeed='-1' msdata:AutoIncrementStep='-1'/><xs:element name='MeetingID' type='xs:int'/><xs:element name='MediaEventID' type='xs:int'/><xs:element name='MediaStatusID' type='xs:unsignedByte' default='20'/><xs:element name='MediaStatusMessage' type='xs:string' minOccurs='0'/><xs:element name='MediaEncoderID' type='xs:short' minOccurs='0'/><xs:element name='FileFormat' type='xs:string' minOccurs='0'/><xs:element name='FileUpdated' type='xs:dateTime' minOccurs='0' msdata:DateTimeMode='UnspecifiedLocal'/><xs:element name='FileSize' type='xs:long' minOccurs='0'/><xs:element name='FileData' type='xs:base64Binary' minOccurs='0'/><xs:element name='FileSizeMP4' type='xs:long' minOccurs='0'/><xs:element name='MediaURL' type='xs:string' minOccurs='0'/><xs:element name='MediaURLMP4' type='xs:string' minOccurs='0'/><xs:element name='Started' type='xs:dateTime' msdata:DateTimeMode='UnspecifiedLocal'/><xs:element name='Duration' type='xs:int'/><xs:element name='Published' type='xs:dateTime' minOccurs='0' msdata:DateTimeMode='UnspecifiedLocal'/><xs:element name='TranscodeStatusID' type='xs:unsignedByte' default='10'/><xs:element name='TranscodeID' type='xs:long' minOccurs='0'/><xs:element name='TranscodeFormats' type='xs:string' minOccurs='0'/><xs:element name='TranscodeTimeLeft' type='xs:long' minOccurs='0'/><xs:element name='TranscodeProgress' type='xs:unsignedByte' default='0'/><xs:element name='TranscodeInfo' type='xs:string' minOccurs='0'/><xs:element name='TranscodeStarted' type='xs:dateTime' minOccurs='0' msdata:DateTimeMode='UnspecifiedLocal'/><xs:element name='TranscodeUpdated' type='xs:dateTime' minOccurs='0' msdata:DateTimeMode='UnspecifiedLocal'/><xs:element name='MediaEncoderPresetID' type='xs:int' minOccurs='0'/><xs:element name='LocalVaultStatusID' type='xs:unsignedByte' default='20'/><xs:element name='Created' type='xs:dateTime' msdata:DateTimeMode='UnspecifiedLocal'/><xs:element name='CreatedUserID' type='xs:int'/><xs:element name='Updated' type='xs:dateTime' msdata:DateTimeMode='UnspecifiedLocal'/><xs:element name='MediaEncoderStartDelta' type='xs:int' default='0' minOccurs='0'/><xs:element name='UpdatedUserID' type='xs:int'/></xs:sequence></xs:complexType></xs:element></xs:choice></xs:complexType><xs:key name='MediaKey' msdata:PrimaryKey='true'><xs:selector xpath='.//mstns:Media'/><xs:field xpath='mstns:MediaID'/></xs:key></xs:element></xs:schema>'''
_MEDIA_SCHEMA_NS = [('xs', XML_SCHEMA_NS), ('msdata', MSDATA_NS), ('mstns', DB_NS)]
_EXPECTED_TYPES = {
    'MediaID': 'int', 'MeetingID': 'int', 'MediaEventID': 'int',
    'MediaStatusID': 'unsignedByte', 'MediaStatusMessage': 'string',
    'MediaEncoderID': 'short', 'FileFormat': 'string', 'FileUpdated': 'dateTime',
    'FileSize': 'long', 'FileData': 'base64Binary', 'FileSizeMP4': 'long',
    'MediaURL': 'string', 'MediaURLMP4': 'string', 'Started': 'dateTime',
    'Duration': 'int', 'Published': 'dateTime', 'TranscodeStatusID': 'unsignedByte',
    'TranscodeID': 'long', 'TranscodeFormats': 'string', 'TranscodeTimeLeft': 'long',
    'TranscodeProgress': 'unsignedByte', 'TranscodeInfo': 'string',
    'TranscodeStarted': 'dateTime', 'TranscodeUpdated': 'dateTime',
    'MediaEncoderPresetID': 'int', 'LocalVaultStatusID': 'unsignedByte',
    'Created': 'dateTime', 'CreatedUserID': 'int', 'Updated': 'dateTime',
    'MediaEncoderStartDelta': 'int', 'UpdatedUserID': 'int',
}


def _positive_int32(value, label):
    if isinstance(value, bool):
        raise ValueError(label + ' must be a positive native identifier.')
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and re.fullmatch('[1-9][0-9]*', value):
        parsed = int(value)
    else:
        raise ValueError(label + ' must be a positive native identifier.')
    if not 1 <= parsed <= MAX_INT32:
        raise ValueError(label + ' must be within the native identifier range.')
    return str(parsed)


def _positive_int64(value, label):
    if isinstance(value, bool):
        raise ValueError(label + ' must be a positive native identifier.')
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and re.fullmatch('[1-9][0-9]*', value):
        parsed = int(value)
    else:
        raise ValueError(label + ' must be a positive native identifier.')
    if not 1 <= parsed <= MAX_INT64:
        raise ValueError(label + ' must be within the native identifier range.')
    return str(parsed)


def _validate_options(source):
    options = source.options
    if not isinstance(options, dict) or set(options) != _OPTION_KEYS:
        raise ValueError('MinuteTraq media options must be exactly minutetraq_agency and meeting_id.')
    agency = options['minutetraq_agency']
    if not isinstance(agency, str) or not agency or len(agency) > _MAX_AGENCY_LENGTH:
        raise ValueError('minutetraq_agency must be a bounded non-empty agency label.')
    if agency != agency.strip() or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in agency):
        raise ValueError('minutetraq_agency must be a bounded non-empty agency label.')
    meeting_id = _positive_int32(options['meeting_id'], 'meeting_id')
    return {'minutetraq_agency': agency, 'meeting_id': meeting_id}


def _media_namespace(source):
    options = _validate_options(source)
    parsed = urlsplit(source.url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port is not None:
        raise ValueError('MinuteTraq media URLs must be exact HTTPS URLs without credentials or ports.')
    host = parsed.hostname.lower() if parsed.hostname else ''
    if not re.fullmatch('[^.]+[.]iqm2[.]com', host):
        raise ValueError('MinuteTraq media host must be a tenant .iqm2.com host.')
    if parsed.path != '/MinuteTraqService/Data_1_0.asmx' or parsed.query or parsed.fragment:
        raise ValueError('MinuteTraq media URL must be the exact Data_1_0.asmx endpoint.')
    return '//' + host + '/MinuteTraqService/agency/' + quote(options['minutetraq_agency'], safe='')


def _allowlisted(config, key, value):
    values = config.get(key)
    if not isinstance(values, (list, tuple, set, frozenset)) or not values or len(values) > 128:
        return False
    target = str(value)
    for candidate in values:
        if isinstance(candidate, bool):
            return False
        try:
            parsed = _positive_int32(candidate, key)
        except ValueError:
            return False
        if parsed == target:
            return True
    return False


def _trusted_config(source, options, namespace_value, context):
    credentials = getattr(context, 'credentials', None)
    config = credentials.get('iqm2') if isinstance(credentials, dict) else None
    if not isinstance(config, dict) or not context.tenant:
        raise iqm2_soap._CredentialsError
    if config.get('tenant') != context.tenant:
        raise iqm2_soap._CredentialsError
    if config.get('origin') != iqm2_soap._source_origin(source):
        raise iqm2_soap._CredentialsError
    if config.get('agency') != options['minutetraq_agency']:
        raise iqm2_soap._CredentialsError
    allowed = config.get('allowed_namespaces')
    if (not isinstance(allowed, (list, tuple, set, frozenset)) or not allowed
            or len(allowed) > 128 or namespace_value not in allowed):
        raise iqm2_soap._CredentialsError
    if not _allowlisted(config, 'meeting_ids', options['meeting_id']):
        raise iqm2_soap._CredentialsError
    version = config.get('client_version')
    if not isinstance(version, str) or not re.fullmatch('[0-9]+[.][0-9]+[.][0-9]+[.][0-9]+', version):
        raise iqm2_soap._CredentialsError
    authorization_header = config.get('authorization_header')
    iqm2_soap._validate_authorization_header(authorization_header, options['minutetraq_agency'], version)
    permissions = config.get('permissions')
    if not isinstance(permissions, (list, tuple, set, frozenset)) or 'recording:upload' not in permissions:
        raise iqm2_soap._CredentialsError
    if config.get('bigfiles_enabled') is not True:
        raise ValueError('Native MinuteTraq BigFiles media upload must be explicitly enabled.')
    return {'authorization_header': authorization_header, 'client_version': version, 'config': config}


def _schema_type_local(type_value):
    if not isinstance(type_value, str):
        return None
    return type_value.rsplit(':', 1)[-1]


def _validate_media_schema(schema_raw):
    try:
        root = ET.fromstring(schema_raw)
    except ET.ParseError as exc:
        raise ValueError('The inline Media schema could not be parsed.') from exc
    if root.tag != '{' + XML_SCHEMA_NS + '}schema':
        raise ValueError('The inline Media schema could not be parsed.')
    if root.attrib.get('targetNamespace') != DB_NS:
        raise ValueError('The native Media schema targetNamespace is not DB_1_0.')
    if root.attrib.get('elementFormDefault') != 'qualified':
        raise ValueError('The native Media schema must use qualified elements.')
    data_element = None
    for element in root.iter():
        if element.tag == '{' + XML_SCHEMA_NS + '}element' and element.attrib.get('name') == 'DB_1_0':
            data_element = element
            break
    if data_element is None or data_element.attrib.get('{' + MSDATA_NS + '}IsDataSet') not in {'true', '1'}:
        raise ValueError('The inline schema does not define the native DB_1_0 DataSet.')
    media = None
    for element in data_element.iter():
        if element.tag == '{' + XML_SCHEMA_NS + '}element' and element.attrib.get('name') == 'Media':
            media = element
            break
    if media is None:
        raise ValueError('The inline schema does not define the Media table.')
    fields = {}
    for child in media.iter():
        if child.tag == '{' + XML_SCHEMA_NS + '}element' and child.attrib.get('name') in _MEDIA_FIELDS:
            fields[child.attrib['name']] = child
    if set(fields) != set(_MEDIA_FIELDS):
        raise ValueError('The native Media schema must contain all 31 Media fields.')
    for name, expected in _EXPECTED_TYPES.items():
        actual = _schema_type_local(fields[name].attrib.get('type'))
        if actual != expected:
            raise ValueError('Native Media field ' + name + ' has an unexpected type.')
    for name in _DATE_FIELDS:
        mode = fields[name].attrib.get('{' + MSDATA_NS + '}DateTimeMode')
        if mode and mode != 'UnspecifiedLocal':
            raise ValueError('Unsupported native DateTimeMode for ' + name + '.')
    media_id = fields['MediaID']
    if media_id.attrib.get('{' + MSDATA_NS + '}ReadOnly') not in {'true', '1'}:
        raise ValueError('MediaID must be readonly.')
    if media_id.attrib.get('{' + MSDATA_NS + '}AutoIncrement') not in {'true', '1'}:
        raise ValueError('MediaID must be autoincrement.')
    if (media_id.attrib.get('{' + MSDATA_NS + '}AutoIncrementSeed') != '-1'
            or media_id.attrib.get('{' + MSDATA_NS + '}AutoIncrementStep') != '-1'):
        raise ValueError('MediaID must use source -1 seed/step.')
    primary_key = False
    for element in data_element.iter():
        if element.tag not in {'{' + XML_SCHEMA_NS + '}key', '{' + XML_SCHEMA_NS + '}unique'}:
            continue
        if element.attrib.get('{' + MSDATA_NS + '}PrimaryKey') not in {'true', '1'}:
            continue
        selector = next((child for child in element if child.tag == '{' + XML_SCHEMA_NS + '}selector'), None)
        field = next((child for child in element if child.tag == '{' + XML_SCHEMA_NS + '}field'), None)
        if selector is not None and field is not None:
            if 'Media' in selector.attrib.get('xpath', '') and 'MediaID' in field.attrib.get('xpath', ''):
                primary_key = True
    if not primary_key:
        raise ValueError('MediaID must be the native primary key.')


def _canonical_media_datetime(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' must be an explicit native dateTime.')
    try:
        return iqm2_write._canonical_native_datetime(value.strip())
    except ValueError:
        raise ValueError(label + ' must be an explicit native dateTime.') from None


def _canonicalize_media_row(row, readback):
    for child in list(row):
        local = iqm2_soap._local(child.tag)
        if readback and local in _READBACK_IGNORED_FIELDS:
            row.remove(child)
            continue
        if local not in _DATE_FIELDS:
            continue
        if child.attrib.get('{' + XSI_NS + '}nil') in {'true', '1'}:
            continue
        if child.text is not None and child.text.strip():
            child.text = _canonical_media_datetime(child.text, local)


def _media_fingerprint(schema_raw, schema_ns_decls, data_root, *, readback=False):
    if not ET.iselement(data_root):
        raise ValueError('Media fingerprint requires a copied DB_1_0 dataset root.')
    root = deepcopy(data_root)
    for row in list(root):
        if row.tag == '{' + DB_NS + '}Media':
            _canonicalize_media_row(row, readback)
    return iqm2_write.canonical_hash({
        'schema': schema_raw,
        'schema_namespaces': sorted(schema_ns_decls),
        'data': iqm2_write._root_repr(root, 'media'),
    })


def _build_media_get_body(media_id, meeting_id):
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="' + SOAP_NS + '">'
            '<soap:Body><MediaGet xmlns="' + SERVICE_NS + '">'
            '<MediaID>' + str(media_id) + '</MediaID>'
            '<MeetingID>' + str(meeting_id) + '</MeetingID>'
            '<MediaEventID>' + str(_MEDIA_EVENT_ID) + '</MediaEventID>'
            '<fRetrieveTranscript>false</fRetrieveTranscript>'
            '</MediaGet></soap:Body></soap:Envelope>').encode('utf-8')


def _build_bigfile_get_body(file_type, identity):
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="' + SOAP_NS + '">'
            '<soap:Body><BigFileGetUploadInfo xmlns="' + SERVICE_NS + '">'
            '<FileType>' + str(file_type) + '</FileType>'
            '<ID>' + str(identity) + '</ID>'
            '</BigFileGetUploadInfo></soap:Body></soap:Envelope>').encode('utf-8')


def _response_media_type(response):
    headers = getattr(response, 'headers', None)
    if not isinstance(headers, dict):
        return None
    for key, value in headers.items():
        if str(key).lower() == 'content-type':
            return str(value).split(';', 1)[0].strip().lower()
    return None


def _response_result(content, method):
    root = iqm2_soap._parse_xml(content)
    if root.tag != '{' + SOAP_NS + '}Envelope':
        raise ValueError('Saved response must be a SOAP 1.1 Envelope.')
    body = iqm2_soap._single_ns(root, SOAP_NS, 'Body', 'SOAP Body')
    if any(iqm2_soap._local(element.tag) == 'Fault' for element in body.iter()):
        raise ValueError('SOAP Fault responses are not successful acknowledgments.')
    body_children = list(body)
    if len(body_children) != 1:
        raise ValueError('SOAP Body must contain exactly one response.')
    response = body_children[0]
    if response.tag != '{' + SERVICE_NS + '}' + method + 'Response':
        raise ValueError('The response operation is malformed.')
    result_children = list(response)
    if len(result_children) != 1:
        raise ValueError('The response must contain exactly one result.')
    result = result_children[0]
    if result.tag != '{' + SERVICE_NS + '}' + method + 'Result':
        raise ValueError('The response result wrapper is malformed.')
    return result


def _parse_media_get_response(content, expected_media_id, expected_meeting_id):
    result = _response_result(content, 'MediaGet')
    schema_raw, schema_ns_decls = iqm2_write._extract_raw_schema(content)
    _validate_media_schema(schema_raw)
    diffgram = iqm2_soap._single_ns(result, DIFFGR_NS, 'diffgram', 'diffgram')
    if [child for child in diffgram if child.tag in {'{' + DIFFGR_NS + '}before', '{' + DIFFGR_NS + '}errors'}]:
        raise ValueError('Media read snapshots must not contain before/errors blocks.')
    data_root = iqm2_soap._single_ns(diffgram, DB_NS, 'DB_1_0', 'DB_1_0 data root')
    rows = []
    for row in list(data_root):
        ns_uri, local = iqm2_soap._split_tag(row.tag)
        if local == 'Media' and ns_uri != DB_NS:
            raise ValueError('A Media row uses a foreign namespace.')
        if local == 'Media':
            changes = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasChanges')
            errors = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasErrors')
            if changes is not None and changes.strip():
                raise ValueError('Media read snapshots must not contain changed rows.')
            if errors is not None and errors.strip().lower() in {'true', '1'}:
                raise ValueError('Media read snapshots must not contain row errors.')
            rows.append(row)
    if len(rows) != 1:
        raise ValueError('MediaGet must return exactly one current Media row.')
    row = rows[0]
    media_id = iqm2_soap._int32_text(row, 'MediaID')
    meeting_id = iqm2_soap._int32_text(row, 'MeetingID')
    if str(media_id) != str(expected_media_id):
        raise ValueError('MediaID does not match the selected media identity.')
    if str(meeting_id) != str(expected_meeting_id):
        raise ValueError('MeetingID does not match the selected meeting identity.')
    return {
        'schema_raw': schema_raw,
        'schema_ns_decls': schema_ns_decls,
        'data_root': data_root,
        'media_row': row,
        'media_id': str(media_id),
        'meeting_id': str(meeting_id),
        'fingerprint': _media_fingerprint(schema_raw, schema_ns_decls, data_root),
    }


def _parse_bigfile_upload_info_response(content, expected_id):
    result = _response_result(content, 'BigFileGetUploadInfo')
    schema_raw, schema_ns_decls = iqm2_write._extract_raw_schema(content)
    diffgram = iqm2_soap._single_ns(result, DIFFGR_NS, 'diffgram', 'diffgram')
    if [child for child in diffgram if child.tag in {'{' + DIFFGR_NS + '}before', '{' + DIFFGR_NS + '}errors'}]:
        raise ValueError('BigFile upload-info snapshots must not contain before/errors blocks.')
    data_root = iqm2_soap._single_ns(diffgram, DB_NS, 'DB_1_0', 'DB_1_0 data root')
    rows = []
    for row in list(data_root):
        ns_uri, local = iqm2_soap._split_tag(row.tag)
        if local == 'BigFile' and ns_uri != DB_NS:
            raise ValueError('A BigFile row uses a foreign namespace.')
        if local == 'BigFile':
            changes = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasChanges')
            errors = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasErrors')
            if changes is not None and changes.strip():
                raise ValueError('BigFile upload-info snapshots must not contain changed rows.')
            if errors is not None and errors.strip().lower() in {'true', '1'}:
                raise ValueError('BigFile upload-info snapshots must not contain row errors.')
            rows.append(row)
    if len(rows) != 1:
        raise ValueError('BigFileGetUploadInfo must return exactly one BigFile row.')
    row = rows[0]
    file_type = iqm2_soap._required_text(row, 'FileType')
    identity = iqm2_soap._required_text(row, 'ID')
    if file_type != str(FILE_TYPE_MEDIA):
        raise ValueError('BigFile FileType must be the native media type 11.')
    if identity != str(expected_id):
        raise ValueError('BigFile ID does not match the selected native identity.')
    exists, nil, value = iqm2_soap._child_value(row, 'FileSize')
    if exists and not nil and value and value.strip() and int(value.strip()) != 0:
        raise ValueError('A nonempty preexisting BigFile upload offset exists; no resume or delete is permitted.')
    exists, nil, value = iqm2_soap._child_value(row, 'FileUpdated')
    if exists and not nil and value and value.strip():
        raise ValueError('A nonempty preexisting BigFile upload timestamp exists; no resume or delete is permitted.')
    exists, nil, value = iqm2_soap._child_value(row, 'FileData')
    if exists and not nil and value and value.strip():
        raise ValueError('A nonempty preexisting BigFile upload payload exists; no resume or delete is permitted.')
    return {
        'schema_raw': schema_raw,
        'schema_ns_decls': schema_ns_decls,
        'data_root': data_root,
        'row': row,
        'file_type': FILE_TYPE_MEDIA,
        'id': str(expected_id),
    }


def _parse_media_update_ack(content):
    result = _response_result(content, 'MediaUpdate')
    diffgram = iqm2_soap._single_ns(result, DIFFGR_NS, 'diffgram', 'diffgram')
    if [child for child in diffgram if child.tag in {'{' + DIFFGR_NS + '}before', '{' + DIFFGR_NS + '}errors'}]:
        raise ValueError('MediaUpdate acknowledgment must not contain before/errors blocks.')
    data_root = iqm2_soap._single_ns(diffgram, DB_NS, 'DB_1_0', 'DB_1_0 data root')
    rows = []
    for row in list(data_root):
        if iqm2_soap._local(row.tag) == 'Media':
            changes = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasChanges')
            errors = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasErrors')
            if changes is not None and changes.strip():
                raise ValueError('MediaUpdate acknowledgment must not contain dirty rows.')
            if errors is not None and errors.strip().lower() in {'true', '1'}:
                raise ValueError('MediaUpdate acknowledgment must not contain row errors.')
            rows.append(row)
    if len(rows) != 1:
        raise ValueError('MediaUpdate acknowledgment must return exactly one Media row.')
    return str(iqm2_soap._int32_text(rows[0], 'MediaID'))


def _set_media_values(row, values):
    iqm2_write._set_field(row, 'MeetingID', str(values['meeting_id']))
    iqm2_write._set_field(row, 'Duration', '0')
    iqm2_write._set_field(row, 'MediaStatusID', '100')
    iqm2_write._set_field(row, 'FileFormat', values['file_format'])
    iqm2_write._set_field(row, 'FileData', values['marker_base64'])
    iqm2_write._set_field(row, 'Started', values['started'])
    iqm2_write._set_field(row, 'FileSize', str(values['file_size']))
    iqm2_write._set_field(row, 'Published', values['published'])


def _replace_media_row(data_root, media_row):
    if not ET.iselement(data_root):
        raise ValueError('Media replacement requires a copied DB_1_0 dataset root.')
    root = deepcopy(data_root)
    replaced = False
    for index, row in enumerate(list(root)):
        if row.tag == '{' + DB_NS + '}Media':
            root[index] = deepcopy(media_row)
            replaced = True
    if not replaced:
        raise ValueError('The selected dataset does not contain a Media row.')
    return root


def _build_bigfile_append_body(upload_info, chunk):
    before = deepcopy(upload_info['row'])
    after = deepcopy(upload_info['row'])
    iqm2_write._ensure_diffgr_id(before, 'BigFile', upload_info['id'])
    iqm2_write._ensure_diffgr_id(after, 'BigFile', upload_info['id'])
    after.attrib['{' + DIFFGR_NS + '}hasChanges'] = 'modified'
    iqm2_write._set_field(after, 'FileData', base64.b64encode(chunk).decode('ascii'))
    return iqm2_write._build_request_body(
        'BigFileAppend', upload_info['schema_raw'], upload_info['schema_ns_decls'],
        [after], [before])


def _file_info(change):
    if len(change.files) != 1:
        raise ValueError('A recording upload requires exactly one immutable file input.')
    part = change.files[0]
    if not isinstance(part, dict) or set(part) != {'part', 'filename', 'content_type', 'reference'}:
        raise ValueError('A recording file requires part, filename, content_type and an immutable reference.')
    if part['part'] != 'file':
        raise ValueError('The recording file part must be named file.')
    filename = part['filename']
    if (not isinstance(filename, str) or not filename or len(filename) > 200
            or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_. -]{0,199}', filename)
            or '/' in filename or chr(92) in filename or '..' in filename):
        raise ValueError('The recording filename must be a bounded ASCII basename.')
    try:
        filename.encode('ascii')
    except UnicodeError:
        raise ValueError('The recording filename must be ASCII.') from None
    content_type = part['content_type']
    if not isinstance(content_type, str) or not re.fullmatch('[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+', content_type):
        raise ValueError('The recording content type is invalid.')
    reference = part['reference']
    if not isinstance(reference, dict):
        raise ValueError('The recording file reference is invalid.')
    length = reference.get('byte_length')
    digest = reference.get('sha256')
    if type(length) is not int or length <= 0:
        raise ValueError('The recording file must be nonempty.')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('The recording file reference must contain its SHA-256.')
    suffix = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if not suffix or not re.fullmatch('[a-z0-9]{1,10}', suffix):
        raise ValueError('The recording filename must include a native file-format suffix.')
    marker = b'~~BIGFILE~~' + filename.encode('ascii')
    if len(marker) > 1500:
        raise ValueError('The native BigFile marker exceeds its bounded size.')
    return {
        'filename': filename,
        'content_type': content_type,
        'byte_length': length,
        'sha256': digest,
        'file_format': suffix,
        'marker_base64': base64.b64encode(marker).decode('ascii'),
        'chunk_size': CHUNK_SIZE,
        'chunks_total': (length + CHUNK_SIZE - 1) // CHUNK_SIZE,
    }


class IQM2MediaWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__('iqm2', transport)

    def credentials(self, source, context):
        if source.provider != self.provider:
            raise WriteFailure('mapping_unverified', 'The selected source is not an iQM2 MinuteTraq source.')
        if source.input_format != FORMAT or source.body is not None:
            raise WriteFailure('mapping_unverified', 'The exact saved MinuteTraq media SOAP source format is required.')
        try:
            options = _validate_options(source)
            namespace_value = _media_namespace(source)
            if source.namespace != namespace_value:
                raise ValueError('Source namespace does not match the selected agency endpoint.')
            trusted = _trusted_config(source, options, namespace_value, context)
        except iqm2_soap._CredentialsError:
            raise WriteFailure('credentials_required', 'A trusted MinuteTraq session-scoped credential is required.') from None
        except ValueError as exc:
            raise WriteFailure('mapping_unverified', str(exc)) from None
        if context.allowed_namespaces is not None and namespace_value not in context.allowed_namespaces:
            raise WriteFailure('permission_denied', 'The selected MinuteTraq namespace is outside current policy.')
        return {
            'options': options,
            'namespace': namespace_value,
            'authorization': trusted['authorization_header'],
            'client_version': trusted['client_version'],
            'config': trusted['config'],
        }

    def validate_source(self, source, context):
        self.credentials(source, context)

    def _validate_change(self, change, binding):
        if change.entity != 'recording' or change.operation != 'upload':
            raise WriteFailure('mapping_unverified', 'Only recording:upload is mapped.')
        if any(value is not None for value in (
                change.parent_id, change.language, change.page_number, change.meeting_id, change.expected_version)):
            raise WriteFailure('mapping_unverified', 'Foreign relationship, revision or media event metadata is not mapped.')
        if change.resource_id is not None:
            media_id = _positive_int32(change.resource_id, 'resource_id')
            if not _allowlisted(binding['config'], 'media_ids', media_id):
                raise WriteFailure('permission_denied', 'The selected existing MediaID is outside current policy.')
        else:
            media_id = None
        fields = change.fields
        if not isinstance(fields, dict) or not fields or set(fields) - {'published', 'started'} or 'published' not in fields:
            raise ValueError('Recording fields must contain published and optional started.')
        published = _canonical_media_datetime(fields['published'], 'published')
        started = _canonical_media_datetime(fields.get('started', published), 'started')
        file_info = _file_info(change)
        return {
            'media_id': media_id,
            'existing': media_id is not None,
            'meeting_id': binding['options']['meeting_id'],
            'media_event_id': _MEDIA_EVENT_ID,
            'published': published,
            'started': started,
            'started_source': 'caller' if 'started' in fields else 'published',
            'file': file_info,
        }

    def authorize(self, source, change, context):
        binding = self.credentials(source, context)
        self._validate_change(change, binding)

    def _headers(self, binding, method):
        return {
            'Content-Type': 'text/xml;charset=utf-8',
            'SOAPAction': '"' + SERVICE_NS + '/' + method + '"',
            'Authorization': binding['authorization'],
            'MinuteTraqVersion': binding['client_version'],
        }

    def _read_soap(self, source, binding, method, body, context, bounds, deadline):
        if context.check_cancelled():
            raise WriteCancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure('deadline_exceeded', 'The MinuteTraq read deadline expired.')
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        if len(body) > limit or limit < 1:
            raise ValueError('The exact MinuteTraq request exceeds byte bounds.')
        try:
            response = self.transport.send(
                source.url, method='POST', body=body, headers=self._headers(binding, method),
                byte_limit=limit, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq dataset could not be read.') from None
        if context.check_cancelled():
            raise WriteCancelled()
        if not isinstance(response, WriteResponse) or len(response.content) > limit:
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq response was invalid.')
        if response.status in {401, 403}:
            raise WriteFailure('permission_denied', 'The provider denied the selected MinuteTraq read.')
        if response.status != 200:
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq response was not successful.')
        media_type = _response_media_type(response)
        if media_type is not None and media_type not in {'text/xml', 'application/xml'}:
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq read did not return XML.')
        if monotonic() >= deadline:
            raise WriteFailure('deadline_exceeded', 'The MinuteTraq read exceeded the total deadline.')
        return response

    def _mutate_soap(self, source, binding, method, body, context, bounds, deadline):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise AmbiguousWrite('The mutation deadline expired before send; no resend is permitted.')
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        if len(body) > limit or limit < 1:
            raise ValueError('The exact MinuteTraq mutation request exceeds byte bounds.')
        try:
            response = self.transport.send(
                source.url, method='POST', body=body, headers=self._headers(binding, method),
                byte_limit=limit, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite('The MinuteTraq mutation may have been accepted; do not resend.') from None
        if not isinstance(response, WriteResponse) or len(response.content) > limit:
            raise AmbiguousWrite('The MinuteTraq mutation response was invalid.')
        if response.status in {401, 403}:
            raise WriteFailure('permission_denied', 'The provider denied the selected MinuteTraq mutation.')
        if response.status in {409, 412}:
            raise WriteFailure('conflict', 'The provider rejected the MinuteTraq mutation as conflicting.')
        if not 200 <= response.status < 300:
            raise AmbiguousWrite('The MinuteTraq mutation response was not successful; do not resend.')
        media_type = _response_media_type(response)
        if media_type is not None and media_type not in {'text/xml', 'application/xml'}:
            raise AmbiguousWrite('The MinuteTraq mutation acknowledgment was not XML; do not resend.')
        try:
            _response_result(response.content, method)
        except ValueError:
            raise AmbiguousWrite('The MinuteTraq acknowledgment could not be exactly verified; do not resend.') from None
        return response

    def _read_media(self, source, binding, media_id, context, bounds, deadline):
        body = _build_media_get_body(media_id, binding['options']['meeting_id'])
        response = self._read_soap(source, binding, 'MediaGet', body, context, bounds, deadline)
        try:
            parsed = _parse_media_get_response(
                response.content, media_id, binding['options']['meeting_id'])
        except ValueError as exc:
            raise WriteFailure('minutetraq_unavailable', str(exc)) from None
        if len(list(parsed['data_root'])) > bounds.max_records:
            raise ValueError('The selected MinuteTraq media dataset exceeds the configured record bound.')
        return parsed

    def _read_upload_info(self, source, binding, identity, context, bounds, deadline):
        body = _build_bigfile_get_body(FILE_TYPE_MEDIA, identity)
        response = self._read_soap(source, binding, 'BigFileGetUploadInfo', body, context, bounds, deadline)
        try:
            return _parse_bigfile_upload_info_response(response.content, identity)
        except ValueError as exc:
            raise WriteFailure('conflict', str(exc)) from None

    def _download_original(self, source, binding, media_id, file_info, context, bounds, deadline):
        if context.check_cancelled():
            raise AmbiguousWrite('The recording was sent, but cancellation prevented original-file readback.')
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise AmbiguousWrite('The recording was sent, but the readback deadline expired.')
        parsed = urlsplit(source.url)
        query = urlencode([
            ('Type', str(FILE_TYPE_MEDIA)),
            ('Inline', 'true'),
            ('IsMinuteTraqRequest', 'true'),
            ('ID', str(media_id)),
            ('AgencyName', binding['options']['minutetraq_agency']),
        ])
        url = parsed.scheme + '://' + parsed.netloc + '/Citizens/FileOpen.aspx?' + query
        headers = {'Authorization': binding['authorization'], 'User-Agent': 'MinuteTraq'}
        limit = bounds.transfer_bytes
        if file_info['byte_length'] > limit:
            raise ValueError('The selected recording exceeds the transfer byte limit.')
        try:
            response = self.transport.send(
                url, method='GET', body=None, headers=headers,
                byte_limit=limit, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite('The original recording download could not be confirmed.') from None
        if context.check_cancelled() or monotonic() >= deadline:
            raise AmbiguousWrite('The original recording download finished outside active bounds.')
        if not isinstance(response, WriteResponse) or response.status != 200 or len(response.content) > limit:
            raise AmbiguousWrite('The original recording download was not successful.')
        if len(response.content) != file_info['byte_length']:
            raise AmbiguousWrite('The original recording byte length does not match the immutable file.')
        if hashlib.sha256(response.content).hexdigest() != file_info['sha256']:
            raise AmbiguousWrite('The original recording SHA-256 does not match the immutable file.')
        return response.content

    def _matches_target(self, row, prepared):
        try:
            if str(iqm2_soap._int32_text(row, 'MediaID')) != str(prepared['expected_media_id']):
                return False
            if str(iqm2_soap._int32_text(row, 'MeetingID')) != str(prepared['meeting_id']):
                return False
            if iqm2_soap._required_text(row, 'Duration') != '0':
                return False
            if iqm2_soap._required_text(row, 'MediaStatusID') != '100':
                return False
            if iqm2_soap._required_text(row, 'FileFormat') != prepared['file']['file_format']:
                return False
            if iqm2_soap._required_text(row, 'FileSize') != str(prepared['file']['byte_length']):
                return False
            if _canonical_media_datetime(iqm2_soap._required_text(row, 'Published'), 'Published') != prepared['published']:
                return False
            if _canonical_media_datetime(iqm2_soap._required_text(row, 'Started'), 'Started') != prepared['started']:
                return False
            exists, nil, value = iqm2_soap._child_value(row, 'FileData')
            if not exists or nil or value is None:
                return False
            return base64.b64decode(value, validate=True) == base64.b64decode(prepared['file']['marker_base64'])
        except (ValueError, TypeError):
            return False

    def prepare(self, source, change, context, bounds, deadline):
        binding = self.credentials(source, context)
        normalized = self._validate_change(change, binding)
        if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
            raise ValueError('A bounded change key is required.')
        file_info = normalized['file']
        if file_info['byte_length'] > bounds.transfer_bytes:
            raise ValueError('The recording file exceeds the configured transfer byte limit.')
        identity = normalized['media_id'] or '-1'
        self._read_upload_info(source, binding, identity, context, bounds, deadline)
        target_values = {
            'meeting_id': normalized['meeting_id'],
            'file_format': file_info['file_format'],
            'marker_base64': file_info['marker_base64'],
            'started': normalized['started'],
            'file_size': file_info['byte_length'],
            'published': normalized['published'],
        }
        if normalized['existing']:
            current = self._read_media(source, binding, normalized['media_id'], context, bounds, deadline)
            before = deepcopy(current['media_row'])
            after = deepcopy(current['media_row'])
            _set_media_values(after, target_values)
            iqm2_write._ensure_diffgr_id(before, 'Media', normalized['media_id'])
            iqm2_write._ensure_diffgr_id(after, 'Media', normalized['media_id'])
            after.attrib['{' + DIFFGR_NS + '}hasChanges'] = 'modified'
            target_root = _replace_media_row(current['data_root'], after)
            body = iqm2_write._build_request_body(
                'MediaUpdate', current['schema_raw'], current['schema_ns_decls'], [after], [before])
            before_fingerprint = current['fingerprint']
            target_fingerprint = _media_fingerprint(
                current['schema_raw'], current['schema_ns_decls'], target_root, readback=True)
        else:
            row = ET.Element('{' + DB_NS + '}Media')
            iqm2_write._ensure_diffgr_id(row, 'Media', '-1')
            row.attrib['{' + DIFFGR_NS + '}hasChanges'] = 'inserted'
            iqm2_write._set_field(row, 'MediaID', '-1')
            _set_media_values(row, target_values)
            body = iqm2_write._build_request_body(
                'MediaUpdate', _MEDIA_SCHEMA_XML, _MEDIA_SCHEMA_NS, [row], [])
            before_fingerprint = None
            target_fingerprint = None
        if len(body) > min(bounds.parser_bytes, bounds.transfer_bytes):
            raise ValueError('The exact MinuteTraq MediaUpdate request exceeds byte bounds.')
        return {
            'change': asdict(change),
            'meeting_id': normalized['meeting_id'],
            'media_id': normalized['media_id'],
            'media_event_id': normalized['media_event_id'],
            'existing': normalized['existing'],
            'published': normalized['published'],
            'started': normalized['started'],
            'started_source': normalized['started_source'],
            'file': file_info,
            'file_type': FILE_TYPE_MEDIA,
            'chunk_size': CHUNK_SIZE,
            'chunks_total': file_info['chunks_total'],
            'before_fingerprint': before_fingerprint,
            'target_fingerprint': target_fingerprint,
            'target_values': target_values,
            'method': 'MediaUpdate',
            'native': {
                'method': 'POST',
                'url': source.url,
                'body_base64': base64.b64encode(body).decode('ascii'),
                'headers': {},
            },
            'conflict_semantics': 'preflight_compare_not_atomic_upstream_cas' if normalized['existing'] else 'new_row_exact_returned_id_no_inference',
            'effects': {
                'entity': 'recording',
                'creates': not normalized['existing'],
                'updates': normalized['existing'],
                'deletes': False,
                'publication': True,
                'files': True,
                'transcoding_admin': False,
            },
        }

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        binding = self.credentials(source, context)
        change = WriteChange.from_dict(prepared['change'])
        normalized = self._validate_change(change, binding)
        file_info = normalized['file']
        identity = normalized['media_id'] or '-1'
        if normalized['existing']:
            current = self._read_media(source, binding, normalized['media_id'], context, bounds, deadline)
            if current['fingerprint'] != prepared['before_fingerprint']:
                raise WriteFailure('conflict', 'The selected MinuteTraq media changed after planning.')
        upload_info = self._read_upload_info(source, binding, identity, context, bounds, deadline)
        if persist and persist({'phase': 'upload_info', 'file': file_info, 'upload_session': {'file_type': FILE_TYPE_MEDIA, 'id': identity}}):
            raise WriteCancelled()
        chunks = []
        offset = 0
        with self._open_file(change.files[0]) as stream:
            for index in range(file_info['chunks_total']):
                if context.check_cancelled():
                    if chunks:
                        raise AmbiguousWrite('The recording was partially uploaded; cancellation prevents continuation.')
                    raise WriteCancelled()
                if monotonic() >= deadline:
                    if chunks:
                        raise AmbiguousWrite('The recording was partially uploaded; the deadline prevents continuation.')
                    raise WriteFailure('deadline_exceeded', 'The MinuteTraq upload deadline expired before the first chunk.')
                wanted = min(CHUNK_SIZE, file_info['byte_length'] - offset)
                data = stream.read(wanted)
                if len(data) != wanted:
                    raise ValueError('The immutable recording length changed before upload.')
                digest = hashlib.sha256(data).hexdigest()
                if persist and persist({
                    'phase': 'chunk_intent',
                    'append_intent': {
                        'index': index,
                        'offset': offset,
                        'length': len(data),
                        'sha256': digest,
                        'file_type': FILE_TYPE_MEDIA,
                        'id': identity,
                    },
                }):
                    if chunks:
                        raise AmbiguousWrite('The recording was partially uploaded; cancellation prevents continuation.')
                    raise WriteCancelled()
                body = _build_bigfile_append_body(upload_info, data)
                self._mutate_soap(source, binding, 'BigFileAppend', body, context, bounds, deadline)
                chunks.append({'index': index, 'offset': offset, 'length': len(data), 'sha256': digest})
                offset += len(data)
                if persist and persist({
                    'phase': 'chunk_ack',
                    'append_intent': None,
                    'chunks': list(chunks),
                    'upload_session': {'file_type': FILE_TYPE_MEDIA, 'id': identity, 'bytes_acknowledged': offset},
                }):
                    raise AmbiguousWrite('The recording chunk was acknowledged, but cancellation prevents metadata/readback.')
            if stream.read(1):
                raise ValueError('The immutable recording length changed before upload.')
        if context.check_cancelled() or monotonic() >= deadline:
            raise AmbiguousWrite('The recording chunks were acknowledged, but cancellation/deadline prevents metadata.')
        if persist and persist({
            'phase': 'metadata_intent',
            'metadata_intent': {'file_type': FILE_TYPE_MEDIA, 'id': identity, 'chunks': list(chunks)},
            'chunks': list(chunks),
        }):
            raise AmbiguousWrite('The recording chunks were acknowledged, but cancellation prevents metadata.')
        body = base64.b64decode(prepared['native']['body_base64'])
        response = self._mutate_soap(source, binding, 'MediaUpdate', body, context, bounds, deadline)
        try:
            returned_id = _parse_media_update_ack(response.content)
        except ValueError:
            raise AmbiguousWrite('The MediaUpdate acknowledgment did not return an exact MediaID; do not resend.') from None
        if normalized['existing'] and returned_id != normalized['media_id']:
            return {
                'state': 'uncertain',
                'resource_id': normalized['media_id'],
                'reason': 'MediaUpdate returned a different MediaID; do not resend.',
            }
        result_id = normalized['media_id'] if normalized['existing'] else returned_id
        if persist and persist({
            'phase': 'metadata_ack',
            'resource_id': result_id,
            'metadata_ack': {'media_id': result_id},
            'metadata_intent': None,
            'chunks': list(chunks),
        }):
            return {
                'state': 'uncertain',
                'resource_id': result_id,
                'reason': 'Returned MediaID was persisted, but cancellation/deadline prevented readback.',
            }
        try:
            after = self._read_media(source, binding, result_id, context, bounds, deadline)
            if normalized['existing']:
                after_fingerprint = _media_fingerprint(
                    after['schema_raw'], after['schema_ns_decls'], after['data_root'], readback=True)
                if after_fingerprint != prepared['target_fingerprint']:
                    return {
                        'state': 'uncertain',
                        'resource_id': result_id,
                        'reason': 'MediaGet readback did not match the exact target diff; do not retry.',
                    }
            else:
                check = dict(prepared)
                check['expected_media_id'] = result_id
                if not self._matches_target(after['media_row'], check):
                    return {
                        'state': 'uncertain',
                        'resource_id': result_id,
                        'reason': 'MediaGet readback did not match every supplied media field.',
                    }
            self._download_original(source, binding, result_id, file_info, context, bounds, deadline)
        except (WriteFailure, WriteCancelled, ValueError, AmbiguousWrite):
            return {
                'state': 'uncertain',
                'resource_id': result_id,
                'reason': 'MediaUpdate was acknowledged, but exact MediaGet/original-file readback did not complete.',
            }
        return {
            'state': 'succeeded',
            'resource_id': result_id,
            'readback': {
                'media_id': result_id,
                'meeting_id': normalized['meeting_id'],
                'media_event_id': _MEDIA_EVENT_ID,
                'file_size': file_info['byte_length'],
                'file_sha256': file_info['sha256'],
                'published': normalized['published'],
                'started': normalized['started'],
            },
        }

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        binding = self.credentials(source, context)
        change = WriteChange.from_dict(prepared['change'])
        normalized = self._validate_change(change, binding)
        if item.get('append_intent') is not None:
            return {
                'state': 'uncertain',
                'reason': 'An append acknowledgment was lost; the partial transfer remains uncertain and must not be repeated.',
            }
        resource_id = item.get('resource_id') or prepared.get('media_id')
        if resource_id is None:
            return {
                'state': 'uncertain',
                'reason': 'No positive native MediaID was persisted; new-row identity must not be inferred by meeting or date.',
            }
        try:
            media_id = _positive_int32(resource_id, 'resource_id')
            after = self._read_media(source, binding, media_id, context, bounds, deadline)
            if normalized['existing']:
                after_fingerprint = _media_fingerprint(
                    after['schema_raw'], after['schema_ns_decls'], after['data_root'], readback=True)
                if after_fingerprint != prepared['target_fingerprint']:
                    return {
                        'state': 'uncertain',
                        'resource_id': media_id,
                        'reason': 'Read-only MediaGet does not confirm the exact target diff; do not retry.',
                    }
            else:
                check = dict(prepared)
                check['expected_media_id'] = media_id
                if not self._matches_target(after['media_row'], check):
                    return {
                        'state': 'uncertain',
                        'resource_id': media_id,
                        'reason': 'Read-only MediaGet does not confirm every supplied media field; do not retry.',
                    }
            self._download_original(source, binding, media_id, normalized['file'], context, bounds, deadline)
            return {'state': 'succeeded', 'resource_id': media_id, 'reconciled': True}
        except (WriteFailure, WriteCancelled, ValueError, AmbiguousWrite):
            return {
                'state': 'uncertain',
                'resource_id': str(resource_id),
                'reason': 'Read-only reconciliation could not complete; do not repeat upload or infer identity.',
            }
