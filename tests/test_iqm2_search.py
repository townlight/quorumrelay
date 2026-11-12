import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from quorumrelay import OperationContext, create_engine
from civic_data_connectors.providers.contracts import Response
from civic_data_connectors.providers.iqm2_search import _rows, native_search
from civic_data_connectors.models import Source

ROOT = Path(__file__).parent / 'fixtures'
PAGE = (ROOT / 'iqm2-search-council.html').read_bytes()
EMPTY = (ROOT / 'iqm2-search-empty.html').read_bytes()
URL = 'https://kentwa.iqm2.com/Citizens/calendar.aspx'
SOURCE = {'provider': 'iqm2', 'url': URL}
FORM = b'''<form id="aspnetForm" method="post" action="Search.aspx">
<input name="__VIEWSTATE" type="hidden" value="synthetic-state">
<input name="ctl$SearchText" type="text"><input name="ctl$hfInputHashQuery" type="hidden">
<input name="ctl$hfRealSearchTerms" type="hidden"><input name="ctl$hfAdvancedSearchOption" type="hidden">
<input name="ctl$txtExclude" type="text"></form>'''


class Transport:
    def __init__(self, first=PAGE): self.calls, self.first = [], first
    def request(self, url, **kw):
        self.calls.append((url, kw))
        if kw['method'] == 'GET':
            return Response(url, FORM, 'text/html', set_cookie_headers=('s=synthetic-cookie; Path=/; Secure',))
        assert 's=synthetic-cookie' in kw['headers']['Cookie']
        fields = parse_qs(kw['body'].decode(), keep_blank_values=True)
        assert fields['ctl$SearchText'] == ['Council'] and fields['__VIEWSTATE'] == ['synthetic-state']
        action = parse_qs(urlsplit(url).query)['Action'][0]
        if action == 'DoSearchFull':
            assert 'Start=20' in fields['ctl$hfInputHashQuery'][0]
            return Response(url, EMPTY, 'text/html')
        assert action == 'DoSearch'
        return Response(url, self.first, 'text/html')


def request(**bounds):
    return {'native': True, 'source': SOURCE, 'query': {'terms': ['Council']}, 'bounds': bounds}


def test_observed_mixed_rows_and_no_parent_inference():
    rows, next_link = _rows(Source('iqm2', URL), PAGE)
    assert len(rows) == 20 and 'Start=20' in next_link
    assert {r[2] for r in rows} == {'attachment', 'communication', 'legislative_file'}
    assert rows[0][0]['external_id'] == '3511' and rows[0][0]['meeting_date'] is None
    assert rows[1][0]['meeting_date'] == '2019-06-18'
    assert _rows(Source('iqm2', URL), EMPTY) == ([], None)


def test_native_scoped_continuation_and_private_session():
    engine, ctx, t = create_engine(), OperationContext(principal='alice'), Transport()
    first = native_search(engine, request(max_pages=1, max_records=30), None, ctx, transport=t)
    assert first.status == 'partial', first.public_dict()
    assert len(first.data['bundle']['records']) == 20 and first.coverage['checkpoint']
    assert not first.coverage['catalog_complete'] and not first.coverage['full_source_searched']
    assert 'synthetic-cookie' not in json.dumps(first.public_dict())
    assert 'synthetic-state' not in json.dumps(first.public_dict())
    token = first.coverage['checkpoint']
    with pytest.raises(ValueError):
        native_search(engine, request(checkpoint=token), None, replace(ctx, principal='bob'), transport=t)
    second = native_search(engine, request(max_pages=1, checkpoint=token), None, ctx, transport=t)
    assert second.status == 'partial' and second.coverage['checkpoint'] is None
    assert len(t.calls) == 3


def test_empty_denial_bad_response_and_cancel():
    t = Transport(EMPTY)
    result = native_search(create_engine(), request(), None, OperationContext(), transport=t)
    assert result.status == 'partial' and not result.data['hits']
    denied = native_search(create_engine(), request(), None,
                           OperationContext(allowed_operations=frozenset()), transport=Transport())
    assert denied.status == 'failed'
    class Wrong(Transport):
        def request(self, url, **kw): return Response('https://example.org/', b'', 'text/html')
    assert native_search(create_engine(), request(), None, OperationContext(), transport=Wrong()).status == 'failed'
    ctx, t = OperationContext(), Transport()
    ctx.cancellation.set()
    assert native_search(create_engine(), request(), None, ctx, transport=t).status == 'cancelled' and not t.calls


def test_bad_pager_scope_and_parser_bounds_fail_closed():
    bad = PAGE.replace(b'SearchText=Council&Type=All&MediaOnly=False&Start=20',
                       b'SearchText=Other&Type=All&MediaOnly=False&Start=20')
    result = native_search(create_engine(), request(max_pages=2), None, OperationContext(), transport=Transport(bad))
    assert result.status == 'partial' and result.errors
    limited = native_search(create_engine(), request(parser_bytes=100), None, OperationContext(), transport=Transport())
    assert limited.status == 'failed'


def test_midpage_resume_and_date_filter_remain_scoped():
    engine, ctx, t = create_engine(), OperationContext(principal='alice'), Transport()
    first = native_search(engine, request(max_records=3), None, ctx, transport=t)
    assert len(first.data['bundle']['records']) == 3 and first.coverage['checkpoint']
    second = native_search(engine, request(max_records=4, checkpoint=first.coverage['checkpoint']), None, ctx, transport=t)
    assert len(second.data['bundle']['records']) == 4
    assert len(t.calls) == 2
    with pytest.raises(ValueError):
        native_search(engine, request(checkpoint=first.coverage['checkpoint'], date_from='2026-01-01'),
                      None, ctx, transport=t)


def test_deadline_failure_is_reported_without_leaking_private_state():
    import time
    class Slow(Transport):
        def request(self, url, **kw):
            time.sleep(0.02)
            return super().request(url, **kw)
    result = native_search(create_engine(), request(deadline_seconds=0.005), None, OperationContext(), transport=Slow())
    assert result.status == 'failed'
    assert any(error.code == 'provider_deadline_exceeded' for error in result.errors)
    assert 'synthetic-state' not in json.dumps(result.public_dict())


def test_transfer_budget_covers_initial_form_and_response():
    result = native_search(create_engine(), request(transfer_bytes=len(FORM) + 1), None,
                           OperationContext(), transport=Transport())
    assert result.status == 'failed'


def test_public_engine_registration_and_saved_parser_preserve_mixed_ids():
    result = create_engine(provider_transport=Transport()).execute('search', request())
    assert result.status == 'partial' and not result.errors
    records = result.data['bundle']['records']
    assert len(records) == 20
    assert {r['identity']['record_type'] for r in records} == {
        'attachment', 'communication', 'legislative_file'}
    saved = create_engine().execute('normalize', {
        'source': {**SOURCE, 'input_format': 'iqm2-public-search-html'}}, content=PAGE)
    assert saved.status == 'completed', saved.public_dict()
    assert [r['identity'] for r in saved.data['records']] == [r['identity'] for r in records]
    assert saved.data['capture']['content_base64'] == result.data['bundle']['captures'][0]['content_base64']


def test_existing_kent_default_source_uses_same_fixed_search_route():
    item = request(max_pages=1)
    item['source'] = {**SOURCE, 'url': 'https://kentwa.iqm2.com/Citizens/default.aspx'}
    transport = Transport()
    result = native_search(create_engine(), item, None, OperationContext(), transport=transport)
    assert result.status == 'partial' and len(result.data['bundle']['records']) == 20
    assert transport.calls[0][0] == 'https://kentwa.iqm2.com/Citizens/Search.aspx'
