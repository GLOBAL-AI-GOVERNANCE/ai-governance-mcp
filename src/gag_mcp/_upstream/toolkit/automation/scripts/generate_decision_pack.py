#!/usr/bin/env python3
"""
Generate a deterministic, human-reviewed AI Governance Decision Pack.

The generator consumes verified pipeline artifacts. It does not approve,
certify, or accept risk for an AI system.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence


PACK_FILES = (
    "executive-summary.md",
    "system-profile.md",
    "risk-and-findings.md",
    "evidence-and-ownership.md",
    "decision-record.md",
    "action-plan.md",
    "manifest.json",
)
DOCUMENT_FILES = PACK_FILES[:-1]
SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
}
FINDING_PATTERN = re.compile(
    r"^- \[(?P<rule_id>[^\]]+)\] "
    r"(?P<system_name>.+) "
    r"\((?P<system_id>[^()]*)\): "
    r"(?P<severity>CRITICAL|HIGH) - "
    r"(?P<message>.+)$"
)


class DecisionPackError(ValueError):
    """Raised when required decision-pack inputs are invalid."""


@dataclass(frozen=True)
class Finding:
    rule_id: str
    system_name: str
    system_id: str
    severity: str
    message: str


@dataclass(frozen=True)
class SourceArtifact:
    role: str
    path: Path


def normalized_text_bytes(path: Path) -> bytes:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DecisionPackError(
            f"Source artifact is not UTF-8 text: {path}"
        ) from exc

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.encode("utf-8")


def sha256_text(path: Path) -> str:
    return hashlib.sha256(normalized_text_bytes(path)).hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def safe_text(value: object) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    text = text.replace("|", r"\|").replace("`", "'")
    return text or "Not recorded"


def read_required_text(path: Path, role: str) -> str:
    if not path.is_file():
        raise DecisionPackError(
            f"Missing required {role}: {path}"
        )
    return normalized_text_bytes(path).decode("utf-8")


def read_inventory(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        raise DecisionPackError(
            f"Missing required risk-tier inventory: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file_handle:
        reader = csv.DictReader(file_handle)
        if reader.fieldnames is None:
            raise DecisionPackError(
                "Risk-tier inventory has no header row."
            )
        rows = list(reader)

    if not rows:
        raise DecisionPackError(
            "Risk-tier inventory has no records."
        )

    required = {
        "system_id",
        "system_name",
        "owner",
        "business_unit",
        "vendor_internal",
        "use_case",
        "data_sensitivity",
        "autonomy_level",
        "public_facing",
        "monitoring_active",
        "shutdown_path_exists",
        "evidence_complete",
        "calculated_risk_tier",
    }
    missing = sorted(required - set(reader.fieldnames))
    if missing:
        raise DecisionPackError(
            "Risk-tier inventory is missing fields: "
            + ", ".join(missing)
        )

    normalized = [
        {
            str(key): "" if value is None else str(value)
            for key, value in row.items()
            if key is not None
        }
        for row in rows
    ]
    return sorted(
        normalized,
        key=lambda row: (
            row.get("system_id", ""),
            row.get("system_name", ""),
        ),
    )


def parse_findings(report_text: str) -> List[Finding]:
    if not report_text.startswith("# Governance Validation Report"):
        raise DecisionPackError(
            "Governance report has an unexpected format."
        )

    findings: List[Finding] = []
    for line in report_text.splitlines():
        if not line.startswith("- ["):
            continue

        match = FINDING_PATTERN.fullmatch(line)
        if match is None:
            raise DecisionPackError(
                f"Unrecognized governance finding format: {line}"
            )

        findings.append(
            Finding(
                rule_id=match.group("rule_id"),
                system_name=match.group("system_name"),
                system_id=match.group("system_id"),
                severity=match.group("severity"),
                message=match.group("message"),
            )
        )

    if not findings and "No governance gaps found." not in report_text:
        raise DecisionPackError(
            "Governance report contains neither findings nor a pass result."
        )

    return sorted(
        findings,
        key=lambda finding: (
            SEVERITY_ORDER[finding.severity],
            finding.system_id,
            finding.rule_id,
        ),
    )


def validate_source_documents(
    schema_report: str,
    executive_report: str,
) -> None:
    if "Inventory schema validation passed." not in schema_report:
        raise DecisionPackError(
            "Schema report does not contain a passing validation result."
        )

    if not executive_report.startswith(
        "# Executive AI Governance Report"
    ):
        raise DecisionPackError(
            "Executive report has an unexpected format."
        )


def source_section(sources: Sequence[SourceArtifact]) -> str:
    lines = [
        "## Source Artifacts",
        "",
    ]
    for source in sources:
        lines.append(
            f"- {safe_text(source.role)}: `{source.path.name}`"
        )
    return "\n".join(lines)


def gate_state(findings: Sequence[Finding]) -> str:
    if any(
        finding.severity == "CRITICAL"
        for finding in findings
    ):
        return "BLOCKED BY CRITICAL FINDINGS"
    if findings:
        return "HUMAN REVIEW REQUIRED"
    return "PASSED CURRENT AUTOMATED CHECKS"


def render_executive_summary(
    rows: Sequence[Mapping[str, str]],
    findings: Sequence[Finding],
    sources: Sequence[SourceArtifact],
) -> str:
    tier_counts = Counter(
        row["calculated_risk_tier"] for row in rows
    )
    critical_count = sum(
        finding.severity == "CRITICAL"
        for finding in findings
    )
    high_count = sum(
        finding.severity == "HIGH"
        for finding in findings
    )

    tier_lines = [
        f"- {tier}: **{tier_counts[tier]}**"
        for tier in (
            "Low",
            "Moderate",
            "High",
            "Critical",
            "Frontier",
        )
        if tier_counts[tier]
    ]

    lines = [
        "# Executive Summary",
        "",
        f"**Automation gate result:** {gate_state(findings)}",
        "",
        "**Human decision status:** PENDING HUMAN DECISION",
        "",
        (
            f"Systems reviewed: **{len(rows)}**. "
            f"Critical findings: **{critical_count}**. "
            f"High findings: **{high_count}**."
        ),
        "",
        "## Risk Tier Distribution",
        "",
        *(tier_lines or ["- No risk tiers recorded."]),
        "",
        "## Decision Boundary",
        "",
        (
            "This pack prepares evidence for human review. "
            "It does not approve deployment, certify compliance, "
            "accept risk, or replace legal, security, privacy, "
            "procurement, compliance, executive, or board review."
        ),
        "",
        source_section(sources),
        "",
    ]
    return "\n".join(lines)


def render_system_profile(
    rows: Sequence[Mapping[str, str]],
    sources: Sequence[SourceArtifact],
) -> str:
    lines = [
        "# System Profile",
        "",
        (
            "| System ID | System | Owner | Business Unit | "
            "Source | Use Case | Data | Autonomy | Public | Risk Tier |"
        ),
        (
            "|---|---|---|---|---|---|---|---|---|---|"
        ),
    ]

    for row in rows:
        values = (
            row["system_id"],
            row["system_name"],
            row["owner"],
            row["business_unit"],
            row["vendor_internal"],
            row["use_case"],
            row["data_sensitivity"],
            row["autonomy_level"],
            row["public_facing"],
            row["calculated_risk_tier"],
        )
        lines.append(
            "| " + " | ".join(safe_text(value) for value in values) + " |"
        )

    lines.extend(
        [
            "",
            (
                "Risk tiers are preliminary governance-support "
                "classifications and require human review."
            ),
            "",
            source_section(sources),
            "",
        ]
    )
    return "\n".join(lines)


def render_risk_and_findings(
    rows: Sequence[Mapping[str, str]],
    findings: Sequence[Finding],
    sources: Sequence[SourceArtifact],
) -> str:
    lines = [
        "# Risk and Findings",
        "",
        f"**Automation gate result:** {gate_state(findings)}",
        "",
        "## Findings",
        "",
    ]

    if findings:
        for finding in findings:
            lines.extend(
                [
                    f"### {finding.rule_id}: {finding.severity}",
                    "",
                    f"- System: {safe_text(finding.system_name)} "
                    f"(`{safe_text(finding.system_id)}`)",
                    f"- Finding: {safe_text(finding.message)}",
                    "- Disposition: Pending human remediation and review.",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "No governance gaps were identified by the current "
                "automated policy checks.",
                "",
                (
                    "This result is not an approval or proof that all "
                    "applicable risks and obligations have been evaluated."
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## Preliminary Risk Tiers",
            "",
        ]
    )
    for row in rows:
        lines.append(
            f"- `{safe_text(row['system_id'])}`: "
            f"**{safe_text(row['calculated_risk_tier'])}**"
        )

    lines.extend(["", source_section(sources), ""])
    return "\n".join(lines)


def render_evidence_and_ownership(
    rows: Sequence[Mapping[str, str]],
    sources: Sequence[SourceArtifact],
) -> str:
    lines = [
        "# Evidence and Ownership",
        "",
        (
            "| System ID | Named Owner | Monitoring | "
            "Shutdown Path | Evidence Complete |"
        ),
        "|---|---|---|---|---|",
    ]

    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                safe_text(value)
                for value in (
                    row["system_id"],
                    row["owner"],
                    row["monitoring_active"],
                    row["shutdown_path_exists"],
                    row["evidence_complete"],
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Human Review Questions",
            "",
            "- Is the named owner accountable and available?",
            "- Is the evidence current, sufficient, and independently reviewable?",
            "- Are monitoring thresholds and escalation paths defined?",
            "- Can authorized humans restrict, suspend, roll back, or shut down the system?",
            "- Are legal, security, privacy, procurement, and sector reviews complete where required?",
            "",
            source_section(sources),
            "",
        ]
    )
    return "\n".join(lines)


def render_decision_record(
    sources: Sequence[SourceArtifact],
) -> str:
    lines = [
        "# Decision Record",
        "",
        "| Decision Field | Status |",
        "|---|---|",
        "| Human decision | Not recorded |",
        "| Decision authority | Not recorded |",
        "| Decision date | Not recorded |",
        "| Risk acceptance | Not recorded |",
        "| Conditions or restrictions | Not recorded |",
        "| Approval status | Not approved by automation |",
        "",
        "## Available Human Dispositions",
        "",
        "- Approve with documented conditions",
        "- Restrict scope or access",
        "- Remediate and resubmit",
        "- Reject deployment or expansion",
        "- Suspend, roll back, or shut down",
        "",
        (
            "A named human authority must record the final disposition. "
            "Generated content cannot authorize deployment or accept risk."
        ),
        "",
        source_section(sources),
        "",
    ]
    return "\n".join(lines)


def action_for_finding(finding: Finding) -> str:
    actions = {
        "GAI-AUTO-001": (
            "Assign and confirm a named accountable human owner."
        ),
        "GAI-AUTO-002": (
            "Activate monitoring and document thresholds, alerts, "
            "and escalation."
        ),
        "GAI-AUTO-003": (
            "Define, test, and authorize a restriction, rollback, "
            "or shutdown path."
        ),
        "GAI-AUTO-004": (
            "Complete the required evidence package and human review."
        ),
        "GAI-AUTO-005": (
            "Escalate full autonomy for Critical or Frontier review."
        ),
    }
    return actions.get(
        finding.rule_id,
        f"Resolve finding {finding.rule_id} and document closure evidence.",
    )


def render_action_plan(
    rows: Sequence[Mapping[str, str]],
    findings: Sequence[Finding],
    sources: Sequence[SourceArtifact],
) -> str:
    lines = [
        "# Action Plan",
        "",
        "## Immediate Actions",
        "",
    ]

    if findings:
        seen: set[tuple[str, str]] = set()
        for finding in findings:
            key = (finding.system_id, finding.rule_id)
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"- `{safe_text(finding.system_id)}` "
                f"[{safe_text(finding.rule_id)}]: "
                f"{action_for_finding(finding)}"
            )
    else:
        lines.extend(
            [
                "- Confirm the inventory record with the named owner.",
                "- Validate evidence quality and review applicability.",
                "- Confirm monitoring and escalation responsibilities.",
                "- Exercise or review the documented shutdown path.",
            ]
        )

    lines.extend(
        [
            "",
            "## Before a Human Decision",
            "",
            "- Resolve or formally disposition every open finding.",
            "- Record the decision authority and review date.",
            "- Record conditions, restrictions, and residual risk.",
            "- Link supporting evidence and reviewer sign-off.",
            "- Re-run the toolkit after material changes.",
            "",
            "## Thirty-Day Follow-Through",
            "",
            "- Verify assigned actions were completed.",
            "- Confirm controls operate as documented.",
            "- Reassess risk after system, data, vendor, or use-case changes.",
            "- Preserve the reviewed pack as decision evidence.",
            "",
            source_section(sources),
            "",
        ]
    )
    return "\n".join(lines)


def render_documents(
    rows: Sequence[Mapping[str, str]],
    findings: Sequence[Finding],
    sources: Sequence[SourceArtifact],
) -> Dict[str, str]:
    return {
        "executive-summary.md": render_executive_summary(
            rows, findings, sources
        ),
        "system-profile.md": render_system_profile(
            rows, sources
        ),
        "risk-and-findings.md": render_risk_and_findings(
            rows, findings, sources
        ),
        "evidence-and-ownership.md": render_evidence_and_ownership(
            rows, sources
        ),
        "decision-record.md": render_decision_record(
            sources
        ),
        "action-plan.md": render_action_plan(
            rows, findings, sources
        ),
    }


def build_manifest(
    rows: Sequence[Mapping[str, str]],
    findings: Sequence[Finding],
    sources: Sequence[SourceArtifact],
    documents: Mapping[str, str],
    *,
    policy_id: str = "legacy-unspecified",
    policy_version: str = "legacy-unspecified",
    normalization_version: str = "legacy-unspecified",
    canonical_inventory_digest: str = "sha256:" + "0" * 64,
    evaluation_time: str | None = None,
) -> str:
    generated_files = []
    for name in sorted(documents):
        content = documents[name].encode("utf-8")
        generated_files.append(
            {
                "path": name,
                "sha256": sha256_bytes(content),
            }
        )

    manifest = {
        "canonical_inventory_digest": canonical_inventory_digest,
        "decision_status": "pending_human_decision",
        "evaluation_time": evaluation_time,
        "generator": "automation/scripts/generate_decision_pack.py",
        "generator_version": "1.0.0",
        "generated_files": generated_files,
        "governance_gate_result": gate_state(findings),
        "hash_mode": "sha256-text-lf",
        "manifest_schema_version": "1.0.0",
        "normalization_version": normalization_version,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "schema_version": "1.0",
        "source_artifacts": [
            {
                "path": source.path.name,
                "role": source.role,
                "sha256": sha256_text(source.path),
            }
            for source in sources
        ],
        "system_count": len(rows),
        "system_ids": [
            row["system_id"] for row in rows
        ],
    }
    return json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
    ) + "\n"


def prepare_pack(
    risk_csv: Path,
    schema_report: Path,
    governance_report: Path,
    executive_report: Path,
    schema: Path,
    policy: Path,
    normalized_inventory: Path | None = None,
    findings_json: Path | None = None,
    result_json: Path | None = None,
    evaluation_time: str | None = None,
) -> Dict[str, str]:
    source_items = [
        SourceArtifact("Schema validation report", schema_report),
        SourceArtifact("Risk-tier inventory", risk_csv),
        SourceArtifact("Governance validation report", governance_report),
        SourceArtifact("Executive governance report", executive_report),
        SourceArtifact("Runtime inventory schema", schema),
        SourceArtifact("Runtime governance policy", policy),
    ]
    for role, path in (
        ("Normalized canonical inventory", normalized_inventory),
        ("Machine-readable governance findings", findings_json),
        ("Machine-readable governance result", result_json),
    ):
        if path is not None:
            source_items.append(SourceArtifact(role, path))
    sources = tuple(source_items)

    for source in sources:
        if not source.path.is_file():
            raise DecisionPackError(
                f"Missing required {source.role}: {source.path}"
            )

    schema_text = read_required_text(
        schema_report,
        "schema validation report",
    )
    governance_text = read_required_text(
        governance_report,
        "governance validation report",
    )
    executive_text = read_required_text(
        executive_report,
        "executive governance report",
    )
    validate_source_documents(
        schema_text,
        executive_text,
    )

    rows = read_inventory(risk_csv)
    findings = parse_findings(governance_text)

    known_ids = {
        row["system_id"] for row in rows
    }
    unknown_ids = sorted(
        {
            finding.system_id
            for finding in findings
            if finding.system_id not in known_ids
        }
    )
    if unknown_ids:
        raise DecisionPackError(
            "Governance findings reference unknown system IDs: "
            + ", ".join(unknown_ids)
        )

    documents = render_documents(
        rows,
        findings,
        sources,
    )
    policy_value = json.loads(policy.read_text(encoding="utf-8"))
    normalized_value = (
        json.loads(normalized_inventory.read_text(encoding="utf-8"))
        if normalized_inventory is not None
        else None
    )
    canonical_digest = "sha256:" + sha256_bytes(
        json.dumps(
            normalized_value["records"] if normalized_value else rows,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    documents["manifest.json"] = build_manifest(
        rows,
        findings,
        sources,
        documents,
        policy_id=policy_value.get("policy_id", "legacy-unspecified"),
        policy_version=policy_value.get("policy_version", "legacy-unspecified"),
        normalization_version=(normalized_value or {}).get("normalization_version", "legacy-unspecified"),
        canonical_inventory_digest=canonical_digest,
        evaluation_time=evaluation_time,
    )
    return documents


def write_pack(
    output_dir: Path,
    documents: Mapping[str, str],
) -> None:
    if output_dir.exists():
        if output_dir.is_dir():
            shutil.rmtree(output_dir)
        else:
            output_dir.unlink()

    output_dir.mkdir(parents=True)

    for name in PACK_FILES:
        (output_dir / name).write_text(
            documents[name],
            encoding="utf-8",
            newline="\n",
        )


def directory_files(path: Path) -> Dict[str, bytes]:
    if not path.is_dir():
        raise DecisionPackError(
            f"Decision Pack directory not found: {path}"
        )

    return {
        file.relative_to(path).as_posix(): file.read_bytes()
        for file in sorted(path.rglob("*"))
        if file.is_file()
    }


def compare_pack(
    expected_dir: Path,
    generated_dir: Path,
) -> List[str]:
    expected = directory_files(expected_dir)
    generated = directory_files(generated_dir)
    differences: List[str] = []

    expected_names = set(expected)
    generated_names = set(generated)

    for name in sorted(expected_names - generated_names):
        differences.append(f"missing generated file: {name}")

    for name in sorted(generated_names - expected_names):
        differences.append(f"unexpected generated file: {name}")

    for name in sorted(expected_names & generated_names):
        if expected[name] != generated[name]:
            differences.append(f"changed generated file: {name}")

    return differences


def generate_or_check(
    output_dir: Path,
    documents: Mapping[str, str],
    check: bool,
) -> None:
    if not check:
        write_pack(output_dir, documents)
        print(f"Decision Pack generated: {output_dir}")
        return

    with tempfile.TemporaryDirectory() as temp_name:
        generated_dir = Path(temp_name) / "decision-pack"
        write_pack(generated_dir, documents)
        differences = compare_pack(
            output_dir,
            generated_dir,
        )

    if differences:
        print("Decision Pack drift detected:")
        for difference in differences:
            print(f"- {difference}")
        raise SystemExit(1)

    print(f"Decision Pack is reproducible: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or verify a deterministic AI Governance "
            "Decision Pack."
        )
    )
    parser.add_argument(
        "--risk-csv",
        type=Path,
        required=True,
        help="Risk-tier inventory CSV.",
    )
    parser.add_argument(
        "--schema-report",
        type=Path,
        required=True,
        help="Passing schema-validation report.",
    )
    parser.add_argument(
        "--governance-report",
        type=Path,
        required=True,
        help="Governance-validation report.",
    )
    parser.add_argument(
        "--executive-report",
        type=Path,
        required=True,
        help="Executive governance report.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        required=True,
        help="Runtime inventory schema.",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        required=True,
        help="Runtime governance policy.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Decision Pack output directory.",
    )
    parser.add_argument("--normalized-inventory", type=Path)
    parser.add_argument("--findings-json", type=Path)
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--evaluation-time")
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Regenerate in a temporary directory and fail when "
            "the committed output differs."
        ),
    )
    args = parser.parse_args()

    try:
        documents = prepare_pack(
            args.risk_csv,
            args.schema_report,
            args.governance_report,
            args.executive_report,
            args.schema,
            args.policy,
            args.normalized_inventory,
            args.findings_json,
            args.result_json,
            args.evaluation_time,
        )
        generate_or_check(
            args.output_dir,
            documents,
            args.check,
        )
    except DecisionPackError as exc:
        print(f"Decision Pack generation failed: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
