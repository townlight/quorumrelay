"""Opt-in bounded public-read check. Never downloads attachments or performs writes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

from civic_data_connectors import Engine
from civic_data_connectors import providers
from civic_data_connectors.providers.contracts import PublicTransport
from civic_data_connectors.providers.discovery import DEFAULT_FORMAT

ROOT = Path(__file__).resolve().parents[1]
ALIASES = {"civicplus_select": "civicplus-select", "icompass-civicweb": "civicweb",
           "granicus-peak": "peak", "hyland-onbase-agenda-online": "onbase",
           "laserfiche": "laserfiche-weblink", "diligent-boarddocs": "boarddocs"}


class RecordedPublicReads(PublicTransport):
    """This checker never supplies credentials; only its public request spec is logged."""

    def __init__(self):
        self.requests = []

    def request(self, url, **kwargs):
        self.requests.append({
            "url": url, "method": kwargs.get("method", "GET"),
            "json_body": json.loads(kwargs["body"]) if kwargs.get("body") else None,
            "byte_limit": kwargs["byte_limit"],
            "deadline_seconds": round(kwargs["deadline_seconds"], 3),
            "allowed_origins": list(kwargs["allowed_origins"]),
        })
        return super().request(url, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--providers", nargs="+")
    parser.add_argument("--source-policy", choices=("inventory", "baseline"), default="baseline")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_network:
        parser.error("Public read checks require explicit --allow-network.")
    inventory = json.loads((ROOT / "docs" / "capabilities" / "inventory.json").read_text())
    cases = json.loads((ROOT / "tests" / "fixtures" / "baseline" / "cases.json").read_text())
    tenants = {}
    for row in inventory["providers"]:
        canonical = row.get("canonical_id") or ALIASES.get(row["id"], row["id"])
        for tenant in row.get("tenants", []):
            if tenant.get("url"):
                tenants.setdefault(canonical, tenant["url"])
    case_by_provider = {row["connector"]: row for row in cases}
    for row in cases:
        if row["input_format"] == DEFAULT_FORMAT.get(row["connector"]):
            case_by_provider[row["connector"]] = row
    owner = Engine()
    transport = RecordedPublicReads()
    providers.register(owner, transport=transport)
    rows = []
    selected = args.providers or list(providers.FORMATS)
    if set(selected) - set(providers.FORMATS):
        parser.error("Only the fixed 31 provider families may be checked.")
    for provider in selected:
        baseline = case_by_provider[provider]
        url = (tenants.get(provider, baseline["source_url"]) if args.source_policy == "inventory"
               or provider in {"legistar", "primegov", "civicplus-select", "escribe"}
               else baseline["source_url"])
        source = {"provider": provider, "url": url}
        if provider == "wistia":
            source = {"provider": provider, "url": baseline["source_url"],
                      "input_format": baseline["input_format"]}
        request = {"source": source, "bounds": {
            "date_from": "2026-11-01", "date_to": "2026-11-11",
            "max_records": 20, "max_pages": 2, "parser_bytes": 8 * 1024 * 1024,
            "deadline_seconds": 15}}
        start = monotonic()
        transport.requests = []
        result = owner.execute("discover", request)
        row = {"provider": provider, "source_url": source["url"], "status": result.status,
               "elapsed_seconds": round(monotonic() - start, 3),
               "record_count": len((result.data or {}).get("records", [])),
               "pages": result.coverage.get("pages", 0),
               "truncated": result.coverage.get("truncated"),
               "errors": [error.code for error in result.errors],
               "error_details": [error.details for error in result.errors],
               "capture_sha256": [capture["sha256"] for capture in
                                  (result.data or {}).get("captures", [])],
               "scope": result.coverage.get("scope"),
               "configuration_policy": args.source_policy,
               "input_format": source.get("input_format") or DEFAULT_FORMAT[provider],
               "request_bounds": request["bounds"], "requests": transport.requests,
               "acceptance": ("live_native_bounded_listing" if result.status == "completed" and
                              provider in {"legistar", "primegov", "civicplus-select", "escribe"}
                              else "live_configured_capture_only" if
                              (result.data or {}).get("captures") else "not_passed")}
        rows.append(row)
        print(json.dumps(row), flush=True)
    report = {"observed_at": datetime.now(timezone.utc).isoformat(), "policy": (
        "Bounded public reads only. No attachment downloads, credentials, browser or remote writes. "
        "A partial listing is not full discovery acceptance."), "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
