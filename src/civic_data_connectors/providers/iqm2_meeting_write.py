'''Scoped MinuteTraq MeetingUpdate create/update via existing WriteCoordinator.'''
from __future__ import annotations

import base64
import io
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from time import monotonic
from urllib.parse import quote, urlsplit
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from ..engine import canonical_hash
from ..write_adapters import AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure
from ..write_transport import WriteResponse
from . import iqm2_soap, iqm2_write

FORMAT = 'iqm2-minutetraq-meeting-soap-xml'
MAX_INT32 = 2147483647
MIN_INT32 = -2147483648
SERVICE_NS = iqm2_soap.SERVICE_NS
SOAP_NS = iqm2_soap.SOAP_NS
DIFFGR_NS = iqm2_soap.DIFFGR_NS
DB_NS = iqm2_soap.DB_NS
XSI_NS = iqm2_soap.XSI_NS
XML_SCHEMA_NS = iqm2_write.XML_SCHEMA_NS
MSDATA_NS = iqm2_write.MSDATA_NS
_OPTION_KEYS = {'minutetraq_agency'}
_REQUIRED_FIELDS = {'meeting_date', 'resolution_due_date', 'meeting_type_id', 'meeting_location_id', 'meeting_status_id', 'department_id'}
_OPTIONAL_FIELDS = {'timestamp_start', 'timestamp_start_delta'}
_ALLOWED_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS | {'meeting_get'}
_GET_KEYS = {'date_from', 'date_to', 'meeting_status', 'department_id'}
_MEETING_FIELDS = ('MeetingID', 'MeetingDate', 'ResolutionDueDate', 'MeetingTypeID', 'MeetingLocationID', 'MeetingStatusID', 'DepartmentID', 'TimestampStart', 'TimestampStartDelta')
_DATE_FIELDS = {'MeetingDate', 'ResolutionDueDate', 'TimestampStart'}
_INT_FIELDS = {'MeetingID', 'MeetingTypeID', 'MeetingLocationID', 'DepartmentID', 'TimestampStartDelta'}
_MAX_AGENCY_LENGTH = 128
_sq = chr(39)
_dq = chr(34)

_MEETING_SCHEMA_XML = '''<xs:schema id='DB_1_0' targetNamespace='http://tempuri.org/DB_1_0.xsd' xmlns:mstns='http://tempuri.org/DB_1_0.xsd' xmlns='http://tempuri.org/DB_1_0.xsd' xmlns:xs='http://www.w3.org/2001/XMLSchema' xmlns:msdata='urn:schemas-microsoft-com:xml-msdata' attributeFormDefault='qualified' elementFormDefault='qualified'><xs:element name='DB_1_0' msdata:IsDataSet='true' msdata:UseCurrentLocale='true'><xs:complexType><xs:choice minOccurs='0' maxOccurs='unbounded'><xs:element name='Meeting'><xs:complexType><xs:sequence><xs:element name='MeetingID' type='xs:int' msdata:ReadOnly='true' msdata:AutoIncrement='true' msdata:AutoIncrementSeed='-1' msdata:AutoIncrementStep='-1'/><xs:element name='MeetingDate' type='xs:dateTime'/><xs:element name='ResolutionDueDate' type='xs:dateTime'/><xs:element name='MeetingTypeID' type='xs:int'/><xs:element name='MeetingLocationID' type='xs:int'/><xs:element name='MeetingStatusID' type='xs:unsignedByte' default='10'/><xs:element name='DepartmentID' type='xs:int' minOccurs='0'/><xs:element name='TimestampStart' type='xs:dateTime' minOccurs='0' nillable='true'/><xs:element name='TimestampStartDelta' type='xs:int' minOccurs='0' default='0'/></xs:sequence></xs:complexType></xs:element></xs:choice></xs:complexType><xs:key name='MeetingKey' msdata:PrimaryKey='true'><xs:selector xpath='.//mstns:Meeting'/><xs:field xpath='mstns:MeetingID'/></xs:key></xs:element></xs:schema>'''
_MEETING_SCHEMA_NS = [('xs', XML_SCHEMA_NS), ('msdata', MSDATA_NS), ('mstns', DB_NS)]


def _validate_options(source):
    options = source.options
    if not isinstance(options, dict) or set(options) != _OPTION_KEYS:
        raise ValueError('MinuteTraq meeting options must be exactly minutetraq_agency.')
    agency = options['minutetraq_agency']
    if not isinstance(agency, str) or not agency or len(agency) > _MAX_AGENCY_LENGTH:
        raise ValueError('minutetraq_agency must be a bounded non-empty agency label.')
    if agency != agency.strip() or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in agency):
        raise ValueError('minutetraq_agency must be a bounded non-empty agency label.')
    return {'minutetraq_agency': agency}


def _meeting_namespace(source):
    options = _validate_options(source)
    parsed = urlsplit(source.url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port is not None:
        raise ValueError('MinuteTraq meeting URLs must be exact HTTPS URLs without credentials or ports.')
    host = parsed.hostname.lower() if parsed.hostname else ''
    parts = host.split('.')
    if len(parts) != 3 or not parts[0] or parts[1] != 'iqm2' or parts[2] != 'com':
        raise ValueError('MinuteTraq meeting host must be a tenant .iqm2.com host.')
    if parsed.path != '/MinuteTraqService/Data_1_0.asmx' or parsed.query or parsed.fragment:
        raise ValueError('MinuteTraq meeting URL must be the exact Data_1_0.asmx endpoint.')
    return '//' + host + '/MinuteTraqService/agency/' + quote(options['minutetraq_agency'], safe='')


def _canonical_local_datetime(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Native meeting date/time must be an explicit UnspecifiedLocal dateTime.')
    try:
        return iqm2_write._canonical_native_datetime(value)
    except ValueError:
        raise ValueError('Native meeting date/time must be an explicit UnspecifiedLocal dateTime.') from None


def _positive_id(value, label):
    if isinstance(value, bool):
        raise ValueError(label + ' must be a positive native identifier.')
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value and value[0] != '0' and value.isdigit():
        parsed = int(value)
    else:
        raise ValueError(label + ' must be a positive native identifier.')
    if not 1 <= parsed <= MAX_INT32:
        raise ValueError(label + ' must be within the native identifier range.')
    return str(parsed)


def _native_int(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(label + ' must be within the native integer range.')
    return value


def _status_byte(value):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError('meeting_status_id must be a native byte selected by the caller.')
    return value


def _parse_native_int_text(text, label, minimum, maximum):
    candidate = text.strip()
    if not candidate:
        raise ValueError(label + ' must be an integer.')
    digits = candidate[1:] if candidate[0] == '-' else candidate
    if not digits.isdigit() or candidate[0] == '+':
        raise ValueError(label + ' must be an integer.')
    parsed = int(candidate)
    if not minimum <= parsed <= maximum:
        raise ValueError(label + ' must be within the native integer range.')
    return parsed


def _validate_get(value, department_id):
    if not isinstance(value, dict) or set(value) != _GET_KEYS:
        raise ValueError('meeting_get must contain exactly date_from, date_to, meeting_status and department_id.')
    date_from = _canonical_local_datetime(value['date_from'])
    date_to = _canonical_local_datetime(value['date_to'])
    if datetime.fromisoformat(date_from) > datetime.fromisoformat(date_to):
        raise ValueError('meeting_get date_from must not be after date_to.')
    get_department = _native_int(value['department_id'], 'meeting_get department_id', 1, MAX_INT32)
    if get_department != department_id:
        raise ValueError('meeting_get department_id must equal the selected meeting DepartmentID.')
    status = value['meeting_status']
    if status is not None:
        if not isinstance(status, str) or not status or any(ord(ch) < 0x20 for ch in status):
            raise ValueError('meeting_get meeting_status must be explicit null or a non-empty string.')
    return {'date_from': date_from, 'date_to': date_to, 'meeting_status': status, 'department_id': get_department}


def _trusted_meeting_config(source, options, namespace_value, context):
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
    if not isinstance(allowed, (list, tuple, set, frozenset)) or not allowed or len(allowed) > 128 or namespace_value not in allowed:
        raise iqm2_soap._CredentialsError
    version = config.get('client_version')
    if not isinstance(version, str) or not version:
        raise iqm2_soap._CredentialsError
    auth = config.get('authorization_header')
    iqm2_soap._validate_authorization_header(auth, options['minutetraq_agency'], version)
    return {'authorization_header': auth, 'client_version': version, 'config': config}


def _allowlisted(config, key, value):
    values = config.get(key)
    if not isinstance(values, (list, tuple, set, frozenset)) or not values or len(values) > 128:
        return False
    target = str(value)
    for candidate in values:
        if isinstance(candidate, bool):
            return False
        try:
            parsed = _positive_id(candidate, key)
        except ValueError:
            return False
        if parsed == target:
            return True
    return False


def _type_matches(type_value, local, ns_map):
    if type_value == '{' + XML_SCHEMA_NS + '}' + local:
        return True
    if ':' in type_value:
        prefix, name = type_value.split(':', 1)
        return name == local and ns_map.get(prefix) == XML_SCHEMA_NS
    return type_value == local


def _parse_schema_with_namespaces(schema_raw):
    if not isinstance(schema_raw, str) or not schema_raw:
        raise ValueError('The inline Meeting schema could not be parsed.')
    pending = []
    stack = []
    current = {}
    namespaces = {}
    root = None
    try:
        events = ET.iterparse(io.BytesIO(schema_raw.encode('utf-8')), events=('start', 'end', 'start-ns'))
        for event, item in events:
            if event == 'start-ns':
                prefix, uri = item
                pending.append((prefix or '', uri))
            elif event == 'start':
                new_current = dict(current)
                for prefix, uri in pending:
                    new_current[prefix] = uri
                pending = []
                stack.append(current)
                current = new_current
                namespaces[id(item)] = dict(current)
                if root is None:
                    root = item
            else:
                current = stack.pop()
    except ET.ParseError as exc:
        raise ValueError('The inline Meeting schema could not be parsed.') from exc
    if root is None:
        raise ValueError('The inline Meeting schema could not be parsed.')
    return root, namespaces


def _validate_meeting_schema(schema_raw):
    root, ns_by_id = _parse_schema_with_namespaces(schema_raw)
    if root.tag != '{' + XML_SCHEMA_NS + '}schema':
        raise ValueError('The inline Meeting schema could not be parsed.')
    if root.attrib.get('targetNamespace') != DB_NS:
        raise ValueError('The native Meeting schema targetNamespace is not DB_1_0.')
    if root.attrib.get('elementFormDefault') != 'qualified':
        raise ValueError('The native Meeting schema must use qualified elements.')
    data_element = None
    for element in root.iter():
        if element.tag == '{' + XML_SCHEMA_NS + '}element' and element.attrib.get('name') == 'DB_1_0':
            data_element = element
            break
    if data_element is None or data_element.attrib.get('{' + MSDATA_NS + '}IsDataSet') not in {'true', '1'}:
        raise ValueError('The inline schema does not define the native DB_1_0 DataSet.')
    meeting = None
    for element in data_element.iter():
        if element.tag == '{' + XML_SCHEMA_NS + '}element' and element.attrib.get('name') == 'Meeting':
            meeting = element
            break
    if meeting is None:
        raise ValueError('The inline schema does not define the Meeting table.')
    fields = {}
    for child in meeting.iter():
        if child.tag == '{' + XML_SCHEMA_NS + '}element' and child.attrib.get('name') in _MEETING_FIELDS:
            fields[child.attrib['name']] = child
    if set(fields) != set(_MEETING_FIELDS):
        raise ValueError('The native Meeting schema must contain exactly the nine source fields.')
    expected = {'MeetingID': 'int', 'MeetingDate': 'dateTime', 'ResolutionDueDate': 'dateTime', 'MeetingTypeID': 'int', 'MeetingLocationID': 'int', 'MeetingStatusID': 'unsignedByte', 'DepartmentID': 'int', 'TimestampStart': 'dateTime', 'TimestampStartDelta': 'int'}
    for name, local in expected.items():
        type_value = fields[name].attrib.get('type')
        if not type_value or not _type_matches(type_value, local, ns_by_id.get(id(fields[name]), {})):
            raise ValueError('Native Meeting field ' + name + ' has an unexpected type.')
    for name in _DATE_FIELDS:
        mode = fields[name].attrib.get('{' + MSDATA_NS + '}DateTimeMode')
        if mode and mode != 'UnspecifiedLocal':
            raise ValueError('Unsupported native DateTimeMode for ' + name + '.')
    meeting_id = fields['MeetingID']
    if meeting_id.attrib.get('{' + MSDATA_NS + '}ReadOnly') not in {'true', '1'}:
        raise ValueError('MeetingID must be readonly.')
    if meeting_id.attrib.get('{' + MSDATA_NS + '}AutoIncrement') not in {'true', '1'}:
        raise ValueError('MeetingID must be autoincrement.')
    if meeting_id.attrib.get('{' + MSDATA_NS + '}AutoIncrementSeed') != '-1' or meeting_id.attrib.get('{' + MSDATA_NS + '}AutoIncrementStep') != '-1':
        raise ValueError('MeetingID must use source -1 seed/step.')
    primary_key = False
    for element in data_element.iter():
        if element.tag not in {'{' + XML_SCHEMA_NS + '}key', '{' + XML_SCHEMA_NS + '}unique'}:
            continue
        if element.attrib.get('{' + MSDATA_NS + '}PrimaryKey') not in {'true', '1'}:
            continue
        selector = next((child for child in element if child.tag == '{' + XML_SCHEMA_NS + '}selector'), None)
        field = next((child for child in element if child.tag == '{' + XML_SCHEMA_NS + '}field'), None)
        if selector is None or field is None:
            continue
        selector_xpath = selector.attrib.get('xpath', '')
        field_xpath = field.attrib.get('xpath', '')
        if selector_xpath != './/mstns:Meeting' or field_xpath != 'mstns:MeetingID':
            continue
        if ns_by_id.get(id(selector), {}).get('mstns') != DB_NS or ns_by_id.get(id(field), {}).get('mstns') != DB_NS:
            continue
        primary_key = True
    if not primary_key:
        raise ValueError('MeetingID must be the native primary key.')


def _set_meeting_values(row, values):
    iqm2_write._set_field(row, 'MeetingDate', values['meeting_date'])
    iqm2_write._set_field(row, 'ResolutionDueDate', values['resolution_due_date'])
    iqm2_write._set_field(row, 'MeetingTypeID', str(values['meeting_type_id']))
    iqm2_write._set_field(row, 'MeetingLocationID', str(values['meeting_location_id']))
    iqm2_write._set_field(row, 'MeetingStatusID', str(values['meeting_status_id']))
    iqm2_write._set_field(row, 'DepartmentID', str(values['department_id']))
    if 'timestamp_start' in values:
        iqm2_write._set_field(row, 'TimestampStart', values['timestamp_start'])
    if 'timestamp_start_delta' in values:
        iqm2_write._set_field(row, 'TimestampStartDelta', str(values['timestamp_start_delta']))


def _validate_meeting_row(row):
    meeting_id = iqm2_soap._int32_text(row, 'MeetingID')
    for name in ('MeetingDate', 'ResolutionDueDate'):
        text = iqm2_soap._required_text(row, name)
        _canonical_local_datetime(text.strip())
    iqm2_soap._int32_text(row, 'MeetingTypeID')
    iqm2_soap._int32_text(row, 'MeetingLocationID')
    status = iqm2_soap._required_text(row, 'MeetingStatusID').strip()
    if not status.isdigit() or not 0 <= int(status) <= 255:
        raise ValueError('MeetingStatusID must be a native byte.')
    iqm2_soap._int32_text(row, 'DepartmentID')
    exists, nil, value = iqm2_soap._child_value(row, 'TimestampStart')
    if exists and not nil and value and value.strip():
        _canonical_local_datetime(value.strip())
    exists, nil, value = iqm2_soap._child_value(row, 'TimestampStartDelta')
    if exists and not nil and value and value.strip():
        _parse_native_int_text(value, 'TimestampStartDelta', MIN_INT32, MAX_INT32)
    return meeting_id


def _canonicalize_meeting_row(row):
    for name in _MEETING_FIELDS:
        exists, nil, value = iqm2_soap._child_value(row, name)
        if not exists or nil or value is None:
            continue
        if name in _DATE_FIELDS:
            if value.strip():
                iqm2_write._set_field(row, name, _canonical_local_datetime(value.strip()))
        elif name == 'MeetingStatusID':
            iqm2_write._set_field(row, name, str(int(value.strip())))
        elif name in _INT_FIELDS:
            iqm2_write._set_field(row, name, str(int(value.strip())))


def _meeting_fingerprint(schema_raw, schema_ns_decls, data_root):
    if not ET.iselement(data_root) or data_root.tag != '{' + DB_NS + '}DB_1_0':
        raise ValueError('Meeting fingerprint requires a copied DB_1_0 dataset root.')
    root = deepcopy(data_root)
    for row in list(root):
        if row.tag == '{' + DB_NS + '}Meeting':
            _canonicalize_meeting_row(row)
    return canonical_hash({'schema': schema_raw, 'schema_namespaces': sorted(schema_ns_decls), 'data': iqm2_write._root_repr(root, 'meeting')})


def _parse_meeting_get_response(content, expected_id, namespace_value):
    root = iqm2_soap._parse_xml(content)
    if root.tag != '{' + SOAP_NS + '}Envelope':
        raise ValueError('Saved response must be a SOAP 1.1 Envelope.')
    body = iqm2_soap._single_ns(root, SOAP_NS, 'Body', 'SOAP Body')
    if any(iqm2_soap._local(element.tag) == 'Fault' for element in body.iter()):
        raise ValueError('SOAP Fault responses are not valid MeetingGet snapshots.')
    body_children = list(body)
    if len(body_children) != 1:
        raise ValueError('SOAP Body must contain exactly one response.')
    response = body_children[0]
    if response.tag != '{' + SERVICE_NS + '}MeetingGetResponse':
        raise ValueError('The saved response operation is not MeetingGet.')
    result_children = list(response)
    if len(result_children) != 1 or result_children[0].tag != '{' + SERVICE_NS + '}MeetingGetResult':
        raise ValueError('SOAP MeetingGet result wrapper is malformed.')
    result = result_children[0]
    schemas = [child for child in result if child.tag == '{' + XML_SCHEMA_NS + '}schema']
    if len(schemas) != 1:
        raise ValueError('The MeetingGet response must contain exactly one inline schema.')
    schema_raw, schema_ns_decls = iqm2_write._extract_raw_schema(content)
    _validate_meeting_schema(schema_raw)
    diffgram = iqm2_soap._single_ns(result, DIFFGR_NS, 'diffgram', 'diffgram')
    if [child for child in diffgram if child.tag in {'{' + DIFFGR_NS + '}before', '{' + DIFFGR_NS + '}errors'}]:
        raise ValueError('Meeting read snapshots must not contain before/errors diffgram blocks.')
    data_root = iqm2_soap._single_ns(diffgram, DB_NS, 'DB_1_0', 'DB_1_0 data root')
    for row in list(data_root):
        row_ns, row_local = iqm2_soap._split_tag(row.tag)
        if row_local == 'Meeting' and row_ns != DB_NS:
            raise ValueError('A Meeting row uses a foreign namespace.')
        changes = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasChanges')
        errors = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasErrors')
        if changes is not None and changes.strip():
            raise ValueError('Meeting read snapshots must not contain changed rows.')
        if errors is not None and errors.strip().lower() in {'true', '1'}:
            raise ValueError('Meeting read snapshots must not contain row errors.')
    meetings = [row for row in list(data_root) if row.tag == '{' + DB_NS + '}Meeting']
    if len(meetings) != 1:
        raise ValueError('MeetingGet must return exactly one current Meeting row.')
    meeting = meetings[0]
    if _validate_meeting_row(meeting) != expected_id:
        raise ValueError('MeetingID does not match the selected meeting identity.')
    return {'schema_raw': schema_raw, 'schema_ns_decls': schema_ns_decls, 'data_root': data_root, 'meeting_row': meeting, 'fingerprint': _meeting_fingerprint(schema_raw, schema_ns_decls, data_root)}


def _parse_meeting_update_ack(content):
    root = iqm2_soap._parse_xml(content)
    if root.tag != '{' + SOAP_NS + '}Envelope':
        raise ValueError('Saved response must be a SOAP 1.1 Envelope.')
    body = iqm2_soap._single_ns(root, SOAP_NS, 'Body', 'SOAP Body')
    if any(iqm2_soap._local(element.tag) == 'Fault' for element in body.iter()):
        raise ValueError('SOAP Fault responses are not successful MeetingUpdate acknowledgments.')
    body_children = list(body)
    if len(body_children) != 1:
        raise ValueError('SOAP Body must contain exactly one MeetingUpdate acknowledgment.')
    response = body_children[0]
    if response.tag != '{' + SERVICE_NS + '}MeetingUpdateResponse':
        raise ValueError('The MeetingUpdate acknowledgment operation is malformed.')
    result_children = list(response)
    if len(result_children) != 1 or result_children[0].tag != '{' + SERVICE_NS + '}MeetingUpdateResult':
        raise ValueError('The MeetingUpdate result wrapper is malformed.')
    result = result_children[0]
    diffgram = iqm2_soap._single_ns(result, DIFFGR_NS, 'diffgram', 'diffgram')
    if [child for child in diffgram if child.tag in {'{' + DIFFGR_NS + '}before', '{' + DIFFGR_NS + '}errors'}]:
        raise ValueError('MeetingUpdate acknowledgment must not contain before/errors blocks.')
    data_root = iqm2_soap._single_ns(diffgram, DB_NS, 'DB_1_0', 'DB_1_0 data root')
    meetings = []
    for row in list(data_root):
        row_ns, row_local = iqm2_soap._split_tag(row.tag)
        if row_local == 'Meeting' and row_ns != DB_NS:
            raise ValueError('A Meeting acknowledgment row uses a foreign namespace.')
        changes = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasChanges')
        errors = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasErrors')
        if changes is not None and changes.strip():
            raise ValueError('MeetingUpdate acknowledgment must not contain dirty rows.')
        if errors is not None and errors.strip().lower() in {'true', '1'}:
            raise ValueError('MeetingUpdate acknowledgment must not contain row errors.')
        if row_local == 'Meeting':
            meetings.append(row)
    if len(meetings) != 1:
        raise ValueError('MeetingUpdate acknowledgment must return exactly one Meeting row.')
    return iqm2_soap._int32_text(meetings[0], 'MeetingID')


def _build_meeting_get_body(meeting_id, filters):
    status = filters['meeting_status']
    if status is None:
        status_xml = '<MeetingStatus xsi:nil=' + _sq + 'true' + _sq + '/>'
    else:
        status_xml = '<MeetingStatus>' + escape(status) + '</MeetingStatus>'
    return ('<?xml version=' + _sq + '1.0' + _sq + ' encoding=' + _sq + 'utf-8' + _sq + '?>'
            '<soap:Envelope xmlns:soap=' + _sq + SOAP_NS + _sq + ' xmlns:xsi=' + _sq + XSI_NS + _sq + '>'
            '<soap:Body><MeetingGet xmlns=' + _sq + SERVICE_NS + _sq + '>'
            '<MeetingID>' + str(meeting_id) + '</MeetingID>'
            '<DateFrom>' + filters['date_from'] + '</DateFrom>'
            '<DateTo>' + filters['date_to'] + '</DateTo>' + status_xml +
            '<DepartmentID>' + str(filters['department_id']) + '</DepartmentID>'
            '</MeetingGet></soap:Body></soap:Envelope>').encode('utf-8')


def _replace_meeting_row(data_root, meeting_row):
    if not ET.iselement(data_root) or data_root.tag != '{' + DB_NS + '}DB_1_0':
        raise ValueError('Meeting replacement requires a copied DB_1_0 dataset root.')
    root = deepcopy(data_root)
    replaced = False
    for index, row in enumerate(list(root)):
        if row.tag == '{' + DB_NS + '}Meeting':
            root[index] = deepcopy(meeting_row)
            replaced = True
    if not replaced:
        raise ValueError('The selected dataset does not contain a Meeting row.')
    return root


def _row_matches_values(row, values):
    for name, expected in values.items():
        if name == 'meeting_date':
            field = 'MeetingDate'
        elif name == 'resolution_due_date':
            field = 'ResolutionDueDate'
        elif name == 'meeting_type_id':
            field = 'MeetingTypeID'
        elif name == 'meeting_location_id':
            field = 'MeetingLocationID'
        elif name == 'meeting_status_id':
            field = 'MeetingStatusID'
        elif name == 'department_id':
            field = 'DepartmentID'
        elif name == 'timestamp_start':
            field = 'TimestampStart'
        elif name == 'timestamp_start_delta':
            field = 'TimestampStartDelta'
        else:
            return False
        exists, nil, value = iqm2_soap._child_value(row, field)
        if not exists or nil or value is None:
            return False
        if field in _DATE_FIELDS:
            if _canonical_local_datetime(value.strip()) != expected:
                return False
        else:
            try:
                if int(value.strip()) != expected:
                    return False
            except ValueError:
                return False
    return True


def _response_media_type(response):
    headers = getattr(response, 'headers', None)
    if not isinstance(headers, dict):
        return None
    for key, value in headers.items():
        if str(key).lower() == 'content-type':
            return str(value).split(';', 1)[0].strip().lower()
    return None


class IQM2MeetingWriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__('iqm2', transport)

    def credentials(self, source, context):
        if source.provider != self.provider:
            raise WriteFailure('mapping_unverified', 'The selected source is not an iQM2 MinuteTraq source.')
        if source.input_format != FORMAT or source.body is not None:
            raise WriteFailure('mapping_unverified', 'The exact saved MinuteTraq meeting SOAP source format is required.')
        try:
            options = _validate_options(source)
            namespace_value = _meeting_namespace(source)
            if source.namespace != namespace_value:
                raise ValueError('Source namespace does not match the selected agency endpoint.')
            trusted = _trusted_meeting_config(source, options, namespace_value, context)
        except iqm2_soap._CredentialsError:
            raise WriteFailure('credentials_required', 'A trusted MinuteTraq session-scoped credential is required.') from None
        except ValueError as exc:
            raise WriteFailure('mapping_unverified', str(exc)) from None
        if context.allowed_namespaces is not None and namespace_value not in context.allowed_namespaces:
            raise WriteFailure('permission_denied', 'The selected MinuteTraq namespace is outside current policy.')
        return {'options': options, 'namespace': namespace_value, 'authorization': trusted['authorization_header'], 'client_version': trusted['client_version'], 'config': trusted['config']}

    def validate_source(self, source, context):
        self.credentials(source, context)

    def _validate_change(self, change, binding):
        if change.entity != 'meeting' or change.operation not in {'create', 'update'}:
            raise WriteFailure('mapping_unverified', 'Only Meeting create/update is mapped.')
        if change.files:
            raise WriteFailure('mapping_unverified', 'Meeting writes do not accept files.')
        if any(value is not None for value in (change.parent_id, change.language, change.page_number, change.meeting_id, change.expected_version)):
            raise WriteFailure('mapping_unverified', 'Foreign relationship or revision metadata is not mapped.')
        if change.operation == 'create' and change.resource_id is not None:
            raise ValueError('A create cannot supply a MeetingID before provider response.')
        if change.operation == 'update' and change.resource_id is None:
            raise ValueError('An update requires an exact MeetingID resource_id.')
        fields = change.fields
        if not isinstance(fields, dict):
            raise ValueError('Meeting fields must be an object.')
        required = _REQUIRED_FIELDS | {'meeting_get'}
        unknown = set(fields) - _ALLOWED_FIELDS
        missing = required - set(fields)
        if unknown or missing:
            raise ValueError('Meeting fields must contain every required field, meeting_get, and only supported optional timestamps.')
        meeting_date = _canonical_local_datetime(fields['meeting_date'])
        resolution_due = _canonical_local_datetime(fields['resolution_due_date'])
        if datetime.fromisoformat(resolution_due) > datetime.fromisoformat(meeting_date):
            raise ValueError('ResolutionDueDate cannot be after MeetingDate.')
        values = {'meeting_date': meeting_date, 'resolution_due_date': resolution_due, 'meeting_type_id': _native_int(fields['meeting_type_id'], 'meeting_type_id', 1, MAX_INT32), 'meeting_location_id': _native_int(fields['meeting_location_id'], 'meeting_location_id', 1, MAX_INT32), 'meeting_status_id': _status_byte(fields['meeting_status_id']), 'department_id': _native_int(fields['department_id'], 'department_id', 1, MAX_INT32)}
        if 'timestamp_start' in fields:
            values['timestamp_start'] = _canonical_local_datetime(fields['timestamp_start'])
        if 'timestamp_start_delta' in fields:
            values['timestamp_start_delta'] = _native_int(fields['timestamp_start_delta'], 'timestamp_start_delta', MIN_INT32, MAX_INT32)
        meeting_get = _validate_get(fields['meeting_get'], values['department_id'])
        permission = 'meeting:' + change.operation
        permissions = binding['config'].get('permissions')
        if not isinstance(permissions, (list, tuple, set, frozenset)) or permission not in permissions:
            raise WriteFailure('permission_denied', 'This exact MinuteTraq meeting operation is outside current policy.')
        if not _allowlisted(binding['config'], 'department_ids', values['department_id']):
            raise WriteFailure('permission_denied', 'The selected DepartmentID is outside current policy.')
        if not _allowlisted(binding['config'], 'meeting_type_ids', values['meeting_type_id']):
            raise WriteFailure('permission_denied', 'The selected MeetingTypeID is outside current policy.')
        if not _allowlisted(binding['config'], 'meeting_location_ids', values['meeting_location_id']):
            raise WriteFailure('permission_denied', 'The selected MeetingLocationID is outside current policy.')
        resource_id = None
        if change.operation == 'update':
            resource_id = _positive_id(change.resource_id, 'resource_id')
            if not _allowlisted(binding['config'], 'meeting_ids', resource_id):
                raise WriteFailure('permission_denied', 'The selected MeetingID is outside current policy.')
        return {'operation': change.operation, 'resource_id': resource_id, 'values': values, 'meeting_get': meeting_get, 'method': 'MeetingUpdate'}

    def authorize(self, source, change, context):
        binding = self.credentials(source, context)
        self._validate_change(change, binding)

    def _headers(self, binding, method):
        return {'Content-Type': 'text/xml;charset=utf-8', 'SOAPAction': _dq + SERVICE_NS + '/' + method + _dq, 'Authorization': binding['authorization'], 'MinuteTraqVersion': binding['client_version']}

    def _read_meeting(self, source, binding, meeting_id, filters, context, bounds, deadline):
        if context.check_cancelled():
            raise WriteCancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure('deadline_exceeded', 'The MinuteTraq meeting read deadline expired.')
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        if limit < 1:
            raise ValueError('MinuteTraq byte bounds must allow a response.')
        body = _build_meeting_get_body(meeting_id, filters)
        try:
            response = self.transport.send(source.url, method='POST', body=body, headers=self._headers(binding, 'MeetingGet'), byte_limit=limit, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq meeting could not be read.') from None
        if not isinstance(response, WriteResponse) or len(response.content) > limit:
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq meeting response was invalid.')
        if response.status in {401, 403}:
            raise WriteFailure('permission_denied', 'The provider denied the selected MinuteTraq meeting read.')
        if response.status != 200:
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq meeting response was not successful.')
        media_type = _response_media_type(response)
        if media_type is not None and media_type not in {'text/xml', 'application/xml'}:
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq meeting read did not return XML.')
        parsed = _parse_meeting_get_response(response.content, int(meeting_id), binding['namespace'])
        if context.check_cancelled():
            raise WriteCancelled()
        if len(list(parsed['data_root'])) > bounds.max_records:
            raise ValueError('The selected MinuteTraq meeting exceeds the configured record bound.')
        if monotonic() >= deadline:
            raise WriteFailure('deadline_exceeded', 'The MinuteTraq meeting read exceeded the total deadline.')
        return parsed

    def prepare(self, source, change, context, bounds, deadline):
        binding = self.credentials(source, context)
        normalized = self._validate_change(change, binding)
        if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
            raise ValueError('A bounded change key is required.')
        if change.operation == 'create':
            row = ET.Element('{' + DB_NS + '}Meeting')
            iqm2_write._ensure_diffgr_id(row, 'Meeting', '-1')
            row.attrib['{' + DIFFGR_NS + '}hasChanges'] = 'inserted'
            iqm2_write._set_field(row, 'MeetingID', '-1')
            _set_meeting_values(row, normalized['values'])
            if 'timestamp_start_delta' not in normalized['values']:
                iqm2_write._set_field(row, 'TimestampStartDelta', '0')
            body = iqm2_write._build_request_body('MeetingUpdate', _MEETING_SCHEMA_XML, _MEETING_SCHEMA_NS, [row], [])
            if len(body) > min(bounds.parser_bytes, bounds.transfer_bytes):
                raise ValueError('The exact MinuteTraq meeting create request exceeds byte bounds.')
            return {'change': asdict(change), 'before_fingerprint': None, 'target_fingerprint': None, 'target_values': normalized['values'], 'meeting_get': normalized['meeting_get'], 'resource_id': None, 'operation': 'create', 'method': 'MeetingUpdate', 'native': {'method': 'POST', 'url': source.url, 'body_base64': base64.b64encode(body).decode('ascii'), 'headers': {}}, 'conflict_semantics': 'create_readback_no_blind_retry', 'effects': {'entity': 'meeting', 'creates': True, 'updates': False, 'deletes': False, 'publication': False, 'files': False}}
        current = self._read_meeting(source, binding, normalized['resource_id'], normalized['meeting_get'], context, bounds, deadline)
        before = deepcopy(current['meeting_row'])
        after = deepcopy(current['meeting_row'])
        _set_meeting_values(after, normalized['values'])
        iqm2_write._ensure_diffgr_id(before, 'Meeting', normalized['resource_id'])
        iqm2_write._ensure_diffgr_id(after, 'Meeting', normalized['resource_id'])
        after.attrib['{' + DIFFGR_NS + '}hasChanges'] = 'modified'
        body = iqm2_write._build_request_body('MeetingUpdate', current['schema_raw'], current['schema_ns_decls'], [after], [before])
        if len(body) > min(bounds.parser_bytes, bounds.transfer_bytes):
            raise ValueError('The exact MinuteTraq meeting update request exceeds byte bounds.')
        target_root = _replace_meeting_row(current['data_root'], after)
        return {'change': asdict(change), 'before_fingerprint': current['fingerprint'], 'target_fingerprint': _meeting_fingerprint(current['schema_raw'], current['schema_ns_decls'], target_root), 'target_values': normalized['values'], 'meeting_get': normalized['meeting_get'], 'resource_id': normalized['resource_id'], 'operation': 'update', 'method': 'MeetingUpdate', 'native': {'method': 'POST', 'url': source.url, 'body_base64': base64.b64encode(body).decode('ascii'), 'headers': {}}, 'conflict_semantics': 'preflight_compare_not_atomic_upstream_cas', 'effects': {'entity': 'meeting', 'creates': False, 'updates': True, 'deletes': False, 'publication': False, 'files': False}}

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        binding = self.credentials(source, context)
        change = WriteChange.from_dict(prepared['change'])
        normalized = self._validate_change(change, binding)
        if normalized['operation'] == 'update':
            current = self._read_meeting(source, binding, prepared['resource_id'], prepared['meeting_get'], context, bounds, deadline)
            if current['fingerprint'] != prepared['before_fingerprint']:
                raise WriteFailure('conflict', 'The selected MinuteTraq meeting changed after planning.')
            if persist and persist({'resource_id': prepared['resource_id']}):
                raise WriteCancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure('deadline_exceeded', 'The MinuteTraq meeting write deadline expired before send.')
        body = base64.b64decode(prepared['native']['body_base64'])
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        if context.check_cancelled():
            raise WriteCancelled()
        try:
            response = self.transport.send(source.url, method='POST', body=body, headers=self._headers(binding, normalized['method']), byte_limit=limit, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite('The MinuteTraq meeting update may have been accepted; do not resend.') from None
        if not isinstance(response, WriteResponse) or len(response.content) > limit:
            raise AmbiguousWrite('The MinuteTraq meeting update response was invalid.')
        if response.status in {401, 403}:
            raise WriteFailure('permission_denied', 'The provider denied the selected MinuteTraq meeting update.')
        if response.status in {409, 412}:
            raise WriteFailure('conflict', 'The provider rejected the MinuteTraq meeting update as conflicting.')
        if not 200 <= response.status < 300:
            raise AmbiguousWrite('The MinuteTraq meeting update response was not successful; do not resend.')
        media_type = _response_media_type(response)
        if media_type is not None and media_type not in {'text/xml', 'application/xml'}:
            raise AmbiguousWrite('The MinuteTraq meeting acknowledgment was not XML; do not resend.')
        try:
            returned_id = _parse_meeting_update_ack(response.content)
        except ValueError:
            raise AmbiguousWrite('The MinuteTraq meeting acknowledgment could not be exactly verified; do not resend.') from None
        identity = str(returned_id)
        if normalized['operation'] == 'create':
            persisted = False
            if persist:
                persisted = persist({'resource_id': identity})
            if persisted or context.check_cancelled() or monotonic() >= deadline:
                return {'state': 'uncertain', 'resource_id': identity, 'reason': 'Returned MeetingID was persisted, but cancellation/deadline prevented readback.'}
        else:
            if identity != prepared['resource_id']:
                return {'state': 'uncertain', 'resource_id': prepared['resource_id'], 'reason': 'MeetingUpdate returned a different MeetingID.'}
            if context.check_cancelled() or monotonic() >= deadline:
                return {'state': 'uncertain', 'resource_id': identity, 'reason': 'MeetingUpdate was acknowledged, but cancellation/deadline prevented readback.'}
        try:
            after = self._read_meeting(source, binding, identity, prepared['meeting_get'], context, bounds, deadline)
        except (WriteFailure, WriteCancelled, ValueError):
            return {'state': 'uncertain', 'resource_id': identity, 'reason': 'MeetingUpdate was acknowledged but exact readback could not complete.'}
        if normalized['operation'] == 'create':
            if _row_matches_values(after['meeting_row'], prepared['target_values']):
                return {'state': 'succeeded', 'resource_id': identity, 'readback': {'meeting_id': identity}}
            return {'state': 'uncertain', 'resource_id': identity, 'reason': 'Create readback did not match every supplied field.'}
        after_fingerprint = _meeting_fingerprint(after['schema_raw'], after['schema_ns_decls'], after['data_root'])
        if after_fingerprint == prepared['target_fingerprint']:
            return {'state': 'succeeded', 'resource_id': identity, 'readback': {'meeting_id': identity}}
        return {'state': 'uncertain', 'resource_id': identity, 'reason': 'Readback did not match the exact target meeting diff; do not retry.'}

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        binding = self.credentials(source, context)
        change = WriteChange.from_dict(prepared['change'])
        self._validate_change(change, binding)
        if prepared['operation'] == 'create':
            identity = item.get('resource_id')
            if identity is None:
                return {'state': 'uncertain', 'reason': 'Create acknowledgment was lost before a positive MeetingID was known; do not repeat create or infer by title/date.'}
            try:
                meeting_id = _positive_id(identity, 'resource_id')
            except ValueError:
                return {'state': 'uncertain', 'reason': 'Persisted MeetingID is not a positive native identifier.'}
            try:
                after = self._read_meeting(source, binding, meeting_id, prepared['meeting_get'], context, bounds, deadline)
            except (WriteFailure, WriteCancelled, ValueError):
                return {'state': 'uncertain', 'resource_id': meeting_id, 'reason': 'Read-only create reconciliation could not complete; do not retry create.'}
            if _row_matches_values(after['meeting_row'], prepared['target_values']):
                return {'state': 'succeeded', 'resource_id': meeting_id, 'reconciled': True}
            return {'state': 'uncertain', 'resource_id': meeting_id, 'reason': 'Create readback does not confirm every supplied field; do not retry create.'}
        meeting_id = prepared['resource_id']
        try:
            after = self._read_meeting(source, binding, meeting_id, prepared['meeting_get'], context, bounds, deadline)
        except (WriteFailure, WriteCancelled, ValueError):
            return {'state': 'uncertain', 'resource_id': meeting_id, 'reason': 'Read-only update reconciliation could not complete; do not retry.'}
        after_fingerprint = _meeting_fingerprint(after['schema_raw'], after['schema_ns_decls'], after['data_root'])
        if after_fingerprint == prepared['target_fingerprint']:
            return {'state': 'succeeded', 'resource_id': meeting_id, 'reconciled': True}
        return {'state': 'uncertain', 'resource_id': meeting_id, 'reason': 'Readback does not confirm the exact target meeting diff; do not retry.'}
