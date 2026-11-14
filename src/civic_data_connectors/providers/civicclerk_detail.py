"""Selected CivicClerk public meeting detail and published-file locators."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from time import monotonic
from urllib.parse import urljoin

from ..engine import source_identity_key
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .contracts import _origin
from .discovery import _api_source
from .native import make_bundle


def _id(value):
    return type(value) is int and 0 < value <= 2147483647


def _api_root(source):
    return _api_source(source).removesuffix('/Events')


def event_documents(source, event, *, legacy=False):
    if (not isinstance(event, dict) or not _id(event.get('id'))
            or event.get('isPublished') != 'Published' or event.get('isDeleted')):
        raise ValueError('The selected Event is not a captured published event.')
    files = event.get('publishedFiles')
    if files is None:
        return []
    if not isinstance(files, list) or len(files) > 10000:
        raise ValueError('Invalid Event published file collection.')
    result = []
    for item in files:
        if not isinstance(item, dict) or not _id(item.get('fileId')):
            continue
        path = f"/v1/Meetings/GetMeetingFileStream(fileId={item['fileId']},plainText=false)"
        result.append({'external_id': str(item['fileId']), 'kind': str(item.get('type') or 'document'),
                       'title': str(item.get('name') or ''),
                       'url': urljoin(source.url if legacy else _api_root(source), path)})
    return result


def declared_documents(source, event, meeting):
    if (not isinstance(event, dict) or not isinstance(meeting, dict) or not _id(event.get('id'))
            or not _id(event.get('agendaId')) or not _id(meeting.get('id')) or meeting['id'] != event['agendaId']
            or event.get('isPublished') != 'Published' or event.get('isDeleted')):
        raise ValueError('The selected published event and meeting do not match.')
    raw_files = meeting.get('publishedFiles')
    if raw_files is None:
        return []
    if not isinstance(raw_files, list) or len(raw_files) > 10000:
        raise ValueError('Invalid published file collection.')
    documents = []
    for raw in raw_files:
        if not isinstance(raw, dict) or not _id(raw.get('fileId')):
            continue
        file_id = raw['fileId']
        documents.append({'external_id': str(file_id), 'kind': str(raw.get('type') or 'document'),
                          'title': str(raw.get('name') or ''),
                          'url': _api_root(source) + f'/Meetings/GetMeetingFileStream(fileId={file_id},plainText=false)',
                          'agenda_id': str(event['agendaId']), 'event_id': str(event['id']),
                          'source_fields': deepcopy(raw)})
    return documents


def fetch_detail(engine, source, namespace, external_id, bounds, context, transport):
    identity = {'provider': source.provider, 'namespace': namespace, 'record_type': 'meeting',
                'external_id': external_id}
    stored = engine.storage.get('records', source_identity_key(identity), scope=context.scope) if engine.storage else None
    record = stored.value if stored else None
    if isinstance(record, dict) and 'record' in record:
        record = record['record']
    original = record.get('original') if isinstance(record, dict) else None
    event = original.get('event') if isinstance(original, dict) and 'meeting' in original else original
    if (not isinstance(event, dict) or not _id(event.get('id')) or str(event['id']) != external_id
            or not _id(event.get('agendaId')) or event.get('isPublished') != 'Published'
            or event.get('isDeleted') or record.get('source_url') != source.url):
        raise ValueError('Detail requires a stored published event with its captured agenda ID and source.')
    if bounds.checkpoint:
        raise ValueError('Selected detail does not accept a checkpoint.')
    coverage = {'scope': 'one selected published event agenda', 'catalog_complete': False,
                'source_complete': False, 'available_text': 'captured metadata only'}
    if operation_cancelled(engine.storage, context):
        return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
    url = _api_root(source) + '/Meetings/' + str(event['agendaId'])
    deadline = monotonic() + bounds.deadline_seconds
    captures = []
    try:
        response = transport.request(url, headers={'Accept': 'application/json'},
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes), deadline_seconds=bounds.deadline_seconds,
            allowed_origins=(_origin(url),), allow_redirects=False)
        if (response.status != 200 or response.url != url or monotonic() >= deadline
                or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)):
            raise ValueError('Detail response exceeded its bounds or changed route.')
        captures.append({'source_url': source.url, 'retrieval_url': url, 'input_format': 'civicclerk-meeting-detail-json',
            'captured_at': datetime.now(timezone.utc).isoformat(), 'sha256': hashlib.sha256(response.content).hexdigest(),
            'byte_length': len(response.content), 'content_type': response.content_type,
            'content_base64': base64.b64encode(response.content).decode('ascii')})
        if operation_cancelled(engine.storage, context):
            return OperationResult('cancelled', {'captures': captures}, coverage=coverage, operation_id=context.operation_id)
        meeting = json.loads(response.content)
        docs = declared_documents(source, event, meeting)
        normalized = deepcopy(record['normalized'])
        normalized['documents'] = docs
        normalized['agenda_id'] = str(event['agendaId'])
        items = meeting.get('items')
        if items is not None and not isinstance(items, list):
            raise ValueError('Invalid meeting item collection.')
        normalized['agenda_items'] = [
            {'external_id': str(item['id']), 'title': item.get('agendaObjectItemName'),
             'source_parent_id': item.get('parentId'), 'source_fields': deepcopy(item)}
            for item in (items or []) if isinstance(item, dict) and _id(item.get('id'))
        ]
        normalized['agenda_items_availability'] = 'supplied' if items is not None else 'absent'
        bundle = make_bundle(source, namespace, response.content, 'civicclerk-meeting-detail-json',
                             [(normalized, {'event': deepcopy(event), 'meeting': meeting,
                               'event_capture_sha256': record.get('capture_sha256')}, 'meeting')])
        bundle['capture']['retrieval_url'] = url
        return OperationResult('partial', bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception:
        return OperationResult('partial' if captures else 'failed', {'captures': captures} if captures else None,
            errors=(Error('provider_detail_unavailable', 'The selected meeting detail could not be verified.',
                          source=source.url),), coverage=coverage, operation_id=context.operation_id)
