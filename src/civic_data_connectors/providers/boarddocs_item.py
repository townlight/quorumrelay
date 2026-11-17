"""Saved public item fragments with explicit native identity, not inferred parents."""

from .boarddocs_public import _configured_source, _MEETING_ID
from .escribe_detail import Page, Node
from .native import make_bundle

FORMAT = 'boarddocs-public-item-html'


def _clean(node):
    children = []
    for child in node.children:
        if isinstance(child, Node):
            if (child.tag in {'script', 'style', 'template'}
                    or child.attrs.get('security', 'public') != 'public'
                    or any(marker in value.casefold() for value in child.classes()
                           for marker in ('private', 'admin', 'executive'))):
                continue
            _clean(child)
        children.append(child)
    node.children = children


def parse_bundle(source, namespace, content):
    parts, site, _ = _configured_source(source)
    page = Page()
    page.feed(content.decode('utf-8-sig'))
    _clean(page.root)
    views = [n for n in page.root.walk() if n.attrs.get('id') == 'view-agenda-item']
    if len(views) != 1 or views[0].attrs.get('security') != 'public':
        raise ValueError('Supply one explicitly public native agenda item.')
    view = views[0]
    inputs = [n for n in view.walk() if n.tag == 'input' and n.attrs.get('name') == 'agenda-item-unique']
    identity = inputs[0].attrs.get('value') if len(inputs) == 1 else None
    if not isinstance(identity, str) or not _MEETING_ID.fullmatch(identity):
        raise ValueError('The native item identity is missing or ambiguous.')
    citation = f'{parts.scheme}://{parts.netloc}/{site}/Board.nsf/goto?open&id={identity}'
    clips = [n.attrs['data-clipboard-text'] for n in page.root.walk() if 'data-clipboard-text' in n.attrs]
    bases = [n.attrs.get('base') for n in page.root.walk() if n.tag == 'button'
             and n.classes() & {'previous', 'next'}]
    if clips != [citation] or len(bases) != 2 or any(value != identity for value in bases):
        raise ValueError('Item citation/navigation must match the configured site and native identity.')
    fields = {}
    for row in view.walk():
        if row.tag != 'dl' or 'row' not in row.classes():
            continue
        labels = [n.text() for n in row.walk() if n.tag == 'dt' and 'leftcol' in n.classes()]
        values = [n.text() for n in row.walk() if n.tag == 'dd' and 'rightcol' in n.classes()]
        if len(labels) != 1 or len(values) != 1 or labels[0] in fields:
            raise ValueError('Item fields are incomplete or ambiguous.')
        fields[labels[0]] = values[0]
    bodies = [n for n in view.walk() if n.attrs.get('key') == 'publicbody']
    if not fields.get('Subject') or len(bodies) != 1:
        raise ValueError('The public subject/body contract is absent.')
    motion_text = ' '.join(n.text() for n in view.walk() if 'motions' in n.classes())
    normalized = {'external_id': identity, 'title': fields['Subject'], 'url': citation,
                  'description': bodies[0].text(), 'source_fields': fields,
                  'source_motion_text': motion_text, 'documents': [], 'recordings': [],
                  'documents_availability': 'separate_public_files_response_not_supplied',
                  'meeting_identity_availability': 'not_asserted_in_fragment',
                  'section_identity_availability': 'not_asserted_in_fragment'}
    bundle = make_bundle(source, namespace, content, FORMAT,
                         [(normalized, {'native_citation': citation, 'fields': fields}, 'agenda_item')])
    bundle['records'][0]['text'] = [{'field': key, 'text': text, 'citation_url': citation}
        for key, text in [('publicbody', normalized['description']),
                          ('recommended_action', fields.get('Recommended Action', '')),
                          ('motion_text', motion_text)] if text]
    bundle['extensions']['boarddocs_item'] = {
        'provenance': 'third_party_archived_fragment_not_official_vendor_acceptance',
        'parent_binding': 'none_no_title_date_or_category_join',
        'motion_mapping': 'supplied_text_only_no_structured_motion_or_vote_inference'}
    return bundle
