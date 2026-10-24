#!/usr/bin/env python3
"""Run the backwards-compatible Wave A governance contract pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.scripts.contract_verifier import verify_output_directory
from automation.scripts.generate_decision_pack import prepare_pack, write_pack
from automation.scripts.generate_governance_report import generate_report
from automation.scripts.governance_validator import load_policy, read_rows, evaluate_row, should_fail, write_report
from automation.scripts.inventory_normalizer import NormalizationError, normalize_file
from automation.scripts.machine_contracts import build_findings, build_handoff, build_result, write_json
from automation.scripts.risk_tier_calculator import process_csv
from automation.scripts.schema_validator import validate_csv


AUTOMATION = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = AUTOMATION / "schemas" / "ai-system-inventory.schema.json"
DEFAULT_POLICY = AUTOMATION / "policy-as-code" / "governance-rules.yaml"


def run_pipeline(
    input_csv: Path,
    outdir: Path,
    *,
    schema: Path = DEFAULT_SCHEMA,
    policy: Path = DEFAULT_POLICY,
    decision_pack_dir: Path | None = None,
    fail_on: str = "critical",
    evaluation_time: str | None = None,
    target_repository: str = "agentic-ai-governance",
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    normalized_json = outdir / "normalized-inventory.json"
    canonical_csv = outdir / "canonical-inventory.csv"
    schema_report = outdir / "schema-validation-report.md"
    tiered_csv = outdir / "risk-tier-output.csv"
    governance_report = outdir / "governance-validation-report.md"
    findings_path = outdir / "governance-findings.json"
    result_path = outdir / "governance-result.json"
    executive_report = outdir / "executive-ai-governance-report.md"
    pack_dir = decision_pack_dir or outdir / "decision-pack"
    handoff_path = outdir / "governance-handoff.json"

    try:
        normalized = normalize_file(input_csv, normalized_json, canonical_csv)
    except NormalizationError as exc:
        issue = exc.issue
        if issue.code == "MISSING_REQUIRED_COLUMN":
            details = "\n".join(f"- Header: missing required field '{field}'." for field in issue.expected)
        elif issue.code == "INVALID_ENUM_VALUE":
            details = f"- Field '{issue.source_column}': value '{issue.supplied_value}' is not allowed."
        else:
            details = f"- [{issue.code}] {issue.remediation}"
        schema_report.write_text(
            "# Inventory Schema Validation Report\n\n## Errors\n\n" + details + "\n",
            encoding="utf-8",
            newline="\n",
        )
        raise
    schema_errors = validate_csv(canonical_csv, schema, schema_report)
    if schema_errors:
        raise ValueError(f"Inventory schema validation failed with {len(schema_errors)} error(s).")
    process_csv(canonical_csv, tiered_csv)

    policy_value = load_policy(policy)
    rows = read_rows(tiered_csv)
    findings = []
    for row in rows:
        findings.extend(evaluate_row(row, policy_value["rules"]))
    write_report(governance_report, policy, findings, len(policy_value["rules"]))

    findings_doc = build_findings(normalized, policy_value, findings)
    result_doc = build_result(normalized, policy_value, findings, fail_on=fail_on, evaluation_time=evaluation_time)
    write_json(findings_path, findings_doc)
    write_json(result_path, result_doc)

    if should_fail(findings, fail_on):
        print(f"Governance validation blocked by {fail_on.upper()} findings.")
        raise SystemExit(1)

    generate_report(tiered_csv, executive_report)
    documents = prepare_pack(
        tiered_csv, schema_report, governance_report, executive_report,
        schema, policy, normalized_json, findings_path, result_path, evaluation_time,
    )
    write_pack(pack_dir, documents)
    handoff = build_handoff(
        manifest_path=pack_dir / "manifest.json",
        result=result_doc,
        findings_doc=findings_doc,
        target_repository=target_repository,
    )
    write_json(handoff_path, handoff)
    if pack_dir == outdir / "decision-pack":
        verify_output_directory(outdir)

    print("\nGovernance automation complete.")
    for path in (
        normalized_json, canonical_csv, schema_report, tiered_csv,
        governance_report, findings_path, result_path, executive_report,
        pack_dir, handoff_path,
    ):
        print(f"- {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize inventory, run governance checks, and produce a human-review Decision Pack."
    )
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--outdir", type=Path, default=Path("automation/reports"))
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--decision-pack-dir", type=Path)
    parser.add_argument("--fail-on", choices=("none", "high", "critical"), default="critical")
    parser.add_argument("--evaluation-time")
    parser.add_argument("--target-repository", default="agentic-ai-governance")
    args = parser.parse_args()
    try:
        run_pipeline(
            args.input_csv, args.outdir, schema=args.schema, policy=args.policy,
            decision_pack_dir=args.decision_pack_dir, fail_on=args.fail_on,
            evaluation_time=args.evaluation_time, target_repository=args.target_repository,
        )
    except SystemExit:
        raise
    except (OSError, ValueError) as exc:
        print(f"Governance automation failed: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
