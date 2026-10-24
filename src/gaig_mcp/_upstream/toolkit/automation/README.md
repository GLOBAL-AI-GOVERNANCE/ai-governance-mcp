# Automation Layer

## Optional profiles

`gaig profile PROFILE_ID INPUT --outdir DIRECTORY` runs a profile from [`profiles/registry.json`](profiles/registry.json) and writes deterministic `profile-result.json`. Optional `--decision-pack-manifest` verifies and records its digest without rewriting the Decision Pack. `--evaluation-time` enables reproducible expiry checks. Exit codes are `0` for PASS/CONDITIONAL, `1` for FAIL, and `2` for input or configuration error. Every result has `authority_effect: NONE`.

[`profiles/registry.json`](profiles/registry.json) is the source of truth for registered profiles and for which profiles the common browser supports. Organizational maturity uses the local-first maturity route. v2.3.0 introduced Auditable AI, the synthetic Quantum-AI exercise, and CISO accountability. v2.4.0 added independent assurance, mission assurance, and machine-learning assurance. v2.5.0 added organizational AI maturity evidence.

New profile authors can start from the additive [Profile Development Kit](PROFILE_DEVELOPMENT_KIT.md). Its deterministic scaffold is intentionally not registered or runnable until a separate contract and registry review.

The automation layer provides a repeatable path from an AI system inventory CSV to preliminary risk classification, policy-driven findings, an executive report, and a human-review Decision Pack.

## Quick Start

Installed command:

```bash
gaig check automation/sample-data/sample-ai-inventory.csv \
  --outdir automation/reports \
  --fail-on none
```

The historical script path remains a supported compatibility entry point:

```bash
python automation/scripts/run_governance_checks.py \
  automation/sample-data/sample-ai-inventory.csv \
  --outdir automation/reports \
  --fail-on none
```

The bundled sample contains intentionally blocked systems. Explicit report-only mode generates a blocked-state Decision Pack while preserving every critical finding. Remove `--fail-on none` to exercise the default fail-closed gate.

## Failure Thresholds

- Default: block `CRITICAL` findings and return exit code `1`.
- `--fail-on high`: block `HIGH` and `CRITICAL` findings.
- `--fail-on none`: explicit report-only mode; retain findings while returning exit code `0`.

## What the Pipeline Does

1. Normalizes supported CSV inputs into canonical v1 JSON and CSV.
2. Validates the canonical CSV and calculates a preliminary risk tier.
3. Checks required governance conditions.
4. Writes versioned findings and aggregate-result JSON.
5. Writes the existing human reports and Decision Pack when the gate permits.
6. Verifies pack digests and emits a reference-only handoff.
7. Blocks the process when findings meet the selected threshold.

Current checks include:

- Named ownership
- Active monitoring
- Shutdown readiness
- Evidence completeness for high-impact systems
- Escalation of full-autonomy systems

## Outputs

```text
normalized-inventory.json
canonical-inventory.csv
schema-validation-report.md
risk-tier-output.csv
governance-validation-report.md
governance-findings.json
governance-result.json
executive-ai-governance-report.md
decision-pack/
governance-handoff.json
```

Use `gaig normalize` when only canonical normalization is needed and `gaig verify` to revalidate machine contracts and pack integrity.

Schema or policy configuration errors return exit code `2`. Governance findings that meet the selected threshold return exit code `1`.

## Hosted Verification

The active workflow is:

```text
.github/workflows/ai-governance-checks.yml
```

It verifies the default valid path, the default blocked path, and explicit report-only behavior.

## Runtime Sources of Truth

The pipeline consumes:

```text
automation/schemas/ai-system-inventory.schema.json
automation/policy-as-code/governance-rules.yaml
```

The schema validates required fields and enumerated values before risk calculation. The policy file drives governance findings and stable rule identifiers. Missing or malformed runtime sources fail safely.

Risk-tier logic remains implemented in `risk_tier_calculator.py` and is not yet externalized as policy.

## Human Review Boundary

These tools support governance review. They do not replace human judgment, legal review, security review, privacy review, procurement review, compliance review, executive accountability, or board-level risk acceptance.

## Operating Law

> No AI system moves faster than ownership, evidence, authority, and control.

## Decision Pack

The generated `decision-pack/` directory contains:

```text
executive-summary.md
system-profile.md
risk-and-findings.md
evidence-and-ownership.md
decision-record.md
action-plan.md
manifest.json
```

The pack is deterministic and records a pending human decision. It does not approve deployment, certify compliance, or accept risk.

Rebuild the checked-in reference:

```bash
python automation/scripts/build_decision_pack_example.py
```

Verify that it has not drifted:

```bash
python automation/scripts/build_decision_pack_example.py --check
```
