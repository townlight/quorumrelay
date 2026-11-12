"""Safe injectable write transport. Tests replace this boundary, not the adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class WriteResponse:
    status: int
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)


class WriteTransport(Protocol):
    mock: bool

    def send(self, url: str, *, method: str, body: bytes | None, headers: dict[str, str],
             byte_limit: int, deadline_seconds: float) -> WriteResponse: ...


class PublicWriteTransport:
    """Use the engine's public-socket, TLS, origin, size and deadline safeguards."""

    mock = False

    def send(self, url, *, method, body, headers, byte_limit, deadline_seconds):
        from urllib.parse import urlsplit
        from . import fetch

        request = getattr(fetch, "request_public_response", None)
        if request is None:
            # Never silently fall back to a transport that loses error status or ETag.
            raise RuntimeError("The structured safe public request transport is not installed.")
        parsed = urlsplit(url)
        response = request(
            url, method=method, body=body, headers=headers, byte_limit=byte_limit,
            deadline_seconds=deadline_seconds,
            allowed_origins={f"{parsed.scheme}://{parsed.hostname}"},
            allow_redirects=False,
        )
        return WriteResponse(response.status, response.content, response.headers)
