import base64

from quorumrelay import Source, create_engine
from quorumrelay.providers.contracts import Response
from civic_data_connectors import compat
from civic_data_connectors.providers.granicus import listing_rows

SOURCE = Source('peak', 'https://lowermerion.granicus.com/ViewPublisher.php?view_id=1',
    input_format='granicus-listing-html', options={'download_origins': ['https://d3n9y02raazwpg.cloudfront.net']})
PACKET = 'https://d3n9y02raazwpg.cloudfront.net/lowermerion/synthetic-packet.pdf'
CAPTURE = ('<table><tr><td headers="Name">Council</td><td headers="Date">November 10, 2026</td>'
    '<td headers="AgendaPacketLink"><a href="' + PACKET + '">Agenda Packet</a>'
    '<a href="' + PACKET + '">Duplicate</a></td></tr></table>').encode()


def test_peak_packet_mapping_is_additive_with_capture_position_identity_unchanged():
    normalized, raw, _ = listing_rows(SOURCE, CAPTURE)[0]
    assert normalized['documents'] == [{'kind': 'packet', 'url': PACKET}]
    assert raw['packet_links'] == [PACKET, PACKET]
    without = CAPTURE.replace(b'AgendaPacketLink', b'UnknownCell')
    assert listing_rows(SOURCE, without)[0][0]['external_id'] == normalized['external_id']
    assert normalized['external_id'].startswith('derived:')
    baseline = compat.ViewPublisherRows()
    baseline.feed(CAPTURE.decode())
    assert 'packet_links' not in baseline.rows[0]


def test_peak_packet_rejects_unsafe_or_unverified_links():
    for url in ['javascript:void(0)', 'https://localhost/a.pdf', 'https://example.com/a.html',
                'https://user:secret@example.com/a.pdf', 'https://example.com/a.pdf?token=secret']:
        capture = CAPTURE.replace(PACKET.encode(), url.encode())
        assert listing_rows(SOURCE, capture)[0][0]['documents'] == []


def test_peak_packet_fetch_requires_explicit_origin_and_keeps_supplied_url():
    class Transport:
        calls = []

        def request(self, url, **kwargs):
            self.calls.append(url)
            assert url == PACKET
            return Response(url, b'%PDF-1.7\nsynthetic packet', 'application/pdf')

    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.execute('discover', {'source': SOURCE.public_dict()}, content=CAPTURE)
    record = result.data['records'][0]
    assert record['normalized']['documents'][0]['url'] == PACKET
    fetched = engine.fetch_attachment(SOURCE, record, capture=CAPTURE)
    assert fetched.status == 'completed', fetched.public_dict()
    assert base64.b64decode(fetched.data['attachment']['content_base64']).startswith(b'%PDF-')
    assert fetched.data['attachment']['citation_url'] == PACKET
    source = Source('peak', SOURCE.url, input_format=SOURCE.input_format)
    refused = engine.fetch_attachment(source, record, capture=CAPTURE)
    assert refused.status == 'partial' and len(transport.calls) == 1
