"""Generate packaged capability research data from its reviewed documentation source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def generate() -> dict:
    source = ROOT / "docs/capabilities/inventory.json"
    inventory = json.loads(source.read_text(encoding="utf-8"))
    runtime = {
        "schema_version": inventory["schema_version"],
        "observation_date": inventory["observation_date"],
        "status_model": inventory["status_model"],
        "proof_policy": inventory["status_model"]["rule"],
        "release_completion": "incomplete",
        "research_snapshot": (
            "researched-pass-2; research status is not current engine implementation or acceptance. "
            "Engine owners merge separately verified implementation status."
        ),
        "generated_from": "docs/capabilities/inventory.json",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "alias_definition": "provider-identities.json",
        "providers": [],
    }
    for row in inventory["providers"]:
        runtime["providers"].append({
            key: row[key] for key in (
                "id", "canonical_id", "family_id", "aliases", "name", "baseline_formats",
                "family_acceptance_id", "baseline_acceptance_ids", "requirement_ids",
                "operations", "outbound_mappings", "auth", "restrictions",
                "remaining_research", "tenants", "test_environment", "account_tier",
                "official_docs_status",
            )
        })
        runtime["providers"][-1]["evidence"] = [{
            key: evidence[key] for key in (
                "id", "url", "title", "kind", "proof_level", "limits", "observation_date"
            )
        } for evidence in row["evidence"]]
    destination = ROOT / "src/civic_data_connectors/data"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "capabilities.json").write_text(
        json.dumps(runtime, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    identities = json.loads(
        (ROOT / "docs/capabilities/provider-identities.json").read_text(encoding="utf-8")
    )
    (destination / "provider-identities.json").write_text(
        json.dumps(identities, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"providers": len(runtime["providers"]), "source_sha256": runtime["source_sha256"]}


if __name__ == "__main__":
    print(json.dumps(generate(), sort_keys=True))
