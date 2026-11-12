import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs

import pytest
from quorumrelay import OperationContext, create_engine
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.utah_search import native_search

ROOT = Path(__file__).parent / 'fixtures'
RESULT = (ROOT / 'utah-public-search-redacted.html').read_bytes()
FORM = b'''<html><head><meta name="_csrf" content="synthetic-token"></head>
<form id="searchform" action="search.html" method="post"></form></html>'''
SOURCE = {'provider': 'utah-public-notice', 'url': 'https://www.utah.gov/pmn/search.html',
          'body': 'Ridges Estates Infrastructure Financing District'}


class Transport:
    def __init__(self, result=RESULT):
        self.calls, self.result = [], result
    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if kwargs['method'] == 'GET':
            return Response(url, FORM, 'text/html', set_cookie_headers=('session=synthetic-cookie; Path=/; Secure',))
        assert 'session=synthetic-cookie' in kwargs['headers']['Cookie']
        assert kwargs['headers']['X-CSRF-TOKEN'] == 'synthetic-token'
        fields = parse_qs(kwargs['body'].decode(), keep_blank_values=True)
        assert fields['publicBodyName'] == [SOURCE['body']]
        assert fields['title'] == ['Board'] and fields['startDate'] == ['2026-11-11']
        return Response(url, self.result, 'text/html')


def request(**bounds):
    return {'native': True, 'source': SOURCE, 'query': {'terms': ['Board']},
            'bounds': {'date_from': '2026-11-11', 'date_to': '2026-11-11', **bounds}}


def test_public_form_search_and_private_cookie():
    transport = Transport()
    result = native_search(create_engine(), request(), None, OperationContext(principal='a'), transport=transport)
    assert result.status == 'partial', result.public_dict()
    assert len(result.data['hits']) == 1
    assert result.data['hits'][0]['identity']['external_id'] == '1120627'
    assert not result.coverage['catalog_complete'] and not result.coverage['full_source_searched']
    assert 'synthetic-cookie' not in json.dumps(result.public_dict())
    assert len(transport.calls) == 2


def test_scope_binding_and_midpage_continuation():
    html = RESULT.decode()
    start = html.index('<tr class="on">')
    end = html.index('</tr>', start) + len('</tr>')
    row = html[start:end].replace('1120627', '1120628')
    result_html = (html[:end] + row + html[end:]).encode()
    t, engine, ctx = Transport(result_html), create_engine(), OperationContext(principal='alice')
    first = native_search(engine, request(max_records=1), None, ctx, transport=t)
    token = first.coverage['checkpoint']
    assert token and len(first.data['bundle']['records']) == 1
    second = native_search(engine, request(max_records=2, checkpoint=token), None, ctx, transport=t)
    assert len(second.data['bundle']['records']) == 1 and second.coverage['checkpoint'] is None
    with pytest.raises(ValueError):
        native_search(engine, request(checkpoint=token), None, replace(ctx, principal='bob'), transport=t)


def test_denial_mismatch_and_cancellation():
    denied = native_search(create_engine(), request(), None,
        OperationContext(allowed_operations=frozenset()), transport=Transport())
    assert denied.status == 'failed' and denied.errors[0].code == 'permission_denied'
    with pytest.raises(ValueError):
        native_search(create_engine(), {**request(), 'bounds': {}}, None, OperationContext(), transport=Transport())
    class Wrong(Transport):
        def request(self, url, **kwargs):
            return Response('https://example.org/', b'', 'text/html')
    result = native_search(create_engine(), request(), None, OperationContext(), transport=Wrong())
    assert result.status == 'failed' and 'synthetic-token' not in json.dumps(result.public_dict())



def test_supplied_next_control_and_bounded_parser():
    html = RESULT.decode()
    page1 = html.replace('</table>', '</table><a class="jump_to" data-rel="20">Next</a>', 1).encode()
    page2 = html.replace('1120627', '1120628').encode()
    class Pager(Transport):
        def request(self, url, **kwargs):
            if url.endswith('searchresult.html'):
                self.calls.append((url, kwargs))
                assert parse_qs(kwargs['body'].decode())['startingRow'] == ['20']
                assert kwargs['headers']['X-CSRF-TOKEN'] == 'synthetic-token'
                return Response(url, page2, 'text/html')
            return super().request(url, **kwargs)
    transport = Pager(page1)
    result = native_search(create_engine(), request(max_pages=2), None, OperationContext(), transport=transport)
    assert len(result.data['bundle']['records']) == 2
    assert result.coverage['checkpoint'] is None and len(transport.calls) == 3
    too_small = native_search(create_engine(), request(parser_bytes=100), None, OperationContext(), transport=Transport())
    assert too_small.status == 'failed'


def test_pre_cancel_does_not_request_or_leak():
    ctx = OperationContext()
    ctx.cancellation.set()
    transport = Transport()
    result = native_search(create_engine(), request(), None, ctx, transport=transport)
    assert result.status == 'cancelled' and not transport.calls


def test_public_engine_native_and_discovery_registration_keep_notice_identity():
    native = create_engine(provider_transport=Transport()).execute('search', request())
    assert native.status == 'partial' and not native.errors
    assert native.data['hits'][0]['identity']['external_id'] == '1120627'

    class DiscoveryTransport:
        def request(self, url, **kwargs):
            if kwargs['method'] == 'GET':
                return Response(url, FORM, 'text/html')
            fields = parse_qs(kwargs['body'].decode(), keep_blank_values=True)
            assert fields['title'] == [''] and fields['publicBodyName'] == [SOURCE['body']]
            return Response(url, RESULT, 'text/html')
    discovered = create_engine(provider_transport=DiscoveryTransport()).execute('discover', {
        'source': SOURCE, 'bounds': {'date_from': '2026-11-11', 'date_to': '2026-11-11'}})
    assert discovered.status == 'partial' and not discovered.errors
    assert discovered.data['records'][0]['identity']['external_id'] == '1120627'


def test_deadline_failure_is_reported():
    import time
    class Slow(Transport):
        def request(self, url, **kw):
            time.sleep(0.02)
            return super().request(url, **kw)
    result = native_search(create_engine(), request(deadline_seconds=0.005), None, OperationContext(), transport=Slow())
    assert result.status == 'failed'
    assert any(error.code == 'provider_deadline_exceeded' for error in result.errors)


def test_transfer_budget_covers_initial_form_and_response():
    result = native_search(create_engine(), request(transfer_bytes=len(FORM) + 1), None,
                           OperationContext(), transport=Transport())
    assert result.status == 'failed'
