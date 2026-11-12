"""Write packaged schema files and a synthetic, schema-validated public example."""

import json
from pathlib import Path

from civic_data_connectors import Engine, Source
from civic_data_connectors.schemas import SCHEMAS, json_schema

root = Path(__file__).resolve().parents[1]
directory = root / "src/civic_data_connectors/schemas"
directory.mkdir(exist_ok=True)
for name in SCHEMAS:
    (directory / f"{name}.schema.json").write_text(json.dumps(json_schema(name), indent=2) + "\n", encoding="utf-8")
example = Engine().normalize(Source("legistar", "https://example.org/meetings"), json.dumps({
    "MeetingId": 1, "MeetingName": "Synthetic council", "MeetingDate": "2026-11-11T19:00:00Z",
    "AgendaItems": [{"FileNumber": "1-A", "Title": "Public hearing", "DepartmentName": "Clerk"}],
    "unknown_extension": {"empty": "", "null": None, "false": False, "zero": 0},
}).encode()).public_dict()
examples = root / "examples"
examples.mkdir(exist_ok=True)
(examples / "normalize-result.json").write_text(json.dumps(example, indent=2) + "\n", encoding="utf-8")
