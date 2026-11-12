from io import BytesIO
from unittest.mock import Mock

import pytest

from civic_data_connectors import fetch
from civic_data_connectors.compat import ImportInputError


class Response:
    def __init__(self, data=b'{"ok":true}', status=200, headers=None):
        self.data, self.status, self.headers = BytesIO(data), status, headers or {}

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def getheaders(self):
        return list(self.headers.items())

    def read1(self, size):
        return self.data.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def install(monkeypatch, responses):
    calls, connections = [], []

    class Connection:
        def __init__(self, host, port, timeout):
            self.host, self.port, self.timeout = host, port, timeout
            self.sock = Mock()
            self.closed = False
            connections.append(self)

        def request(self, method, target, body=None, headers=None):
            calls.append((self.host, method, target, body, headers))
            self._create_connection((self.host, self.port), self.timeout, None)

        def getresponse(self):
            return responses.pop(0)

        def close(self):
            self.closed = True

    monkeypatch.setattr(fetch.http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(fetch.http.client, "HTTPConnection", Connection)
    monkeypatch.setattr(fetch.socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, ("8.8.8.8", 443))])
    sockets = Mock(return_value=Mock())
    monkeypatch.setattr(fetch.socket, "create_connection", sockets)
    return calls, connections, sockets


def test_post_body_headers_and_actual_validated_socket(monkeypatch):
    calls, connections, sockets = install(monkeypatch, [Response()])
    url, data, _ = fetch.request_public("https://provider.example/calendar", method="POST", body=b"range",
                                        headers={"Content-Type": "application/json", "Authorization": "secret"},
                                        byte_limit=100)
    assert data == b'{"ok":true}' and url.endswith("/calendar")
    assert calls[0][1:4] == ("POST", "/calendar", b"range")
    assert sockets.call_args.args[0] == ("8.8.8.8", 443)
    assert connections[0].closed


def test_distinct_session_cookies_remain_private_transport_state(monkeypatch):
    response = Response()
    cookies = ("ASP.NET_SessionId=synthetic; Path=/; Secure", "balance=fixture; Path=/; Secure")
    response.getheaders = lambda: [("Set-Cookie", value) for value in cookies]
    install(monkeypatch, [response])
    result = fetch.request_public_response("https://provider.example/list", byte_limit=100)
    assert result.set_cookie_headers == cookies
    assert "set-cookie" not in result.headers
    assert "synthetic" not in repr(result) and "balance" not in repr(result)


def test_explicit_no_redirect_policy_stops_before_any_second_socket(monkeypatch):
    calls, connections, sockets = install(monkeypatch, [
        Response(status=302, headers={"Location": "/WebLink/Browse.aspx?id=2&repo=Other"})])
    with pytest.raises(ImportInputError, match="Redirects are disabled"):
        fetch.request_public_response("https://provider.example/WebLink/Browse.aspx?id=1&repo=Public",
                                      byte_limit=100, allow_redirects=False)
    assert len(calls) == len(connections) == sockets.call_count == 1
    assert connections[0].closed


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.2", "169.254.1.1", "::1", "fc00::1",
                                    "::ffff:127.0.0.1", "192.0.2.1", "224.0.0.1", "0.0.0.0"])
def test_private_mapped_reserved_dns_rejected(monkeypatch, address):
    _, _, sockets = install(monkeypatch, [])
    monkeypatch.setattr(fetch.socket, "getaddrinfo",
                        lambda *a, **k: [(None, None, None, None, (address, 443))])
    with pytest.raises(ImportInputError, match="public addresses"):
        fetch.request_public("https://provider.example", byte_limit=100)
    sockets.assert_not_called()


def test_mixed_dns_all_answers_must_be_public(monkeypatch):
    _, _, sockets = install(monkeypatch, [])
    monkeypatch.setattr(fetch.socket, "getaddrinfo", lambda *a, **k: [
        (None, None, None, None, ("8.8.8.8", 443)), (None, None, None, None, ("127.0.0.1", 443))])
    with pytest.raises(ImportInputError):
        fetch.request_public("https://provider.example", byte_limit=100)
    sockets.assert_not_called()


def test_cross_origin_rejected_by_default_and_headers_never_escape(monkeypatch):
    calls, _, _ = install(monkeypatch, [Response(status=302, headers={"Location": "https://cdn.example/file"})])
    with pytest.raises(ImportInputError, match="configured provider origins"):
        fetch.request_public("https://provider.example", byte_limit=100, headers={"Authorization": "secret"})
    assert len(calls) == 1
    calls, _, _ = install(monkeypatch, [Response(status=302, headers={"Location": "https://cdn.example/file"}),
                                      Response(b"pdf")])
    assert fetch.request_public("https://provider.example", byte_limit=100,
                                headers={"Authorization": "secret", "Cookie": "secret"},
                                allowed_origins={"https://provider.example", "https://cdn.example"})[1] == b"pdf"
    assert not ({"Authorization", "Cookie"} & calls[1][4].keys())


def test_redirect_rechecks_dns_and_closes_every_connection(monkeypatch):
    calls, connections, sockets = install(monkeypatch, [
        Response(status=302, headers={"Location": "/other"}), Response(b"ok")])
    answers = iter(["8.8.8.8", "127.0.0.1"])
    monkeypatch.setattr(fetch.socket, "getaddrinfo",
                        lambda *a, **k: [(None, None, None, None, (next(answers), 443))])
    with pytest.raises(ImportInputError, match="public addresses"):
        fetch.request_public("https://provider.example", byte_limit=100)
    assert len(calls) == 1 and connections[0].closed and sockets.call_count == 1


def test_stream_cap_and_no_full_in_memory_copy(monkeypatch):
    _, connections, _ = install(monkeypatch, [Response(b"1234567890")])
    sink = BytesIO()
    result = fetch.request_public("https://provider.example", byte_limit=10, destination=sink)
    assert result[1] == b"" and sink.getvalue() == b"1234567890" and connections[0].closed
    install(monkeypatch, [Response(b"12345678901")])
    with pytest.raises(ImportInputError, match="too large"):
        fetch.request_public("https://provider.example", byte_limit=10)


@pytest.mark.parametrize("url", ["https://user:secret@provider.example", "https://provider.example:444/a",
                                "file:///a", "https://provider.example/#fragment"])
def test_unsafe_url(url):
    with pytest.raises(ImportInputError):
        fetch.request_public(url, byte_limit=100)


@pytest.mark.parametrize("kwargs", [{"deadline_seconds": float("nan")}, {"deadline_seconds": 0},
                                   {"byte_limit": 0}, {"method": "DELETE"},
                                   {"headers": {"Host": "other.example"}},
                                   {"headers": {"x-test": "a\r\ninjected: true"}}])
def test_invalid_request_bounds_and_headers(kwargs):
    with pytest.raises(ImportInputError):
        fetch.request_public("https://provider.example", **({"byte_limit": 100} | kwargs))


def test_credentialed_post_never_replayed_cross_origin(monkeypatch):
    calls, _, _ = install(monkeypatch, [Response(status=307, headers={"Location": "https://cdn.example/a"})])
    with pytest.raises(ImportInputError, match="cannot redirect"):
        fetch.request_public("https://provider.example", byte_limit=100, method="POST", body=b"secret",
                             allowed_origins={"https://provider.example", "https://cdn.example"})
    assert len(calls) == 1


def test_https_downgrade_rejected(monkeypatch):
    install(monkeypatch, [Response(status=302, headers={"Location": "http://provider.example/a"})])
    with pytest.raises(ImportInputError, match="insecure"):
        fetch.request_public("https://provider.example", byte_limit=100,
                             allowed_origins={"https://provider.example", "http://provider.example"})


def test_structured_response_retains_bounded_error_and_protocol_metadata_without_secret_headers(monkeypatch):
    install(monkeypatch, [Response(b'{"conflict":true}', status=409, headers={
        "ETag": '"version-2"', "Upload-Offset": "1024", "Set-Cookie": "secret", "Authorization": "secret",
    })])
    result = fetch.request_public_response("https://provider.example", byte_limit=100)
    assert result.status == 409 and result.content == b'{"conflict":true}'
    assert result.headers == {"etag": '"version-2"', "upload-offset": "1024"}
    assert "secret" not in repr(result)
    install(monkeypatch, [Response(b"denied", status=403)])
    with pytest.raises(ImportInputError, match="HTTP 403"):
        fetch.request_public("https://provider.example", byte_limit=100)


@pytest.mark.parametrize("data,headers", [(b"short", {"Content-Length": "10"}),
                                         (b"", {"Content-Length": "101"}),
                                         (b"", {"Content-Length": "invalid"}),
                                         (b"ok", {"Content-Length": "2", "Transfer-Encoding": "chunked"})])
def test_declared_length_rejected_on_mismatch_or_ambiguity(monkeypatch, data, headers):
    install(monkeypatch, [Response(data, headers=headers)])
    with pytest.raises(ImportInputError):
        fetch.request_public("https://provider.example", byte_limit=100)


def test_dns_resolution_cannot_overrun_total_request_deadline(monkeypatch):
    import time
    install(monkeypatch, [])
    released = __import__("threading").Event()

    def stalled(*a, **k):
        released.wait(1)
        return [(None, None, None, None, ("8.8.8.8", 443))]

    monkeypatch.setattr(fetch.socket, "getaddrinfo", stalled)
    started = time.monotonic()
    try:
        with pytest.raises(ImportInputError):
            fetch.request_public("https://provider.example", byte_limit=100, deadline_seconds=0.03)
        assert time.monotonic() - started < 0.2
    finally:
        released.set()


def test_default_large_transfer_boundary_streams_without_parser_cap(monkeypatch):
    from civic_data_connectors import Bounds
    limit = Bounds().transfer_bytes

    class Generated(Response):
        def __init__(self, total):
            super().__init__()
            self.total = total

        def read1(self, size):
            amount = min(size, self.total)
            self.total -= amount
            return b"x" * amount

    class Sink:
        size = 0

        def write(self, chunk):
            self.size += len(chunk)

    install(monkeypatch, [Generated(limit)])
    sink = Sink()
    result = fetch.request_public("https://provider.example", byte_limit=limit, destination=sink)
    assert sink.size == 200 * 1024 * 1024 and result[1] == b""
    install(monkeypatch, [Generated(limit + 1)])
    with pytest.raises(ImportInputError, match="too large"):
        fetch.request_public("https://provider.example", byte_limit=limit, destination=Sink())
