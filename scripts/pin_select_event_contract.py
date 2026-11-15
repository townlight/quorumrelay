"""Retain the selected event update/read models from the pinned vendor OpenAPI."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compile_contract():
    path = ROOT / "docs/capabilities/evidence/civicclerk-openapi/swagger.json"
    raw = path.read_bytes()
    source = json.loads(raw)
    models = source["components"]["schemas"]
    selected = {}

    def keep(value):
        if isinstance(value, dict):
            if "$ref" in value:
                name = value["$ref"].removeprefix("#/components/schemas/")
                if name not in selected:
                    selected[name] = models[name]
                    keep(models[name])
            for child in value.values():
                keep(child)
        elif isinstance(value, list):
            for child in value:
                keep(child)

    route = source["paths"]["/v1/Events/{key}"]
    request = route["put"]["requestBody"]["content"]["application/json"]["schema"]
    response = route["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    keep(request)
    keep(response)
    return {"source_sha256": sha256(raw).hexdigest(), "path": "/v1/Events/{key}",
            "request": request, "response": response, "models": selected}


if __name__ == "__main__":
    path = ROOT / "src/civic_data_connectors/data/select_event_update.json"
    path.write_bytes((json.dumps(compile_contract(), indent=2, ensure_ascii=True) + "\n")
                     .replace("\n", "\r\n").encode())
