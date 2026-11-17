import base64
import json

import pytest

from quorumrelay import Bounds, OperationContext, create_engine
from quorumrelay.storage import SQLiteStorage
from civic_data_connectors.interchange import read_bundle
from civic_data_connectors.providers import iqm2_soap
from civic_data_connectors.providers.contracts import Response
from test_iqm2_soap import (URL, SOURCE, SOURCE_MINUTES, agenda_response, minutes_response,
                           agenda_response_without_meeting, minutes_response_without_meeting)

NS = iqm2_soap.namespace(SOURCE)
VERSION = '8.11.3.1452015'
CONNECTION_ID = '0123456789ABCDEF'
AUTH = ('Basic:clerk@City of Test:' + 'a' * 32 + ':' + CONNECTION_ID + ':M-127.0.0.1:'
        'MinuteTraq:' + VERSION + ':.NET 4.8')
PRIVATE_VALUES = (AUTH, 'a' * 32, CONNECTION_ID, 'DEADBEEF', 'client-secret')


def request_dates():
    return {'minutetraq_file_since': '2026-11-17T00:00:00',
            'minutetraq_public_file_since': '2026-11-17T00:00:00Z'}


def context(kind='agenda', **overrides):
    document_id = 77 if kind == 'agenda' else 88
    config = {
        'tenant': 'test-client', 'origin': 'https://test.iqm2.com',
        'agency': 'City of Test', 'allowed_namespaces': [NS],
        'meeting_ids': [501], 'document_ids': [document_id],
        'document_kind': kind, 'authorization_header': AUTH,
        'client_version': VERSION,
    }
    config.update(overrides)
    return OperationContext(tenant='test-client', allowed_namespaces=frozenset({NS}),
                            credentials={'iqm2': config})


class Server:
    def __init__(self, raw=None, url=URL, mime='text/xml; charset=utf-8', status=200):
        self.calls = []
        self.raw = agenda_response() if raw is None else raw
        self.url = url
        self.mime = mime
        self.status = status
        self.after = lambda: None
        self.headers = {'ConnectionID': 'DEADBEEF'}

    def request(self, url, **options):
        self.calls.append((url, options))
        self.after()
        return Response(self.url, self.raw, self.mime, self.status, headers=self.headers)


def fetch(server, source=SOURCE, ctx=None, bounds=None):
    result = create_engine(provider_transport=server).fetch(
        source, request_dates(), bounds=bounds, context=ctx or context())
    return result


def test_agenda_read_posts_one_exact_wrapped_literal_and_redacts_session(tmp_path):
    server = Server(agenda_response())
    ctx = context()
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'iqm2.sqlite'), provider_transport=server)
    result = engine.fetch(SOURCE, request_dates(), context=ctx)
    assert result.status == 'completed', result.public_dict()
    assert len(server.calls) == 1
    url, options = server.calls[0]
    assert url == URL
    assert options['method'] == 'POST'
    assert options['allow_redirects'] is False
    assert options['allowed_origins'] == ('https://test.iqm2.com',)
    headers = options['headers']
    assert headers['Content-Type'] == 'text/xml;charset=utf-8'
    assert headers['SOAPAction'] == '"' + iqm2_soap.SERVICE_NS + '/AgendaGet"'
    assert headers['Authorization'] == AUTH
    assert headers['MinuteTraqVersion'] == VERSION
    body = options['body']
    assert b'<AgendaGet xmlns="' + iqm2_soap.SERVICE_NS.encode() + b'">' in body
    assert (body.index(b'<AgendaID>77</AgendaID>') < body.index(b'<MeetingID>501</MeetingID>')
            < body.index(b'<GetFileDataIfNewerThan>') < body.index(b'<GetPublicFileDataIfNewerThan>'))
    assert b'2026-11-17T00:00:00' in body and b'2026-11-17T00:00:00Z' in body
    public = json.dumps(result.public_dict(), sort_keys=True)
    capture = json.dumps(result.data['capture'], sort_keys=True)
    for secret in PRIVATE_VALUES:
        assert secret not in public
        assert secret not in capture
    imported = engine.execute('import_bundle', {'bundle': result.data, 'persist': True}, context=ctx)
    assert imported.status == 'completed', imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'iqm2.sqlite'))
    found = reopened.execute('search', {'query': {'terms': ['Bridge repair']}}, context=ctx)
    assert len(found.data['hits']) == 1, found.public_dict()
    for format in ('json', 'jsonl', 'zip'):
        exported = engine.execute('export', {'bundle': result.data, 'format': format}, context=ctx)
        payload = json.dumps(exported.public_dict(), sort_keys=True)
        decoded = read_bundle(base64.b64decode(exported.data['content_base64']), format=format)
        decoded_payload = json.dumps(decoded, sort_keys=True)
        for secret in PRIVATE_VALUES:
            assert secret not in payload
            assert secret not in decoded_payload
        assert decoded == result.data


def test_minutes_read_uses_minutes_id_and_exact_order():
    server = Server(minutes_response())
    result = fetch(server, source=SOURCE_MINUTES, ctx=context('minutes'))
    assert result.status == 'completed', result.public_dict()
    assert len(server.calls) == 1
    _, options = server.calls[0]
    assert options['headers']['SOAPAction'] == '"' + iqm2_soap.SERVICE_NS + '/MinutesGet"'
    body = options['body']
    assert b'<MinutesGet xmlns="' + iqm2_soap.SERVICE_NS.encode() + b'">' in body
    assert (body.index(b'<MinutesID>88</MinutesID>') < body.index(b'<MeetingID>501</MeetingID>')
            < body.index(b'<GetFileDataIfNewerThan>') < body.index(b'<GetPublicFileDataIfNewerThan>'))
    assert [record['identity']['record_type'] for record in result.data['records']] == [
        'meeting', 'minutes', 'minutes_item']


def test_agenda_read_accepts_absent_meeting_and_roundtrips(tmp_path):
    server = Server(agenda_response_without_meeting())
    ctx = context()
    engine = create_engine(storage=SQLiteStorage(tmp_path / 'iqm2-fetch-absent.sqlite'),
                           provider_transport=server)
    result = engine.fetch(SOURCE, request_dates(), context=ctx)
    assert result.status == 'completed', result.public_dict()
    assert len(server.calls) == 1
    records = result.data['records']
    assert [record['identity']['record_type'] for record in records] == ['agenda', 'agenda_item', 'agenda_item']
    agenda = records[0]
    expected_meeting = {'provider': 'iqm2', 'namespace': agenda['identity']['namespace'],
                        'record_type': 'meeting', 'external_id': '501', 'parent': None,
                        'derivation': 'provider_identifier',
                        'stability': 'Provider-issued identifier within the configured namespace.'}
    assert agenda['identity']['parent'] == expected_meeting
    assert all(record['identity']['record_type'] != 'meeting' for record in records)
    found = engine.execute('search', {'bundle': result.data, 'query': {'terms': ['Bridge repair']}}, context=ctx)
    assert len(found.data['hits']) == 1, found.public_dict()
    imported = engine.execute('import_bundle', {'bundle': result.data, 'persist': True}, context=ctx)
    assert imported.status == 'completed', imported.public_dict()
    reopened = create_engine(storage=SQLiteStorage(tmp_path / 'iqm2-fetch-absent.sqlite'))
    found = reopened.execute('search', {'query': {'terms': ['Bridge repair']}}, context=ctx)
    assert len(found.data['hits']) == 1, found.public_dict()
    for format in ('json', 'jsonl', 'zip'):
        exported = engine.execute('export', {'bundle': result.data, 'format': format}, context=ctx)
        assert read_bundle(base64.b64decode(exported.data['content_base64']), format=format) == result.data


def test_minutes_read_accepts_absent_meeting_and_roundtrips():
    server = Server(minutes_response_without_meeting())
    result = fetch(server, source=SOURCE_MINUTES, ctx=context('minutes'))
    assert result.status == 'completed', result.public_dict()
    records = result.data['records']
    assert [record['identity']['record_type'] for record in records] == ['minutes', 'minutes_item']
    minutes = records[0]
    expected_meeting = {'provider': 'iqm2', 'namespace': minutes['identity']['namespace'],
                        'record_type': 'meeting', 'external_id': '501', 'parent': None,
                        'derivation': 'provider_identifier',
                        'stability': 'Provider-issued identifier within the configured namespace.'}
    assert minutes['identity']['parent'] == expected_meeting
    assert records[1]['identity']['parent'] == minutes['identity']
    assert not any(record['identity']['record_type'] == 'meeting' for record in records)
    found = create_engine(provider_transport=server).execute(
        'search', {'bundle': result.data, 'query': {'terms': ['Approved minutes']}})
    assert len(found.data['hits']) == 1, found.public_dict()
    for format in ('json', 'jsonl', 'zip'):
        exported = create_engine(provider_transport=server).execute(
            'export', {'bundle': result.data, 'format': format})
        assert read_bundle(base64.b64decode(exported.data['content_base64']), format=format) == result.data


@pytest.mark.parametrize('case', [
    'tenant', 'origin', 'agency', 'namespace', 'meeting', 'document', 'kind',
    'header_crlf', 'header_segments', 'header_prefix', 'header_hash',
    'header_connection', 'header_source', 'header_literal', 'header_version',
    'client_version', 'date_missing', 'date_bad', 'date_offset_15',
    'date_offset_minutes', 'date_offset_14_nonzero', 'attachment', 'cancel',
])
def test_invalid_scope_credentials_threshold_or_cancel_never_calls(case):
    server = Server()
    ctx = context()
    bounds = Bounds()
    request = request_dates()
    config = ctx.credentials['iqm2']
    if case == 'tenant':
        config['tenant'] = 'other'
    elif case == 'origin':
        config['origin'] = 'https://other.iqm2.com'
    elif case == 'agency':
        config['agency'] = 'Other Agency'
    elif case == 'namespace':
        config['allowed_namespaces'] = ['//other']
    elif case == 'meeting':
        config['meeting_ids'] = [999]
    elif case == 'document':
        config['document_ids'] = [999]
    elif case == 'kind':
        config['document_kind'] = 'minutes'
    elif case == 'header_crlf':
        config['authorization_header'] = AUTH.replace('MinuteTraq', 'MinuteTraq\r\nX')
    elif case == 'header_segments':
        config['authorization_header'] = AUTH + ':extra'
    elif case == 'header_prefix':
        config['authorization_header'] = AUTH.replace('Basic:', 'Admin:', 1)
    elif case == 'header_hash':
        config['authorization_header'] = AUTH.replace('a' * 32, 'z' * 32)
    elif case == 'header_connection':
        config['authorization_header'] = AUTH.replace(':' + CONNECTION_ID + ':', ':' + CONNECTION_ID + '0:')
    elif case == 'header_source':
        config['authorization_header'] = AUTH.replace('M-127.0.0.1', 'X-127.0.0.1')
    elif case == 'header_literal':
        config['authorization_header'] = AUTH.replace('MinuteTraq', 'MinuteTrax')
    elif case == 'header_version':
        config['authorization_header'] = AUTH.replace(VERSION, '8.11.3')
    elif case == 'client_version':
        config['client_version'] = '8.11.3'
    elif case == 'date_missing':
        request.pop('minutetraq_public_file_since')
    elif case == 'date_bad':
        request['minutetraq_file_since'] = '2026-11-17'
    elif case == 'date_offset_15':
        request['minutetraq_file_since'] = '2026-11-17T00:00:00+15:00'
    elif case == 'date_offset_minutes':
        request['minutetraq_file_since'] = '2026-11-17T00:00:00+00:60'
    elif case == 'date_offset_14_nonzero':
        request['minutetraq_file_since'] = '2026-11-17T00:00:00+14:01'
    elif case == 'attachment':
        request['attachment'] = {'name': 'outbound'}
    else:
        ctx.cancellation.set()
    result = create_engine(provider_transport=server).fetch(SOURCE, request, bounds=bounds, context=ctx)
    assert result.status in {'failed', 'cancelled'}, result.public_dict()
    assert not server.calls
    public = json.dumps(result.public_dict(), sort_keys=True)
    for secret in PRIVATE_VALUES:
        assert secret not in public


def test_max_records_zero_rejected_at_bounds_construction():
    server = Server()
    with pytest.raises(ValueError):
        create_engine(provider_transport=server).fetch(
            SOURCE, request_dates(), bounds=Bounds(max_records=0), context=context())
    assert not server.calls


def test_transport_runtime_error_is_redacted():
    secret = 'transport-secret-message'

    class FailingServer(Server):
        def request(self, url, **options):
            self.calls.append((url, options))
            raise RuntimeError(secret)

    server = FailingServer()
    result = fetch(server)
    assert result.status == 'failed'
    public = json.dumps(result.public_dict(), sort_keys=True)
    assert secret not in public
    assert 'minutetraq_unavailable' in public
    assert len(server.calls) == 1


def test_exact_14h_offsets_accepted_for_request_dates():
    for offset in ('+14:00', '-14:00'):
        server = Server()
        request = {'minutetraq_file_since': '2026-11-17T00:00:00' + offset,
                   'minutetraq_public_file_since': '2026-11-17T00:00:00' + offset}
        result = create_engine(provider_transport=server).fetch(
            SOURCE, request, context=context())
        assert result.status == 'completed', result.public_dict()
        assert len(server.calls) == 1


@pytest.mark.parametrize('case', [
    'wrong_url', 'redirect', 'status_401', 'status_403', 'status_500', 'mime',
    'bytes', 'records', 'deadline', 'cancel_after', 'wrong_operation',
])
def test_response_boundaries(case, monkeypatch):
    server = Server(agenda_response())
    ctx = context()
    bounds = Bounds()
    if case == 'wrong_url':
        server.url = URL + '?changed=1'
    elif case == 'redirect':
        server.url = URL.replace('test.', 'other.')
    elif case == 'status_401':
        server.status = 401
    elif case == 'status_403':
        server.status = 403
    elif case == 'status_500':
        server.status = 500
    elif case == 'mime':
        server.mime = 'text/html'
    elif case == 'bytes':
        server.raw = agenda_response() + b' ' * 4096
        bounds = Bounds(transfer_bytes=len(agenda_response()))
    elif case == 'records':
        bounds = Bounds(max_records=2)
    elif case == 'deadline':
        now = [100.0]
        monkeypatch.setattr(iqm2_soap, 'monotonic', lambda: now[0])
        server.after = lambda: now.__setitem__(0, 10000.0)
    elif case == 'cancel_after':
        server.after = ctx.cancellation.set
    else:
        server.raw = minutes_response()
    result = create_engine(provider_transport=server).fetch(
        SOURCE, request_dates(), bounds=bounds, context=ctx)
    assert result.status == ('cancelled' if case == 'cancel_after' else 'failed'), result.public_dict()
    assert len(server.calls) == 1
    public = json.dumps(result.public_dict(), sort_keys=True)
    for secret in PRIVATE_VALUES:
        assert secret not in public
