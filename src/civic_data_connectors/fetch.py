"""Read explicitly selected public meeting material without local network access."""

from __future__ import annotations

import http.client
import ipaddress
import math
import re
import socket
from dataclasses import dataclass, field
from queue import Empty, Queue
from threading import BoundedSemaphore, Thread
from time import monotonic, sleep
from typing import BinaryIO
from urllib.parse import urljoin, urlsplit

from civic_data_connectors.compat import ImportInputError, read_json


_DNS_SLOTS = BoundedSemaphore(8)


def _resolve(host: str, port: int, deadline: float | None):
    if deadline is None:
        return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    remaining = deadline - monotonic()
    if remaining <= 0 or not _DNS_SLOTS.acquire(timeout=max(0, remaining)):
        raise TimeoutError("Public source DNS deadline exceeded")
    result = Queue(maxsize=1)

    def lookup():
        try:
            result.put((True, socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
        except Exception as error:
            result.put((False, error))
        finally:
            _DNS_SLOTS.release()

    # A stalled OS resolver must not block caller cancellation/deadlines or interpreter exit.
    Thread(target=lookup, daemon=True, name="civic-source-dns").start()
    try:
        succeeded, value = result.get(timeout=max(0, deadline - monotonic()))
    except Empty as error:
        raise TimeoutError("Public source DNS deadline exceeded") from error
    if not succeeded:
        raise value
    return value


def _public_addresses(host: str, port: int, deadline: float | None = None) -> tuple[str, ...]:
    answers = _resolve(host, port, deadline)
    addresses = tuple(dict.fromkeys(answer[4][0] for answer in answers))
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise ImportInputError("Meeting import URLs must resolve to public addresses.")
    if not addresses:
        raise ImportInputError("The public meeting host did not resolve.")
    return addresses


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    port = 443 if parsed.scheme == "https" else 80
    if (parsed.scheme not in {"https", "http"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in {None, port} or parsed.fragment):
        raise ImportInputError("Use a public HTTP(S) URL without credentials, custom port or fragment.")
    host = parsed.hostname.lower()
    return f"{parsed.scheme}://{'[' + host + ']' if ':' in host else host}"


@dataclass(frozen=True)
class PublicResponse:
    """Internal provider response; headers are not an engine public result.

    Header keys are lower-case. Only allowlisted protocol metadata is retained;
    callers must not serialize download/location tokens in public receipts.
    """

    url: str
    content: bytes = field(repr=False)
    media_type: str
    status: int
    headers: dict[str, str] = field(default_factory=dict, repr=False)


def request_public_response(
    url: str, *, byte_limit: int, method: str = "GET", body: bytes | None = None,
    headers: dict[str, str] | None = None, allowed_origins: set[str] | tuple[str, ...] | None = None,
    destination: BinaryIO | None = None, deadline_seconds: float = 45,
    _legacy_public_redirects: bool = False,
) -> PublicResponse:
    """Bounded provider request; resolve/validate the actual socket on every redirect.

    Origins are exact ``scheme://hostname`` values. Default is the original
    origin. Cross-origin redirects require an explicit allowlist, and no caller
    headers or request body cross that boundary. The compatibility GET wrapper
    alone retains legacy unrestricted-public redirect behavior.
    """
    if type(byte_limit) is not int or byte_limit <= 0:
        raise ImportInputError("The response byte limit must be a positive integer.")
    if (not isinstance(deadline_seconds, (int, float)) or not math.isfinite(deadline_seconds)
            or deadline_seconds <= 0):
        raise ImportInputError("The request deadline must be a positive finite duration.")
    method = method.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "HEAD"}:
        raise ImportInputError("This HTTP method is outside the connector request boundary.")
    if body is not None and not isinstance(body, bytes):
        raise ImportInputError("A request body must be bytes.")
    if body is not None and method in {"GET", "HEAD"}:
        raise ImportInputError("GET and HEAD requests cannot include a body.")
    try:
        initial_origin = _origin(url)
        origins = {initial_origin} if allowed_origins is None else set(allowed_origins)
        if any(_origin(origin) != origin for origin in origins) or initial_origin not in origins:
            raise ImportInputError("Allowed origins must explicitly include the selected exact source origin.")
    except (ValueError, TypeError) as error:
        raise ImportInputError("The request origin configuration is invalid.") from error
    caller_headers = dict(headers or {})
    for key, value in caller_headers.items():
        if (not isinstance(key, str) or not isinstance(value, str)
                or "\r" in key + value or "\n" in key + value
                or key.lower() in {"host", "content-length", "transfer-encoding", "connection"}):
            raise ImportInputError("The request contains an unsafe HTTP header.")
    current_origin = initial_origin
    deadline = monotonic() + deadline_seconds
    for _ in range(5):
        try:
            parsed = urlsplit(url)
            origin = _origin(url)
            if origin not in origins and not _legacy_public_redirects:
                raise ImportInputError("The redirect leaves the configured provider origins.")
            if origin != current_origin:
                # Never forward cookies, bearer keys, custom headers or bodies to a new origin.
                caller_headers = {}
                if body is not None or method not in {"GET", "HEAD"}:
                    raise ImportInputError("A credentialed/body request cannot redirect to another origin.")
            if initial_origin.startswith("https:") and origin.startswith("http:"):
                raise ImportInputError("An HTTPS source cannot redirect to insecure HTTP.")
            current_origin = origin
            port = 443 if parsed.scheme == "https" else 80
            addresses = _public_addresses(parsed.hostname, port, deadline)
            connection_type = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("Public meeting response timed out")
            connection = connection_type(parsed.hostname, port, timeout=min(8, remaining))

            def connect_to_public_address(_address, timeout, source_address):
                last_error = None
                for address in addresses[:3]:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Public meeting response timed out")
                    try:
                        return socket.create_connection((address, port), min(timeout, remaining), source_address)
                    except OSError as error:
                        last_error = error
                raise last_error or OSError("No public meeting address")

            connection._create_connection = connect_to_public_address
            target = parsed.path or "/"
            if parsed.query:
                target += "?" + parsed.query
            try:
                connection.request(method, target, body=body,
                                   headers={"User-Agent": "Civic data connectors/0.1", **caller_headers})
                if connection.sock is not None:
                    connection.sock.settimeout(max(0.001, min(8, deadline - monotonic())))
                with connection.getresponse() as response:
                    if response.status in {301, 302, 303, 307, 308} and response.getheader("Location"):
                        url = urljoin(url, response.getheader("Location"))
                        if response.status == 303:
                            method, body = "GET", None
                            caller_headers = {k: v for k, v in caller_headers.items()
                                              if k.lower() not in {"content-type", "content-encoding"}}
                        elif response.status in {301, 302} and method not in {"GET", "HEAD"}:
                            raise ImportInputError("The provider must confirm the redirected request method.")
                        continue
                    content = bytearray()
                    size = 0
                    declared = response.getheader("Content-Length")
                    if declared is not None:
                        if not declared.isascii() or not declared.isdecimal():
                            raise ImportInputError("The provider sent an invalid content length.")
                        declared = int(declared)
                        if declared > byte_limit:
                            raise ImportInputError("The public response is too large. Select a smaller input.")
                    if declared is not None and response.getheader("Transfer-Encoding"):
                        raise ImportInputError("The provider sent conflicting response length headers.")
                    while size <= byte_limit:
                        if monotonic() >= deadline:
                            raise TimeoutError("Public meeting response timed out")
                        if connection.sock is not None:
                            connection.sock.settimeout(max(0.001, min(8, deadline - monotonic())))
                        chunk = response.read1(min(65536, byte_limit + 1 - size))
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > byte_limit:
                            raise ImportInputError("The public response is too large. Select a smaller input.")
                        if destination is None:
                            content.extend(chunk)
                        else:
                            destination.write(chunk)
                    if declared is not None and method != "HEAD" and response.status not in {204, 304} and size != declared:
                        raise ImportInputError("The provider response ended before its declared content length.")
                    media_type = response.getheader("Content-Type", "").partition(";")[0].strip().lower()
                    metadata = {}
                    for name in ("ETag", "Last-Modified", "Content-Type", "Content-Length", "Content-Range",
                                 "Accept-Ranges", "Retry-After", "Location", "Upload-Offset", "Upload-Length",
                                 "Upload-Expires", "Upload-Concat", "Tus-Resumable", "X-Goog-Upload-Status",
                                 "X-Goog-Upload-Size-Received", "X-Goog-Upload-URL"):
                        value = response.getheader(name)
                        if value is not None:
                            metadata[name.lower()] = value
                    return PublicResponse(url, bytes(content), media_type, response.status, metadata)
            finally:
                connection.close()
        except ImportInputError:
            raise
        except (OSError, ValueError, http.client.HTTPException, UnicodeError) as error:
            raise ImportInputError("Could not read the public meeting URL. Save the source response and try again.") from error
    raise ImportInputError("The public meeting URL redirected too many times.")


def request_public(
    url: str, *, byte_limit: int, method: str = "GET", body: bytes | None = None,
    headers: dict[str, str] | None = None, allowed_origins: set[str] | tuple[str, ...] | None = None,
    destination: BinaryIO | None = None, deadline_seconds: float = 45,
    _legacy_public_redirects: bool = False,
) -> tuple[str, bytes, str]:
    """Compatibility tuple wrapper; non-2xx responses remain actionable errors."""
    response = request_public_response(
        url, byte_limit=byte_limit, method=method, body=body, headers=headers,
        allowed_origins=allowed_origins, destination=destination, deadline_seconds=deadline_seconds,
        _legacy_public_redirects=_legacy_public_redirects,
    )
    if not 200 <= response.status < 300:
        raise ImportInputError(f"The public meeting host returned HTTP {response.status}.")
    return response.url, response.content, response.media_type


def fetch_public(
    url: str, *, byte_limit: int, destination: BinaryIO | None = None, deadline_seconds: int = 45,
) -> tuple[str, bytes, str]:
    """Legacy GET interface; retained while all new requests use explicit origin scope."""
    return request_public(url, byte_limit=byte_limit, destination=destination,
                          deadline_seconds=deadline_seconds, _legacy_public_redirects=True)


def fetch_meeting_document(url: str, *, byte_limit: int) -> tuple[str, bytes, str]:
    """Resolve gWorks' public, short-lived download without saving its signed URL."""
    source = urlsplit(url)
    if (source.hostname == "api.gworks.cloud" and
            re.fullmatch(r"/cms/public/city/\d+/(?:agenda|minutes)/pdf/\d+/", source.path)):
        for delay in (0, 1, 2):
            if delay:
                sleep(delay)
            _, content, _ = fetch_public(url, byte_limit=64 * 1024)
            response = read_json(content)
            if isinstance(response, dict) and response.get("status") == "ready":
                signed_url = response.get("signedUrl")
                if isinstance(signed_url, str):
                    return fetch_public(signed_url, byte_limit=byte_limit)
                break
            if not isinstance(response, dict) or response.get("status") != "wait":
                break
        raise ImportInputError("gWorks has not made this PDF available. Retry from the saved import.")
    return fetch_public(url, byte_limit=byte_limit)
