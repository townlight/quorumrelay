"""Opt-in WebLink browser with all allowed HTTP served by PublicTransport.

The isolated browser is offline. No route is ever continued or fetched by
Playwright: same-origin requests are fulfilled from the bounded Python transport.
This preserves socket/DNS/TLS guards but does not bypass HTTP access challenges.
"""
from __future__ import annotations

import json
import math
import socket
from time import monotonic
from urllib.parse import unquote, urlsplit

from ..fetch import _origin
from .contracts import PublicTransport, RetrievalError
from .laserfiche import INFO, LISTING, TEXT, _parts

__all__ = ["GuardedWebLinkSession"]


class GuardedWebLinkSession:
    """Caller-owned, synchronous and single-threaded; use as a context manager.

    Requires the optional browser extra and installed Chrome. Construction does
    not launch Chrome. Session state is never borrowed from a user profile.
    """

    guarded = True

    def __init__(self, source_url: str, *, channel="chrome", transport=None):
        self.origin = _origin(source_url)
        self._base, _, self._repo, self._dbid = _parts(source_url)
        self._channel = channel
        self._transport = transport or PublicTransport()
        self._playwright = self._browser = self._context = self._page = None
        self._deny_proxy = None
        self._deadline = 0.0
        self._byte_limit = self._remaining_bytes = self._requests = 0
        self._target = None
        self._captured = None
        self.captured_content = None
        self._failure = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            self._browser = self._context = self._page = None
            try:
                if self._playwright is not None:
                    self._playwright.stop()
            finally:
                self._playwright = None
                if self._deny_proxy is not None:
                    self._deny_proxy.close()
                    self._deny_proxy = None

    def _open(self):
        if self._page is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise ValueError("Install quorumrelay[browser] and Chrome for an explicit WebLink session.") from error
        try:
            self._playwright = sync_playwright().start()
            # Own a non-forwarding proxy endpoint instead of assuming an unused
            # fixed localhost port. No request is accepted or connected onward.
            self._deny_proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._deny_proxy.bind(("127.0.0.1", 0))
            self._deny_proxy.listen(1)
            proxy_port = self._deny_proxy.getsockname()[1]
            self._browser = self._playwright.chromium.launch(
                channel=self._channel, headless=True,
                args=["--disable-quic", "--disable-background-networking",
                      "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                      "--host-resolver-rules=MAP * ~NOTFOUND",
                      f"--proxy-server=http://127.0.0.1:{proxy_port}", "--proxy-bypass-list=<-loopback>"],
            )
            self._context = self._browser.new_context(
                offline=True, service_workers="block", accept_downloads=False,
                permissions=[], ignore_https_errors=False,
            )
            self._context.route("**/*", self._route)
            self._context.route_web_socket("**/*", lambda socket: socket.close())
            self._context.add_init_script("""(() => {
                for (const name of ['RTCPeerConnection','webkitRTCPeerConnection','WebTransport']) {
                    Object.defineProperty(globalThis, name, {value: undefined, configurable: false});
                }
            })();""")
            self._page = self._context.new_page()
        except Exception:
            self.close()
            raise ValueError("The isolated guarded Chrome session could not start; use a saved capture.") from None

    def _begin(self, target, byte_limit, deadline_seconds):
        if type(byte_limit) is not int or byte_limit < 1:
            raise ValueError("WebLink requires a positive byte limit.")
        if (not isinstance(deadline_seconds, (int, float)) or
                not math.isfinite(deadline_seconds) or deadline_seconds <= 0):
            raise ValueError("WebLink requires a positive finite deadline.")
        if target not in {self._base + LISTING, self._base + INFO, self._base + TEXT}:
            raise ValueError("Only the observed WebLink read services are allowed.")
        self._deadline = monotonic() + deadline_seconds
        self._byte_limit = byte_limit
        # Separate finite navigation overhead from the caller's JSON response cap.
        self._remaining_bytes = min(32 * 1024**2, byte_limit + 16 * 1024**2)
        self._requests = 0
        self._target, self._captured, self._failure = target, None, None
        self.captured_content = None
        self._open()
        self._page.set_default_timeout(max(1, (self._deadline - monotonic()) * 1000))

    def _route(self, route):
        request = route.request
        try:
            parsed = urlsplit(request.url)
            if _origin(request.url) != self.origin or parsed.fragment:
                raise RetrievalError("weblink_origin_denied")
            if not parsed.path.startswith(self._base + "/"):
                raise RetrievalError("weblink_path_denied")
            decoded_path = unquote(parsed.path)
            if "\\" in decoded_path or any(part in {".", ".."} for part in decoded_path.split("/")):
                raise RetrievalError("weblink_path_denied")
            if request.method not in {"GET", "POST"}:
                raise RetrievalError("weblink_method_denied")
            if request.method == "POST" and parsed.path not in {
                    self._base + LISTING, self._base + INFO, self._base + TEXT}:
                raise RetrievalError("weblink_mutation_denied")
            if request.method == "GET":
                filename = parsed.path.rsplit("/", 1)[-1].lower()
                if filename in {"browse.aspx", "docview.aspx"}:
                    base, _, repo, dbid = _parts(request.url)
                    if (base, repo, dbid) != (self._base, self._repo, self._dbid):
                        raise RetrievalError("weblink_repository_denied")
                elif (filename not in {"webresource.axd", "scriptresource.axd"} and
                      not filename.endswith((".js", ".css", ".png", ".jpg", ".jpeg", ".gif",
                                             ".svg", ".ico", ".woff", ".woff2", ".ttf"))):
                    raise RetrievalError("weblink_unrecognized_get")
            if request.resource_type in {"image", "media", "font"}:
                route.abort()
                return
            if self._requests >= 128 or self._remaining_bytes < 1 or monotonic() >= self._deadline:
                raise RetrievalError("weblink_navigation_bound")
            self._requests += 1
            limit = min(self._remaining_bytes,
                        self._byte_limit if parsed.path == self._target else 4 * 1024**2)
            headers = {k: v for k, v in request.all_headers().items()
                       if k.lower() in {"accept", "content-type", "cookie", "referer",
                                        "origin", "x-lf-suppress-login-redirect", "x-requested-with"}}
            body = request.post_data_buffer
            if body is not None and len(body) > self._byte_limit:
                raise RetrievalError("weblink_request_bound")
            if request.method == "POST":
                payload = json.loads(body or b"null")
                if not isinstance(payload, dict) or payload.get("repoName") != self._repo:
                    raise RetrievalError("weblink_repository_denied")
            response = self._transport.request(
                request.url, method=request.method, body=body, headers=headers,
                byte_limit=limit, deadline_seconds=max(0.001, self._deadline - monotonic()),
                allowed_origins=(self.origin,), allow_redirects=False,
            )
            if _origin(response.url) != self.origin or len(response.content) > limit:
                raise RetrievalError("weblink_response_boundary")
            self._remaining_bytes -= len(response.content)
            if response.status in {401, 403, 429, 503}:
                raise RetrievalError("weblink_access_required", status=response.status)
            if not 200 <= response.status < 300:
                raise RetrievalError("weblink_http_error", status=response.status)
            if parsed.path == self._target:
                self._captured = json.loads(response.content)
                self.captured_content = response.content
            # Disallow active secondary contexts and browser-only network APIs.
            # Cookies are returned solely to this new isolated browser context.
            returned_headers = {"content-type": response.content_type,
                "content-security-policy": "worker-src 'none'; frame-src 'none'; object-src 'none'; "
                    "form-action 'none'; connect-src 'self'; base-uri 'self'"}
            if response.set_cookie_headers:
                if (len(response.set_cookie_headers) > 32 or any(
                        len(value) > 8192 or "\r" in value or "\n" in value
                        for value in response.set_cookie_headers)):
                    raise RetrievalError("weblink_cookie_bound")
                returned_headers["set-cookie"] = "\n".join(response.set_cookie_headers)
            route.fulfill(status=response.status, headers=returned_headers, body=response.content)
        except Exception as error:
            self._failure = (error if isinstance(error, RetrievalError)
                             else RetrievalError("weblink_guarded_request_failed"))
            route.abort()

    def _result(self):
        if self._failure:
            raise self._failure
        if self._captured is None:
            raise RetrievalError("weblink_expected_response_missing")
        return self._captured

    def open_and_catch(self, url, response_path, *, byte_limit, deadline_seconds):
        if _origin(url) != self.origin:
            raise ValueError("The WebLink page leaves the configured origin.")
        base, _, repo, dbid = _parts(url)
        if (base, repo, dbid) != (self._base, self._repo, self._dbid):
            raise ValueError("The WebLink page leaves the configured repository.")
        self._begin(response_path, byte_limit, deadline_seconds)
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            while self._captured is None and not self._failure and monotonic() < self._deadline:
                self._page.wait_for_timeout(min(20, max(1, (self._deadline - monotonic()) * 1000)))
        except Exception:
            if not self._failure:
                self._failure = RetrievalError("weblink_navigation_failed")
        return self._result()

    def post_json(self, path, data, headers, *, byte_limit, deadline_seconds):
        if self._page is None or _origin(self._page.url) != self.origin:
            raise ValueError("Open the scoped WebLink page before requesting its read services.")
        if headers != {"X-Lf-Suppress-Login-Redirect": "1"}:
            raise ValueError("Only WebLink read headers are accepted.")
        if not isinstance(data, dict) or data.get("repoName") != self._repo:
            raise ValueError("The WebLink read belongs to a different repository.")
        self._begin(path, byte_limit, deadline_seconds)
        try:
            self._page.evaluate("""([path,data,headers]) => {
                fetch(path,{method:'POST',credentials:'same-origin',
                    headers:{'Content-Type':'application/json',...headers},
                    body:JSON.stringify(data)}).catch(() => {});
            }""", [path, data, headers])
            while self._captured is None and not self._failure and monotonic() < self._deadline:
                self._page.wait_for_timeout(min(20, max(1, (self._deadline - monotonic()) * 1000)))
        except Exception:
            if not self._failure:
                self._failure = RetrievalError("weblink_read_failed")
        return self._result()
