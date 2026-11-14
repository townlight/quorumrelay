"""Bounded public Tyler meeting-search candidates, with local exact matching."""
import json
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
from time import monotonic

from ..engine import canonical_hash
from ..models import Bounds, Error, OperationResult
from ..search import _query, search_records
from ..storage import operation_cancelled
from .contracts import PublicTransport, _origin
from .discovery import _checkpoint, _enrich, _resume
from .identification import configured_source, validate_source
from .native import make_bundle
from .tyler_public import api_base
from .tyler_rows import calendar_rows


def native_search(engine, request, content, context, *, transport=None):
    source = configured_source(request['source'])
    namespace = validate_source(source, context)
    if not context.allows('search', namespace):
        return OperationResult('failed', errors=(Error('permission_denied', 'Source namespace is not authorized.'),))
    if content is not None or any(k in request for k in ('records', 'bundle', 'result')):
        raise ValueError('Native search requires a public request, not a saved capture.')
    bounds = Bounds(**request.get('bounds', {}))
    query = _query(request.get('query', {}))
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
    coverage = {'sources': [{**source.public_dict(), 'namespace': namespace}], 'native_search': True,
                'scope': 'provider candidates and exact local metadata matching', 'catalog_complete': False,
                'source_complete': False, 'full_document_text_searched': False}
    if operation_cancelled(engine.storage, context):
        return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
    deadline = monotonic() + bounds.deadline_seconds
    try:
        response = (transport or PublicTransport()).request(url, method='POST', body=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes), deadline_seconds=bounds.deadline_seconds,
            allowed_origins=(_origin(source.url),), allow_redirects=False)
        if operation_cancelled(engine.storage, context):
            return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
        if (response.status != 200 or response.url != url or monotonic() >= deadline
                or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)):
            raise ValueError('Search response exceeded bounds or changed route.')
        data = json.loads(response.content)
        raw_rows, total = data['searchResults'], data['totalElements']
        if (not isinstance(raw_rows, list) or len(raw_rows) > size or type(total) is not int or total < 0):
            raise ValueError('Unexpected Tyler search envelope.')
        rows = calendar_rows(source.url, raw_rows)
        bundle = make_bundle(source, namespace, response.content, 'tyler-public-search-json', rows)
        bundle['capture']['retrieval_url'] = url
        _enrich(bundle, source.provider)
        coverage.update({'pages': 1, 'provider_total': total, 'provider_returned_rows': len(raw_rows),
                         'checkpoint': _checkpoint(binding, [{'page': page + 1}], set())
                         if len(raw_rows) == size and page * size < total else None})
        result = search_records(deepcopy(bundle['records']), query,
            bounds=replace(bounds, checkpoint=None, deadline_seconds=max(.001, deadline - monotonic())),
            sources=coverage['sources'], inherited_coverage=coverage, context=context, storage=engine.storage)
        return OperationResult(result.status, {**result.data, 'bundle': bundle} if result.data else result.data,
                               result.errors, {**result.coverage, **coverage}, context.operation_id)
    except Exception:
        return OperationResult('failed', errors=(Error('provider_search_failed',
            'The public search could not be retrieved or verified.', source=source.url),), coverage=coverage,
            operation_id=context.operation_id)
