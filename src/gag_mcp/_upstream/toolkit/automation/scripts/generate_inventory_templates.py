#!/usr/bin/env python3
"""Generate human inventory templates from canonical metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.scripts.inventory_normalizer import CONTRACT_ROOT, canonical_fields


ROOT = REPO_ROOT
CSV_TARGET = ROOT / "spreadsheets" / "ai-system-inventory-template.csv"
MD_TARGET = ROOT / "templates" / "ai-system-inventory.md"
WEB_CSV_TARGET = ROOT / "web" / "ai-system-inventory-template.csv"
WEB_SAMPLE_TARGET = ROOT / "web" / "sample-ai-inventory.csv"


def render() -> dict[Path, str]:
    mapping = json.loads((CONTRACT_ROOT / "inventory-mapping.json").read_text(encoding="utf-8"))
    schema = json.loads((CONTRACT_ROOT / "canonical-inventory-record.schema.json").read_text(encoding="utf-8"))
    fields = ["schema_version", *canonical_fields()]
    labels = [mapping["fields"][field]["human_label"] for field in fields]
    csv_text = ",".join(labels) + "\n"
    lines = [
        "# AI System Inventory Template",
        "",
        "This template is generated from the canonical inventory contract. Use the CSV template for data entry; do not add columns without updating the versioned contract and mapping.",
        "",
        "| Human label | Canonical field | Allowed values |",
        "|---|---|---|",
    ]
    for field in fields:
        definition = schema["properties"][field]
        allowed = " / ".join(definition.get("enum", [])) or "Text"
        lines.append(f"| {mapping['fields'][field]['human_label']} | `{field}` | {allowed} |")
    lines.extend(["", "Canonical schema version: `1.0.0`", ""])
    sample_text = (
        ROOT / "automation" / "fixtures" / "valid-ai-inventory.csv"
    ).read_text(encoding="utf-8")
    return {
        CSV_TARGET: csv_text,
        MD_TARGET: "\n".join(lines),
        WEB_CSV_TARGET: csv_text,
        WEB_SAMPLE_TARGET: sample_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render()
    if args.check:
        drift = [str(path.relative_to(ROOT)) for path, content in rendered.items() if not path.is_file() or path.read_text(encoding="utf-8-sig").replace("\r\n", "\n") != content]
        if drift:
            print("Template drift: " + ", ".join(drift))
            raise SystemExit(1)
        print("Generated inventory templates are current.")
        return
    for path, content in rendered.items():
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"Generated: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
