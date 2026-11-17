"""Selected public agenda outlines from third-party-archived BoardDocs responses."""

from copy import deepcopy
from time import monotonic
from urllib.parse import urlencode

from ..engine import source_identity_key
from ..models import Error, OperationResult
from ..storage import operation_cancelled
from .boarddocs_public import _configured_source, _MEETING_ID
from .escribe_detail import Page
from .native import make_bundle

FORMAT = 'boarddocs-selected-agenda-html'


def outline_bundle(source, namespace, content, meeting, record_type, max_records):
    page = Page()
    page.feed(content.decode('utf-8-sig'))
    parts, site, _ = _configured_source(source)
    base = f'{parts.scheme}://{parts.netloc}/{site}/Board.nsf/goto?open&id='
    rows, seen = [], set()
    for node in page.root.walk():
        kind = ('agenda_section' if node.tag == 'dt' and 'category' in node.classes()
                else 'agenda_item' if node.tag == 'li' and 'item' in node.classes() else None)
        if kind is None:
            continue
        ancestor, excluded = node, False
        while ancestor is not None:
            if (ancestor.tag in {'script', 'style', 'template'}
                    or any(marker in value.casefold() for value in ancestor.classes()
                           for marker in ('private', 'admin', 'executive'))):
                excluded = True
            ancestor = ancestor.parent
        if excluded:
            continue
        if kind == 'agenda_item' and 'public' not in node.classes():
            continue
        identity = node.attrs.get('unique')
        if (not isinstance(identity, str) or not _MEETING_ID.fullmatch(identity)
                or node.attrs.get('id') != identity or identity in seen):
            raise ValueError('The selected agenda has missing, conflicting or duplicate native identities.')
        seen.add(identity)
        title_class = 'category-name' if kind == 'agenda_section' else 'title'
        titles = [n for n in node.walk() if title_class in n.classes()]
        if len(titles) != 1 or not titles[0].text():
            raise ValueError('The selected agenda omitted or repeated its visible title.')
        outlines = [n.text() for n in node.walk() if 'order' in n.classes()]
        normalized = {'external_id': identity, 'title': titles[0].text(), 'url': base + identity,
            'meeting_external_id': meeting, 'source_outline': outlines[0] if len(outlines) == 1 else None,
            'source_unid': node.attrs.get('unid'), 'source_order_within_category': node.attrs.get('orderwithincategory'),
            'parent_section_availability': 'not_asserted_by_native_ID_in_response',
            'content_availability': 'outline_metadata_only', 'documents': [], 'recordings': [],
            'documents_availability': 'separate_public_files_response_not_supplied'}
        rows.append((normalized, {'attributes': deepcopy(node.attrs), 'rendered_title': titles[0].text()}, kind))
    if not rows:
        raise ValueError('The selected response contains no recognized public agenda outline.')
    selected = [r for r in rows if r[2] == record_type]
    bundle = make_bundle(source, namespace, content, FORMAT, selected[:max_records])
    parent = {'provider': source.provider, 'namespace': namespace, 'record_type': 'meeting',
              'external_id': meeting, 'parent': None}
    for record in bundle['records']:
        record['identity']['parent'] = deepcopy(parent)
        record['relationships'].append({'relation': 'meeting', 'identity': deepcopy(parent)})
    bundle['extensions']['boarddocs_outline'] = {
        'matching_records_in_response': len(selected), 'record_limit_reached': len(selected) > max_records,
        'meeting_binding': 'selected_stored_identity_and_request_context_not_response_asserted',
        'section_membership': 'not_inferred_from_adjacent_heading_or_outline_number'}
    bundle['capture']['content_type_hint'] = 'text/html'
    return bundle


def fetch_related(engine, source, namespace, request, bounds, context, transport):
    parts, site, committee = _configured_source(source)
    meeting, kind = request.get('parent_id'), request.get('record_type')
    if (not isinstance(meeting, str) or not _MEETING_ID.fullmatch(meeting)
            or kind not in {'agenda_item', 'agenda_section'} or request.get('external_id') is not None
            or bounds.checkpoint or bounds.date_from or bounds.date_to):
        raise ValueError('Select a stored native meeting and agenda_item/agenda_section without a checkpoint/date filter.')
    parent = {'provider': source.provider, 'namespace': namespace, 'record_type': 'meeting', 'external_id': meeting}
    stored = engine.storage.get('records', source_identity_key(parent), scope=context.scope) if engine.storage else None
    record = stored.value if stored else None
    if isinstance(record, dict) and 'record' in record:
        record = record['record']
    original = record.get('original') if isinstance(record, dict) else None
    root = f'{parts.scheme}://{parts.netloc}/{site}/Board.nsf'
    if isinstance(original, dict) and 'listing_row' in original:
        original = original['listing_row']
    if (not isinstance(original, dict) or record.get('source_url') != source.url
            or not (str(original.get('unique')) == meeting
                    or original.get('native_citation') == root + '/goto?open&id=' + meeting)):
        raise ValueError('The selected meeting is not captured in this caller scope and configured source.')
    coverage = {'scope': 'one selected meeting public agenda outline', 'catalog_complete': False,
                'collection_complete': False, 'available_text': 'outline titles only',
                'contract': 'third_party_archived_response_not_official_vendor_acceptance'}
    if operation_cancelled(engine.storage, context):
        return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
    url = root + '/BD-GetAgenda?open'
    deadline = monotonic() + bounds.deadline_seconds
    retained = None
    try:
        response = transport.request(url, method='POST',
            body=urlencode({'id': meeting, 'current_committee_id': committee}).encode('ascii'),
            headers={'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'text/html'},
            allowed_origins=(f'{parts.scheme}://{parts.netloc}',), allow_redirects=False,
            byte_limit=min(bounds.parser_bytes, bounds.transfer_bytes), deadline_seconds=bounds.deadline_seconds)
        if (response.status != 200 or response.url != url
                or len(response.content) > min(bounds.parser_bytes, bounds.transfer_bytes)):
            raise ValueError('The selected outline was denied, redirected or exceeded byte bounds.')
        retained = make_bundle(source, namespace, response.content, FORMAT, [])
        retained['capture']['retrieval_url'] = url
        if operation_cancelled(engine.storage, context):
            return OperationResult('cancelled', retained, coverage=coverage, operation_id=context.operation_id)
        if monotonic() >= deadline:
            raise ValueError('The selected outline exceeded its deadline.')
        bundle = outline_bundle(source, namespace, response.content, meeting, kind, bounds.max_records)
        bundle['capture']['retrieval_url'] = url
        coverage.update(bundle['extensions']['boarddocs_outline'])
        return OperationResult('partial', bundle, coverage=coverage, operation_id=context.operation_id)
    except Exception:
        return OperationResult('partial' if retained else 'failed', retained,
            errors=(Error('provider_outline_unavailable', 'The selected agenda outline could not be verified.',
                          source=source.url),), coverage=coverage, operation_id=context.operation_id)
