#!/usr/bin/env python3
"""
sovereignty_check.py — AI Sovereignty Control Layer (v2.2.0)
Part of Global AI Governance Toolkit.

Converts sovereignty policy into an automated pass/fail governance report.

Reads a sovereignty assessment CSV (one row per AI system), evaluates each
system against the Sovereignty Law hard gates and advisory controls, assigns
a verdict (PASS / CONDITIONAL / FAIL), and writes Markdown + JSON reports.

Sovereignty Law:
  "No AI system may extract more institutional value than the organization
   can govern, audit, reverse, or retain."

Usage:
  python automation/scripts/sovereignty_check.py \
      automation/sample-data/sample-sovereignty-assessment.csv \
      --outdir automation/reports

Exit codes:
  0 = no hard-gate failures (PASS or CONDITIONAL only)
  1 = one or more systems FAILED a hard gate (suitable for CI enforcement)
  2 = input or schema error

Stdlib only. No dependencies. Python 3.8+.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SENSITIVITY_TIERS = ["S0", "S1", "S2", "S3", "S4"]

TIER_LABELS = {
    "S0": "Public / No Institutional Signal",
    "S1": "Internal Productivity",
    "S2": "Sensitive Enterprise Workflow",
    "S3": "High-Alpha / Regulated / Client-Impacting",
    "S4": "Sovereign / Core Institutional Knowledge",
}

ASSURANCE_LEVELS = {
    "tier1_owned": 1,       # owned / air-gapped hardware (structural)
    "tier2_attested": 2,    # rented compute w/ hardware attestation (structural)
    "tier3_zdr_cloud": 3,   # closed model under zero-data-retention (contractual)
    "tier4_standard": 4,    # default third-party usage, no ZDR (contractual, weakest)
}

BOOL_FIELDS = [
    "owner_present",
    "system_inventory_complete",
    "zdr_confirmed",
    "training_on_customer_data_prohibited",
    "metadata_retention_reviewed",
    "model_provider_switchable",
    "model_routing_documented",
    "agent_tool_access",
    "agent_permissions_defined",
    "autonomous_actions",
    "rollback_or_branching_available",
    "audit_logging_enabled",
    "human_oversight_defined",
    "context_capture_owned_by_org",
    "shutdown_path_defined",
]

REQUIRED_FIELDS = ["system_name", "sensitivity_tier", "compute_assurance_level"] + BOOL_FIELDS

TRUE_VALUES = {"true", "yes", "y", "1"}
FALSE_VALUES = {"false", "no", "n", "0", ""}


def parse_bool(raw, field, system_name):
    val = str(raw).strip().lower()
    if val in TRUE_VALUES:
        return True
    if val in FALSE_VALUES:
        return False
    raise ValueError(
        f"System '{system_name}': field '{field}' has invalid boolean value '{raw}' "
        f"(use yes/no or true/false)"
    )


# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------
# Hard gates enforce the Sovereignty Law. Any hard-gate failure = FAIL.
# Advisory controls flag sovereignty debt. Any advisory finding = CONDITIONAL.

def tier_at_least(system, tier):
    return SENSITIVITY_TIERS.index(system["sensitivity_tier"]) >= SENSITIVITY_TIERS.index(tier)


HARD_GATES = [
    {
        "id": "G01",
        "law": "No owner, no deployment.",
        "check": lambda s: s["owner_present"],
        "finding": "No accountable owner is assigned to this AI system.",
        "action": "Assign a named accountable owner before any deployment or continued use.",
    },
    {
        "id": "G02",
        "law": "No inventory, no governance.",
        "check": lambda s: s["system_inventory_complete"],
        "finding": "System is not fully recorded in the AI system inventory.",
        "action": "Complete the inventory record: purpose, data touched, models, providers, integrations.",
    },
    {
        "id": "G03",
        "law": "No ZDR or equivalent protection, no sensitive data.",
        "check": lambda s: (not tier_at_least(s, "S2"))
        or s["zdr_confirmed"]
        or ASSURANCE_LEVELS[s["compute_assurance_level"]] <= 2,
        "finding": "Sensitive data (S2+) flows to an external model without confirmed ZDR or structural compute assurance.",
        "action": "Confirm a zero-data-retention agreement, move the workload to structural assurance (owned or attested compute), or downgrade the data sent.",
    },
    {
        "id": "G04",
        "law": "No training on institutional data.",
        "check": lambda s: (not tier_at_least(s, "S2")) or s["training_on_customer_data_prohibited"],
        "finding": "Provider training on institutional/customer data is not contractually prohibited for an S2+ workload.",
        "action": "Obtain a contractual prohibition on training with institutional and customer data before S2+ use.",
    },
    {
        "id": "G05",
        "law": "No granular permissions, no tool access.",
        "check": lambda s: (not s["agent_tool_access"]) or s["agent_permissions_defined"],
        "finding": "An agent has tool or data access without granular, role/classification/purpose-based permissions.",
        "action": "Define and enforce agent permissions before granting tool, data, or action access.",
    },
    {
        "id": "G06",
        "law": "No audit trail, no production agent.",
        "check": lambda s: (not tier_at_least(s, "S2")) or s["audit_logging_enabled"],
        "finding": "S2+ workload runs without append-only audit logging of initiator, prompt, model, data accessed, and result.",
        "action": "Enable audit logging that can replay any decision and answer 'who touched what' before continued use.",
    },
    {
        "id": "G07",
        "law": "No rollback path, no autonomous action.",
        "check": lambda s: (not s["autonomous_actions"]) or s["rollback_or_branching_available"],
        "finding": "System takes autonomous actions without branching, rollback, or reversibility.",
        "action": "Restrict the system to human-in-the-loop, or implement branch-before-commit with rollback.",
    },
    {
        "id": "G08",
        "law": "Human authority remains accountable.",
        "check": lambda s: (not tier_at_least(s, "S3")) or s["human_oversight_defined"],
        "finding": "S3+ workload lacks a defined human oversight and escalation model.",
        "action": "Document who reviews outputs, who can override, and how escalation works before S3+ use.",
    },
    {
        "id": "G09",
        "law": "No shutdown path, no frontier release.",
        "check": lambda s: (not tier_at_least(s, "S3")) or s["shutdown_path_defined"],
        "finding": "S3+ workload has no defined shutdown authority or kill path.",
        "action": "Define who can shut the system down, how fast, and what happens to in-flight work.",
    },
    {
        "id": "G10",
        "law": "Sovereign workloads require structural assurance.",
        "check": lambda s: (not tier_at_least(s, "S4"))
        or ASSURANCE_LEVELS[s["compute_assurance_level"]] <= 2,
        "finding": "S4 (sovereign / core institutional knowledge) workload runs on contractual-only assurance.",
        "action": "Move S4 workloads to owned hardware or attested compute. Contracts are not isolation.",
    },
]

ADVISORY_CONTROLS = [
    {
        "id": "A01",
        "principle": "ZDR alone is not enough — review derived metadata.",
        "check": lambda s: (not tier_at_least(s, "S2")) or s["metadata_retention_reviewed"],
        "finding": "Retention of derived metadata (classifier outputs, monitoring logs, telemetry) has not been reviewed.",
        "action": "Review provider terms for metadata and telemetry retention that falls outside content-only ZDR language.",
    },
    {
        "id": "A02",
        "principle": "No model liquidity, no strategic dependency.",
        "check": lambda s: s["model_provider_switchable"],
        "finding": "The system depends on a single model provider and cannot switch with low friction.",
        "action": "Add model-agnostic routing and a documented exit path to restore negotiating leverage.",
    },
    {
        "id": "A03",
        "principle": "Route every workload deliberately.",
        "check": lambda s: s["model_routing_documented"],
        "finding": "No documented routing decision (sensitivity -> assurance -> model path) exists for this workload.",
        "action": "Record a model routing decision using templates/ai-model-routing-record.md.",
    },
    {
        "id": "A04",
        "principle": "No owned context layer, no compounding institutional knowledge.",
        "check": lambda s: (not tier_at_least(s, "S2")) or s["context_capture_owned_by_org"],
        "finding": "Workflow signal and know-how are captured inside a provider's system, not an organization-owned context layer.",
        "action": "Capture decisions, actions, and structured context in an ontology/knowledge layer the organization owns.",
    },
]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_system(system):
    gate_failures = []
    for gate in HARD_GATES:
        if not gate["check"](system):
            gate_failures.append(
                {"id": gate["id"], "law": gate["law"], "finding": gate["finding"], "action": gate["action"]}
            )

    advisories = []
    for adv in ADVISORY_CONTROLS:
        if not adv["check"](system):
            advisories.append(
                {"id": adv["id"], "principle": adv["principle"], "finding": adv["finding"], "action": adv["action"]}
            )

    total_checks = len(HARD_GATES) + len(ADVISORY_CONTROLS)
    passed = total_checks - len(gate_failures) - len(advisories)
    score = round(100 * passed / total_checks)

    if gate_failures:
        verdict = "FAIL"
    elif advisories:
        verdict = "CONDITIONAL"
    else:
        verdict = "PASS"

    return {
        "system_name": system["system_name"],
        "sensitivity_tier": system["sensitivity_tier"],
        "sensitivity_label": TIER_LABELS[system["sensitivity_tier"]],
        "compute_assurance_level": system["compute_assurance_level"],
        "verdict": verdict,
        "score": score,
        "hard_gate_failures": gate_failures,
        "advisories": advisories,
    }


def load_assessments(csv_path):
    systems = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV appears to be empty.")
        headers = [h.strip() for h in reader.fieldnames]
        missing = [c for c in REQUIRED_FIELDS if c not in headers]
        if missing:
            raise ValueError("CSV is missing required columns: " + ", ".join(missing))

        for i, row in enumerate(reader, start=2):
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            name = row.get("system_name", "")
            if not name:
                raise ValueError(f"Row {i}: system_name is required.")

            tier = row.get("sensitivity_tier", "").upper()
            if tier not in SENSITIVITY_TIERS:
                raise ValueError(
                    f"System '{name}': sensitivity_tier '{row.get('sensitivity_tier')}' is invalid "
                    f"(use one of {', '.join(SENSITIVITY_TIERS)})."
                )

            assurance = row.get("compute_assurance_level", "").lower()
            if assurance not in ASSURANCE_LEVELS:
                raise ValueError(
                    f"System '{name}': compute_assurance_level '{row.get('compute_assurance_level')}' is invalid "
                    f"(use one of {', '.join(ASSURANCE_LEVELS)})."
                )

            system = {"system_name": name, "sensitivity_tier": tier, "compute_assurance_level": assurance}
            for field in BOOL_FIELDS:
                system[field] = parse_bool(row.get(field, ""), field, name)
            systems.append(system)

    if not systems:
        raise ValueError("CSV contains no assessment rows.")
    return systems


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def md_safe(text):
    """Escape characters that would break Markdown table cells or headings."""
    return str(text).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_markdown(results, source_file, generated_at):
    counts = {"PASS": 0, "CONDITIONAL": 0, "FAIL": 0}
    for r in results:
        counts[r["verdict"]] += 1

    lines = []
    lines.append("# AI Sovereignty Check Report")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append(f"Source: `{source_file}`")
    lines.append("")
    lines.append("Sovereignty Law: *No AI system may extract more institutional value than the "
                 "organization can govern, audit, reverse, or retain.*")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Verdict | Count |")
    lines.append("|---|---|")
    lines.append(f"| PASS | {counts['PASS']} |")
    lines.append(f"| CONDITIONAL | {counts['CONDITIONAL']} |")
    lines.append(f"| FAIL | {counts['FAIL']} |")
    lines.append("")
    lines.append("| System | Sensitivity | Compute Assurance | Score | Verdict |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        lines.append(
            f"| {md_safe(r['system_name'])} | {r['sensitivity_tier']} — {r['sensitivity_label']} "
            f"| {r['compute_assurance_level']} | {r['score']}/100 | **{r['verdict']}** |"
        )
    lines.append("")

    lines.append("## Findings")
    for r in results:
        lines.append("")
        lines.append(f"### {md_safe(r['system_name'])} — {r['verdict']}")
        lines.append("")
        lines.append(f"Sensitivity: {r['sensitivity_tier']} ({r['sensitivity_label']}). "
                     f"Compute assurance: {r['compute_assurance_level']}. Control score: {r['score']}/100.")
        if not r["hard_gate_failures"] and not r["advisories"]:
            lines.append("")
            lines.append("All hard gates and advisory controls satisfied.")
        if r["hard_gate_failures"]:
            lines.append("")
            lines.append("**Hard-gate failures (deployment blocked until resolved):**")
            lines.append("")
            for g in r["hard_gate_failures"]:
                lines.append(f"- `{g['id']}` {g['law']} — {g['finding']} Required action: {g['action']}")
        if r["advisories"]:
            lines.append("")
            lines.append("**Advisory findings (sovereignty debt — remediate on a schedule):**")
            lines.append("")
            for a in r["advisories"]:
                lines.append(f"- `{a['id']}` {a['principle']} — {a['finding']} Recommended action: {a['action']}")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI Sovereignty Control Layer — automated governance check.")
    parser.add_argument("csv_path", help="Path to the sovereignty assessment CSV.")
    parser.add_argument("--outdir", default="automation/reports", help="Directory for generated reports.")
    args = parser.parse_args(argv)

    try:
        systems = load_assessments(args.csv_path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    results = [evaluate_system(s) for s in systems]
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    os.makedirs(args.outdir, exist_ok=True)
    md_path = os.path.join(args.outdir, "sovereignty-report.md")
    json_path = os.path.join(args.outdir, "sovereignty-report.json")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(results, args.csv_path, generated_at))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": generated_at, "source": args.csv_path, "results": results},
            f, indent=2,
        )

    any_fail = False
    print("AI Sovereignty Check — v2.2.0")
    print("-" * 60)
    for r in results:
        flag = {"PASS": "[PASS]       ", "CONDITIONAL": "[CONDITIONAL]", "FAIL": "[FAIL]       "}[r["verdict"]]
        print(f"{flag} {r['system_name']}  ({r['sensitivity_tier']}, {r['score']}/100)")
        if r["verdict"] == "FAIL":
            any_fail = True
    print("-" * 60)
    print(f"Reports written: {md_path}  {json_path}")

    if any_fail:
        print("RESULT: BLOCKED — one or more systems failed a sovereignty hard gate.")
        return 1
    print("RESULT: CLEAR — no hard-gate failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
