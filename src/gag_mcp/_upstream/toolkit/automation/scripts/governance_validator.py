#!/usr/bin/env python3
"""
Governance policy evaluator.

Loads governance-rules.yaml as JSON-compatible YAML and evaluates each
inventory row against the checked-in rule definitions.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence


SEVERITY_LEVELS = {
    "high": 1,
    "critical": 2,
}
FAIL_THRESHOLDS = {
    "high": 1,
    "critical": 2,
}
SUPPORTED_OPERATORS = {
    "blank",
    "equals",
    "in",
    "not_in",
}


class PolicyValidationError(ValueError):
    """Raised when policy configuration cannot be safely evaluated."""


@dataclass(frozen=True)
class Finding:
    rule_id: str
    rule_name: str
    severity: str
    system_id: str
    system_name: str
    message: str


def load_policy(path: Path) -> Dict[str, object]:
    if not path.is_file():
        raise PolicyValidationError(
            f"Policy file not found: {path}"
        )

    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyValidationError(
            "governance-rules.yaml must remain JSON-compatible YAML: "
            f"{exc}"
        ) from exc

    if not isinstance(policy, dict):
        raise PolicyValidationError(
            "Policy root must be an object."
        )

    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise PolicyValidationError(
            "Policy must contain a non-empty 'rules' list."
        )

    seen_ids: set[str] = set()

    for index, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            raise PolicyValidationError(
                f"Rule {index} must be an object."
            )

        required_keys = {
            "id",
            "name",
            "description",
            "severity",
            "message",
            "all",
        }
        missing = required_keys - set(rule)
        if missing:
            raise PolicyValidationError(
                f"Rule {index} missing keys: "
                + ", ".join(sorted(missing))
            )

        rule_id = rule["id"]
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise PolicyValidationError(
                f"Rule {index} has an invalid id."
            )
        if rule_id in seen_ids:
            raise PolicyValidationError(
                f"Duplicate rule id: {rule_id}"
            )
        seen_ids.add(rule_id)

        severity = rule["severity"]
        if severity not in SEVERITY_LEVELS:
            raise PolicyValidationError(
                f"{rule_id}: unsupported severity '{severity}'."
            )

        conditions = rule["all"]
        if not isinstance(conditions, list) or not conditions:
            raise PolicyValidationError(
                f"{rule_id}: 'all' must be a non-empty list."
            )

        for condition in conditions:
            validate_condition(rule_id, condition)

    return policy


def validate_condition(
    rule_id: str,
    condition: object,
) -> None:
    if not isinstance(condition, dict):
        raise PolicyValidationError(
            f"{rule_id}: every condition must be an object."
        )

    field = condition.get("field")
    operator = condition.get("operator")

    if not isinstance(field, str) or not field.strip():
        raise PolicyValidationError(
            f"{rule_id}: condition field is required."
        )

    if operator not in SUPPORTED_OPERATORS:
        raise PolicyValidationError(
            f"{rule_id}: unsupported operator '{operator}'."
        )

    if operator == "blank":
        allowed_keys = {"field", "operator"}
    elif operator == "equals":
        allowed_keys = {"field", "operator", "value"}
        if not isinstance(condition.get("value"), str):
            raise PolicyValidationError(
                f"{rule_id}: equals requires a string value."
            )
    else:
        allowed_keys = {"field", "operator", "values"}
        values = condition.get("values")
        if (
            not isinstance(values, list)
            or not values
            or not all(isinstance(item, str) for item in values)
        ):
            raise PolicyValidationError(
                f"{rule_id}: {operator} requires string values."
            )

    unknown_keys = set(condition) - allowed_keys
    if unknown_keys:
        raise PolicyValidationError(
            f"{rule_id}: unsupported condition keys: "
            + ", ".join(sorted(unknown_keys))
        )


def condition_matches(
    row: Mapping[str, str],
    condition: Mapping[str, object],
) -> bool:
    field = str(condition["field"])
    operator = str(condition["operator"])
    value = str(row.get(field, "")).strip()

    if operator == "blank":
        return value == ""
    if operator == "equals":
        return value == condition["value"]
    if operator == "in":
        return value in condition["values"]
    if operator == "not_in":
        return value not in condition["values"]

    raise PolicyValidationError(
        f"Unsupported operator reached runtime: {operator}"
    )


def evaluate_row(
    row: Mapping[str, str],
    rules: Sequence[Mapping[str, object]],
) -> List[Finding]:
    findings: List[Finding] = []

    for rule in rules:
        conditions = rule["all"]

        if all(
            condition_matches(row, condition)
            for condition in conditions
        ):
            findings.append(
                Finding(
                    rule_id=str(rule["id"]),
                    rule_name=str(rule["name"]),
                    severity=str(rule["severity"]),
                    system_id=(
                        row.get("system_id", "").strip()
                        or "[unknown id]"
                    ),
                    system_name=(
                        row.get("system_name", "").strip()
                        or "[unknown system]"
                    ),
                    message=str(rule["message"]),
                )
            )

    return findings


def read_rows(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        raise PolicyValidationError(
            f"Inventory file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file_handle:
        reader = csv.DictReader(file_handle)
        rows = list(reader)

    if not rows:
        raise PolicyValidationError(
            "Inventory CSV has no data rows."
        )

    return [
        {
            str(key): "" if value is None else str(value)
            for key, value in row.items()
            if key is not None
        }
        for row in rows
    ]


def should_fail(
    findings: Sequence[Finding],
    fail_on: str,
) -> bool:
    if fail_on == "none":
        return False

    threshold = FAIL_THRESHOLDS[fail_on]
    return any(
        SEVERITY_LEVELS[finding.severity] >= threshold
        for finding in findings
    )


def write_report(
    report_path: Path,
    policy_path: Path,
    findings: Sequence[Finding],
    rule_count: int,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Governance Validation Report",
        "",
        f"- Policy source: `{policy_path.name}`",
        f"- Rules evaluated: **{rule_count}**",
        "",
    ]

    if not findings:
        lines.append("No governance gaps found.")
    else:
        lines.extend(["## Findings", ""])
        for finding in findings:
            lines.append(
                f"- [{finding.rule_id}] {finding.system_name} "
                f"({finding.system_id}): "
                f"{finding.severity.upper()} - {finding.message}"
            )

    report_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def validate_csv(
    input_path: Path,
    report_path: Path,
    policy_path: Path,
) -> List[Finding]:
    policy = load_policy(policy_path)
    rules = policy["rules"]
    rows = read_rows(input_path)

    findings: List[Finding] = []
    for row in rows:
        findings.extend(evaluate_row(row, rules))

    write_report(
        report_path,
        policy_path,
        findings,
        len(rules),
    )
    print(f"Governance validation complete: {report_path}")
    return findings


def main() -> None:
    default_policy = (
        Path(__file__).resolve().parent.parent
        / "policy-as-code"
        / "governance-rules.yaml"
    )

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate AI inventory records against "
            "runtime governance policy."
        )
    )
    parser.add_argument(
        "input_csv",
        type=Path,
        help="Path to risk-tiered AI inventory CSV.",
    )
    parser.add_argument(
        "--report",
        "-r",
        type=Path,
        default=Path("governance-validation-report.md"),
        help="Output report path.",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=default_policy,
        help="Path to governance-rules.yaml.",
    )
    parser.add_argument(
        "--fail-on",
        choices=("none", "high", "critical"),
        default="critical",
        help=(
            "Return exit code 1 when findings meet or exceed "
            "the selected severity."
        ),
    )
    args = parser.parse_args()

    try:
        findings = validate_csv(
            args.input_csv,
            args.report,
            args.policy,
        )
    except PolicyValidationError as exc:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            "# Governance Validation Report\n\n"
            f"Policy or input error: {exc}\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"Governance validation failed: {exc}")
        raise SystemExit(2) from exc

    if should_fail(findings, args.fail_on):
        print(
            "Governance validation blocked by "
            f"{args.fail_on.upper()} findings."
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
