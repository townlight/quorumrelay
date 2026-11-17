'''Saved iQM2 MinuteTraq Data_1_0 SOAP response reader; no transport and no writes.'''
from __future__ import annotations

from datetime import datetime
import re
from time import monotonic
from urllib.parse import quote, urlsplit
import xml.etree.ElementTree as ET

from ..models import Error, OperationResult
from .native import make_bundle

FORMAT = 'iqm2-minutetraq-soap-xml'
SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
SERVICE_NS = 'http://tempuri.org/MinuteTraqService/Data_1_0'
DIFFGR_NS = 'urn:schemas-microsoft-com:xml-diffgram-v1'
DB_NS = 'http://tempuri.org/DB_1_0.xsd'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
_OPTION_KEYS = {'minutetraq_agency', 'meeting_id', 'document_id', 'document_kind'}
_MAPPED_TABLES = {'Meeting', 'Agenda', 'AgendaItem', 'Minutes', 'MinutesItem'}


def _split_tag(tag):
    if tag.startswith('{'):
        ns, local = tag[1:].split('}', 1)
        return ns, local
    return '', tag


def _local(tag):
    return _split_tag(tag)[1]


def _attr_ns(element, ns, local):
    return element.attrib.get('{' + ns + '}' + local)


def _has_nil(element):
    value = _attr_ns(element, XSI_NS, 'nil')
    if value is None:
        return False
    lexical = value.strip().lower()
    if lexical not in {'true', 'false', '1', '0'}:
        raise ValueError('Malformed xsi:nil lexical value.')
    return lexical in {'true', '1'}


def _child_value(row, name):
    matches = [child for child in row if _local(child.tag) == name]
    if not matches:
        return False, False, None
    if len(matches) != 1:
        raise ValueError('Row contains ambiguous ' + name + ' fields.')
    child = matches[0]
    if _split_tag(child.tag)[0] != DB_NS:
        raise ValueError(name + ' must use the native DB_1_0 namespace.')
    if _has_nil(child):
        if (child.text is not None and child.text.strip()) or list(child):
            raise ValueError(name + ' cannot contain content when xsi:nil is true.')
        return True, True, None
    return True, False, child.text if child.text is not None else ''


def _required_text(row, name):
    exists, nil, value = _child_value(row, name)
    if not exists or nil or value is None or not value.strip():
        raise ValueError('Row is missing required ' + name + '.')
    return value.strip()


def _optional_text(row, name):
    exists, nil, value = _child_value(row, name)
    if not exists or nil:
        return None
    return value if value is not None else ''


def _positive_int32(value, label):
    if isinstance(value, bool):
        raise ValueError(label + ' must be a positive int32.')
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r'[1-9][0-9]*', value):
        parsed = int(value)
    else:
        raise ValueError(label + ' must be a positive int32.')
    if not 1 <= parsed <= 2147483647:
        raise ValueError(label + ' must be a positive int32.')
    return parsed


def _positive_long_text(row, name):
    text = _required_text(row, name)
    if not re.fullmatch(r'[1-9][0-9]*', text):
        raise ValueError(name + ' must be a positive native identifier.')
    value = int(text)
    if value > 9223372036854775807:
        raise ValueError(name + ' must fit a signed 64-bit integer.')
    return value


def _optional_int_text(row, name, minimum=None, maximum=None):
    exists, nil, value = _child_value(row, name)
    if not exists or nil:
        return None
    text = (value or '').strip()
    if not text:
        return None
    if not re.fullmatch(r'-?[0-9]+', text):
        raise ValueError(name + ' must be an integer.')
    parsed = int(text)
    if minimum is not None and parsed < minimum:
        raise ValueError(name + ' is outside the typed integer range.')
    if maximum is not None and parsed > maximum:
        raise ValueError(name + ' is outside the typed integer range.')
    return parsed


def _optional_iso_text(row, name):
    text = _optional_text(row, name)
    if text is None:
        return None
    candidate = text.strip()
    if not candidate:
        return None
    check = candidate[:-1] + '+00:00' if candidate.endswith('Z') else candidate
    try:
        datetime.fromisoformat(check)
    except ValueError as exc:
        raise ValueError(name + ' must be a valid ISO 8601 date-time.') from exc
    return candidate


def _int32_text(row, name):
    text = _required_text(row, name)
    if not re.fullmatch(r'[1-9][0-9]*', text):
        raise ValueError(name + ' must be a positive int32.')
    value = int(text)
    if not 1 <= value <= 2147483647:
        raise ValueError(name + ' must be a positive int32.')
    return value


def _reject_dtd(content):
    encodings = ('utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'utf-32', 'utf-32-le', 'utf-32-be')
    for encoding in encodings:
        try:
            text = content.decode(encoding, errors='ignore').casefold()
        except (LookupError, UnicodeError):
            continue
        if '<!doctype' in text or '<!entity' in text:
            raise ValueError('DTD and entity declarations are not allowed in saved MinuteTraq responses.')
    lowered = content.lower()
    if b'<!doctype' in lowered or b'<!entity' in lowered:
        raise ValueError('DTD and entity declarations are not allowed in saved MinuteTraq responses.')


def _parse_xml(content):
    if not isinstance(content, (bytes, bytearray)):
        raise ValueError('A saved MinuteTraq response must be bytes.')
    _reject_dtd(content)
    try:
        return ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError('The saved MinuteTraq response is not well-formed XML.') from exc


def _single_ns(parent, ns, local, label):
    matches = [child for child in parent if child.tag == '{' + ns + '}' + local]
    if len(matches) != 1:
        raise ValueError('The saved MinuteTraq response must contain exactly one ' + label + '.')
    return matches[0]


def _inactive_row(row):
    changes = _attr_ns(row, DIFFGR_NS, 'hasChanges')
    errors = _attr_ns(row, DIFFGR_NS, 'hasErrors')
    return ((changes or '').strip().lower() in {'deleted', 'error'} or
            (errors or '').strip().lower() in {'true', '1'})


def _raw_element(element):
    ns, local = _split_tag(element.tag)
    return {'tag': local, 'namespace': ns,
            'attributes': dict(element.attrib),
            'text': element.text,
            'children': [_raw_element(child) for child in element]}


def validate_options(source):
    options = source.options
    if not isinstance(options, dict) or set(options) != _OPTION_KEYS:
        raise ValueError('MinuteTraq SOAP options must be exactly minutetraq_agency, meeting_id, document_id and document_kind.')
    agency = options['minutetraq_agency']
    if not isinstance(agency, str) or not agency or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in agency):
        raise ValueError('minutetraq_agency must be a non-empty agency label.')
    meeting_id = _positive_int32(options['meeting_id'], 'meeting_id')
    document_id = _positive_int32(options['document_id'], 'document_id')
    kind = options['document_kind']
    if kind not in {'agenda', 'minutes'}:
        raise ValueError('document_kind must be agenda or minutes.')
    return {'minutetraq_agency': agency, 'meeting_id': meeting_id,
            'document_id': document_id, 'document_kind': kind}


def namespace(source):
    options = validate_options(source)
    parsed = urlsplit(source.url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port is not None:
        raise ValueError('MinuteTraq source URLs must be exact HTTPS URLs without credentials or ports.')
    host = parsed.hostname.lower() if parsed.hostname else ''
    if not re.fullmatch(r'[^.]+[.]iqm2[.]com', host):
        raise ValueError('MinuteTraq source host must be a tenant .iqm2.com host.')
    if parsed.path != '/MinuteTraqService/Data_1_0.asmx' or parsed.query or parsed.fragment:
        raise ValueError('MinuteTraq source URL must be the exact Data_1_0.asmx endpoint.')
    return '//' + host + '/MinuteTraqService/agency/' + quote(options['minutetraq_agency'], safe='')


def parse_bundle(source, namespace_value, content):
    options = validate_options(source)
    if namespace_value != namespace(source):
        raise ValueError('Passed namespace does not match the source namespace.')
    expected = (('AgendaGetResponse', 'AgendaGetResult', 'agenda')
                if options['document_kind'] == 'agenda' else
                ('MinutesGetResponse', 'MinutesGetResult', 'minutes'))
    root = _parse_xml(content)
    if root.tag != '{' + SOAP_NS + '}Envelope':
        raise ValueError('Saved response must be a SOAP 1.1 Envelope.')
    body = _single_ns(root, SOAP_NS, 'Body', 'SOAP Body')
    if any(_local(element.tag) == 'Fault' for element in body.iter()):
        raise ValueError('SOAP Fault responses are not importable captures.')
    body_children = list(body)
    if len(body_children) != 1:
        raise ValueError('SOAP Body must contain exactly one response.')
    response = body_children[0]
    if response.tag != '{' + SERVICE_NS + '}' + expected[0]:
        raise ValueError('The saved response operation does not match document_kind.')
    response_children = list(response)
    if len(response_children) != 1:
        raise ValueError('SOAP response must contain exactly one result.')
    result = response_children[0]
    if result.tag != '{' + SERVICE_NS + '}' + expected[1]:
        raise ValueError('SOAP result wrapper is malformed.')
    diffgram = _single_ns(result, DIFFGR_NS, 'diffgram', 'diffgram')
    data_root = _single_ns(diffgram, DB_NS, 'DB_1_0', 'DB_1_0 data root')
    before_roots = [child for child in diffgram if child.tag == '{' + DIFFGR_NS + '}before']
    error_roots = [child for child in diffgram if child.tag == '{' + DIFFGR_NS + '}errors']
    if len(before_roots) > 1 or len(error_roots) > 1:
        raise ValueError('The saved diffgram has multiple before/error blocks.')
    current_rows = []
    for row in list(data_root):
        ns_uri, local = _split_tag(row.tag)
        if local in _MAPPED_TABLES and ns_uri != DB_NS:
            raise ValueError('A mapped MinuteTraq row uses a foreign namespace.')
        if _inactive_row(row):
            continue
        current_rows.append(row)
    rows_by_local = {}
    for row in current_rows:
        rows_by_local.setdefault(_local(row.tag), []).append(row)
    meeting_rows = rows_by_local.get('Meeting', [])
    if len(meeting_rows) > 1:
        raise ValueError('The saved response cannot contain multiple current Meeting rows.')
    meeting_row = meeting_rows[0] if meeting_rows else None
    if meeting_row is not None:
        meeting_id = _int32_text(meeting_row, 'MeetingID')
        if meeting_id != options['meeting_id']:
            raise ValueError('MeetingID does not match the configured meeting_id.')
    else:
        meeting_id = options['meeting_id']
    if options['document_kind'] == 'agenda':
        forbidden = [name for name in ('Minutes', 'MinutesItem') if rows_by_local.get(name)]
        if forbidden:
            raise ValueError('An Agenda response contains Minutes rows.')
        doc_rows = rows_by_local.get('Agenda', [])
        item_rows = rows_by_local.get('AgendaItem', [])
        doc_id_field, item_id_field, item_doc_field, item_type, doc_type = ('AgendaID', 'AgendaItemID', 'AgendaID', 'agenda_item', 'agenda')
    else:
        forbidden = [name for name in ('Agenda', 'AgendaItem') if rows_by_local.get(name)]
        if forbidden:
            raise ValueError('A Minutes response contains Agenda rows.')
        doc_rows = rows_by_local.get('Minutes', [])
        item_rows = rows_by_local.get('MinutesItem', [])
        doc_id_field, item_id_field, item_doc_field, item_type, doc_type = ('MinutesID', 'MinutesItemID', 'MinutesID', 'minutes_item', 'minutes')
    if len(doc_rows) != 1:
        raise ValueError('The saved response must contain exactly one current document row.')
    doc_row = doc_rows[0]
    doc_id = _int32_text(doc_row, doc_id_field)
    if doc_id != options['document_id']:
        raise ValueError('Document ID does not match the configured document_id.')
    doc_meeting_id = _int32_text(doc_row, 'MeetingID')
    if doc_meeting_id != meeting_id:
        raise ValueError('Document MeetingID does not match the selected meeting identity.')
    item_normalized = []
    seen_item_ids = set()
    for item_row in item_rows:
        item_id = _positive_long_text(item_row, item_id_field)
        if item_id in seen_item_ids:
            raise ValueError('Duplicate native item ID in the saved response.')
        seen_item_ids.add(item_id)
        linked_doc = _int32_text(item_row, item_doc_field)
        if linked_doc != doc_id:
            raise ValueError('An item row is linked to a different document ID.')
        parent_id = _optional_int_text(item_row, 'ParentItemID', -9223372036854775808, 9223372036854775807)
        sort = _optional_int_text(item_row, 'Sort', -32768, 32767)
        title = _optional_text(item_row, 'Title')
        normalized = {'external_id': str(item_id), 'meeting_id': meeting_id,
                      'document_id': doc_id, 'document_kind': doc_type,
                      'parent_item_id': parent_id, 'sort': sort, 'title': title}
        item_normalized.append((normalized, _raw_element(item_row), item_type))
    doc_norm = {'external_id': str(doc_id), 'meeting_id': meeting_id,
                'document_id': doc_id, 'document_kind': doc_type,
                'url': source.url, 'source_operation': expected[0]}
    rows = []
    if meeting_row is not None:
        meeting_norm = {'external_id': str(meeting_id), 'meeting_id': meeting_id,
                        'document_id': doc_id, 'document_kind': doc_type,
                        'url': source.url, 'source_operation': expected[0]}
        scheduled_start = _optional_iso_text(meeting_row, 'MeetingDate')
        if scheduled_start is not None:
            meeting_norm['scheduled_start'] = scheduled_start
        rows.append((meeting_norm, _raw_element(meeting_row), 'meeting'))
    rows.append((doc_norm, _raw_element(doc_row), doc_type))
    rows.extend(item_normalized)
    bundle = make_bundle(source, namespace_value, content, FORMAT, rows)
    bundle['extensions']['iqm2_soap'] = {
        'operation': expected[0],
        'raw_data': _raw_element(data_root),
        'raw_before': [_raw_element(element) for element in before_roots],
        'raw_errors': [_raw_element(element) for element in error_roots],
    }
    by_id = {}
    for record in bundle['records']:
        if record['identity']['record_type'] in {'agenda_item', 'minutes_item'}:
            by_id[record['identity']['external_id']] = record['identity']
    meeting_record = next((record for record in bundle['records']
                           if record['identity']['record_type'] == 'meeting'), None)
    if meeting_record is not None:
        meeting_identity = meeting_record['identity']
    else:
        meeting_identity = {
            'provider': source.provider, 'namespace': namespace_value,
            'record_type': 'meeting', 'external_id': str(meeting_id), 'parent': None,
            'derivation': 'provider_identifier',
            'stability': 'Provider-issued identifier within the configured namespace.',
        }
    doc_record = next(record for record in bundle['records']
                      if record['identity']['record_type'] == doc_type)
    doc_identity = doc_record['identity']
    doc_identity['parent'] = meeting_identity
    doc_record['relationships'].append({'relation': 'meeting', 'identity': meeting_identity})
    for record in bundle['records']:
        if record['identity']['record_type'] not in {'agenda_item', 'minutes_item'}:
            continue
        record['identity']['parent'] = doc_identity
        record['relationships'].append({'relation': doc_type, 'identity': doc_identity})
        parent_value = record['normalized'].get('parent_item_id')
        if parent_value is not None and str(parent_value) in by_id:
            record['relationships'].append({'relation': record['identity']['record_type'], 'identity': by_id[str(parent_value)]})
        title = record['normalized'].get('title')
        if title:
            record['text'] = [{'field': 'Title', 'text': title, 'citation_url': source.url,
                               'completeness': 'supplied'}]
    return bundle


_XML_MEDIA_TYPES = {'text/xml', 'application/xml'}
_DATETIME_RE = re.compile(
    r'^-?\d{4,}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$')


class _CredentialsError(Exception):
    pass


def _source_origin(source):
    parsed = urlsplit(source.url)
    return parsed.scheme + '://' + (parsed.hostname or '')


def _ids_include(values, selected, kind=None):
    if isinstance(values, dict):
        values = values.get(kind)
    return (isinstance(values, (list, tuple, set, frozenset)) and len(values) <= 128
            and selected in values)


def _validate_authorization_header(value, agency, client_version):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise _CredentialsError
    if any(ord(char) < 0x20 or ord(char) == 0x7f for char in value):
        raise _CredentialsError
    parts = value.split(':')
    if len(parts) != 8:
        raise _CredentialsError
    prefix, identity, password_hash, connection_id, source_address, literal, version, _ = parts
    if prefix not in {'Basic', 'Web', 'Service'}:
        raise _CredentialsError
    suffix = '@' + agency.replace(':', '|~|')
    if not identity.endswith(suffix) or not identity[:-len(suffix)]:
        raise _CredentialsError
    if re.fullmatch(r'[0-9A-Fa-f]{32}', password_hash) is None:
        raise _CredentialsError
    if re.fullmatch(r'[0-9A-Fa-f]{1,16}', connection_id) is None:
        raise _CredentialsError
    if source_address and not source_address.startswith(('M-', 'I-', 'N-')):
        raise _CredentialsError
    if literal != 'MinuteTraq':
        raise _CredentialsError
    if re.fullmatch(r'\d+\.\d+\.\d+\.\d+', version) is None:
        raise _CredentialsError
    if client_version != version:
        raise _CredentialsError


def _trusted_config(source, options, namespace_value, context):
    credentials = getattr(context, 'credentials', None)
    config = credentials.get('iqm2') if isinstance(credentials, dict) else None
    if not isinstance(config, dict) or not context.tenant:
        raise _CredentialsError
    if config.get('tenant') != context.tenant:
        raise _CredentialsError
    if config.get('origin') != _source_origin(source):
        raise _CredentialsError
    if config.get('agency') != options['minutetraq_agency']:
        raise _CredentialsError
    allowed = config.get('allowed_namespaces')
    if (not isinstance(allowed, (list, tuple, set, frozenset)) or len(allowed) > 128
            or namespace_value not in allowed):
        raise _CredentialsError
    if not _ids_include(config.get('meeting_ids'), options['meeting_id']):
        raise _CredentialsError
    kind = options['document_kind']
    if not _ids_include(config.get('document_ids'), options['document_id'], kind):
        raise _CredentialsError
    if config.get('document_kind') != kind:
        raise _CredentialsError
    version = config.get('client_version')
    if not isinstance(version, str) or re.fullmatch(r'\d+\.\d+\.\d+\.\d+', version) is None:
        raise _CredentialsError
    authorization_header = config.get('authorization_header')
    _validate_authorization_header(authorization_header, options['minutetraq_agency'], version)
    return {'authorization_header': authorization_header, 'client_version': version}


def _valid_datetime(value):
    if not isinstance(value, str) or _DATETIME_RE.fullmatch(value) is None:
        return False
    if value.endswith('Z'):
        candidate = value[:-1] + '+00:00'
    else:
        candidate = value
        offset = re.search(r'([+-])(\d{2}):(\d{2})$', candidate)
        if offset:
            hours = int(offset.group(2))
            minutes = int(offset.group(3))
            if hours > 14 or minutes > 59 or (hours == 14 and minutes != 0):
                return False
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def _request_dates(request):
    values = []
    for key in ('minutetraq_file_since', 'minutetraq_public_file_since'):
        value = request.get(key) if isinstance(request, dict) else None
        if not _valid_datetime(value):
            raise ValueError('MinuteTraq file-since values must be explicit XML-schema dateTimes.')
        values.append(value)
    return values


def _soap_body(method, id_field, document_id, meeting_id, file_since, public_since):
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="' + SOAP_NS + '">'
            '<soap:Body><' + method + ' xmlns="' + SERVICE_NS + '">'
            '<' + id_field + '>' + str(document_id) + '</' + id_field + '>'
            '<MeetingID>' + str(meeting_id) + '</MeetingID>'
            '<GetFileDataIfNewerThan>' + file_since + '</GetFileDataIfNewerThan>'
            '<GetPublicFileDataIfNewerThan>' + public_since + '</GetPublicFileDataIfNewerThan>'
            '</' + method + '></soap:Body></soap:Envelope>').encode('utf-8')


def read(source, namespace_value, request, bounds, context, transport):
    try:
        options = validate_options(source)
        expected_namespace = namespace(source)
        if namespace_value != expected_namespace:
            raise ValueError('MinuteTraq namespace does not match the selected source.')
        trusted = _trusted_config(source, options, namespace_value, context)
        if request.get('attachment') is not None or any(
                key in request for key in ('external_id', 'parent_id', 'record_type')):
            raise ValueError('MinuteTraq SOAP reads select only the configured meeting and document.')
        file_since, public_since = _request_dates(request)
        if context.check_cancelled():
            return OperationResult('cancelled', operation_id=context.operation_id)
        if bounds.max_records < 1:
            raise ValueError('MinuteTraq record bounds must allow at least one record.')
        kind = options['document_kind']
        method = 'AgendaGet' if kind == 'agenda' else 'MinutesGet'
        id_field = 'AgendaID' if kind == 'agenda' else 'MinutesID'
        body = _soap_body(method, id_field, options['document_id'], options['meeting_id'],
                          file_since, public_since)
        origin = _source_origin(source)
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        if limit < 1:
            raise ValueError('MinuteTraq byte bounds must allow a response.')
        headers = {
            'Content-Type': 'text/xml;charset=utf-8',
            'SOAPAction': '"' + SERVICE_NS + '/' + method + '"',
            'Authorization': trusted['authorization_header'],
            'MinuteTraqVersion': trusted['client_version'],
        }
        deadline = monotonic() + bounds.deadline_seconds
        response = transport.request(
            source.url, method='POST', body=body, headers=headers,
            byte_limit=limit, deadline_seconds=bounds.deadline_seconds,
            allowed_origins=(origin,), allow_redirects=False)
        if context.check_cancelled():
            return OperationResult('cancelled', operation_id=context.operation_id)
        if response.url != source.url:
            raise ValueError('The MinuteTraq response changed its selected URL.')
        if len(response.content) > limit or monotonic() >= deadline:
            raise ValueError('The MinuteTraq response exceeded its byte or deadline boundary.')
        if response.status in {401, 403}:
            return OperationResult('failed', errors=(Error(
                'permission_denied', 'The selected MinuteTraq read was denied.', source=source.url),),
                operation_id=context.operation_id)
        if response.status != 200:
            raise ValueError('The MinuteTraq response was not a successful HTTP response.')
        media_type = response.content_type.split(';', 1)[0].strip().lower()
        if media_type not in _XML_MEDIA_TYPES:
            raise ValueError('The MinuteTraq response was not XML.')
        bundle = parse_bundle(source, namespace_value, response.content)
        if len(bundle['records']) > bounds.max_records:
            raise ValueError('The MinuteTraq response exceeds the configured record bound.')
        if context.check_cancelled():
            return OperationResult('cancelled', operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise ValueError('The MinuteTraq response exceeded its total deadline.')
        return OperationResult('completed', bundle, coverage={
            'scope': 'one selected MinuteTraq ' + kind + ' document',
            'catalog_complete': False, 'source_complete': False,
            'returned_records': len(bundle['records']), 'operation': method,
        }, operation_id=context.operation_id)
    except _CredentialsError:
        return OperationResult('failed', errors=(Error(
            'credentials_required',
            'A trusted MinuteTraq session-scoped credential is required.'),),
            operation_id=context.operation_id)
    except InterruptedError:
        return OperationResult('cancelled', operation_id=context.operation_id)
    except Exception:
        return OperationResult('failed', errors=(Error(
            'minutetraq_unavailable',
            'The selected MinuteTraq response could not be retrieved or validated.',
            source=source.url),), operation_id=context.operation_id)
