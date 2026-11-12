import base64
from dataclasses import replace

from quorumrelay import Bounds, OperationContext, Source, create_engine
from quorumrelay.providers.contracts import Response

SOURCE = Source('civicweb', 'https://ciindependenceor.civicweb.net/Portal/MeetingTypeList.aspx')
DETAIL = 'https://ciindependenceor.civicweb.net/Portal/MeetingInformation.aspx?Id=11021'
PDF = 'https://ciindependenceor.civicweb.net/document/87303/synthetic.pdf?handle=public-handle'
HTML = ('<form id="aspnetForm" action="./MeetingInformation.aspx?Id=11021">'
 '<button id="ctl00_MainContent_MeetingButton11021" aria-selected="true">'
 '<div class="meeting-list-item-button-date">22 Jul 2025</div>'
 '<div title="City Council Work Session">City Council Work Session</div></button>'
 '<a id="ctl00_MainContent_DocumentPrintVersion" href="'+PDF+'"></a></form>').encode()


class Transport:
    def __init__(self, html=HTML):
        self.html = html
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url == DETAIL:
            assert kwargs['allow_redirects'] is False
            return Response(url, self.html, 'text/html')
        assert url == PDF
        return Response(url, b'%PDF-1.7 synthetic PDF', 'application/pdf')


def test_civicweb_requested_detail_preserves_identity_raw_and_supplied_document():
    transport = Transport()
    engine = create_engine(provider_transport=transport)
    result = engine.fetch_record(SOURCE, '11021')
    assert result.status == 'partial', result.public_dict()
    record = result.data['records'][0]
    assert record['identity']['external_id'] == '11021'
    assert record['normalized']['meeting_date'] == '2025-07-22'
    assert record['normalized']['title'] == 'City Council Work Session'
    assert record['normalized']['documents'] == [{'kind': 'published_document', 'url': PDF}]
    assert record['original']['html'].encode() == HTML
    assert base64.b64decode(result.data['capture']['content_base64']) == HTML
    source = replace(SOURCE, url=DETAIL, input_format='civicweb-detail-html')
    saved = engine.normalize(source, HTML, input_format=source.input_format)
    assert saved.data['records'][0]['normalized'] == record['normalized']
    fetched = engine.fetch_attachment(source, record, capture=HTML)
    assert fetched.status == 'completed', fetched.public_dict()
    assert fetched.data['attachment']['citation_url'] == PDF


def test_civicweb_wrong_selected_identity_cross_origin_and_bounds_are_rejected():
    for content in [HTML.replace(b'MeetingButton11021', b'MeetingButton11022'),
                    HTML.replace(b'?Id=11021', b'?Id=11022'),
                    HTML.replace(PDF.encode(), b'https://other.example/document/87303/file.pdf')]:
        result = create_engine(provider_transport=Transport(content)).fetch_record(SOURCE, '11021')
        assert result.status == 'failed' and not result.data
    limited = create_engine(provider_transport=Transport()).fetch_record(SOURCE, '11021', bounds=Bounds(parser_bytes=100))
    assert limited.status == 'failed'
    transport = Transport()
    context = OperationContext()
    context.cancellation.set()
    cancelled = create_engine(provider_transport=transport).fetch_record(SOURCE, '11021', context=context)
    assert cancelled.status == 'cancelled' and not transport.calls

