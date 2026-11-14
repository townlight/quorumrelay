"""Vendor-declared document kinds stay consistent across public HTML surfaces."""

import base64
from urllib.parse import urljoin

import pytest

from quorumrelay import Source, create_engine
from test_onbase_detail import FORMAT, MEETING, MEETING_URL
from test_onbase_listing import HTML, SOURCE


@pytest.mark.parametrize('surface', ['listing', 'meeting'])
def test_minutes_packet_keeps_vendor_kind_locator_identity_and_capture(surface):
    # Synthetic type-6 link using the captured client's MinutesPacket enum.
    path = '/OnBaseAgendaOnline/Documents/Downloadfile/MinutesPacket.pdf?documentType=6&amp;meetingId=3825&amp;isAttachment=true'
    link = f'<a href="{path}">Minutes packet</a>'.encode()
    if surface == 'listing':
        source = SOURCE
        content = HTML.replace(b'</td></tr></table>', link + b'</td></tr></table>')
    else:
        source = Source('onbase', MEETING_URL)
        content = MEETING
        # Insert inside the captured unique main-content section.
        start = content.index(b'main-content')
        position = content.index(b'>', start) + 1
        content = content[:position] + link + content[position:]
    result = create_engine().normalize(source, content, input_format=FORMAT)
    assert result.status == 'completed', result.public_dict()
    record = result.data['records'][0]
    document = next(d for d in record['normalized']['documents'] if 'MinutesPacket.pdf' in d['url'])
    assert document['kind'] == 'minutes_packet'
    assert document['url'] == urljoin(SOURCE.url, path.replace('&amp;', '&'))
    assert record['identity']['external_id'] == '3825'
    assert base64.b64decode(result.data['capture']['content_base64']) == content
