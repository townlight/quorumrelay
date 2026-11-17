"""Date-window membership enables older meeting detail without guessing IDs."""
import base64
from dataclasses import replace

import pytest

from quorumrelay import Bounds, create_engine
from civic_data_connectors.providers.onbase import window_url
from test_onbase_detail import Transport, HTML, SOURCE, MEETING_URL, AGENDA_URL, ITEM_URL


WINDOW = window_url(SOURCE, '2026-11-12', '2026-11-12')


@pytest.mark.parametrize('related', [False, True])
def test_window_selected_detail_uses_current_window_membership(related):
    transport = Transport()
    transport.pages[WINDOW] = HTML
    del transport.pages[SOURCE.url]  # selected meeting need not occur at the current root
    engine = create_engine(provider_transport=transport)
    bounds = Bounds(date_from='2026-11-12', date_to='2026-11-12')
    result = (engine.fetch_related(SOURCE, '3825', 'agenda_item', external_id='88173', bounds=bounds)
              if related else engine.fetch_record(SOURCE, '3825', bounds=bounds))
    assert result.status == 'partial' and not result.errors, result.public_dict()
    assert [url for url, _ in transport.calls] == [WINDOW, MEETING_URL, AGENDA_URL] + ([ITEM_URL] if related else [])
    assert result.coverage['membership_url'] == WINDOW
    captures = [result.data['capture'], *result.data['captures']]
    assert any(capture['source_url'] == WINDOW and base64.b64decode(capture['content_base64']) == HTML
               for capture in captures)


@pytest.mark.parametrize('dates', [('2026-11-11', '2026-11-11'), ('2026-11-13', '2026-11-13')])
def test_window_response_cannot_attribute_out_of_window_meeting(dates):
    transport = Transport()
    transport.pages[window_url(SOURCE, *dates)] = HTML
    result = create_engine(provider_transport=transport).fetch_record(
        SOURCE, '3825', bounds=Bounds(date_from=dates[0], date_to=dates[1]))
    assert result.status == 'failed' and result.errors
    assert len(transport.calls) == 1


def test_window_membership_failure_never_falls_back_to_unbounded_root():
    transport = Transport()
    transport.pages[WINDOW] = HTML
    transport.statuses[WINDOW] = 403
    result = create_engine(provider_transport=transport).fetch_record(
        SOURCE, '3825', bounds=Bounds(date_from='2026-11-12', date_to='2026-11-12'))
    assert result.status == 'failed' and result.errors
    assert [url for url, _ in transport.calls] == [WINDOW]


def test_window_detail_preserves_listing_on_later_page_budget_exhaustion():
    transport = Transport()
    transport.pages[WINDOW] = HTML
    result = create_engine(provider_transport=transport).fetch_record(
        SOURCE, '3825', bounds=Bounds(date_from='2026-11-12', date_to='2026-11-12', max_pages=1))
    assert result.status == 'partial' and result.errors and result.coverage['truncated']
    assert result.data['records'][0]['identity']['external_id'] == '3825'
    assert len(transport.calls) == 1


def test_single_date_boundary_is_rejected_before_network():
    transport = Transport()
    result = create_engine(provider_transport=transport).fetch_record(
        SOURCE, '3825', bounds=Bounds(date_from='2026-11-12'))
    assert result.errors and not transport.calls


def test_documented_meetings_root_also_supports_selected_detail():
    source = replace(SOURCE, url=SOURCE.url.rstrip('/') + '/Meetings')
    transport = Transport()
    transport.pages[source.url] = HTML
    result = create_engine(provider_transport=transport).fetch_record(source, '3825')
    assert result.status == 'partial' and not result.errors, result.public_dict()
    assert transport.calls[0][0] == source.url
