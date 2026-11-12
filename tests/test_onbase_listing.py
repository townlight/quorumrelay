from quorumrelay import Source,create_engine
from civic_data_connectors.providers.onbase import listing_rows

SOURCE = Source('onbase','https://agendas.fitchburgwi.gov/OnBaseAgendaOnline/')
HTML = b'''<table><tr><td data-sortable-type="mtgName">Commission on Aging Well</td><td data-sortable-type="mtgTime">11/12/2026 8:30:00 AM</td><td>
<a href="/OnBaseAgendaOnline/Meetings/ViewMeeting?id=3825&amp;doctype=1">Agenda</a>
<a href="/OnBaseAgendaOnline/Documents/Downloadfile/Agenda.pdf?documentType=1&amp;meetingId=3825">PDF</a>
<a href="/OnBaseAgendaOnline/Documents/Downloadfile/Packet.pdf?documentType=5&amp;meetingId=3825">Packet</a></td></tr></table>'''


def test_current_onbase_meeting_name_layout_maps_supplied_documents_without_body_inference():
    row,original,_ = listing_rows(SOURCE,HTML)[0]
    assert row['external_id']=='3825' and row['meeting_date']=='2026-11-12'
    assert row['title']=='Commission on Aging Well' and 'body' not in row
    assert [x['kind'] for x in row['documents']]==['agenda','packet']
    assert original['cells'][0]['label']=='mtgName'
    result = create_engine().execute('discover',{'source':SOURCE.public_dict()},content=HTML)
    assert result.data['records'][0]['normalized']==row
    assert listing_rows(SOURCE,HTML.replace(b'mtgName',b'mtgType'))[0][0]==row


def test_onbase_retains_meeting_without_files_and_rejects_mixed_ids():
    without_files=HTML.split(b'<a href="/OnBaseAgendaOnline/Documents/')[0]+b'</td></tr></table>'
    row=listing_rows(SOURCE,without_files)[0][0]
    assert row['external_id']=='3825' and row['documents']==[]
    try:
        listing_rows(SOURCE,HTML.replace(b'meetingId=3825',b'meetingId=999'))
    except ValueError:
        pass
    else:
        raise AssertionError('Conflicting supplied IDs cannot be silently merged.')
