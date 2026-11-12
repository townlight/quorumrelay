"""Real isolated Chrome routes with synthetic wire responses, no remote writes."""
import json

import pytest

from civic_data_connectors.providers.contracts import Response, RetrievalError
from civic_data_connectors.providers.laserfiche import HEADERS, LISTING
from civic_data_connectors.providers.weblink_session import GuardedWebLinkSession

ORIGIN = "https://weblink.example"
URL = ORIGIN + "/WebLink/Browse.aspx?id=1&dbid=0&repo=Public"
PATH = "/WebLink" + LISTING


class Wire:
    def __init__(self, *, script="", status=200, large=False):
        self.calls = []
        self.status, self.large = status, large
        self.html = ("<html><head><link rel='icon' href='data:,'></head><body><script>" + script +
            "fetch('" + PATH + "',{method:'POST',headers:{'Content-Type':'application/json'},"
            "body:JSON.stringify({repoName:'Public',folderId:1})});</script></body></html>").encode()

    def request(self, url, **kwargs):
        assert kwargs["allowed_origins"] == (ORIGIN,)
        assert kwargs["allow_redirects"] is False
        assert kwargs["deadline_seconds"] > 0
        self.calls.append((url, kwargs))
        if url == URL:
            return Response(url, self.html, "text/html", self.status,
                            set_cookie_headers=("session=private; Path=/WebLink; Secure; HttpOnly",))
        assert url == ORIGIN + PATH
        content = json.dumps({"data": {"results": [{"unknown": "kept"}], "totalEntries": 1}}).encode()
        if self.large:
            content += b" " * kwargs["byte_limit"]
        return Response(url, content, "application/json")


@pytest.fixture
def session_factory():
    pytest.importorskip("playwright.sync_api")
    active = []
    def make(wire):
        session = GuardedWebLinkSession(URL, transport=wire)
        active.append(session)
        return session
    yield make
    for session in active:
        session.close()


def test_real_offline_browser_routes_navigation_and_posts_with_private_cookie(session_factory):
    wire = Wire()
    session = session_factory(wire)
    result = session.open_and_catch(URL, PATH, byte_limit=4096, deadline_seconds=15)
    assert result["data"]["results"] == [{"unknown": "kept"}]
    assert len(wire.calls) == 2
    assert wire.calls[1][1]["headers"]["cookie"] == "session=private"
    result2 = session.post_json(PATH, {"repoName": "Public", "folderId": 1}, HEADERS,
                                byte_limit=4096, deadline_seconds=5)
    assert result2 == result
    assert len(wire.calls) == 3
    with pytest.raises(ValueError, match="different repository"):
        session.post_json(PATH, {"repoName": "Other"}, HEADERS, byte_limit=4096, deadline_seconds=5)


@pytest.mark.parametrize("target", ["http://127.0.0.1/private", "https://other.example/private"])
def test_subresources_never_leave_origin_or_reach_transport(session_factory, target):
    wire = Wire(script=f"fetch('{target}').then(()=>window.probe='unexpected').catch(()=>window.probe='blocked');")
    session = session_factory(wire)
    session.open_and_catch(URL, PATH, byte_limit=4096, deadline_seconds=10)
    # The injected CSP rejects this before it reaches even the route handler.
    assert session._page.evaluate("window.probe") == "blocked"
    assert all(url.startswith(ORIGIN + "/") for url, _ in wire.calls)


def test_browser_only_network_paths_are_disabled(session_factory):
    wire = Wire()
    session = session_factory(wire)
    session.open_and_catch(URL, PATH, byte_limit=4096, deadline_seconds=10)
    assert session._page.evaluate("typeof RTCPeerConnection + ':' + typeof WebTransport") == "undefined:undefined"
    worker = session._page.evaluate("""async () => {
        try {
            const registration = await navigator.serviceWorker.register('/WebLink/worker.js');
            return registration ? 'registered' : 'suppressed';
        } catch (_) { return 'blocked'; }
    }""")
    assert worker in {"blocked", "suppressed"}
    assert session._context.service_workers == []
    assert not any("worker.js" in url for url, _ in wire.calls)


def test_exact_provider_json_bytes_are_retained_for_capture_hash():
    from civic_data_connectors.providers.laserfiche import _json_size
    class Captured:
        captured_content = b'{ "data" : {"unknown": 2} }\r\n'
    assert _json_size({"data": {"unknown": 2}}, 4096, Captured()) == Captured.captured_content
    with pytest.raises(ValueError, match="do not match"):
        _json_size({"data": {"unknown": 3}}, 4096, Captured())


def test_challenge_is_access_failure_and_no_ajax_followup(session_factory):
    wire = Wire(status=403)
    with pytest.raises(RetrievalError) as error:
        session_factory(wire).open_and_catch(URL, PATH, byte_limit=4096, deadline_seconds=10)
    assert error.value.code == "weblink_access_required"
    assert error.value.status == 403
    assert len(wire.calls) == 1


@pytest.mark.parametrize("script,code", [
    ("fetch('/WebLink/Delete.aspx?id=1').catch(()=>{});", "weblink_unrecognized_get"),
    ("fetch('" + PATH + "',{method:'POST',body:JSON.stringify({repoName:'Other'})}).catch(()=>{});",
     "weblink_repository_denied"),
])
def test_unrecognized_actions_and_other_repositories_are_not_forwarded(session_factory, script, code):
    wire = Wire(script=script)
    with pytest.raises(RetrievalError) as error:
        session_factory(wire).open_and_catch(URL, PATH, byte_limit=4096, deadline_seconds=10)
    assert error.value.code == code
    assert not any("Delete.aspx" in url for url, _ in wire.calls)
    assert all(not args.get("body") or b'Other' not in args["body"] for _, args in wire.calls)


def test_response_cap_enforced_before_browser_fulfillment(session_factory):
    wire = Wire(large=True)
    with pytest.raises(RetrievalError) as error:
        session_factory(wire).open_and_catch(URL, PATH, byte_limit=4096, deadline_seconds=10)
    assert error.value.code == "weblink_response_boundary"


def test_no_browser_started_for_invalid_origin_repository_or_service():
    session = GuardedWebLinkSession(URL)
    for url, path in [(URL.replace("weblink.example", "other.example"), PATH),
                      (URL.replace("repo=Public", "repo=Other"), PATH),
                      (URL, "/WebLink/Admin/Delete")]:
        with pytest.raises(ValueError):
            session.open_and_catch(url, path, byte_limit=4096, deadline_seconds=5)
    assert session._browser is None
