"""Synthetic replay of the exact PrimeGov public client document routes."""
import base64
import hashlib
import json
from copy import deepcopy

import pytest
from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors.providers.primegov_documents import resolve_document
from quorumrelay.storage import SQLiteStorage
from test_primegov_native_search import SOURCE, request

ORIGIN = "https://reno.primegov.com"
PDF = b"%PDF-1.7\nsynthetic\n%%EOF"


class Transport:
    def __init__(self, kind, failure=None, context=None):
        self.kind, self.failure, self.context, self.calls = kind, failure, context, []
        self.row = {"info": "Attachment", "type": kind, "id": 42, "meetingId": 91,
                    "meetingDate": "2026-11-12T12:00:00", "title": "Council document",
                    "compileOutputType": 1, "unknown": [False, None]}

    def request(self, url, **options):
        self.calls.append((url, options))
        assert options['allow_redirects'] is False
        if url.endswith('/api/v2/PublicPortal/search'):
            return Response(url, json.dumps([self.row]).encode(), 'application/json')
        if 'GetPublicPdfDownloadUrl' in url or 'getcompiledfiledownloadurl' in url:
            if self.failure == 'redirect':
                return Response(url, b'', 'text/plain', 302)
            target = ORIGIN + '/synthetic-file'
            if self.failure == 'foreign':
                target = 'https://foreign.example/file'
            elif self.failure == 'relative':
                target = '../files/synthetic-file'
            elif self.failure == 'protocol_foreign':
                target = '//foreign.example/file'
            data = {'url': target} if self.failure == 'shape' else target
            response = Response(url, b'{broken' if self.failure == 'invalid_json' else json.dumps(data).encode(), 'application/json')
            if self.context:
                self.context.cancellation.set()
            return response
        if self.failure == 'file':
            return Response(url, b'not-pdf', 'text/html')
        if self.failure == 'direct_redirect':
            return Response(url, b'', 'text/html', 302)
        if self.failure == 'non_pdf':
            return Response(url, b'synthetic document', 'application/octet-stream')
        return Response(url, PDF, 'application/pdf')


def setup(tmp_path, kind, failure=None, context=None):
    transport = Transport(kind, failure, context)
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'data.sqlite'), provider_transport=transport)
    search = owner.execute('search', request())
    assert search.status == 'partial', search.public_dict()
    record = search.data['bundle']['records'][0]
    imported = owner.execute('import_bundle', {'bundle': search.data['bundle'], 'persist': True})
    assert imported.status == 'completed', imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'data.sqlite'), provider_transport=transport)
    return reopened, record, transport


@pytest.mark.parametrize('kind', [1, 2, 3, 4])
def test_selected_search_document_from_scoped_storage(kind, tmp_path):
    owner, record, transport = setup(tmp_path, kind)
    result = owner.fetch_attachment(Source.from_dict(SOURCE), record)
    assert result.status == 'completed', result.public_dict()
    attachment = result.data['attachment']
    assert base64.b64decode(attachment['content_base64']) == PDF
    assert attachment['citation_url'] == ORIGIN + '/Portal/Meeting?meetingId=91'
    assert attachment['resolution']['document_type'] == kind
    assert len(transport.calls) == (3 if kind in {1, 4} else 2)
    expected = {1:'/api/systemitemattachment/GetPublicPdfDownloadUrl/42',
                2:'/api/portal/DownloadSystemItemAttachedDocToBrowser/42',
                3:'/api/meetingSectionAttachment/DownloadPublicPdf?id=42&meetingId=91',
                4:'/api/Meeting/getcompiledfiledownloadurl?compiledFileId=42'}
    assert transport.calls[1][0] == ORIGIN + expected[kind]
    if kind in {1, 4}:
        assert len(result.data['captures']) == 1
        search_bundle = owner.execute('import_bundle', {'bundle': {'schema_version':'2.0.0',
            'records':[record], 'capture':{}, 'captures':result.data['captures']}, 'persist':True})
        assert search_bundle.status == 'completed', search_bundle.public_dict()
        exported = owner.execute('export', {'bundle': search_bundle.data['bundle'], 'format':'zip'})
        destination = create_engine(storage=SQLiteStorage(tmp_path / 'other.sqlite'))
        restored = destination.execute('import_bundle', {'format':'zip', 'persist':True},
            content=base64.b64decode(exported.data['content_base64']))
        assert restored.status == 'completed', restored.public_dict()
        capture = restored.data['bundle']['captures'][0]
        with destination.storage.open_capture(capture['storage_reference'], scope=OperationContext().scope) as stream:
            assert json.loads(stream.read()) == ORIGIN + '/synthetic-file'


@pytest.mark.parametrize('failure', ['shape', 'foreign', 'protocol_foreign', 'invalid_json', 'redirect', 'file'])
def test_resolver_failure_retains_only_verified_capture(tmp_path, failure):
    owner, record, transport = setup(tmp_path, 1, failure)
    result = owner.fetch_attachment(Source.from_dict(SOURCE), record)
    assert result.status == 'partial' and result.data['attachment'] is None
    assert result.data['record']['identity'] == record['identity']
    captures = result.data.get('captures', [])
    assert len(captures) == (0 if failure == 'redirect' else 1)
    if captures:
        content = base64.b64decode(captures[0]['content_base64'])
        assert hashlib.sha256(content).hexdigest() == captures[0]['sha256']
        if failure == 'invalid_json':
            assert content == b'{broken'
        if failure in {'foreign', 'protocol_foreign'}:
            assert b'foreign.example' in content
    assert len(transport.calls) == (3 if failure == 'file' else 2)


def test_request_budget_and_cancellation_preserve_resolver(tmp_path):
    owner, record, transport = setup(tmp_path, 1)
    result = owner.fetch_attachment(Source.from_dict(SOURCE), record, bounds=Bounds(max_pages=1))
    assert result.status == 'partial' and len(transport.calls) == 1
    caller = OperationContext()
    transport.context = caller
    result = owner.fetch_attachment(Source.from_dict(SOURCE), record, context=caller)
    assert result.status == 'cancelled' and len(result.data['captures']) == 1


def test_resolver_parser_limit_stops_before_file_request(tmp_path):
    owner, record, transport = setup(tmp_path, 1)
    result = owner.fetch_attachment(Source.from_dict(SOURCE), record, bounds=Bounds(parser_bytes=8))
    assert result.status == 'partial' and result.data['attachment'] is None
    assert len(transport.calls) == 2 and transport.calls[-1][1]['byte_limit'] == 8
    assert not result.data.get('captures')


def test_deadline_after_resolver_retains_capture_without_file_request(tmp_path, monkeypatch):
    from civic_data_connectors.providers import primegov_documents
    from civic_data_connectors.providers.retrieval import _download_origins

    _, record, transport = setup(tmp_path, 1)
    ticks = iter([0, 0, 10])
    monkeypatch.setattr(primegov_documents, 'monotonic', lambda: next(ticks))
    document = record['normalized']['documents'][0]
    captures = []
    with pytest.raises(ValueError, match='byte/deadline bounds'):
        resolve_document(Source.from_dict(SOURCE), document['url'], record, document, Bounds(),
                         OperationContext(), transport, 10, _download_origins, captures)
    assert len(transport.calls) == 2 and len(captures) == 1
    content = base64.b64decode(captures[0]['content_base64'])
    assert json.loads(content) == ORIGIN + '/synthetic-file'
    assert hashlib.sha256(content).hexdigest() == captures[0]['sha256']


@pytest.mark.parametrize('mutation', ['parent', 'item', 'type', 'html', 'url'])
def test_captured_identity_and_declared_branch_are_bound(tmp_path, mutation):
    from time import monotonic
    from civic_data_connectors.providers.retrieval import _download_origins
    owner, record, transport = setup(tmp_path, 4)
    record = deepcopy(record)
    document = record['normalized']['documents'][0]
    if mutation == 'parent':
        record['identity']['parent']['external_id'] = '999'
    elif mutation == 'item':
        record['identity']['external_id'] = '999'
    elif mutation == 'type':
        record['original']['type'] = 1
    elif mutation == 'html':
        record['original']['compileOutputType'] = 3
    else:
        document['url'] = 'https://foreign.example/file'
    before = len(transport.calls)
    with pytest.raises(ValueError):
        resolve_document(Source.from_dict(SOURCE), document['url'], record, document, Bounds(),
                         OperationContext(), transport, monotonic() + 30, _download_origins, [])
    assert len(transport.calls) == before



def test_overlapping_native_ids_keep_subtypes_and_meeting_parents_distinct(tmp_path):
    from quorumrelay.engine import source_identity_key
    transport = Transport(1)
    rows = [{**transport.row, 'type': kind, 'meetingId': meeting} for meeting in (91, 92)
            for kind in (1, 2, 3, 4)]
    transport.request = lambda url, **kw: Response(url, json.dumps(rows).encode(), 'application/json')
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'identities.sqlite'), provider_transport=transport)
    result = owner.execute('search', request())
    records = result.data['bundle']['records']
    assert len(records) == 8 and len({source_identity_key(r['identity']) for r in records}) == 8
    for row in records:
        raw, identity = row['original'], row['identity']
        assert row['normalized']['documents'][0]['external_id'] == '42'
        assert identity['external_id'] == ('42' if raw['type'] == 2 else f"type:{raw['type']}:42")
        assert identity['parent']['external_id'] == str(raw['meetingId'])
    first = owner.execute('import_bundle', {'bundle': result.data['bundle'], 'persist': True})
    second = owner.execute('import_bundle', {'bundle': result.data['bundle'], 'persist': True})
    assert first.status == second.status == 'completed'
    assert all(change['outcome'] == 'unchanged' for change in second.data['changes'])
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'identities.sqlite'))
    assert all(reopened.storage.get('records', source_identity_key(row['identity']), scope=OperationContext().scope)
               for row in records)


def test_explicit_cross_origin_and_cumulative_limits(tmp_path):
    owner, record, transport = setup(tmp_path, 1, 'foreign')
    result = owner.fetch_attachment(Source.from_dict(SOURCE), record)
    assert result.status == 'partial' and len(transport.calls) == 2
    source = Source.from_dict({**SOURCE, 'options': {'download_origins': ['https://foreign.example']}})
    result = owner.fetch_attachment(source, record)
    assert result.status == 'completed', result.public_dict()
    assert transport.calls[-1][0] == 'https://foreign.example/file'
    assert transport.calls[-1][1]['allowed_origins'] == (ORIGIN, 'https://foreign.example')
    transport.failure = None
    before = len(transport.calls)
    result = owner.fetch_attachment(source, record, bounds=Bounds(transfer_bytes=50))
    assert result.status == 'partial' and len(transport.calls) == before + 2
    assert result.data['captures']
    assert transport.calls[-1][1]['byte_limit'] < 50


def test_direct_pdf_redirect_and_compiled_nonpdf(tmp_path):
    owner, record, transport = setup(tmp_path, 3, 'direct_redirect')
    assert owner.fetch_attachment(Source.from_dict(SOURCE), record).status == 'partial'
    owner, record, transport = setup(tmp_path / 'compiled', 4, 'non_pdf')
    result = owner.fetch_attachment(Source.from_dict(SOURCE), record)
    assert result.status == 'completed' and base64.b64decode(result.data['attachment']['content_base64']) == b'synthetic document'



def test_compiled_html_and_unknown_output_remain_unmapped(tmp_path):
    from quorumrelay.engine import source_identity_key

    transport = Transport(4)
    rows = [{**transport.row, 'id': 100, 'compileOutputType': 3},
            {**transport.row, 'id': 101, 'compileOutputType': None},
            {**transport.row, 'id': 102, 'compileOutputType': True},
            {**transport.row, 'id': 100, 'type': 2}]
    transport.request = lambda url, **kw: Response(url, json.dumps(rows).encode(), 'application/json')
    result = create_engine(storage=SQLiteStorage(tmp_path / 'unknown.sqlite'), provider_transport=transport).execute(
        'search', request())
    assert result.status == 'partial'
    records = result.data['bundle']['records']
    assert len({source_identity_key(row['identity']) for row in records}) == 4
    compiled = [row for row in records if row['original']['type'] == 4]
    assert all('documents' not in row['normalized'] for row in compiled)
    assert all(row['identity']['external_id'] == f"type:4:{row['original']['id']}" for row in compiled)


def test_type_two_preexisting_locator_still_resolves(tmp_path):
    from time import monotonic
    from civic_data_connectors.providers.retrieval import _download_origins
    owner, record, transport = setup(tmp_path, 2)
    record = deepcopy(record)
    document = record['normalized']['documents'][0]
    document.pop('citation_url')
    response, _ = resolve_document(Source.from_dict(SOURCE), document['url'], record, document,
                                   Bounds(), OperationContext(), transport, monotonic() + 30, _download_origins, [])
    assert response.content == PDF


def test_relative_resolver_target_uses_public_source_url(tmp_path):
    owner, record, transport = setup(tmp_path, 1, 'relative')
    result = owner.fetch_attachment(Source.from_dict(SOURCE), record)
    assert result.status == 'completed', result.public_dict()
    assert transport.calls[-1][0] == ORIGIN + '/files/synthetic-file'


def test_unknown_composite_type_is_retained_without_locator(tmp_path):
    transport = Transport(1)
    rows = [{**transport.row, 'type': ['unknown']}, {**transport.row, 'id': 43, 'type': {'x': 1}}]
    transport.request = lambda url, **kw: Response(url, json.dumps(rows).encode(), 'application/json')
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'unknown.sqlite'), provider_transport=transport)
    result = owner.execute('search', request())
    assert result.status == 'partial', result.public_dict()
    records = result.data['bundle']['records']
    assert len(records) == 2 and [r['original']['type'] for r in records] == [['unknown'], {'x': 1}]
    assert all('documents' not in row['normalized'] for row in records)


@pytest.mark.parametrize('mime,body', [('text/html', b'not a file'),
                                      ('application/octet-stream', b'  <!doctype html><html>')])
def test_compiled_html_response_is_partial_and_retains_resolver(tmp_path, mime, body):
    owner, record, transport = setup(tmp_path, 4)
    original_request = transport.request

    def request_with_html(url, **options):
        if url.endswith('/synthetic-file'):
            transport.calls.append((url, options))
            return Response(url, body, mime)
        return original_request(url, **options)

    transport.request = request_with_html
    result = owner.fetch_attachment(Source.from_dict(SOURCE), record)
    assert result.status == 'partial' and result.data['attachment'] is None
    assert len(result.data['captures']) == 1
