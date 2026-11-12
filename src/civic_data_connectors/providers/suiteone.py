"""Public SuiteOne Older Meetings controls observed in the configured root page."""

from html.parser import HTMLParser
import re
from urllib.parse import urlencode

FIELDS = ('yearFrom', 'groupId', 'uniqueId', 'categoryId', 'groupName')


class _Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.controls = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag != 'a' or 'older_meetings_click' not in values.get('class', '').split():
            return
        if values.get('href') != '#':
            raise ValueError('The SuiteOne older-group control changed its public target.')
        fields = {name: values.get('data-' + name.lower()) for name in FIELDS}
        validate_fields(fields)
        if fields not in self.controls:
            self.controls.append(fields)


def validate_fields(fields):
    if not isinstance(fields, dict) or set(fields) != set(FIELDS):
        raise ValueError('Invalid SuiteOne public group fields.')
    if any(not isinstance(v, str) or not v or len(v) > 256 for v in fields.values()):
        raise ValueError('Invalid SuiteOne public group field value.')
    if not re.fullmatch(r'20[0-9]{2}', fields['yearFrom']):
        raise ValueError('Invalid SuiteOne public group year.')
    if any(not re.fullmatch(r'[0-9]{1,12}', fields[key]) for key in ('groupId', 'categoryId')):
        raise ValueError('Invalid SuiteOne public group identifiers.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', fields['uniqueId']):
        raise ValueError('Invalid SuiteOne public group control identifier.')


def controls(content):
    parser = _Controls()
    parser.feed(content.decode('utf-8', errors='replace'))
    if len(parser.controls) > 100:
        raise ValueError('The public SuiteOne group controls exceed the bounded limit.')
    return parser.controls


def form_body(fields):
    validate_fields(fields)
    return urlencode({**fields, 'psize': 10, 'page': 0}).encode()
