# Quickstart with the published dev15 wheel

Install Python 3.11 or newer. Download the [Python wheel](https://github.com/townlight/quorumrelay/releases/download/v0.1.0.dev15/quorumrelay-0.1.0.dev15-py3-none-any.whl) and [SHA256SUMS](https://github.com/townlight/quorumrelay/releases/download/v0.1.0.dev15/SHA256SUMS) into a new directory. Check the wheel hash against the manifest before installing.

```powershell
Get-FileHash ./quorumrelay-0.1.0.dev15-py3-none-any.whl -Algorithm SHA256
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install ./quorumrelay-0.1.0.dev15-py3-none-any.whl
python -c "import quorumrelay; print(quorumrelay.__version__)"
'{}' | quorumrelay providers
```

On macOS/Linux, activate with `source .venv/bin/activate` and use `shasum -a 256` or `sha256sum` for the hash. Expected Python version is `0.1.0.dev15`. The catalog lists 33 registered providers.

## Read one saved meeting

Save this as `quickstart.py` and run `python quickstart.py`. It uses an in-memory synthetic capture and needs no credentials, database or network request.

```python
from base64 import b64encode

from quorumrelay import Source, create_engine

source = Source(
    "legistar",
    "https://mock-city.legistar.com/Calendar.aspx",
    input_format="legistar-events-json",
)
capture = b'''[{"EventId":7,"EventBodyName":"Council",
                "EventDate":"2026-11-11T00:00:00","EventTime":"7:00 PM"}]'''
result = create_engine().execute("discover", {
    "source": source.public_dict(),
    "content_base64": b64encode(capture).decode("ascii"),
})
assert result.status == "partial", result.public_dict()
record = result.data["records"][0]
assert record["identity"]["external_id"] == "7"
print(result.status, record["identity"]["external_id"])
```

Expected output is `partial 7`. One saved capture supplies one meeting. Preserve the result’s coverage and provenance when your app stores or exports the record.

## Connect through HTTP or MCP

In the same environment, install the service extra from the same wheel:

```sh
python -m pip install "./quorumrelay-0.1.0.dev15-py3-none-any.whl[service]"
```

Consult the [HTTP configuration and security guide](INTERFACES.md#service-ownership-and-startup), then use [operation requests](OPERATION-REQUESTS.md) and [OpenAPI](API-REFERENCE.md). For agents, use [MCP stdio or Streamable HTTP](MCP.md). For Node/TypeScript, verify and install the [published client tarball](https://github.com/townlight/quorumrelay/releases/download/v0.1.0.dev15/quorumrelay-client-0.1.0-dev.15.tgz) in your project. The TypeScript version is `0.1.0-dev.15` and the shared result schema is `2.0.0`.

[Provider coverage](PROVIDER-COVERAGE.md) · [User manual](USER-MANUAL.md) · [Developer guide](DEVELOPER-GUIDE.md) · [Complete examples](../examples/README.md)
