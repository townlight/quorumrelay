'''Bounded MinuteTraq agenda/minutes item Title updates via AgendaUpdate/MinutesUpdate.'''
from __future__ import annotations

import base64
import codecs
from copy import deepcopy
from dataclasses import asdict
import re
from time import monotonic
import xml.etree.ElementTree as ET
from xml.parsers import expat
from xml.sax.saxutils import escape, quoteattr

from ..engine import canonical_hash
from ..write_adapters import (
    AmbiguousWrite, WriteAdapter, WriteCancelled, WriteChange, WriteFailure,
)
from ..write_transport import WriteResponse
from . import iqm2_soap

SERVICE_NS = iqm2_soap.SERVICE_NS
SOAP_NS = iqm2_soap.SOAP_NS
DIFFGR_NS = iqm2_soap.DIFFGR_NS
DB_NS = iqm2_soap.DB_NS
XSI_NS = iqm2_soap.XSI_NS
XML_SCHEMA_NS = 'http://www.w3.org/2001/XMLSchema'
MSDATA_NS = 'urn:schemas-microsoft-com:xml-msdata'
MAX_INT32 = 2147483647
MAX_INT64 = 9223372036854775807
_MEETING_FORMAT = 'iqm2-minutetraq-meeting-soap-xml'
_MEDIA_FORMAT = 'iqm2-minutetraq-media-soap-xml'


def _kind(value):
    return 'agenda' if value == 'agenda' else 'minutes'


def _parent_tag(kind):
    return 'Agenda' if kind == 'agenda' else 'Minutes'


def _item_tag(kind):
    return 'AgendaItem' if kind == 'agenda' else 'MinutesItem'


def _doc_id_field(kind):
    return 'AgendaID' if kind == 'agenda' else 'MinutesID'


def _item_id_field(kind):
    return 'AgendaItemID' if kind == 'agenda' else 'MinutesItemID'


def _read_method(kind):
    return 'AgendaGet' if kind == 'agenda' else 'MinutesGet'


def _update_method(kind):
    return 'AgendaUpdate' if kind == 'agenda' else 'MinutesUpdate'


def _positive_id(value, label, maximum):
    if isinstance(value, bool):
        raise ValueError(label + ' must be a positive native identifier.')
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r'[1-9][0-9]*', value):
        parsed = int(value)
    else:
        raise ValueError(label + ' must be a positive native identifier.')
    if not 1 <= parsed <= maximum:
        raise ValueError(label + ' must be within the native identifier range.')
    return str(parsed)


_NATIVE_DATETIME_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.(\d+))?(?:Z|[+-]\d{2}:\d{2})?$')


def _is_xs_datetime_type(schema_raw, type_value):
    if type_value == '{' + XML_SCHEMA_NS + '}dateTime':
        return True
    if ':' in type_value:
        prefix, local = type_value.split(':', 1)
        if local != 'dateTime':
            return False
        match = re.search(r'xmlns:' + re.escape(prefix) + r'\s*=\s*["\']([^"\']+)["\']', schema_raw)
        return bool(match and match.group(1) == XML_SCHEMA_NS)
    return type_value in {'xs:dateTime', 'xsd:dateTime'}


def _canonical_native_datetime(value):
    if not isinstance(value, str) or not iqm2_soap._valid_datetime(value):
        raise ValueError('Native Updated must be an XML-schema dateTime.')
    match = _NATIVE_DATETIME_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError('Native Updated must be an XML-schema dateTime.')
    result = match.group(1) + 'T' + match.group(2)
    fraction = (match.group(3) or '').rstrip('0')
    if fraction:
        result += '.' + fraction
    return result


def _validate_updated_datetime_mode(schema_raw, kind):
    try:
        schema = ET.fromstring(schema_raw)
    except ET.ParseError as exc:
        raise ValueError('The inline schema could not be parsed.') from exc
    parent_name = _parent_tag(kind)
    for parent in schema.iter():
        if parent.tag != '{' + XML_SCHEMA_NS + '}element' or parent.attrib.get('name') != parent_name:
            continue
        for child in parent.iter():
            if (child.tag == '{' + XML_SCHEMA_NS + '}element'
                    and child.attrib.get('name') == 'Updated'):
                mode = child.attrib.get('{' + MSDATA_NS + '}DateTimeMode')
                if mode and mode != 'UnspecifiedLocal':
                    raise ValueError('Unsupported native Updated DateTimeMode.')
                type_value = child.attrib.get('type')
                if type_value and not _is_xs_datetime_type(schema_raw, type_value):
                    raise ValueError('Native Updated must be an XML-schema dateTime.')
                return
    raise ValueError('The native Updated column is not defined for the selected document.')


def _set_field(row, name, value, *, allow_nil=False):
    matches = [child for child in row if child.tag == '{' + DB_NS + '}' + name]
    if len(matches) > 1:
        raise ValueError('Row contains ambiguous native ' + name + ' fields.')
    if matches:
        child = matches[0]
    else:
        child = ET.SubElement(row, '{' + DB_NS + '}' + name)
    if value is None:
        if not allow_nil:
            raise ValueError(name + ' cannot be null.')
        child.text = None
        child.attrib['{' + XSI_NS + '}nil'] = 'true'
        for nested in list(child):
            child.remove(nested)
    else:
        child.attrib.pop('{' + XSI_NS + '}nil', None)
        child.text = str(value)
        for nested in list(child):
            child.remove(nested)
    return child


def _ensure_diffgr_id(row, prefix, native_id):
    row.attrib.pop('{' + DIFFGR_NS + '}hasChanges', None)
    row.attrib.pop('{' + DIFFGR_NS + '}hasErrors', None)
    row.attrib['{' + DIFFGR_NS + '}id'] = prefix + str(native_id)
    return row.attrib['{' + DIFFGR_NS + '}id']


def _element_repr(element, kind=None, *, is_row=False):
    ns, local = iqm2_soap._split_tag(element.tag)
    skip = {
        '{' + DIFFGR_NS + '}id',
        '{' + DIFFGR_NS + '}hasChanges',
        '{' + DIFFGR_NS + '}hasErrors',
        '{' + MSDATA_NS + '}rowOrder',
    }
    attrs = sorted((key, value) for key, value in element.attrib.items() if key not in skip)
    children = []
    for child in element:
        if (is_row and kind in {'agenda', 'minutes'}
                and local in {'Agenda', 'Minutes'}
                and child.tag == '{' + DB_NS + '}UpdatedUserID'):
            continue
        child_repr = _element_repr(child)
        if child.tail is not None and child.tail.strip():
            child_repr['tail'] = child.tail
        children.append(child_repr)
    if children:
        text = element.text if element.text is not None and element.text.strip() else None
    else:
        text = element.text
    return {'tag': local, 'namespace': ns, 'attrs': attrs, 'text': text, 'children': children}


def _row_key(row, kind):
    local = iqm2_soap._local(row.tag)
    field = {
        'Meeting': 'MeetingID',
        'Agenda': 'AgendaID',
        'Minutes': 'MinutesID',
        'AgendaItem': 'AgendaItemID',
        'MinutesItem': 'MinutesItemID',
    }.get(local)
    if field:
        try:
            exists, nil, value = iqm2_soap._child_value(row, field)
            if exists and not nil and value:
                return local + ':' + value.strip()
        except ValueError:
            pass
    return local + ':' + repr(_element_repr(row, kind, is_row=True))


def _root_repr(root, kind):
    rows = [row for row in list(root) if not iqm2_soap._inactive_row(row)]
    rows.sort(key=lambda row: _row_key(row, kind))
    return {
        'tag': iqm2_soap._local(root.tag),
        'namespace': iqm2_soap._split_tag(root.tag)[0],
        'attrs': sorted(root.attrib.items()),
        'rows': [_element_repr(row, kind, is_row=True) for row in rows],
    }


def _canonicalize_native_title_nulls(root, kind):
    item_tag = '{' + DB_NS + '}' + _item_tag(kind)
    for row in list(root):
        if row.tag != item_tag:
            continue
        for child in list(row):
            if child.tag != '{' + DB_NS + '}Title':
                continue
            if set(child.attrib) != {'{' + XSI_NS + '}nil'}:
                continue
            if child.attrib['{' + XSI_NS + '}nil'] not in {'true', '1'}:
                continue
            if list(child) or child.text is not None:
                continue
            row.remove(child)


def _fingerprint(schema_raw, schema_ns_decls, data_root, kind, *, canonicalize_updated=False):
    root = data_root
    if canonicalize_updated:
        root = deepcopy(data_root)
        parents = [row for row in list(root) if row.tag == '{' + DB_NS + '}' + _parent_tag(kind)]
        if len(parents) != 1:
            raise ValueError('Selected dataset must contain exactly one parent document row.')
        updates = [child for child in parents[0] if child.tag == '{' + DB_NS + '}Updated']
        if len(updates) != 1 or updates[0].attrib.get('{' + XSI_NS + '}nil') == 'true':
            raise ValueError('Selected dataset must contain exactly one non-null native Updated field.')
        updates[0].text = _canonical_native_datetime(updates[0].text)
        _canonicalize_native_title_nulls(root, kind)
    return canonical_hash({
        'schema': schema_raw,
        'schema_namespaces': sorted(schema_ns_decls),
        'data': _root_repr(root, kind),
    })


def _apply_target(root, kind, document_id, titles, updated):
    target = deepcopy(root)
    parent_tag = _parent_tag(kind)
    item_tag = _item_tag(kind)
    parent_id_field = _doc_id_field(kind)
    item_id_field = _item_id_field(kind)
    parents = [row for row in list(target) if row.tag == '{' + DB_NS + '}' + parent_tag]
    if len(parents) != 1:
        raise ValueError('Selected dataset must contain exactly one parent document row.')
    parent = parents[0]
    if iqm2_soap._int32_text(parent, parent_id_field) != int(document_id):
        raise ValueError('Parent document identity changed.')
    _set_field(parent, 'Updated', updated)
    items = {}
    for row in list(target):
        if row.tag != '{' + DB_NS + '}' + item_tag:
            continue
        item_id = str(iqm2_soap._positive_long_text(row, item_id_field))
        items[item_id] = row
    for item_id, title in titles.items():
        if item_id not in items:
            raise ValueError('Selected item disappeared from the dataset.')
        _set_field(items[item_id], 'Title', title, allow_nil=True)
    return target


def _detect_encoding(content):
    if content.startswith(codecs.BOM_UTF32_LE) or content.startswith(codecs.BOM_UTF32_BE):
        return 'utf-32-le' if content.startswith(codecs.BOM_UTF32_LE) else 'utf-32-be'
    if content.startswith(codecs.BOM_UTF8):
        return 'utf-8-sig'
    if content.startswith(codecs.BOM_UTF16_LE) or content.startswith(codecs.BOM_UTF16_BE):
        return 'utf-16-le' if content.startswith(codecs.BOM_UTF16_LE) else 'utf-16-be'
    head = content[:256].decode('ascii', errors='ignore')
    match = re.search(r'<\?xml[^>]*encoding\s*=\s*["\']([^"\']+)["\']', head, re.I)
    if match:
        return match.group(1)
    return 'utf-8'


def _ensure_schema_namespaces(schema_raw, namespaces):
    end = schema_raw.find('>')
    if end == -1:
        raise ValueError('The inline schema start tag could not be located.')
    start_tag = schema_raw[:end + 1]
    existing = set()
    for match in re.finditer(r'xmlns(?::([A-Za-z_][\w.-]*))?\s*=\s*[\x22\x27][^\x22\x27]*[\x22\x27]', start_tag, re.I):
        existing.add(match.group(1) or '')
    additions = []
    for prefix, uri in namespaces:
        if prefix in {'xml', 'xmlns'} or prefix in existing:
            continue
        if prefix:
            additions.append(' xmlns:' + prefix + '=' + quoteattr(uri))
        else:
            additions.append(' xmlns=' + quoteattr(uri))
        existing.add(prefix)
    if not additions:
        return schema_raw
    if start_tag.rstrip().endswith('/>'):
        pos = start_tag.rfind('/>')
        start_tag = start_tag[:pos] + ''.join(additions) + start_tag[pos:]
    else:
        start_tag = start_tag[:-1] + ''.join(additions) + '>'
    return start_tag + schema_raw[end + 1:]


def _extract_raw_schema(content):
    iqm2_soap._reject_dtd(content)
    encoding = _detect_encoding(content)
    try:
        text = content.decode(encoding)
    except (LookupError, UnicodeError) as exc:
        raise ValueError('The inline schema encoding could not be decoded.') from exc
    if text.startswith('\ufeff'):
        text = text[1:]
    text = re.sub(r'^\s*<\?xml[^>]*\?>', '', text, count=1, flags=re.I)
    normalized = text.encode('utf-8')
    iqm2_soap._reject_dtd(normalized)
    parser = expat.ParserCreate(namespace_separator='}')
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.ExternalEntityRefHandler = lambda *args: 0
    state = {
        'depth': 0,
        'target_depth': None,
        'start': None,
        'end': None,
        'namespaces': [],
        'current': {},
        'pending': {},
        'stack': [],
    }

    def start_ns(prefix, uri):
        state['pending'][prefix or ''] = uri

    def start(name, attrs):
        current = dict(state['current'])
        current.update(state['pending'])
        state['pending'] = {}
        state['current'] = current
        state['stack'].append(current)
        state['depth'] += 1
        if state['target_depth'] is None and name == XML_SCHEMA_NS + '}schema':
            state['target_depth'] = state['depth']
            start_index = parser.CurrentByteIndex
            state['start'] = start_index
            state['namespaces'] = list(current.items())
            tag_end = normalized.find(b'>', start_index)
            if tag_end == -1:
                raise ValueError('The inline schema start tag could not be located.')
            if normalized[tag_end - 1:tag_end] == b'/':
                state['end'] = tag_end + 1

    def end(name):
        if (state['target_depth'] is not None and
                state['depth'] == state['target_depth'] and state['end'] is None):
            idx = parser.CurrentByteIndex
            if normalized[idx:idx + 2] == b'</':
                close_end = normalized.find(b'>', idx)
            else:
                close_start = normalized.rfind(b'</', state['start'], idx + 1)
                close_end = normalized.find(b'>', close_start) if close_start != -1 else -1
            if close_end == -1:
                raise ValueError('The inline schema end tag could not be located.')
            state['end'] = close_end + 1
        state['stack'].pop()
        state['current'] = state['stack'][-1] if state['stack'] else {}
        state['depth'] -= 1

    parser.StartNamespaceDeclHandler = start_ns
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(normalized, True)
    if state['start'] is None or state['end'] is None:
        raise ValueError('The saved response must contain one inline XML schema.')
    raw = normalized[state['start']:state['end']].decode('utf-8')
    return _ensure_schema_namespaces(raw, state['namespaces']), state['namespaces']


class _PrefixAllocator:
    def __init__(self, used):
        self._next = 0
        self._used = set(used)

    def new(self):
        while True:
            self._next += 1
            prefix = 'ns' + str(self._next)
            if prefix not in self._used:
                self._used.add(prefix)
                return prefix


def _serialize_element(element, nsmap, allocator, default_ns):
    nsmap = dict(nsmap)
    declarations = []

    def declare(prefix, uri):
        for existing_prefix, _ in declarations:
            if existing_prefix == prefix:
                return
        declarations.append((prefix, uri))

    def ensure_prefix(uri, attribute=False):
        if uri in nsmap and nsmap[uri] and not (attribute and nsmap[uri] == ''):
            return nsmap[uri]
        prefix = allocator.new()
        nsmap[uri] = prefix
        declare(prefix, uri)
        return prefix

    ns_uri, local = iqm2_soap._split_tag(element.tag)
    if ns_uri == '':
        qname = local
        if default_ns != '':
            declare('', '')
        new_default_ns = ''
    elif nsmap.get(ns_uri) == '':
        if default_ns == ns_uri:
            qname = local
        else:
            declare('', ns_uri)
            qname = local
        new_default_ns = ns_uri
    else:
        prefix = ensure_prefix(ns_uri)
        qname = prefix + ':' + local
        new_default_ns = default_ns

    attrs = []
    for key, value in element.attrib.items():
        attr_ns, attr_local = iqm2_soap._split_tag(key)
        if attr_ns:
            attr_prefix = ensure_prefix(attr_ns, True)
            attr_name = attr_prefix + ':' + attr_local
        else:
            attr_name = attr_local
        attrs.append((attr_name, value))

    parts = ['<' + qname]
    for decl_prefix, decl_uri in declarations:
        if decl_prefix == '':
            parts.append(' xmlns=' + quoteattr(decl_uri))
        else:
            parts.append(' xmlns:' + decl_prefix + '=' + quoteattr(decl_uri))
    for attr_name, value in attrs:
        parts.append(' ' + attr_name + '=' + quoteattr(str(value)))

    children = list(element)
    if children:
        if element.text is not None and element.text.strip():
            parts.append('>')
            parts.append(escape(element.text))
        else:
            parts.append('>')
        for child in children:
            parts.append(_serialize_element(child, nsmap, allocator, new_default_ns))
            if child.tail is not None and child.tail.strip():
                parts.append(escape(child.tail))
        parts.append('</' + qname + '>')
    elif element.text is None:
        parts.append('/>')
    else:
        parts.append('>')
        parts.append(escape(element.text))
        parts.append('</' + qname + '>')
    return ''.join(parts)


def _schema_namespace_attrs(namespaces):
    seen = set()
    result = []
    for prefix, uri in namespaces:
        if not prefix or prefix in {'xml', 'xmlns'} or prefix in seen:
            continue
        seen.add(prefix)
        result.append(' xmlns:' + prefix + '=' + quoteattr(uri))
    return ''.join(result)


def _build_request_body(method, schema_xml, schema_ns_decls, current_rows, before_rows):
    base_ns = {DB_NS: '', DIFFGR_NS: 'diffgr', XSI_NS: 'xsi', MSDATA_NS: 'msdata'}
    used_prefixes = {'diffgr', 'msdata', 'xsi', 'xs'}
    current_xml = ''.join(
        _serialize_element(row, base_ns, _PrefixAllocator(used_prefixes), DB_NS) for row in current_rows)
    before_xml = ''.join(
        _serialize_element(row, base_ns, _PrefixAllocator(used_prefixes), DB_NS) for row in before_rows)
    ns_attrs = _schema_namespace_attrs(schema_ns_decls)
    head = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="' + SOAP_NS + '">'
        '<soap:Body>'
        '<' + method + ' xmlns="' + SERVICE_NS + '">'
        '<ds' + ns_attrs + '>'
        + schema_xml +
        '<diffgr:diffgram xmlns:diffgr="' + DIFFGR_NS + '" xmlns:msdata="' + MSDATA_NS +
        '" xmlns:xsi="' + XSI_NS + '">'
        '<DB_1_0 xmlns="' + DB_NS + '">' + current_xml + '</DB_1_0>'
        '<diffgr:before xmlns="' + DB_NS + '">' + before_xml + '</diffgr:before>'
        '</diffgr:diffgram>'
        '</ds>'
        '</' + method + '>'
        '</soap:Body>'
        '</soap:Envelope>'
    )
    return head.encode('utf-8')


def _response_media_type(response):
    headers = getattr(response, 'headers', None)
    if not isinstance(headers, dict):
        return None
    for key, value in headers.items():
        if str(key).lower() == 'content-type':
            return str(value).split(';', 1)[0].strip().lower()
    return None


def _validate_update_ack(content, method):
    root = iqm2_soap._parse_xml(content)
    if root.tag != '{' + SOAP_NS + '}Envelope':
        raise ValueError('Saved response must be a SOAP 1.1 Envelope.')
    body = iqm2_soap._single_ns(root, SOAP_NS, 'Body', 'SOAP Body')
    if any(iqm2_soap._local(element.tag) == 'Fault' for element in body.iter()):
        raise ValueError('SOAP Fault responses are not successful update acknowledgments.')
    body_children = list(body)
    if len(body_children) != 1:
        raise ValueError('SOAP Body must contain exactly one update acknowledgment.')
    response = body_children[0]
    if response.tag != '{' + SERVICE_NS + '}' + method + 'Response':
        raise ValueError('The update acknowledgment operation is malformed.')
    result_children = list(response)
    if len(result_children) != 1:
        raise ValueError('The update acknowledgment must contain exactly one result.')
    result = result_children[0]
    if result.tag != '{' + SERVICE_NS + '}' + method + 'Result':
        raise ValueError('The update acknowledgment result wrapper is malformed.')
    return True


class IQM2WriteAdapter(WriteAdapter):
    def __init__(self, transport=None):
        super().__init__('iqm2', transport)
        self._meeting_adapter = None
        self._media_adapter = None

    def _meeting_delegate(self):
        if self._meeting_adapter is None:
            from .iqm2_meeting_write import IQM2MeetingWriteAdapter
            self._meeting_adapter = IQM2MeetingWriteAdapter(self.transport)
        return self._meeting_adapter

    def _media_delegate(self):
        if self._media_adapter is None:
            from .iqm2_media_write import IQM2MediaWriteAdapter
            self._media_adapter = IQM2MediaWriteAdapter(self.transport)
        self._media_adapter.file_engine = self.file_engine
        self._media_adapter.file_context = self.file_context
        return self._media_adapter

    def credentials(self, source, context):
        if getattr(source, 'input_format', None) == _MEDIA_FORMAT:
            return self._media_delegate().credentials(source, context)
        if getattr(source, 'input_format', None) == _MEETING_FORMAT:
            return self._meeting_delegate().credentials(source, context)
        if source.provider != self.provider:
            raise WriteFailure('mapping_unverified', 'The selected source is not an iQM2 MinuteTraq source.')
        if source.input_format != iqm2_soap.FORMAT or source.body is not None:
            raise WriteFailure('mapping_unverified', 'The exact saved MinuteTraq SOAP source format is required.')
        try:
            options = iqm2_soap.validate_options(source)
            namespace_value = iqm2_soap.namespace(source)
            if source.namespace != namespace_value:
                raise ValueError('Source namespace does not match the selected agency endpoint.')
            trusted = iqm2_soap._trusted_config(source, options, namespace_value, context)
        except iqm2_soap._CredentialsError:
            raise WriteFailure('credentials_required', 'A trusted MinuteTraq session-scoped credential is required.') from None
        except ValueError as exc:
            raise WriteFailure('mapping_unverified', str(exc)) from None
        if context.allowed_namespaces is not None and namespace_value not in context.allowed_namespaces:
            raise WriteFailure('permission_denied', 'The selected MinuteTraq namespace is outside current policy.')
        config = context.credentials.get('iqm2') if isinstance(context.credentials, dict) else None
        if not isinstance(config, dict):
            raise WriteFailure('credentials_required', 'A trusted MinuteTraq configuration is required.')
        return {
            'options': options,
            'namespace': namespace_value,
            'authorization': trusted['authorization_header'],
            'client_version': trusted['client_version'],
            'config': config,
        }

    def validate_source(self, source, context):
        if getattr(source, 'input_format', None) == _MEDIA_FORMAT:
            return self._media_delegate().validate_source(source, context)
        if getattr(source, 'input_format', None) == _MEETING_FORMAT:
            return self._meeting_delegate().validate_source(source, context)
        self.credentials(source, context)

    def _validate_change(self, change, binding, context):
        kind = _kind(binding['options']['document_kind'])
        if change.entity != kind or change.operation != 'update':
            raise WriteFailure('mapping_unverified', 'Only selected agenda/minutes document Title updates are mapped.')
        if change.files:
            raise WriteFailure('mapping_unverified', 'File mutations are outside this bounded increment.')
        if any(value is not None for value in (
                change.parent_id, change.language, change.page_number, change.meeting_id, change.expected_version)):
            raise WriteFailure('mapping_unverified', 'Foreign relationship or revision metadata is not mapped.')
        if change.resource_id is None:
            raise ValueError('The selected document ID must be supplied as resource_id.')
        document_id = _positive_id(change.resource_id, 'resource_id', MAX_INT32)
        if int(document_id) != binding['options']['document_id']:
            raise ValueError('resource_id does not match the selected document_id.')
        fields = change.fields
        allowed = {'updated', 'items', 'minutetraq_file_since', 'minutetraq_public_file_since'}
        if not isinstance(fields, dict) or set(fields) != allowed:
            raise ValueError('MinuteTraq write fields must be exactly updated, items and explicit read thresholds.')
        updated = fields['updated']
        if not iqm2_soap._valid_datetime(updated):
            raise ValueError('updated must be an explicit XML-schema dateTime.')
        file_since = fields['minutetraq_file_since']
        public_since = fields['minutetraq_public_file_since']
        if not iqm2_soap._valid_datetime(file_since) or not iqm2_soap._valid_datetime(public_since):
            raise ValueError('MinuteTraq read thresholds must be explicit XML-schema dateTimes.')
        items = fields['items']
        if not isinstance(items, list) or not items:
            raise ValueError('At least one exact existing item ID and Title must be supplied.')
        item_ids = []
        titles = {}
        for item in items:
            if not isinstance(item, dict) or set(item) != {'item_id', 'title'}:
                raise ValueError('Each item must contain exactly item_id and title.')
            item_id = _positive_id(item['item_id'], 'item_id', MAX_INT64)
            if item_id in titles:
                raise ValueError('Duplicate item IDs are not permitted.')
            title = item['title']
            if title is not None:
                if not isinstance(title, str):
                    raise ValueError('Title must be a string or explicit null.')
                if any(ord(char) < 0x20 and char not in '\t\n\r' for char in title):
                    raise ValueError('Title contains an unsupported control character.')
            item_ids.append(item_id)
            titles[item_id] = title
        permission = kind + '_item:update_title'
        permissions = binding['config'].get('permissions')
        if (not isinstance(permissions, (list, tuple, set, frozenset))
                or permission not in permissions):
            raise WriteFailure('permission_denied', 'This exact MinuteTraq Title update is outside current policy.')
        allowed_items = binding['config'].get('item_ids')
        if isinstance(allowed_items, dict):
            allowed_items = allowed_items.get(kind)
        if not isinstance(allowed_items, (list, tuple, set, frozenset)) or not allowed_items:
            raise WriteFailure('permission_denied', 'Exact native MinuteTraq item IDs are required.')
        allowed_set = {_positive_id(value, 'item_id', MAX_INT64) for value in allowed_items}
        if not set(item_ids) <= allowed_set:
            raise WriteFailure('permission_denied', 'One or more selected item IDs are outside current policy.')
        return {
            'kind': kind,
            'document_id': document_id,
            'item_ids': item_ids,
            'titles': titles,
            'updated': updated,
            'thresholds': {
                'minutetraq_file_since': file_since,
                'minutetraq_public_file_since': public_since,
            },
            'read_method': _read_method(kind),
            'method': _update_method(kind),
        }

    def authorize(self, source, change, context):
        if getattr(source, 'input_format', None) == _MEDIA_FORMAT:
            return self._media_delegate().authorize(source, change, context)
        if getattr(source, 'input_format', None) == _MEETING_FORMAT:
            return self._meeting_delegate().authorize(source, change, context)
        binding = self.credentials(source, context)
        self._validate_change(change, binding, context)

    def _headers(self, binding, method):
        return {
            'Content-Type': 'text/xml;charset=utf-8',
            'SOAPAction': '"' + SERVICE_NS + '/' + method + '"',
            'Authorization': binding['authorization'],
            'MinuteTraqVersion': binding['client_version'],
        }

    def _read_current(self, source, binding, thresholds, context, bounds, deadline):
        if context.check_cancelled():
            raise WriteCancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure('deadline_exceeded', 'The MinuteTraq read deadline expired.')
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        if limit < 1:
            raise ValueError('MinuteTraq byte bounds must allow a response.')
        options = binding['options']
        kind = _kind(options['document_kind'])
        method = _read_method(kind)
        id_field = _doc_id_field(kind)
        body = iqm2_soap._soap_body(
            method, id_field, options['document_id'], options['meeting_id'],
            thresholds['minutetraq_file_since'], thresholds['minutetraq_public_file_since'])
        try:
            response = self.transport.send(
                source.url, method='POST', body=body, headers=self._headers(binding, method),
                byte_limit=limit, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq dataset could not be read.') from None
        if context.check_cancelled():
            raise WriteCancelled()
        if not isinstance(response, WriteResponse) or len(response.content) > limit:
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq dataset response was invalid.')
        if response.status in {401, 403}:
            raise WriteFailure('permission_denied', 'The provider denied the selected MinuteTraq read.')
        if response.status != 200:
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq dataset response was not successful.')
        media_type = _response_media_type(response)
        if media_type is not None and media_type not in {'text/xml', 'application/xml'}:
            raise WriteFailure('minutetraq_unavailable', 'The selected MinuteTraq read did not return XML.')
        if monotonic() >= deadline:
            raise WriteFailure('deadline_exceeded', 'The MinuteTraq read exceeded the total deadline.')
        content = response.content
        iqm2_soap.parse_bundle(source, binding['namespace'], content)
        current = self._parse_dataset_response(content, binding, kind)
        if context.check_cancelled():
            raise WriteCancelled()
        if monotonic() >= deadline:
            raise WriteFailure('deadline_exceeded', 'The MinuteTraq read exceeded the total deadline.')
        if len(current['items']) + 1 > bounds.max_records:
            raise ValueError('The selected MinuteTraq dataset exceeds the configured record bound.')
        return current

    def _parse_dataset_response(self, content, binding, kind):
        root = iqm2_soap._parse_xml(content)
        if root.tag != '{' + SOAP_NS + '}Envelope':
            raise ValueError('Saved response must be a SOAP 1.1 Envelope.')
        body = iqm2_soap._single_ns(root, SOAP_NS, 'Body', 'SOAP Body')
        if any(iqm2_soap._local(element.tag) == 'Fault' for element in body.iter()):
            raise ValueError('SOAP Fault responses are not valid write snapshots.')
        body_children = list(body)
        if len(body_children) != 1:
            raise ValueError('SOAP Body must contain exactly one response.')
        response = body_children[0]
        expected_response = 'AgendaGetResponse' if kind == 'agenda' else 'MinutesGetResponse'
        expected_result = 'AgendaGetResult' if kind == 'agenda' else 'MinutesGetResult'
        if response.tag != '{' + SERVICE_NS + '}' + expected_response:
            raise ValueError('The saved response operation does not match document_kind.')
        result_children = list(response)
        if len(result_children) != 1:
            raise ValueError('SOAP response must contain exactly one result.')
        result = result_children[0]
        if result.tag != '{' + SERVICE_NS + '}' + expected_result:
            raise ValueError('SOAP result wrapper is malformed.')
        schemas = [child for child in result if child.tag == '{' + XML_SCHEMA_NS + '}schema']
        if len(schemas) != 1:
            raise ValueError('The saved response must contain exactly one inline DB_1_0 schema.')
        schema_raw, schema_ns_decls = _extract_raw_schema(content)
        diffgram = iqm2_soap._single_ns(result, DIFFGR_NS, 'diffgram', 'diffgram')
        before_blocks = [child for child in diffgram if child.tag == '{' + DIFFGR_NS + '}before']
        error_blocks = [child for child in diffgram if child.tag == '{' + DIFFGR_NS + '}errors']
        if before_blocks or error_blocks:
            raise ValueError('Read snapshots must not contain before/errors diffgram blocks.')
        data_root = iqm2_soap._single_ns(diffgram, DB_NS, 'DB_1_0', 'DB_1_0 data root')
        current_root = ET.Element(data_root.tag, dict(data_root.attrib))
        mapped = {'Meeting', 'Agenda', 'AgendaItem', 'Minutes', 'MinutesItem'}
        for row in list(data_root):
            row_ns, row_local = iqm2_soap._split_tag(row.tag)
            if row_local in mapped and row_ns != DB_NS:
                raise ValueError('A mapped MinuteTraq row uses a foreign namespace.')
            changes = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasChanges')
            errors = iqm2_soap._attr_ns(row, DIFFGR_NS, 'hasErrors')
            if changes is not None and changes.strip():
                raise ValueError('Read snapshots must not contain changed rows.')
            if errors is not None and errors.strip().lower() in {'true', '1'}:
                raise ValueError('Read snapshots must not contain row errors.')
            current_root.append(deepcopy(row))
        options = binding['options']
        parent_tag = _parent_tag(kind)
        item_tag = _item_tag(kind)
        parent_id_field = _doc_id_field(kind)
        item_id_field = _item_id_field(kind)
        parents = [row for row in list(current_root) if row.tag == '{' + DB_NS + '}' + parent_tag]
        if len(parents) != 1:
            raise ValueError('The selected dataset must contain exactly one current parent document row.')
        parent = parents[0]
        if iqm2_soap._int32_text(parent, parent_id_field) != options['document_id']:
            raise ValueError('Parent document ID does not match the selected source.')
        if iqm2_soap._int32_text(parent, 'MeetingID') != options['meeting_id']:
            raise ValueError('Parent MeetingID does not match the selected source.')
        items = {}
        for row in list(current_root):
            if row.tag != '{' + DB_NS + '}' + item_tag:
                continue
            item_id = str(iqm2_soap._positive_long_text(row, item_id_field))
            if item_id in items:
                raise ValueError('Duplicate native item ID in the selected dataset.')
            if iqm2_soap._int32_text(row, parent_id_field) != options['document_id']:
                raise ValueError('An item row is linked to a different document ID.')
            items[item_id] = row
        return {
            'schema_raw': schema_raw,
            'schema_ns_decls': schema_ns_decls,
            'data_root': current_root,
            'parent': parent,
            'items': items,
            'fingerprint': _fingerprint(schema_raw, schema_ns_decls, current_root, kind),
        }

    def prepare(self, source, change, context, bounds, deadline):
        if getattr(source, 'input_format', None) == _MEDIA_FORMAT:
            return self._media_delegate().prepare(source, change, context, bounds, deadline)
        if getattr(source, 'input_format', None) == _MEETING_FORMAT:
            return self._meeting_delegate().prepare(source, change, context, bounds, deadline)
        binding = self.credentials(source, context)
        normalized = self._validate_change(change, binding, context)
        if not isinstance(change.key, str) or not 0 < len(change.key) <= 200:
            raise ValueError('A bounded change key is required.')
        if len(normalized['item_ids']) > bounds.max_records:
            raise ValueError('Selected MinuteTraq items exceed the configured record bound.')
        current = self._read_current(source, binding, normalized['thresholds'], context, bounds, deadline)
        for item_id in normalized['item_ids']:
            if item_id not in current['items']:
                raise ValueError('An exact selected native item ID is missing from the current dataset.')
        kind = normalized['kind']
        _validate_updated_datetime_mode(current['schema_raw'], kind)
        parent_tag = _parent_tag(kind)
        item_tag = _item_tag(kind)
        parent_before = deepcopy(current['parent'])
        parent_after = deepcopy(current['parent'])
        _set_field(parent_after, 'Updated', normalized['updated'])
        _ensure_diffgr_id(parent_before, parent_tag, normalized['document_id'])
        _ensure_diffgr_id(parent_after, parent_tag, normalized['document_id'])
        parent_after.attrib['{' + DIFFGR_NS + '}hasChanges'] = 'modified'
        current_rows = [parent_after]
        before_rows = [parent_before]
        for item_id in normalized['item_ids']:
            item_before = deepcopy(current['items'][item_id])
            item_after = deepcopy(current['items'][item_id])
            _set_field(item_after, 'Title', normalized['titles'][item_id], allow_nil=True)
            _ensure_diffgr_id(item_before, item_tag, item_id)
            _ensure_diffgr_id(item_after, item_tag, item_id)
            item_after.attrib['{' + DIFFGR_NS + '}hasChanges'] = 'modified'
            current_rows.append(item_after)
            before_rows.append(item_before)
        target_root = _apply_target(
            current['data_root'], kind, normalized['document_id'], normalized['titles'], normalized['updated'])
        target_fingerprint = _fingerprint(
            current['schema_raw'], current['schema_ns_decls'], target_root, kind,
            canonicalize_updated=True)
        body = _build_request_body(
            normalized['method'], current['schema_raw'], current['schema_ns_decls'],
            current_rows, before_rows)
        if len(body) > min(bounds.parser_bytes, bounds.transfer_bytes):
            raise ValueError('The exact MinuteTraq update request exceeds byte bounds.')
        return {
            'change': asdict(change),
            'before_fingerprint': current['fingerprint'],
            'target_fingerprint': target_fingerprint,
            'native': {
                'method': 'POST',
                'url': source.url,
                'body_base64': base64.b64encode(body).decode('ascii'),
                'headers': {},
            },
            'kind': kind,
            'document_id': normalized['document_id'],
            'item_ids': normalized['item_ids'],
            'updated': normalized['updated'],
            'titles': normalized['titles'],
            'thresholds': normalized['thresholds'],
            'method': normalized['method'],
            'read_method': normalized['read_method'],
            'conflict_semantics': 'preflight_compare_not_atomic_upstream_cas',
            'effects': {
                'document_kind': kind,
                'item_count': len(normalized['item_ids']),
                'creates': False,
                'deletes': False,
                'publication': False,
                'files': False,
            },
        }

    def apply(self, source, prepared, context, bounds, deadline, *, persist=None):
        if getattr(source, 'input_format', None) == _MEDIA_FORMAT:
            return self._media_delegate().apply(source, prepared, context, bounds, deadline, persist=persist)
        if getattr(source, 'input_format', None) == _MEETING_FORMAT:
            return self._meeting_delegate().apply(source, prepared, context, bounds, deadline, persist=persist)
        binding = self.credentials(source, context)
        change = WriteChange.from_dict(prepared['change'])
        normalized = self._validate_change(change, binding, context)
        current = self._read_current(source, binding, prepared['thresholds'], context, bounds, deadline)
        if current['fingerprint'] != prepared['before_fingerprint']:
            raise WriteFailure('conflict', 'The selected MinuteTraq dataset changed after planning.')
        if persist and persist({'resource_id': prepared['document_id']}):
            raise WriteCancelled()
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WriteFailure('deadline_exceeded', 'The MinuteTraq update deadline expired before send.')
        body = base64.b64decode(prepared['native']['body_base64'])
        limit = min(bounds.parser_bytes, bounds.transfer_bytes)
        if context.check_cancelled():
            raise WriteCancelled()
        try:
            response = self.transport.send(
                source.url, method='POST', body=body,
                headers=self._headers(binding, normalized['method']),
                byte_limit=limit, deadline_seconds=remaining)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            raise AmbiguousWrite('The MinuteTraq update may have been accepted; do not resend.') from None
        if context.check_cancelled() or monotonic() >= deadline:
            raise AmbiguousWrite('The MinuteTraq update was sent; cancellation/deadline prevents exact confirmation.')
        if not isinstance(response, WriteResponse) or len(response.content) > limit:
            raise AmbiguousWrite('The MinuteTraq update response was invalid.')
        if response.status in {401, 403}:
            raise WriteFailure('permission_denied', 'The provider denied the selected MinuteTraq update.')
        if response.status in {409, 412}:
            raise WriteFailure('conflict', 'The provider rejected the MinuteTraq update as conflicting.')
        if not 200 <= response.status < 300:
            raise AmbiguousWrite('The MinuteTraq update response was not successful; do not resend.')
        media_type = _response_media_type(response)
        if media_type is not None and media_type not in {'text/xml', 'application/xml'}:
            raise AmbiguousWrite('The MinuteTraq update acknowledgment was not XML; do not resend.')
        try:
            _validate_update_ack(response.content, normalized['method'])
        except ValueError:
            raise AmbiguousWrite('The MinuteTraq update acknowledgment could not be exactly verified; do not resend.') from None
        try:
            after = self._read_current(source, binding, prepared['thresholds'], context, bounds, deadline)
            after_target_fingerprint = _fingerprint(
                after['schema_raw'], after['schema_ns_decls'], after['data_root'], normalized['kind'],
                canonicalize_updated=True)
        except WriteCancelled:
            return {
                'state': 'uncertain',
                'resource_id': prepared['document_id'],
                'reason': 'Post-send cancellation prevented exact readback.',
            }
        except (WriteFailure, ValueError):
            return {
                'state': 'uncertain',
                'resource_id': prepared['document_id'],
                'reason': 'Update was sent but exact readback could not complete.',
            }
        if after_target_fingerprint == prepared['target_fingerprint']:
            return {
                'state': 'succeeded',
                'resource_id': prepared['document_id'],
                'readback': {
                    'updated': prepared['updated'],
                    'items': [
                        {'item_id': item_id, 'title': prepared['titles'][item_id]}
                        for item_id in prepared['item_ids']
                    ],
                },
            }
        return {
            'state': 'uncertain',
            'resource_id': prepared['document_id'],
            'reason': 'Readback did not match the exact target diff; do not retry.',
        }

    def reconcile(self, source, prepared, item, context, bounds, deadline):
        if getattr(source, 'input_format', None) == _MEDIA_FORMAT:
            return self._media_delegate().reconcile(source, prepared, item, context, bounds, deadline)
        if getattr(source, 'input_format', None) == _MEETING_FORMAT:
            return self._meeting_delegate().reconcile(source, prepared, item, context, bounds, deadline)
        binding = self.credentials(source, context)
        change = WriteChange.from_dict(prepared['change'])
        self._validate_change(change, binding, context)
        try:
            after = self._read_current(source, binding, prepared['thresholds'], context, bounds, deadline)
            after_target_fingerprint = _fingerprint(
                after['schema_raw'], after['schema_ns_decls'], after['data_root'], prepared['kind'],
                canonicalize_updated=True)
        except (WriteFailure, WriteCancelled, ValueError):
            return {
                'state': 'uncertain',
                'resource_id': prepared['document_id'],
                'reason': 'Read-only reconciliation could not complete; do not retry the update.',
            }
        if after_target_fingerprint == prepared['target_fingerprint']:
            return {
                'state': 'succeeded',
                'resource_id': prepared['document_id'],
                'reconciled': True,
            }
        return {
            'state': 'uncertain',
            'resource_id': prepared['document_id'],
            'reason': 'Read-only readback does not confirm the exact target diff; do not retry.',
        }
