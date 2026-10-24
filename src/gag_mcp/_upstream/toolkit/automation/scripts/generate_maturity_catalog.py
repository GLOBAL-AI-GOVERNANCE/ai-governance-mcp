#!/usr/bin/env python3
"""Write the browser catalog from the versioned framework adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "automation/frameworks/unesco-ai-maturity-2025/category-catalog.json"
DEST = ROOT / "web/maturity/catalog.generated.mjs"


def bundle() -> str:
    catalog = json.loads(SOURCE.read_text(encoding="utf-8"))
    return "export const MATURITY_CATALOG = " + json.dumps(catalog, indent=2, ensure_ascii=False) + ";\n"


def main() -> int:
    body = bundle()
    if "--check" in sys.argv:
        current = DEST.read_text(encoding="utf-8") if DEST.is_file() else ""
        if current != body:
            print("maturity catalog bundle is stale")
            return 1
        print("maturity catalog bundle is current")
        return 0
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
