#!/usr/bin/env python3
"""
Global AI Governance Solutions v1.2
Governance Report Generator

Creates a simple Markdown executive summary from an AI inventory CSV.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def generate_report(input_csv: Path, output_md: Path) -> None:
    rows = read_rows(input_csv)
    total = len(rows)

    tier_counts = Counter(row.get("calculated_risk_tier") or row.get("risk_tier") or "Unclassified" for row in rows)
    owner_missing = sum(1 for row in rows if not row.get("owner", "").strip())
    monitoring_missing = sum(1 for row in rows if row.get("monitoring_active", "").strip().lower() != "yes")
    shutdown_missing = sum(1 for row in rows if row.get("shutdown_path_exists", "").strip().lower() != "yes")
    evidence_missing = sum(1 for row in rows if row.get("evidence_complete", "").strip().lower() != "yes")

    report = f"""# Executive AI Governance Report

## Summary

Total AI systems reviewed: **{total}**

## Risk Tier Distribution

"""
    for tier in ["Low", "Moderate", "High", "Critical", "Frontier", "Unclassified"]:
        if tier_counts.get(tier, 0):
            report += f"- {tier}: {tier_counts[tier]}\n"

    report += f"""

## Governance Gaps

- Systems missing named owner: **{owner_missing}**
- Systems missing active monitoring: **{monitoring_missing}**
- Systems missing shutdown path: **{shutdown_missing}**
- Systems with incomplete evidence: **{evidence_missing}**

## Executive Interpretation

The governance priority is to close ownership, monitoring, evidence, and shutdown gaps before expanding AI deployment.

## Operating Law

No AI system moves faster than ownership, evidence, authority, and control.
"""

    output_md.write_text(report, encoding="utf-8")
    print(f"Governance report generated: {output_md}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an executive AI governance report from inventory CSV.")
    parser.add_argument("input_csv", type=Path, help="Path to AI inventory CSV.")
    parser.add_argument("--output", "-o", type=Path, default=Path("executive-ai-governance-report.md"), help="Output Markdown report path.")
    args = parser.parse_args()
    generate_report(args.input_csv, args.output)


if __name__ == "__main__":
    main()
