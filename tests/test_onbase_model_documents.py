"""Synthetic nonempty rows from the captured vendor Document/link constructor."""

import base64
from copy import deepcopy
import json

import pytest

from quorumrelay import OperationContext, create_engine
from quorumrelay.providers.contracts import Response
from quorumrelay.storage import SQLiteStorage
from test_onbase_search_model import MODEL, SOURCE, page


def model_with_documents():
    model = deepcopy(MODEL)
    row = model['Meetings'][0]
    row.update(HasDocuments=True, Documents=[{
        'ID': 97134, 'Name': 'Budget appendix', 'ItemID': 88173,
        'ItemTitle': 'Budget hearing', 'ItemOutlineNum': '4.a', 'PublishType': 4,
        'MeetingDocumentType': 1, 'UrlFriendlyName': 'Budget appendix',
        'FutureField': {'zero': 0, 'unknown': []}}, {
        'ID': 97135, 'Name': 'Meeting summary', 'ItemID': 0, 'ItemTitle': '',
        'ItemOutlineNum': '', 'PublishType': 3, 'MeetingDocumentType': 3,
        'UrlFriendlyName': 'Summary special'}],
        HasMedia=True, Media={'IsLive': False, 'IsOnDemand': True, 'unknown': 'retained'})
    return model


def normalize(model=None):
    result = create_engine().normalize(SOURCE, page(model or model_with_documents()),
                                     input_format='onbase-public-listing-html')
    assert result.status == 'completed', result.public_dict()
    return result.data


def test_declared_nested_documents_and_media_are_locators_with_exact_parent_metadata():
    record = normalize()['records'][0]
    docs = record['normalized']['documents']
    item = next(d for d in docs if d.get('publish_id') == '97134')
    assert item['url'].endswith('Budget%20appendix.pdf?documentType=1&meetingId=704&itemId=88173&publishId=97134&isSection=False&isAttachment=True')
    assert item['meeting_external_id'] == '704'
    assert item['agenda_item_external_id'] == '88173'
    assert item['title'] == 'Budget appendix' and item['agenda_item_title'] == 'Budget hearing'
    assert item['availability'] == 'supplied_locator_not_fetched'
    summary = next(d for d in docs if d.get('external_id') == '97135')
    assert summary['url'].endswith('Summary%20special.pdf?documentType=3&meetingId=704')
    assert record['normalized']['recordings'] == [{
        'url': record['normalized']['url'], 'availability': 'link_only_not_fetched',
        'is_live': False, 'is_on_demand': True}]
    assert record['original']['Documents'][0]['FutureField'] == {'zero': 0, 'unknown': []}


def test_nested_documents_survive_real_storage_search_zip_and_idempotent_import(tmp_path):
    bundle = normalize()
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'owner.sqlite'))
    request = {'bundle': bundle, 'persist': True}
    assert owner.execute('import_bundle', request).status == 'completed'
    assert all(c['outcome'] == 'unchanged' for c in owner.execute('import_bundle', request).data['changes'])
    owner = create_engine(storage=SQLiteStorage(tmp_path / 'owner.sqlite'))
    result = owner.execute('search', {'query': {'phrases': ['Budget appendix']}})
    assert {h['identity']['external_id'] for h in result.data['hits']} == {'704'}
    exported = owner.execute('export', {'bundle': bundle, 'format': 'zip'})
    target = create_engine(storage=SQLiteStorage(tmp_path / 'target.sqlite'))
    restored = target.execute('import_bundle', {'format': 'zip', 'persist': True},
                             content=base64.b64decode(exported.data['content_base64']))
    assert restored.status == 'completed', restored.public_dict()
    saved = target.storage.list('records', scope=OperationContext().scope)
    assert next(r.value for r in saved if r.value['identity']['external_id'] == '704') == bundle['records'][0]


def test_normalized_nested_document_fetch_uses_the_supplied_url_not_an_item_route(tmp_path):
    bundle = normalize()
    record = bundle['records'][0]
    index = next(i for i, d in enumerate(record['normalized']['documents']) if d.get('publish_id') == '97134')
    calls = []

    class Transport:
        def request(self, url, **kwargs):
            calls.append((url, kwargs))
            assert kwargs['allow_redirects'] is False
            return Response(url, b'%PDF-1.4\nsynthetic document\n%%EOF', 'application/pdf')

    owner = create_engine(storage=SQLiteStorage(tmp_path / 'fetch.sqlite'), provider_transport=Transport())
    assert owner.execute('import_bundle', {'bundle': bundle, 'persist': True}).status == 'completed'
    result = owner.fetch_attachment(SOURCE, record, index=index)
    assert result.status == 'completed', result.public_dict()
    assert len(calls) == 1 and calls[0][0] == record['normalized']['documents'][index]['url']


@pytest.mark.parametrize('changes', [
    {'ID': True}, {'ItemID': '../other'}, {'MeetingDocumentType': True},
    {'UrlFriendlyName': '../secret'}, {'UrlFriendlyName': 'hidden\x00name'},
    {'PublishType': True}, {'ItemTitle': None}])
def test_invalid_nested_document_scope_never_becomes_a_download_locator(changes):
    model = model_with_documents()
    model['Meetings'][0]['Documents'][0].update(changes)
    result = create_engine().normalize(SOURCE, page(model), input_format='onbase-public-listing-html')
    assert result.status == 'failed' and result.errors


def test_unknown_document_type_is_retained_as_raw_and_explicitly_unmapped():
    model = model_with_documents()
    model['Meetings'][0]['Documents'][0]['MeetingDocumentType'] = 99
    record = normalize(model)['records'][0]
    assert not any(d.get('publish_id') == '97134' for d in record['normalized']['documents'])
    assert record['normalized']['document_mapping_complete'] is False
    assert record['original']['Documents'][0]['MeetingDocumentType'] == 99


def test_unadvertised_documents_and_incomplete_media_are_not_fabricated():
    model = model_with_documents()
    model['Meetings'][0].update(HasDocuments=False, Media={'future': 'shape'})
    record = normalize(model)['records'][0]
    assert not any(d.get('publish_id') for d in record['normalized']['documents'])
    assert not record['normalized']['recordings']
    assert record['normalized']['media_availability'] == 'unmapped_submodel'


@pytest.mark.parametrize('wrong_readback', [False, True])
def test_nested_item_wrapper_revalidates_exact_scope_and_keeps_meeting_on_failure(tmp_path, monkeypatch, wrong_readback):
    from test_onbase_item_documents import WRAPPED, ITEM_NAME, PDF
    from civic_data_connectors.providers import onbase_documents
    monkeypatch.setattr(onbase_documents, '_wait', lambda *args: None)
    bundle = normalize()
    record = bundle['records'][0]
    index = next(i for i, d in enumerate(record['normalized']['documents']) if d.get('publish_id') == '97134')
    citation = record['normalized']['documents'][index]['url']
    calls = []

    class Transport:
        def request(self, url, **kwargs):
            calls.append(url)
            assert kwargs['allow_redirects'] is False
            if url == citation:
                return Response(url, WRAPPED.replace(b'3825', b'704'), 'text/html')
            if '/InvokeDownloadAttachment/' in url:
                assert kwargs['method'] == 'POST'
                payload = {'DocumentName': ITEM_NAME, 'MeetingId': 705 if wrong_readback else 704,
                           'ItemId': 88173, 'PublishId': 97134, 'DocumentType': 1, 'IsSection': False}
                return Response(url, json.dumps(payload).encode(), 'application/json')
            assert '/ViewDocument/' in url
            return Response(url, PDF, 'application/pdf')

    owner = create_engine(storage=SQLiteStorage(tmp_path / 'wrapper.sqlite'), provider_transport=Transport())
    assert owner.execute('import_bundle', {'bundle': bundle, 'persist': True}).status == 'completed'
    result = owner.fetch_attachment(SOURCE, record, index=index)
    assert result.status == ('partial' if wrong_readback else 'completed'), result.public_dict()
    assert len(calls) == (2 if wrong_readback else 3)
    assert result.data['record']['identity'] == record['identity']
    if not wrong_readback:
        assert base64.b64decode(result.data['attachment']['content_base64']) == PDF
        assert result.data['attachment']['resolution']['item_id'] == '88173'


@pytest.mark.parametrize('field', ['meeting_external_id', 'agenda_item_external_id', 'publish_id', 'publish_type'])
def test_nested_scope_tampering_rejected_before_preparation(field):
    from time import monotonic
    from quorumrelay import Bounds
    from test_onbase_item_documents import WRAPPED
    from civic_data_connectors.providers.onbase_documents import resolve_document
    record = normalize()['records'][0]
    document = next(d for d in record['normalized']['documents'] if d.get('publish_id') == '97134')
    url = document['url']
    document[field] = 3 if field == 'publish_type' else '9999'

    class NoNetwork:
        def request(self, *args, **kwargs):
            raise AssertionError('Invalid nested scope started document preparation')

    with pytest.raises(ValueError, match='item and meeting'):
        resolve_document(SOURCE, url, record, Response(url, WRAPPED.replace(b'3825', b'704'), 'text/html'),
                         Bounds(), OperationContext(), NoNetwork(), monotonic() + 20)
