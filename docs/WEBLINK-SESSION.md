# Explicit guarded WebLink sessions

Install `quorumrelay[browser]` and Google Chrome to use the optional synchronous
`quorumrelay.providers.weblink_session.GuardedWebLinkSession`. Importing or
constructing it starts no browser. The caller owns its lifetime and must close
it; do not share a session between callers or tenants.

```python
from quorumrelay import create_engine
from quorumrelay.providers.weblink_session import GuardedWebLinkSession

url = "https://your-public-host/WebLink/Browse.aspx?id=123&dbid=0&repo=Public"
with GuardedWebLinkSession(url) as session:
    engine = create_engine(provider_browser=session)
    result = engine.execute("discover", {
        "source": {"provider": "laserfiche-weblink", "url": url},
        "bounds": {"date_from": "2026-01-01", "date_to": "2026-11-11",
                   "max_pages": 10, "max_records": 100, "deadline_seconds": 45},
    })
    print(result.public_dict())
```

The new isolated Chrome context is offline, with service workers, downloads,
frames and worker execution disabled. WebSockets are closed; WebRTC and
WebTransport are disabled. Every permitted page/script/read-service request is
fulfilled through QuorumRelay's public transport, which validates public DNS
addresses, the actual socket destination, TLS, redirects, response size and
deadline. No route uses Playwright's network continuation or fetch. Browser
network fallback also has a nonresolving host policy and a session-owned,
non-forwarding loopback proxy endpoint, closed with the session.
Only the selected origin and WebLink base path are allowed; unrelated POSTs and
unrecognized application GETs are rejected. Read-service repository names must
match the session. This session rejects every HTTP redirect before opening a
second connection, including same-origin redirects, so page routing cannot skip
its path/repository checks. Cookies stay in this fresh context and never enter receipts
or checkpoints. Exact JSON response bytes remain available for capture hashes.

Each navigation has at most 128 allowed requests and at most 32 MiB combined
responses (the smaller bound of that ceiling or the parser cap plus 16 MiB).
The selected service response uses the caller's parser cap; scripts/styles use
at most 4 MiB each within the combined bound. This navigation overhead does not
raise document/media transfer limits. Restrictive policies can make a tenant's
page unusable; the failure remains explicit rather than silently weakening the
network boundary.

This is not an anti-bot workaround. HTTP challenges and access restrictions from
the guarded transport still fail, even when an ordinary user browser can open
the site. Supply a saved capture or an authorized supported access path in that
case. The Repository API is separate; a WebLink repository name does not grant
Repository API access. This session does not prove complete archive discovery.

The local Chrome tests use synthetic responses and check real navigation,
cookies, AJAX, bounded responses, denied cross-origin subresources, disabled
browser-only transports and exact capture bytes. Those checks are adapter
evidence, not successful live provider acceptance. See the dated verification
receipt for actual public probe outcomes.

The implementation uses the documented [Playwright context routing and offline
controls](https://playwright.dev/python/docs/api/class-browsercontext) and
[service-worker restrictions](https://playwright.dev/python/docs/service-workers).
