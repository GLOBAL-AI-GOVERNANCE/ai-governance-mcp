#!/usr/bin/env python3
"""
Global AI Governance Solutions v1.2
AI Risk Tier Calculator

Calculates a preliminary AI risk tier from inventory fields.

This is a governance support tool, not a substitute for human review.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List


RISK_ORDER = ["Low", "Moderate", "High", "Critical", "Frontier"]


def yes(value: str) -> bool:
    return str(value).strip().lower() == "yes"


def calculate_risk_tier(row: Dict[str, str]) -> str:
    impact_flags = [
        yes(row.get("impact_people", "")),
        yes(row.get("impact_money", "")),
        yes(row.get("impact_security", "")),
        yes(row.get("impact_rights", "")),
        yes(row.get("impact_safety", "")),
    ]

    data_sensitivity = row.get("data_sensitivity", "None").strip()
    autonomy = row.get("autonomy_level", "None").strip()
    public_facing = yes(row.get("public_facing", ""))

    if autonomy == "Full" and (public_facing or data_sensitivity in {"Regulated", "Critical"} or any(impact_flags)):
        return "Frontier"

    if autonomy == "Full":
        return "Critical"

    if yes(row.get("impact_safety", "")) or yes(row.get("impact_security", "")) or data_sensitivity == "Critical":
        return "Critical"

    if any(impact_flags) or data_sensitivity in {"Personal", "Regulated"} or public_facing:
        return "High"

    if autonomy == "Partial" or data_sensitivity == "Internal":
        return "Moderate"

    return "Low"


def process_csv(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows: List[Dict[str, str]] = list(reader)

    if not rows:
        raise ValueError("Input CSV has no rows.")

    fieldnames = list(rows[0].keys())
    if "calculated_risk_tier" not in fieldnames:
        fieldnames.append("calculated_risk_tier")

    for row in rows:
        row["calculated_risk_tier"] = calculate_risk_tier(row)

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate preliminary AI risk tiers from inventory CSV.")
    parser.add_argument("input_csv", type=Path, help="Path to AI inventory CSV.")
    parser.add_argument("--output", "-o", type=Path, default=Path("risk-tier-output.csv"), help="Output CSV path.")
    args = parser.parse_args()

    process_csv(args.input_csv, args.output)
    print(f"Risk tier calculation complete: {args.output}")


if __name__ == "__main__":
    main()
