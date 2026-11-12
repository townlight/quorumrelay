# Contributing

QuorumRelay is public source under the Townlight organization. Read the current
source and provider evidence before changing behavior. The repository currently
has no license file; this guide does not invent or select one.

## Local development

Python 3.11+ is required; current CI uses Python 3.13 and Node 24.

```sh
git clone https://github.com/townlight/quorumrelay.git
cd quorumrelay
python -m venv .venv
# Activate the environment using your shell.
python -m pip install -e ".[service,test]"
npm --prefix client ci
npm --prefix client run build
python scripts/validate_capabilities.py
python -X utf8 -m pytest tests -q
python -m ruff check src tests scripts examples
npm --prefix client test
```

For a focused change run meaningful affected checks and the repository-required CI;
reuse unchanged proof rather than blindly repeating installed workflows. The suite
uses synthetic data and saved public captures. A passed fixture test is not a
claim of a live account read, provider mutation or complete catalog.

## Where changes belong

`src/quorumrelay` exposes the canonical import facade over the shared
`src/civic_data_connectors` implementation. Keep compatibility class identities
shared. Provider rules belong in provider adapters; thin transports and consumer
applications should not reimplement them. Use the common result, bounds, identity,
coverage, capture and exact write-plan contracts. Additive parsers must not replace
the 34 original compatibility formats. An extension can run the conformance helper
without modifying transports; see the [developer guide](docs/DEVELOPER-GUIDE.md).

Keep service authentication, application tenant identity and upstream credentials
separate. Never commit live credentials, private application databases or signed
download URLs that grant current private access. Do not test a candidate secret.
Do not mutate a public municipality as a test. Use a designated test environment
for vendor changes and describe the exact acceptance actually performed.

## Documentation and website

The [user manual](docs/USER-MANUAL.md), [developer guide](docs/DEVELOPER-GUIDE.md),
[architecture](docs/ARCHITECTURE.md) and detailed references render into the static
website under `site/`. Update them with changed behavior. Regenerate source API
downloads with `python scripts/build_api_docs.py`. Keep status/coverage labels
honest and preserve older artifact receipts as dated evidence.

```sh
cd site
npm ci
npm run build
npm run preview
```

See [site maintenance](site/README.md) for preview URLs, project-subpath routing,
Mermaid rendering and GitHub Pages deployment. No public service/API is hosted by
the documentation website. The four reference applications have their own
repositories, review processes and releases.
