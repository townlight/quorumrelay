"""Field-level synthetic write/readback coverage for documented Legistar JSON."""
import pytest

from test_write_providers import DocumentedNetwork, make_engine, response, run


class RecordingNetwork(DocumentedNetwork):
    def __init__(self, mismatch=None):
        super().__init__('legistar')
        self.mismatch = mismatch
        self.sent = []
        self.mutated = False

    def legistar(self, parsed, method, fields):
        if method in {'POST', 'PUT'}:
            self.sent.append((method, dict(fields)))
            self.mutated = True
            result = super().legistar(parsed, method, fields)
            if self.mismatch:
                row = self.rows[parsed.path if method == 'PUT' else parsed.path + '/1']
                row[self.mismatch] = False if isinstance(row[self.mismatch], bool) else 'different'
            return result
        if method == 'GET' and self.mutated and self.mismatch and parsed.path in self.rows:
            row = dict(self.rows[parsed.path])
            row[self.mismatch] = False if isinstance(row[self.mismatch], bool) else 'different'
            return response(row)
        return super().legistar(parsed, method, fields)


@pytest.mark.parametrize('entity', ['event', 'matter_attachment'])
def test_legistar_media_or_link_create_update_receipt_and_replay(tmp_path, entity):
    network = RecordingNetwork()
    engine, context, _, source = make_engine(tmp_path, 'legistar', [f'{entity}:create', f'{entity}:update'], network)
    fields = ({'EventDate': '2026-11-11', 'EventLocation': 'Room',
               'EventMedia': 'https://example.org/media', 'EventVideoPath': 'https://example.org/video'}
              if entity == 'event' else
              {'MatterAttachmentName': 'Link', 'MatterAttachmentIsHyperlink': True,
               'MatterAttachmentHyperlink': 'https://example.org/attachment',
               'MatterAttachmentShowOnInternetPage': False})
    change = {'key': 'field-test', 'entity': entity, 'operation': 'create', 'fields': fields}
    if entity == 'matter_attachment':
        change.update(parent_id=9, meeting_id='9')
    for operation in ('create', 'update'):
        if operation == 'update':
            if entity == 'event':
                fields = {'EventMedia': 'https://example.org/new-media',
                          'EventVideoPath': 'https://example.org/new-video'}
            else:
                fields = {'MatterAttachmentHyperlink': 'https://example.org/new-link',
                          'MatterAttachmentShowOnInternetPage': True}
            change.update(operation='update', resource_id=1, fields=fields)
        result, approval = run(engine, context, source, change)
        assert result.status == 'completed', result.public_dict()
        assert all(network.sent[-1][1][key] == value for key, value in fields.items())
        assert all(result.data['items'][0]['readback'][key] == value for key, value in fields.items())
        assert result.data['items'][0]['resource_id'] == 1
        if operation == 'update':
            preserved = ({'EventId': 1, 'EventDate': '2026-11-11', 'EventLocation': 'Room'}
                         if entity == 'event' else
                         {'MatterAttachmentId': 1, 'MatterAttachmentName': 'Link',
                          'MatterAttachmentIsHyperlink': True})
            assert all(network.sent[-1][1][key] == value for key, value in preserved.items())
            assert all(result.data['items'][0]['readback'][key] == value for key, value in preserved.items())
        receipt = engine.execute('receipt', {'plan_id': approval['plan_id']}, context=context)
        assert receipt.status == 'completed' and receipt.data['plan_hash'] == approval['plan_hash']
        calls = list(network.calls)
        assert engine.execute('commit_write', approval, context=context).status == 'completed'
        assert network.calls == calls
    assert not any(path.endswith('/File') for _, path in network.calls)
    assert all('MatterAttachmentBinary' not in body for _, body in network.sent)


@pytest.mark.parametrize('field', ['EventMedia', 'EventVideoPath', 'MatterAttachmentHyperlink',
                                  'MatterAttachmentShowOnInternetPage'])
def test_legistar_media_or_link_mismatch_is_uncertain_without_duplicate(tmp_path, field):
    entity = 'event' if field.startswith('Event') else 'matter_attachment'
    fields = ({'EventDate': '2026-11-11', 'EventMedia': 'https://example.org/media',
               'EventVideoPath': 'https://example.org/video'} if entity == 'event' else
              {'MatterAttachmentName': 'Link', 'MatterAttachmentIsHyperlink': True,
               'MatterAttachmentHyperlink': 'https://example.org/link',
               'MatterAttachmentShowOnInternetPage': True})
    network = RecordingNetwork(field)
    engine, context, _, source = make_engine(tmp_path, 'legistar', [f'{entity}:create'], network)
    change = {'key': 'mismatch', 'entity': entity, 'operation': 'create', 'fields': fields}
    if entity == 'matter_attachment':
        change.update(parent_id=9, meeting_id='9')
    result, approval = run(engine, context, source, change)
    assert result.status == 'partial' and result.data['items'][0]['state'] == 'uncertain'
    assert result.data['items'][0]['readback'][field] != fields[field]
    assert engine.execute('commit_write', approval, context=context).status == 'partial'
    assert sum(method == 'POST' for method, _ in network.calls) == 1
    assert not any(path.endswith('/File') for _, path in network.calls)
