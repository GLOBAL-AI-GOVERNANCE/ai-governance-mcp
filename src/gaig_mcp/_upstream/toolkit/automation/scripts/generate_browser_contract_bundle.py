#!/usr/bin/env python3
"""Generate the browser contract bundle from Wave A canonical sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "web" / "contracts.generated.mjs"


def build() -> str:
    paths = {
        "canonicalSchema": ROOT / "automation/contracts/v1/canonical-inventory-record.schema.json",
        "mapping": ROOT / "automation/contracts/v1/inventory-mapping.json",
        "policy": ROOT / "automation/policy-as-code/governance-rules.yaml",
    }
    values = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in paths.items()
    }
    sample = (ROOT / "automation/fixtures/valid-ai-inventory.csv").read_text(encoding="utf-8")
    gaps_sample = (ROOT / "automation/sample-data/sample-ai-inventory.csv").read_text(encoding="utf-8")
    payload = json.dumps({**values, "sampleCsv": sample, "gapsSampleCsv": gaps_sample}, indent=2, sort_keys=True)
    return "// Generated from Wave A contracts. Do not edit.\nexport const contracts = " + payload + ";\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = build()
    if args.check:
        if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != expected:
            print("Browser contract bundle drift detected.")
            raise SystemExit(1)
        print("Browser contract bundle is current.")
        return
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Generated: {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
