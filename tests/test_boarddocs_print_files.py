"""Archived native public file locators; transfers are synthetic, never live."""

import base64
from copy import deepcopy
from pathlib import Path

import pytest

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.providers.boarddocs_public import detail_bundle, declared_documents
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.identification import validate_source
from civic_data_connectors.interchange import read_bundle

SOURCE = Source('boarddocs', 'https://go.boarddocs.com/vsba/fairfax/Board.nsf/Public',
                options={'boarddocs_committee_id': 'explicit-synthetic-committee'})
RAW = (Path(__file__).parent / 'fixtures/boarddocs-public/fairfax-print-20221115.html').read_bytes()
PDF = b'%PDF-1.7\nsynthetic-file-bytes-not-the-live-original\n%%EOF'


class Network:
    def __init__(self):
        self.calls = []
        self.status, self.body, self.changed, self.cancel = 200, PDF, False, None

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs['allow_redirects'] is False
        assert kwargs['allowed_origins'] == ('https://go.boarddocs.com',)
        if self.cancel:
            self.cancel.cancellation.set()
        return Response(url + '?changed' if self.changed else url, self.body, 'application/pdf', self.status)


def prepared(tmp_path):
    # The print fragment does not assert a meeting ID. This identity is explicit
    # synthetic selected-request context, never inferred from its title/date.
    bundle = detail_bundle(SOURCE, validate_source(SOURCE, OperationContext()), RAW,
                           'SYNTHETICSELECTED', {'original': {'unique': 'SYNTHETICSELECTED'}})
    network = Network()
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'files.sqlite'), provider_transport=network)
    assert engine.execute('import_bundle', {'bundle': bundle, 'persist': True}).status == 'completed'
    return engine, network, bundle


def test_four_native_public_files_preserved_reopened_downloaded_and_exported(tmp_path):
    engine, network, bundle = prepared(tmp_path)
    record = bundle['records'][0]
    docs = record['normalized']['documents']
    assert len(docs) == 4
    assert [d['external_id'] for d in docs] == ['CL73GZ06DDE9', 'CL6VH980AD19', 'CL6VHD80B0DD', 'CL6VJP80DAE7']
    assert all('/files/' + d['external_id'] + '/$file/' in d['url'] for d in docs)
    assert all('CJUTAP70CF8F' not in d['url'] for d in docs)  # Inline body link is not a public-file marker.
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'files.sqlite'), provider_transport=network)
    result = reopened.fetch_attachment(SOURCE, record)
    assert result.status == 'completed', result.public_dict()
    assert network.calls[0][0] == docs[0]['url']
    assert base64.b64decode(result.data['attachment']['content_base64']) == PDF
    archive = reopened.execute('export', {'bundle': bundle, 'format': 'zip'})
    restored = read_bundle(base64.b64decode(archive.data['content_base64']), format='zip')
    assert restored == bundle
    assert base64.b64decode(restored['capture']['content_base64']) == RAW


@pytest.mark.parametrize('fault', ['private', 'template', 'wrong_site', 'identity', 'protocol', 'encoded_path'])
def test_only_matching_native_public_file_locators_become_documents(fault):
    extra = b'<div class="public-file" unique="NATIVE"><a href="/vsba/fairfax/Board.nsf/files/NATIVE/$file/file.pdf">Added</a></div>'
    if fault in {'private', 'template'}:
        extra = (b'<div class="private">' + extra + b'</div>' if fault == 'private'
                 else b'<template>' + extra + b'</template>')
    elif fault == 'wrong_site':
        extra = extra.replace(b'/vsba/fairfax/', b'/vsba/other/')
    elif fault == 'identity':
        extra = extra.replace(b'unique="NATIVE"', b'unique="OTHER"')
    elif fault == 'protocol':
        extra = extra.replace(b'href="/', b'href="http://go.boarddocs.com/')
    else:
        extra = extra.replace(b'file.pdf', b'%2e%2e%2ffile.pdf')
    assert len(declared_documents(SOURCE, RAW + extra)) == 4


@pytest.mark.parametrize('fault', ['denied', 'html', 'redirect', 'cancel', 'byte_bound'])
def test_transfer_failure_preserves_record_without_claiming_bytes(tmp_path, fault):
    engine, network, bundle = prepared(tmp_path)
    context, bounds = OperationContext(), Bounds()
    if fault == 'denied':
        network.status = 403
    elif fault == 'html':
        network.body = b'<html>Sign in</html>'
    elif fault == 'redirect':
        network.changed = True
    elif fault == 'cancel':
        network.cancel = context
    else:
        bounds = Bounds(transfer_bytes=1)
    result = engine.fetch_attachment(SOURCE, bundle['records'][0], context=context, bounds=bounds)
    assert result.status == ('cancelled' if fault == 'cancel' else 'partial'), result.public_dict()
    assert result.data.get('attachment') is None
    assert result.data['record']['identity'] == bundle['records'][0]['identity']


def test_descriptor_must_match_original_locator_before_network(tmp_path):
    engine, network, bundle = prepared(tmp_path)
    changed = deepcopy(bundle)
    changed['records'][0]['normalized']['documents'][0]['url'] = changed['records'][0]['normalized']['documents'][1]['url']
    # Mutate the stored value directly to exercise defense against stale descriptors.
    from civic_data_connectors.engine import source_identity_key
    key = source_identity_key(changed['records'][0]['identity'])
    engine.storage.put('records', key, changed['records'][0], scope=OperationContext().scope)
    result = engine.fetch_attachment(SOURCE, changed['records'][0])
    assert result.status == 'failed', result.public_dict()
    assert not network.calls
