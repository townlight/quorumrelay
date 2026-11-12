"""Provider retrieval boundaries; credentials and browser state are caller-owned."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, BinaryIO, Protocol


@dataclass(frozen=True)
class Response:
    url: str
    content: bytes = field(repr=False)
    content_type: str = "application/octet-stream"
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict, repr=False)
    set_cookie_headers: tuple[str, ...] = field(default=(), repr=False)


class RetrievalError(ValueError):
    def __init__(self, code: str, *, status: int | None = None):
        super().__init__(code)
        self.code = code
        self.status = status


class Transport(Protocol):
    """Implementations must enforce public DNS/socket, TLS, redirect and byte guards."""

    def request(self, url: str, *, method: str = "GET", body: bytes | None = None,
                headers: dict[str, str] | None = None, byte_limit: int,
                deadline_seconds: float, allowed_origins: tuple[str, ...],
                destination: BinaryIO | None = None, allow_redirects: bool = True) -> Response: ...


class BrowserSession(Protocol):
    """Explicitly injected, isolated browser, not an unrestricted browser proxy.

    The implementation owns DNS/socket/redirect/TLS enforcement for ALL browser
    requests, including subresources; deadline and response byte caps apply before
    materialization. A normal unguarded Playwright browser does not meet this
    contract. No concrete live browser is started by the package.
    """

    guarded: bool
    origin: str

    def open_and_catch(self, url: str, response_path: str, *, byte_limit: int,
                       deadline_seconds: float) -> Any: ...

    def post_json(self, path: str, data: dict, headers: dict[str, str], *,
                  byte_limit: int, deadline_seconds: float) -> Any: ...


class PublicTransport:
    def request(self, url, *, method="GET", body=None, headers=None, byte_limit,
                deadline_seconds, allowed_origins, destination=None, allow_redirects=True):
        # Resolve lazily so consumers can import the SDK without opening sockets.
        from .. import fetch
        request = getattr(fetch, "request_public_response", None)
        if request is None:
            raise ValueError("Scoped guarded retrieval is not available; supply a saved capture.")
        else:
            response = request(
                url, method=method, body=body, headers=headers, byte_limit=byte_limit,
                deadline_seconds=deadline_seconds, allowed_origins=allowed_origins,
                destination=destination,
                allow_redirects=allow_redirects,
            )
        return Response(response.url, response.content, response.media_type,
                        response.status, response.headers, response.set_cookie_headers)


def _origin(url: str) -> str:
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    port = parsed.port
    suffix = f":{port}" if port and port != (443 if parsed.scheme == "https" else 80) else ""
    return f"{parsed.scheme}://{parsed.hostname}{suffix}"
