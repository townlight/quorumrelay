'''Synthetic Laserfiche transport tests for ambiguous import timeouts.

No live writes. These tests exercise the documented adapter routes only.
'''

import base64
import json
from urllib.parse import urlsplit

from civic_data_connectors import Engine, OperationContext
from civic_data_connectors.storage import SQLiteStorage
from civic_data_connectors.write_adapters import default_adapters
from civic_data_connectors.write_transport import WriteResponse
from civic_data_connectors.writes import register


ETAG = chr(34) + 'etag-1' + chr(34)


class LaserficheNetwork:
    mock = True

    def __init__(self, *, fail_final_import=False):
        self.fail_final_import = fail_final_import
        self.calls = []
        self.folder_import_calls = 0
        self.server_created_entries = 0
        self.create_urls_calls = 0
        self.signed_put_calls = 0
        self.final_import_calls = 0
        self.uploaded_parts = []

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        parsed = urlsplit(url)
        self.calls.append((method, parsed.hostname, parsed.path, parsed.query))
        assert deadline_seconds > 0
        if parsed.hostname == 'uploads.example.test':
            assert method == 'PUT'
            self.signed_put_calls += 1
            self.uploaded_parts.append(body)
            return WriteResponse(200, b'', headers={'etag': ETAG})
        assert parsed.hostname == 'api.laserfiche.com'
        if method == 'POST' and parsed.path.endswith('/Entries/CreateMultipartUploadUrls'):
            self.create_urls_calls += 1
            request = json.loads(body)
            assert request['numberOfParts'] == 1
            assert request['startingPartNumber'] == 1
            return WriteResponse(200, json.dumps({
                'uploadId': 'upload-1',
                'urls': ['https://uploads.example.test/part-1'],
            }).encode())
        if method == 'POST' and parsed.path.endswith('/Folder/ImportUploadedParts'):
            self.final_import_calls += 1
            if self.fail_final_import:
                return WriteResponse(500, b'unknown ImportUploadedParts timeout')
            request = json.loads(body)
            assert request['uploadId'] == 'upload-1'
            assert request['partETags'] == [ETAG]
            return WriteResponse(200, json.dumps({'taskId': 'task-1'}).encode())
        if method == 'POST' and parsed.path.endswith('/Folder/Import'):
            self.folder_import_calls += 1
            self.server_created_entries += 1
            return WriteResponse(500, b'unknown Import timed out after creating entry')
        raise AssertionError(f'unexpected synthetic Laserfiche request: {method} {url}')


def _context():
    return OperationContext(
        principal='synthetic-actor',
        client_id='fixture-sdk',
        tenant='fixture-city',
        authorization=frozenset({'write:plan', 'write:commit'}),
        credentials={
            'laserfiche': {
                'namespace': 'repo1',
                'token': 'synthetic-secret',
                'permissions': ['document:create', 'document_large:create'],
                'meeting_ids': ['meeting-1'],
                'parent_ids': ['folder-1'],
                'allowed_repositories': ['repo1'],
            },
        },
    )


def _setup(tmp_path, network):
    store = SQLiteStorage(tmp_path / 'writes.sqlite')
    engine = Engine(storage=store)
    register(engine, default_adapters(network))
    return engine, _context()


def _source():
    return {
        'provider': 'laserfiche',
        'url': 'https://api.laserfiche.com/repository/v2/Repositories/repo1',
        'namespace': 'repo1',
    }


def _simple_request(*, pdf_options=None):
    fields = {'name': 'agenda.pdf'}
    if pdf_options is not None:
        fields['pdfOptions'] = pdf_options
    return {
        'source': _source(),
        'changes': [{
            'key': 'document-1',
            'entity': 'document',
            'operation': 'create',
            'parent_id': 'folder-1',
            'meeting_id': 'meeting-1',
            'fields': fields,
        }],
    }


def _file_part():
    return {
        'part': 'file',
        'filename': 'agenda.pdf',
        'content_type': 'application/pdf',
        'content_base64': base64.b64encode(b'%PDF-1.4 synthetic').decode(),
    }


def _large_request():
    return {
        'source': _source(),
        'changes': [{
            'key': 'large-document-1',
            'entity': 'document_large',
            'operation': 'create',
            'parent_id': 'folder-1',
            'meeting_id': 'meeting-1',
            'fields': {'name': 'agenda.pdf'},
            'files': [_file_part()],
        }],
    }


def _plan(engine, context, request):
    result = engine.execute('plan_write', request, context=context)
    assert result.status == 'completed', result.public_dict()
    return {'plan_id': result.data['plan_id'], 'plan_hash': result.data['plan_hash']}


def test_folder_import_500_after_create_without_entry_id_never_retried(tmp_path):
    network = LaserficheNetwork()
    engine, context = _setup(tmp_path, network)
    approval = _plan(engine, context, _simple_request())

    first = engine.execute('commit_write', approval, context=context)
    assert first.status == 'partial'
    item = first.data['items'][0]
    assert item['state'] == 'uncertain'
    assert item.get('resource_id') is None
    assert network.folder_import_calls == 1
    assert network.server_created_entries == 1

    restarted, context = _setup(tmp_path, network)
    second = restarted.execute('commit_write', approval, context=context)
    assert second.status == 'partial'
    assert second.data['items'][0]['state'] == 'uncertain'
    assert network.folder_import_calls == 1
    assert network.server_created_entries == 1


def test_import_uploaded_parts_500_without_task_id_never_resends_parts(tmp_path):
    network = LaserficheNetwork(fail_final_import=True)
    engine, context = _setup(tmp_path, network)
    approval = _plan(engine, context, _large_request())

    first = engine.execute('commit_write', approval, context=context)
    assert first.status == 'partial'
    item = first.data['items'][0]
    assert item['state'] == 'uncertain'
    assert item['upload_id'] == 'upload-1'
    assert item['part_etags'] == [ETAG]
    assert 'task_id' not in item
    assert network.create_urls_calls == 1
    assert network.signed_put_calls == 1
    assert network.final_import_calls == 1
    assert network.folder_import_calls == 0

    restarted, context = _setup(tmp_path, network)
    second = restarted.execute('commit_write', approval, context=context)
    assert second.status == 'partial'
    assert second.data['items'][0]['state'] == 'uncertain'
    assert network.create_urls_calls == 1
    assert network.signed_put_calls == 1
    assert network.final_import_calls == 1


def test_document_large_uses_uploaded_parts_route_and_retains_task_reference(tmp_path):
    network = LaserficheNetwork()
    engine, context = _setup(tmp_path, network)
    approval = _plan(engine, context, _large_request())

    result = engine.execute('commit_write', approval, context=context)
    assert result.status == 'partial'
    item = result.data['items'][0]
    assert item['state'] == 'pending'
    assert item['task_id'] == 'task-1'
    assert network.create_urls_calls == 1
    assert network.signed_put_calls == 1
    assert network.final_import_calls == 1
    assert network.folder_import_calls == 0


def test_pdf_options_accepts_documented_fields_and_rejects_unknown_ocr(tmp_path):
    network = LaserficheNetwork()
    engine, context = _setup(tmp_path, network)
    documented = {
        'generateText': True,
        'generatePages': True,
        'generatePagesImageType': 'Standard',
        'keepPdfAfterImport': True,
    }
    valid = engine.execute('plan_write', _simple_request(pdf_options=documented), context=context)
    assert valid.status == 'completed', valid.public_dict()

    invalid = engine.execute(
        'plan_write',
        _simple_request(pdf_options={**documented, 'ocr': True}),
        context=context,
    )
    assert invalid.status == 'failed'
    assert invalid.errors[0].code == 'unsupported_field'
