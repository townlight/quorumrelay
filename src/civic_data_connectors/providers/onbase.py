"""Observed OnBase public meeting-name/date table with supplied download links."""

from datetime import datetime
from html.parser import HTMLParser
import json
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit

from ..compat import _table_rows
from .identification import validate_url

FORMAT = 'onbase-public-listing-html'
KINDS = {'1':'agenda','2':'minutes','3':'summary','5':'packet','6':'minutes_packet'}


def window_url(source, date_from, date_to):
    """Observed public custom-date GET; no undocumented continuation requests."""
    parsed = urlsplit(source.url)
    if (parsed.scheme != 'https' or parsed.query or
            parsed.path.rstrip('/').lower() not in {
                '/onbaseagendaonline', '/onbaseagendaonline/meetings'}):
        raise ValueError('OnBase date windows require a configured HTTPS public root.')
    root = parsed.path[:len('/OnBaseAgendaOnline')]
    return f'{parsed.scheme}://{parsed.netloc}{root}/Meetings/Search?' + urlencode({
        'dropid': '11', 'dropsv': datetime.fromisoformat(date_from).strftime('%m/%d/%Y'),
        'dropev': datetime.fromisoformat(date_to).strftime('%m/%d/%Y')})


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        self.active = tag == 'script' if tag == 'script' else self.active

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.scripts.append(data)


def search_model(content):
    """Decode the observed v25 embedded JSON; never execute portal JavaScript."""
    parser = _Scripts()
    parser.feed(content.decode('utf-8-sig'))
    marker = 'showSearchResults(new SearchResults('
    models = []
    for script in parser.scripts:
        start = script.find(marker)
        if start < 0:
            continue
        if script.count(marker) != 1:
            raise ValueError('Ambiguous OnBase search models.')
        text = script[start + len(marker):].lstrip()
        model, end = json.JSONDecoder().raw_decode(text)
        if not text[end:].lstrip().startswith('));') or not isinstance(model, dict):
            raise ValueError('Invalid OnBase embedded search result.')
        if not isinstance(model.get('Meetings'), list):
            raise ValueError('OnBase search results must supply a meeting array.')
        if any(model.get(key) for key in ('ErrorOccurred', 'HasError', 'ShowErrorOnly')):
            raise ValueError('OnBase reported a search error.')
        models.append(model)
    if len(models) > 1:
        raise ValueError('Ambiguous OnBase search models.')
    return models[0] if models else None


def _model_rows(source, model):
    parts = urlsplit(source.url)
    root = parts.path.lower().find('/onbaseagendaonline')
    if root < 0:
        raise ValueError('OnBase results require a configured Agenda Online root.')
    prefix = parts.path[:root + len('/OnBaseAgendaOnline')]
    base = f'{parts.scheme}://{parts.netloc}{prefix}'
    result, seen = [], set()
    # These values and URL templates are declared by the captured v25 client.
    variants = [('Agenda', 'agenda', 1), ('Minutes', 'minutes', 2),
                ('Summary', 'summary', 3), ('AgendaPacket', 'packet', 5),
                ('MinutesPacket', 'minutes_packet', 6)]
    for raw in model['Meetings']:
        if not isinstance(raw, dict):
            raise ValueError('Invalid OnBase meeting row.')
        identity = raw.get('ID')
        if type(identity) is not int or identity <= 0 or identity in seen:
            raise ValueError('OnBase meeting identities must be positive and unique.')
        seen.add(identity)
        start = raw.get('Time')
        if not isinstance(start, str):
            raise ValueError('OnBase meeting time is missing.')
        parsed = datetime.fromisoformat(start)
        title = raw.get('Name')
        if not isinstance(title, str) or not title.strip():
            raise ValueError('OnBase meeting title is missing.')
        documents = []
        for field, kind, code in variants:
            if raw.get('Is' + field + 'Available') is not True:
                continue
            name = raw.get(field + 'UniqueName')
            if not isinstance(name, str) or not name or any(c in name for c in '/\\\x00\r\n'):
                raise ValueError('OnBase declared an invalid document name.')
            query = {'documentType': code, 'meetingId': identity}
            if code in (5, 6):
                query['isAttachment'] = 'true'
            documents.append({'kind': kind, 'url': base + '/Documents/DownloadFile/' +
                              quote(name, safe='') + '.pdf?' + urlencode(query)})
        latest = raw.get('LatestDocumentType')
        meeting_url = base + '/Meetings/ViewMeeting?' + urlencode({'id': identity})
        if type(latest) is int and latest in (1, 2, 3, 5, 6):
            meeting_url += '&' + urlencode({'doctype': latest})
        # Documents/Media submodels are preserved, not guessed from flags.
        normalized = {'external_id': str(identity), 'title': title,
                      'meeting_type_name': raw.get('MeetingTypeName'),
                      'meeting_date': parsed.date().isoformat(), 'source_start': start,
                      'time_zone_status': 'source_literal_unverified',
                      'location': raw.get('Location'), 'url': meeting_url,
                      'documents': documents, 'recordings': [],
                      'agenda_items_availability': 'unverified'}
        result.append((normalized, raw, 'meeting'))
    return result


def listing_rows(source, content):
    model = search_model(content)
    return _model_rows(source, model) if model is not None else _legacy_listing_rows(source, content)


def _legacy_listing_rows(source, content):
    result = {}
    for row in _table_rows(content):
        fields = {cell['label']:cell for cell in row if cell['label']}
        title = ' '.join((fields.get('mtgName') or fields.get('mtgType') or {}).get('text','').split())
        time = ' '.join(fields.get('mtgTime',{}).get('text','').split())
        if not title or not time:
            continue
        try:
            start = datetime.strptime(time,'%m/%d/%Y %I:%M:%S %p')
        except ValueError:
            continue
        identities, documents, recordings = set(), [], []
        meeting_url = None
        for cell in row:
            for link in cell['links']:
                url = urljoin(source.url,link['url'])
                try:
                    validate_url(url)
                except ValueError:
                    continue
                p = urlsplit(url)
                if p.hostname != urlsplit(source.url).hostname:
                    continue
                query = parse_qs(p.query)
                if '/documents/downloadfile/' in p.path.lower():
                    identity = query.get('meetingId',[''])[0]
                    kind = KINDS.get(query.get('documentType',[''])[0])
                    if identity.isascii() and identity.isdecimal() and kind:
                        identities.add(identity)
                        document = {'kind':kind,'url':url}
                        if document not in documents:
                            documents.append(document)
                elif p.path.lower().endswith('/meetings/viewmeeting'):
                    identity = query.get('id',[''])[0]
                    if identity.isascii() and identity.isdecimal():
                        identities.add(identity)
                        meeting_url = meeting_url or url
                        if link['text'].strip() == 'View Media':
                            recording = {'url':url}
                            if recording not in recordings:
                                recordings.append(recording)
        if len(identities) != 1:
            continue
        identity = next(iter(identities))
        normalized = {'external_id':identity,'title':title,'meeting_date':start.date().isoformat(),
            'source_start':start.isoformat(),'time_zone_status':'unknown',
            'url':meeting_url or source.url,
            'documents':documents,'recordings':recordings,'agenda_items_availability':'unverified'}
        result.setdefault(identity,(normalized,{'cells':row},'meeting'))
    if not result:
        raise ValueError('No dated public OnBase rows with supplied meeting identities were found.')
    return list(result.values())
