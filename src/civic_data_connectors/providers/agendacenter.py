"""Published Agenda Center year/category read controls; no JavaScript execution."""

from html.parser import HTMLParser
import re
from urllib.parse import urlencode


class _Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.years = []
        self.inputs = {'searchField': '', 'StartDatePicker': '', 'EndDatePicker': ''}

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == 'input' and fields.get('id') in self.inputs:
            self.inputs[fields['id']] = fields.get('value') or ''
        if tag != 'a':
            return
        match = re.fullmatch(r"javascript:changeYear\(\s*(20[0-9]{2})\s*,\s*([1-9][0-9]{0,11})\s*,\s*'[^'<>]{1,128}'\s*\)", fields.get('href', ''))
        if match and match.groups() not in self.years:
            self.years.append(match.groups())


def controls(content):
    parser = _Controls()
    parser.feed(content.decode('utf-8', errors='replace'))
    if len(parser.years) > 1000 or any(len(v) > 256 for v in parser.inputs.values()):
        raise ValueError('Agenda Center public controls exceed their bounds.')
    return [{'year': year, 'catID': category, 'term': parser.inputs['searchField'],
             'startDate': parser.inputs['StartDatePicker'], 'endDate': parser.inputs['EndDatePicker'],
             'prevVersionScreen': 'false'} for year, category in parser.years]


def form_body(fields):
    if (not isinstance(fields, dict) or set(fields) != {'year','catID','term','startDate','endDate','prevVersionScreen'}
            or any(not isinstance(v, str) or len(v) > 256 for v in fields.values())
            or re.fullmatch(r'20[0-9]{2}', fields['year']) is None
            or re.fullmatch(r'[1-9][0-9]{0,11}', fields['catID']) is None
            or fields['prevVersionScreen'] != 'false'):
        raise ValueError('Invalid Agenda Center public year control.')
    return urlencode(fields).encode()
