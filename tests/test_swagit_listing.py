from quorumrelay import Source, create_engine
from civic_data_connectors.providers.swagit import listing_rows

SOURCE = Source('swagit', 'https://princetontx.new.swagit.com/views/261/')
HTML = b'''<table><tr><td><a href="/videos/405097">City Council Work Session</a></td>
<td>Oct 26, 2026</td><td>25m 14s</td><td><a href="/videos/405097/agenda">Agenda</a></td></tr>
<tr><td><a href="/videos/405097?ts=1666.3">00:27:46</a></td></tr></table>'''


def test_current_swagit_table_retains_native_identity_documents_and_timestamp_only_matches():
    row, original, kind = listing_rows(SOURCE, HTML)[0]
    assert row['external_id'] == '405097' and row['meeting_date'] == '2026-10-26'
    assert row['documents'][0]['url'] == 'https://princetontx.new.swagit.com/videos/405097/agenda'
    assert row['search_match_urls'] == ['https://princetontx.new.swagit.com/videos/405097?ts=1666.3']
    assert 'transcript' not in row and original['cells'] and kind == 'meeting'
    parsed = create_engine().execute('discover', {'source': SOURCE.public_dict()}, content=HTML)
    assert parsed.data['records'][0]['identity']['external_id'] == '405097'
    assert parsed.data['records'][0]['normalized'] == row


def test_swagit_does_not_accept_external_identity_or_invent_documents():
    assert listing_rows(SOURCE, HTML.replace(b'href="/videos/', b'href="https://other.example/videos/'), allow_empty=True) == []
    row = listing_rows(SOURCE, HTML.replace(b'/videos/405097/agenda', b'/unknown/agenda'))[0][0]
    assert row['documents'] == []
