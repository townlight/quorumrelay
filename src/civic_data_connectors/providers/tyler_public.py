"""Selected public calendar fields evidenced by the Tyler client."""
from urllib.parse import urlsplit

from .contracts import _origin
from .identification import validate_url


def api_base(source):
    import re

    base = source.options.get('calendar_api_base')
    if not isinstance(base, str):
        raise ValueError('Configure the observed calendar API base.')
    validate_url(base)
    target, original = urlsplit(base), urlsplit(source.url)
    if (target.scheme != 'https' or target.hostname != original.hostname
            or not target.hostname.endswith('.meetingmanager.tylerapp.com')
            or re.fullmatch(r'/tylermmcalendar[A-Za-z0-9]+/?', target.path) is None
            or target.query or target.fragment):
        raise ValueError('The calendar API base does not match the configured Tyler tenant.')
    return _origin(base) + target.path.rstrip('/') + '/'


def documents(source, raw):
    base = api_base(source)
    result = []
    for field, status, kind, route in (('meetingAgendaId', 'agendaStatus', 'agenda', 'Agenda'),
                                       ('minutesId', 'minutesStatus', 'minutes', 'Minutes')):
        value = raw.get(field)
        if type(value) is int and 0 < value <= 2147483647 and raw.get(status) == 5:
            result.append({'kind': kind, 'external_id': str(value), 'url': f'{base}meetingInformation/{route}/false/{value}',
                           'availability': 'supplied_public_document_locator'})
    return result


def fetch_detail(engine, source, namespace, external_id, bounds, context, transport):
    import json
    from time import monotonic

    from ..engine import source_identity_key
    from ..models import Error, OperationResult
    from ..storage import operation_cancelled
    from .discovery import _enrich
    from .native import make_bundle
    from .tyler_rows import meeting_row

    identity = {'provider': source.provider, 'namespace': namespace, 'record_type': 'meeting',
                'external_id': external_id}
    stored = engine.storage.get('records', source_identity_key(identity), scope=context.scope) if engine.storage else None
    record = stored.value if stored else None
    if isinstance(record, dict) and 'record' in record:
        record = record['record']
    raw = record.get('original', {}) if isinstance(record, dict) else {}
    meeting, recurring = raw.get('meetingId'), raw.get('recurringId')
    if (not isinstance(external_id, str) or raw.get('id') != external_id or record.get('source_url') != source.url
            or any(type(v) is not int or not 0 < v <= 2147483647 for v in (meeting, recurring))):
        raise ValueError('Detail requires a captured meeting and its numeric meeting and recurring IDs.')
    if bounds.checkpoint:
        raise ValueError('Selected detail does not accept a checkpoint.')
    coverage = {'scope': 'one selected public meeting detail', 'catalog_complete': False, 'source_complete': False}
    if operation_cancelled(engine.storage, context):
        return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
    url = api_base(source) + 'meetingInformation/getMeeting'
    deadline = monotonic() + bounds.deadline_seconds
    try:
        response = transport.request(url, method='POST', body=json.dumps(
            {'meetingId': meeting, 'recurringId': recurring, 'activity': 'View'}).encode(),
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes), deadline_seconds=bounds.deadline_seconds,
            allowed_origins=(_origin(source.url),), allow_redirects=False)
        if operation_cancelled(engine.storage, context):
            return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
        if (response.status != 200 or response.url != url or monotonic() >= deadline
                or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)):
            raise ValueError('Detail response exceeded its bounds.')
        detail = json.loads(response.content)
        if (not isinstance(detail, dict) or detail.get('id') != external_id
                or detail.get('meetingId') != meeting or detail.get('recurringId') != recurring):
            raise ValueError('Detail does not match the captured meeting.')
        mapped = meeting_row(source.url, detail)
        if mapped is None:
            raise ValueError('Detail was not a visible mapped meeting.')
        bundle = make_bundle(source, namespace, response.content, 'tyler-public-detail-json',
                             [(mapped[0], detail, mapped[1])])
        bundle['capture']['retrieval_url'] = url
        _enrich(bundle, source.provider)
        return OperationResult('partial', bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception:
        return OperationResult('failed', errors=(Error('provider_detail_unavailable',
            'The selected public detail could not be retrieved or validated.', source=source.url),),
            coverage=coverage, operation_id=context.operation_id)
