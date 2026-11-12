"""Observed OnBase public meeting-name/date table with supplied download links."""

from datetime import datetime
from urllib.parse import parse_qs, urljoin, urlsplit

from ..compat import _table_rows
from .identification import validate_url

FORMAT = 'onbase-public-listing-html'
KINDS = {'1':'agenda','2':'minutes','3':'summary','5':'packet','6':'attachment'}


def listing_rows(source, content):
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
