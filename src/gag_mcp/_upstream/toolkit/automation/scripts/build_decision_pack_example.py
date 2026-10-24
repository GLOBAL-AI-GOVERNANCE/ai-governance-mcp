#!/usr/bin/env python3
"""
Build or verify the checked-in Decision Pack reference example.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(command: list[object], environment: dict[str, str]) -> None:
    rendered = [str(item) for item in command]
    print("+ " + " ".join(rendered), flush=True)
    completed = subprocess.run(
        rendered,
        check=False,
        env=environment,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build or verify the checked-in Decision Pack example."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the committed example has drifted.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    automation_dir = script_dir.parent
    repository_root = automation_dir.parent
    fixture = (
        automation_dir
        / "fixtures"
        / "valid-ai-inventory.csv"
    )
    expected_dir = (
        repository_root
        / "examples"
        / "decision-pack"
        / "valid-system"
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    with tempfile.TemporaryDirectory() as temp_name:
        outdir = Path(temp_name) / "valid"

        run(
            [
                sys.executable,
                "-B",
                script_dir / "run_governance_checks.py",
                fixture,
                "--outdir",
                outdir,
            ],
            environment,
        )

        generated_dir = outdir / "decision-pack"

        if not args.check:
            if expected_dir.exists():
                shutil.rmtree(expected_dir)
            expected_dir.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            shutil.copytree(
                generated_dir,
                expected_dir,
            )
            print(
                f"Decision Pack example built: {expected_dir}"
            )
            return

        run(
            [
                sys.executable,
                "-B",
                script_dir / "generate_decision_pack.py",
                "--risk-csv",
                outdir / "risk-tier-output.csv",
                "--schema-report",
                outdir / "schema-validation-report.md",
                "--governance-report",
                outdir / "governance-validation-report.md",
                "--executive-report",
                outdir / "executive-ai-governance-report.md",
                "--schema",
                (
                    automation_dir
                    / "schemas"
                    / "ai-system-inventory.schema.json"
                ),
                "--policy",
                (
                    automation_dir
                    / "policy-as-code"
                    / "governance-rules.yaml"
                ),
                "--normalized-inventory",
                outdir / "normalized-inventory.json",
                "--findings-json",
                outdir / "governance-findings.json",
                "--result-json",
                outdir / "governance-result.json",
                "--output-dir",
                expected_dir,
                "--check",
            ],
            environment,
        )


if __name__ == "__main__":
    main()
