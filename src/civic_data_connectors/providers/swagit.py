"""Observed Swagit public archive/search tables, separate from compatibility inputs."""

from datetime import datetime
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from ..compat import _table_rows
from .identification import validate_url

FORMAT = 'swagit-listing-html'


def listing_rows(source, content, *, allow_empty=False):
    result = {}
    for cells in _table_rows(content):
        if not cells or not cells[0]['links']:
            continue
        link = cells[0]['links'][0]
        url = urljoin(source.url, link['url'])
        parts = urlsplit(url)
        match = re.fullmatch(r'/videos/([1-9][0-9]*)/?', parts.path)
        if not match or parts.hostname != urlsplit(source.url).hostname:
            continue
        validate_url(url)
        identity = match[1]
        if parts.query:
            # Sound Search supplies timestamp links, not transcript text.
            query = parse_qs(parts.query)
            if (set(query) == {'ts'} and len(query['ts']) == 1
                    and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', query['ts'][0]) and identity in result):
                normalized = result[identity][0]
                links = normalized.setdefault('search_match_urls', [])
                for cell in cells:
                    for candidate in cell['links']:
                        target = urljoin(source.url, candidate['url'])
                        p = urlsplit(target)
                        q = parse_qs(p.query)
                        if (p.hostname == parts.hostname and p.path == parts.path and set(q) == {'ts'}
                                and len(q['ts']) == 1 and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', q['ts'][0])
                                and target not in links):
                            links.append(target)
            continue
        title = ' '.join(link['text'].split())
        date_text = ' '.join(cells[1]['text'].split()) if len(cells) > 1 else ''
        try:
            day = datetime.strptime(date_text, '%b %d, %Y').date().isoformat()
        except ValueError:
            continue
        if not title:
            continue
        documents = []
        for cell in cells[2:]:
            for candidate in cell['links']:
                target = urljoin(source.url, candidate['url'])
                p = urlsplit(target)
                if (p.scheme == 'https' and p.hostname == parts.hostname
                        and p.path == f'/videos/{identity}/agenda' and not p.query and not p.fragment):
                    document = {'kind': 'agenda', 'url': target, 'availability': 'supplied_link'}
                    if document not in documents:
                        documents.append(document)
        normalized = {'external_id': identity, 'title': title, 'meeting_date': day, 'url': url,
                      'documents': documents, 'recordings': [{'url': url}],
                      'time_zone_status': 'unknown', 'agenda_items_availability': 'unverified'}
        result.setdefault(identity, (normalized, {'cells': cells}, 'meeting'))
    if not result and not allow_empty:
        raise ValueError('The public Swagit table has no recognizable dated video rows.')
    return list(result.values())
