"""Bounded public Tyler meeting-search candidates, with local exact matching."""
import json
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime
from time import monotonic

from ..engine import canonical_hash
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..search import extract_text_segments
from ..storage import operation_cancelled
from .contracts import PublicTransport, _origin
from .discovery import _checkpoint, _enrich, _resume
from .identification import configured_source, validate_source
from .native import make_bundle
from .tyler_public import api_base
from .tyler_rows import calendar_rows


def _item_bundle(source, namespace, content, raw_rows, bounds, context):
    rows, seen = [], set()
    for raw in raw_rows:
        if (not isinstance(raw, dict) or type(raw.get('agendaItemId')) is not int
                or not 0 < raw['agendaItemId'] <= 2147483647 or raw['agendaItemId'] in seen
                or any(not isinstance(raw.get(k), str) for k in
                       ('itemTitle', 'description', 'outcomeDescription', 'meetingName', 'meetingDate', 'meetingType'))
                or raw.get('votingOutcome') is not None and not isinstance(raw['votingOutcome'], str)):
            raise ValueError('The agenda-item search row lacks an unambiguous native identity or declared fields.')
        seen.add(raw['agendaItemId'])
        # The renderer consumes rich text. Keep only supplied visible text for
        # local matching; original markup and unknown fields stay in the capture.
        text = {}
        for key in ('itemTitle', 'description', 'outcomeDescription'):
            parsed = extract_text_segments(raw[key].encode(), media_type='text/html', citation_url=source.url,
                                           bounds=bounds, context=context)
            if parsed.status != 'completed':
                raise ValueError('The supplied agenda-item text could not be parsed within bounds.')
            text[key] = ' '.join(s['text'] for s in parsed.data['segments']).strip()
        if not text['itemTitle']:
            raise ValueError('A nonempty supplied item title is required.')
        try:
            meeting_date = datetime.fromisoformat(raw['meetingDate'].replace('Z', '+00:00')).date().isoformat()
        except ValueError:
            meeting_date = None
        normalized = {'external_id': str(raw['agendaItemId']), 'title': text['itemTitle'],
                      'description': text['description'], 'outcome_description': text['outcomeDescription'],
                      'voting_outcome': raw.get('votingOutcome'), 'meeting_name': raw['meetingName'],
                      'meeting_date': meeting_date, 'source_meeting_date': raw['meetingDate'],
                      'meeting_type': raw['meetingType'], 'meeting_external_id': None,
                      'meeting_identity_status': 'not_supplied_no_name_date_join',
                      'time_zone_status': 'unknown', 'url': source.url, 'documents': []}
        rows.append((normalized, raw, 'agenda_item'))
    bundle = make_bundle(source, namespace, content, 'tyler-public-agenda-item-search-json', rows)
    for record in bundle['records']:
        record['text'] = [{'field': key, 'text': record['normalized'][key], 'citation_url': source.url,
                           'completeness': 'partial', 'provenance': {
                               'method': 'tyler_public_agenda_item_search_supplied_text',
                               'scope': 'one_returned_item', 'capture_sha256': bundle['capture']['sha256']}}
                          for key in ('description', 'outcome_description') if record['normalized'][key]]
    return bundle


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request['source'])
    namespace = validate_source(source, context)
    if not context.allows('search', namespace):
        return OperationResult('failed', errors=(Error('permission_denied', 'Source namespace is not authorized.'),))
    if content is not None or any(k in request for k in ('records', 'bundle', 'result')):
        raise ValueError('Native search requires a public request, not a saved capture.')
    bounds = Bounds(**request.get('bounds', {}))
    query = _query(request.get('query', {}))
    item_mode = set(query.record_types) == {'agenda_item'}
    if query.record_types and not item_mode and set(query.record_types) != {'meeting'}:
        raise ValueError('Choose meetings or agenda items separately; mixed or other Tyler search types are not mapped.')
    query = replace(query, date_from=query.date_from or bounds.date_from, date_to=query.date_to or bounds.date_to)
    expressions = [*query.terms, *query.phrases]
    if not expressions or not query.date_from or not query.date_to or source.body or query.body:
        raise ValueError('Tyler search requires a term and date bounds without a body filter.')
    if len(expressions[0].encode()) > min(1024, bounds.parser_bytes):
        raise ValueError('The search expression exceeds its bound.')
    types = source.options.get('meeting_type_ids', [-1])
    if (not isinstance(types, list) or len(types) > 100
            or any(type(i) is not int or i < -1 or i > 2147483647 for i in types)):
        raise ValueError('Invalid meeting type selection.')
    if item_mode and types and (len(set(types)) != len(types) or types != [-1] and any(i <= 0 for i in types)):
        raise ValueError('Item search requires all-types or distinct positive native meeting types.')
    size = min(20, query.limit, bounds.max_records)
    binding = canonical_hash({'source': source.public_dict(), 'query': asdict(query), 'scope': context.scope, 'page_size': size,
                              'contract': 'tyler-public-search/v2-preserve-status'})
    queue, seen = _resume(bounds.checkpoint, binding) if bounds.checkpoint else ([{'page': 1}], set())
    if (len(queue) != 1 or set(queue[0]) != {'page'} or seen or type(queue[0]['page']) is not int
            or not 1 <= queue[0]['page'] <= 10000):
        raise ValueError('Invalid Tyler search checkpoint.')
    page = queue[0]['page']
    payload = {'lastPage': False, 'searchKeyword': expressions[0], 'pageNo': page, 'pageSize': size,
               'filter': {'startDate': date.fromisoformat(query.date_from).strftime('%m/%d/%Y'),
                          'endDate': date.fromisoformat(query.date_to).strftime('%m/%d/%Y'),
                          'meetingTypeIds': types, 'agendaPosted': False, 'minutesPosted': False,
                          'videoPosted': False}}
    url = api_base(source) + 'meetingCalendarSearch/search'
    if item_mode:
        payload = {'searchKeyword': expressions[0], 'pageNo': page, 'pageSize': size,
                   'startDate': payload['filter']['startDate'], 'endDate': payload['filter']['endDate'],
                   'meetingTypeIds': types or [-1], 'votingOutcomes': []}
        url = api_base(source) + 'meetingCalendarSearch/agenda-items/search'
    coverage = {'sources': [{**source.public_dict(), 'namespace': namespace}], 'native_search': True,
                'scope': 'provider candidates and exact local metadata matching', 'catalog_complete': False,
                'source_complete': False, 'full_document_text_searched': False}
    if operation_cancelled(engine.storage, context):
        return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
    deadline = monotonic() + bounds.deadline_seconds
    try:
        feature_capture = None
        remaining_bytes = min(bounds.parser_bytes, bounds.transfer_bytes)
        if item_mode:
            flag_url = api_base(source) + 'v1/harness/feature-flags'
            flags = (transport or PublicTransport()).request(flag_url,
                headers={'Accept': 'application/json'}, byte_limit=min(65536, remaining_bytes),
                deadline_seconds=max(.001, deadline - monotonic()),
                allowed_origins=(_origin(source.url),), allow_redirects=False)
            if operation_cancelled(engine.storage, context):
                return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
            if (flags.status != 200 or flags.url != flag_url or monotonic() >= deadline
                    or len(flags.content) > min(65536, remaining_bytes)):
                raise ValueError('The public agenda-item feature response failed its bounds.')
            flag_bundle = make_bundle(source, namespace, flags.content, 'tyler-public-feature-flags-json', [])
            flag_bundle['capture']['retrieval_url'] = flag_url
            flag_data = json.loads(flags.content)
            if not isinstance(flag_data, dict) or flag_data.get('agenda-item-outcome') is not True:
                return OperationResult('partial', {'bundle': flag_bundle}, errors=(Error('provider_feature_not_enabled',
                    'The tenant did not explicitly enable public agenda-item outcomes/search.', source=source.url),),
                    coverage={**coverage, 'failures': ['public_agenda_item_feature_not_enabled'],
                              'feature_flag': flag_data.get('agenda-item-outcome') if isinstance(flag_data, dict) else None},
                    operation_id=context.operation_id)
            feature_capture = flag_bundle['capture']
            remaining_bytes = min(bounds.parser_bytes, bounds.transfer_bytes - len(flags.content))
            if remaining_bytes <= 0:
                raise ValueError('The feature response exhausted the search transfer budget.')
        response = (transport or PublicTransport()).request(url, method='POST', body=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            byte_limit=remaining_bytes, deadline_seconds=max(.001, deadline - monotonic()),
            allowed_origins=(_origin(source.url),), allow_redirects=False)
        if operation_cancelled(engine.storage, context):
            return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
        if (response.status != 200 or response.url != url or monotonic() >= deadline
                or len(response.content) > remaining_bytes):
            raise ValueError('Search response exceeded bounds or changed route.')
        data = json.loads(response.content)
        raw_rows, total = data['searchResults'], data['totalElements']
        if (not isinstance(raw_rows, list) or len(raw_rows) > size or type(total) is not int or total < 0):
            raise ValueError('Unexpected Tyler search envelope.')
        if item_mode:
            if raw_rows and (page - 1) * size + len(raw_rows) > total:
                raise ValueError('The item search count contradicts the returned page.')
            bundle = _item_bundle(source, namespace, response.content, raw_rows, bounds, context)
        else:
            rows = calendar_rows(source.url, raw_rows)
            bundle = make_bundle(source, namespace, response.content, 'tyler-public-search-json', rows)
        bundle['capture']['retrieval_url'] = url
        if feature_capture is not None:
            bundle['captures'] = [feature_capture, bundle['capture']]
        if not item_mode:
            _enrich(bundle, source.provider)
        else:
            coverage.update(scope='provider agenda-item candidates and exact local supplied-text matching',
                            meeting_identity='not_supplied_no_name_date_join',
                            record_type='agenda_item', full_document_text_searched=False)
        coverage.update({'pages': 1, 'provider_total': total, 'provider_returned_rows': len(raw_rows),
                         'checkpoint': _checkpoint(binding, [{'page': page + 1}], set())
                         if len(raw_rows) == size and page * size < total else None})
        result = search_records(deepcopy(bundle['records']), query,
            bounds=replace(bounds, checkpoint=None, deadline_seconds=max(.001, deadline - monotonic())),
            sources=coverage['sources'], inherited_coverage=coverage, context=context, storage=engine.storage)
        return OperationResult(result.status, {**result.data, 'bundle': bundle} if result.data else result.data,
                               result.errors, {**result.coverage, **coverage}, context.operation_id)
    except Exception:
        if operation_cancelled(engine.storage, context):
            return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
        return OperationResult('failed', errors=(Error('provider_search_failed',
            'The public search could not be retrieved or verified.', source=source.url),), coverage=coverage,
            operation_id=context.operation_id)
