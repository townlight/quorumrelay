"""Observed CivicWeb public meeting detail and its supplied print document."""

from dataclasses import replace
from datetime import datetime
from html.parser import HTMLParser
import re
from time import monotonic
from urllib.parse import parse_qs, urljoin, urlsplit

from ..models import Error, OperationResult
from .contracts import RetrievalError, _origin
from .identification import validate_url
from .native import make_bundle

FORMAT = 'civicweb-detail-html'


class _Detail(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form = None
        self.selected_id = None
        self.selected = False
        self.title = None
        self.date = []
        self.in_date = False
        self.documents = []

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == 'form' and fields.get('id') == 'aspnetForm':
            self.form = fields.get('action')
        if tag == 'button':
            match = re.fullmatch(r'ctl00_MainContent_MeetingButton([1-9][0-9]*)', fields.get('id', ''))
            self.selected = bool(match and fields.get('aria-selected') == 'true')
            if self.selected:
                self.selected_id = match[1]
        if self.selected and tag == 'div':
            if fields.get('class') == 'meeting-list-item-button-date':
                self.in_date = True
            if fields.get('title'):
                self.title = fields['title'].strip()
        if tag == 'a' and fields.get('id') == 'ctl00_MainContent_DocumentPrintVersion':
            if fields.get('href'):
                self.documents.append(fields['href'])

    def handle_endtag(self, tag):
        if tag == 'button':
            self.selected = False
        if tag == 'div':
            self.in_date = False

    def handle_data(self, data):
        if self.selected and self.in_date:
            self.date.append(data)


def detail_bundle(source, namespace, content, *, expected_id=None):
    page = _Detail()
    page.feed(content.decode('utf-8', errors='replace'))
    if page.form is None or page.selected_id is None or not page.title:
        raise ValueError('The CivicWeb detail lacks a selected public meeting identity/title.')
    form = urlsplit(urljoin(source.url, page.form))
    values = parse_qs(form.query)
    identity = values.get('Id', values.get('id', []))
    if (_origin(form.geturl()) != _origin(source.url)
            or form.path.lower() != '/portal/meetinginformation.aspx'
            or identity != [page.selected_id]
            or (expected_id is not None and page.selected_id != expected_id)):
        raise ValueError('The CivicWeb selected meeting does not match its requested/form identity.')
    day = datetime.strptime(' '.join(page.date).strip(), '%d %b %Y').date().isoformat()
    documents = []
    for supplied in page.documents:
        url = urljoin(source.url, supplied)
        validate_url(url)
        parts = urlsplit(url)
        if (_origin(url) != _origin(source.url)
                or re.fullmatch(r'/document/[1-9][0-9]*/[^/]+\.pdf', parts.path, re.I) is None):
            raise ValueError('The CivicWeb print document left its observed public document route.')
        document = {'kind': 'published_document', 'url': url}
        if document not in documents:
            documents.append(document)
    normalized = {'external_id': page.selected_id, 'title': page.title, 'meeting_date': day,
                  'url': form.geturl(), 'documents': documents, 'recordings': [],
                  'time_zone_status': 'unknown', 'agenda_items_availability': 'unverified'}
    return make_bundle(source, namespace, content, FORMAT,
                       [(normalized, {'html': content.decode('utf-8', errors='replace')}, 'meeting')])


def fetch_record(source, namespace, external_id, bounds, context, transport):
    if not isinstance(external_id, str) or re.fullmatch(r'[1-9][0-9]{0,18}', external_id) is None:
        raise ValueError('CivicWeb detail requires a positive decimal meeting ID string.')
    if bounds.checkpoint:
        raise ValueError('One CivicWeb meeting detail does not accept catalog continuation.')
    if context.check_cancelled():
        return OperationResult('cancelled', operation_id=context.operation_id)
    url = _origin(source.url) + '/Portal/MeetingInformation.aspx?Id=' + external_id
    coverage = {'scope': 'one selected public meeting; supplied print document only',
                'catalog_complete': False, 'source_complete': False,
                'agenda_items_availability': 'unverified', 'external_id': external_id}
    started = monotonic()
    try:
        response = transport.request(url, byte_limit=bounds.parser_bytes,
            deadline_seconds=bounds.deadline_seconds, allowed_origins=(_origin(url),), allow_redirects=False)
        if context.check_cancelled():
            return OperationResult('cancelled', coverage=coverage, operation_id=context.operation_id)
        if (response.status != 200 or response.url != url or len(response.content) > bounds.parser_bytes
                or monotonic() - started >= bounds.deadline_seconds):
            raise RetrievalError('civicweb_detail_unavailable', status=response.status)
        bundle = detail_bundle(replace(source, url=url), namespace, response.content, expected_id=external_id)
        return OperationResult('partial', bundle, coverage=coverage, operation_id=context.operation_id)
    except (ValueError, OSError) as error:
        return OperationResult('failed', errors=(Error('civicweb_detail_unavailable',
            'The requested public meeting detail could not be retrieved or validated.',
            source=url, details={'reason': error.code if isinstance(error, RetrievalError) else 'invalid_detail'}),),
            coverage=coverage, operation_id=context.operation_id)
