"""Archived public item fields and exact persistence; no live vendor acceptance."""

import base64
from pathlib import Path

import pytest

from quorumrelay import Bounds, Source, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle

SOURCE = Source('boarddocs', 'https://go.boarddocs.com/vsba/fairfax/Board.nsf/Public',
                options={'boarddocs_committee_id': 'explicit-committee'})
FORMAT = 'boarddocs-public-item-html'
RAW = (Path(__file__).parent / 'fixtures/boarddocs-public/fairfax-item-20260716.html').read_bytes()


def test_native_item_public_body_fields_persist_search_reopen_and_exact_zip(tmp_path):
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'item.sqlite'))
    result = engine.normalize(SOURCE, RAW, input_format=FORMAT)
    assert result.status == 'completed', result.public_dict()
    bundle = result.data
    record = bundle['records'][0]
    assert record['identity']['external_id'] == 'DVSPWJ669D42'
    assert record['identity']['record_type'] == 'agenda_item'
    assert record['identity']['parent'] is None
    assert record['relationships'] == []
    value = record['normalized']
    assert value['title'] == '7.04 Skyview High School and Western Pyramids Boundary Study'
    assert value['source_fields']['Meeting'] == 'Jul 16, 2026 - Regular Meeting'
    assert value['source_fields']['Type'] == 'Action'
    assert 'quarterly updates' in value['description']
    assert 'Final Resolution: Motion Fails' in value['source_motion_text']
    assert value['documents'] == [] and value['recordings'] == []
    assert 'meeting_date' not in value and 'scheduled_at' not in value
    assert not any('focus()' in t['text'] for t in record['text'])
    for _ in range(2):
        assert engine.execute('import_bundle', {'bundle': bundle, 'persist': True}).status == 'completed'
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'item.sqlite'))
    found = reopened.execute('search', {'query': {'terms': ['quarterly updates']}})
    assert len(found.data['hits']) == 1
    archive = reopened.execute('export', {'bundle': bundle, 'format': 'zip'})
    restored = read_bundle(base64.b64decode(archive.data['content_base64']), format='zip')
    assert restored == bundle
    assert base64.b64decode(restored['capture']['content_base64']) == RAW


@pytest.mark.parametrize('before,after', [
    (b'security="public"', b'security="private"'),
    (b'value="DVSPWJ669D42"', b'value="OTHER"'),
    (b'base="DVSPWJ669D42"', b'base="OTHER"'),
    (b'/vsba/fairfax/Board.nsf/goto', b'/vsba/other/Board.nsf/goto'),
    (b'data-clipboard-text=', b'not-a-citation='),
    (b'>Subject</dt>', b'>Unmapped</dt>'),
    (b'key="publicbody"', b'key="privatebody"'),
    (b'id="view-agenda-item"', b'id="not-item"'),
])
def test_identity_publication_and_shape_mismatch_fail_without_inference(before, after):
    assert before in RAW
    result = create_engine().normalize(SOURCE, RAW.replace(before, after), input_format=FORMAT)
    assert result.status == 'failed', result.public_dict()


def test_duplicate_fields_and_identity_are_not_silently_selected():
    additions = [b'<input name="agenda-item-unique" value="OTHER">',
                 b'<dl class="row"><dt class="leftcol">Subject</dt><dd class="rightcol">Other</dd></dl>']
    for extra in additions:
        raw = RAW.replace(b'<div class="container">', b'<div class="container">' + extra)
        assert create_engine().normalize(SOURCE, raw, input_format=FORMAT).status == 'failed'


def test_private_script_and_template_content_cannot_become_supplied_public_text():
    extra = (b'<div class="private">HIDDEN_PRIVATE</div><template>HIDDEN_TEMPLATE</template>'
             b'<script>HIDDEN_SCRIPT</script><div security="private">HIDDEN_SECURITY</div>')
    raw = RAW.replace(b'key="publicbody" class="nostyle">', b'key="publicbody" class="nostyle">' + extra)
    assert raw != RAW
    result = create_engine().normalize(SOURCE, raw, input_format=FORMAT)
    assert result.status == 'completed', result.public_dict()
    assert 'HIDDEN_' not in str(result.data['records'][0])


def test_saved_parser_bounds_and_wrong_configured_site_fail():
    engine = create_engine()
    assert engine.normalize(SOURCE, RAW, input_format=FORMAT,
                            bounds=Bounds(parser_bytes=32)).status == 'failed'
    wrong = Source('boarddocs', 'https://go.boarddocs.com/oh/columbus/Board.nsf/Public',
                   options={'boarddocs_committee_id': 'explicit-committee'})
    assert engine.normalize(wrong, RAW, input_format=FORMAT).status == 'failed'
