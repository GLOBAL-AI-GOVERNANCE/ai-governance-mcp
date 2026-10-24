# AI Sovereignty Check Report

Generated: 2026-07-11 05:07:48 UTC
Source: `automation/sample-data/sample-sovereignty-assessment.csv`

Sovereignty Law: *No AI system may extract more institutional value than the organization can govern, audit, reverse, or retain.*

## Summary

| Verdict | Count |
|---|---|
| PASS | 3 |
| CONDITIONAL | 1 |
| FAIL | 3 |

| System | Sensitivity | Compute Assurance | Score | Verdict |
|---|---|---|---|---|
| Public FAQ Chatbot | S0 — Public / No Institutional Signal | tier4_standard | 100/100 | **PASS** |
| Internal Drafting Assistant | S1 — Internal Productivity | tier3_zdr_cloud | 93/100 | **CONDITIONAL** |
| Client Analytics Copilot | S3 — High-Alpha / Regulated / Client-Impacting | tier3_zdr_cloud | 100/100 | **PASS** |
| Procurement Automation Agent | S3 — High-Alpha / Regulated / Client-Impacting | tier3_zdr_cloud | 86/100 | **FAIL** |
| Core IP Research Assistant | S4 — Sovereign / Core Institutional Knowledge | tier3_zdr_cloud | 93/100 | **FAIL** |
| Shadow Marketing Tool | S2 — Sensitive Enterprise Workflow | tier4_standard | 36/100 | **FAIL** |
| Sovereign Modeling Environment | S4 — Sovereign / Core Institutional Knowledge | tier1_owned | 100/100 | **PASS** |

## Findings

### Public FAQ Chatbot — PASS

Sensitivity: S0 (Public / No Institutional Signal). Compute assurance: tier4_standard. Control score: 100/100.

All hard gates and advisory controls satisfied.

### Internal Drafting Assistant — CONDITIONAL

Sensitivity: S1 (Internal Productivity). Compute assurance: tier3_zdr_cloud. Control score: 93/100.

**Advisory findings (sovereignty debt — remediate on a schedule):**

- `A02` No model liquidity, no strategic dependency. — The system depends on a single model provider and cannot switch with low friction. Recommended action: Add model-agnostic routing and a documented exit path to restore negotiating leverage.

### Client Analytics Copilot — PASS

Sensitivity: S3 (High-Alpha / Regulated / Client-Impacting). Compute assurance: tier3_zdr_cloud. Control score: 100/100.

All hard gates and advisory controls satisfied.

### Procurement Automation Agent — FAIL

Sensitivity: S3 (High-Alpha / Regulated / Client-Impacting). Compute assurance: tier3_zdr_cloud. Control score: 86/100.

**Hard-gate failures (deployment blocked until resolved):**

- `G05` No granular permissions, no tool access. — An agent has tool or data access without granular, role/classification/purpose-based permissions. Required action: Define and enforce agent permissions before granting tool, data, or action access.
- `G07` No rollback path, no autonomous action. — System takes autonomous actions without branching, rollback, or reversibility. Required action: Restrict the system to human-in-the-loop, or implement branch-before-commit with rollback.

### Core IP Research Assistant — FAIL

Sensitivity: S4 (Sovereign / Core Institutional Knowledge). Compute assurance: tier3_zdr_cloud. Control score: 93/100.

**Hard-gate failures (deployment blocked until resolved):**

- `G10` Sovereign workloads require structural assurance. — S4 (sovereign / core institutional knowledge) workload runs on contractual-only assurance. Required action: Move S4 workloads to owned hardware or attested compute. Contracts are not isolation.

### Shadow Marketing Tool — FAIL

Sensitivity: S2 (Sensitive Enterprise Workflow). Compute assurance: tier4_standard. Control score: 36/100.

**Hard-gate failures (deployment blocked until resolved):**

- `G01` No owner, no deployment. — No accountable owner is assigned to this AI system. Required action: Assign a named accountable owner before any deployment or continued use.
- `G02` No inventory, no governance. — System is not fully recorded in the AI system inventory. Required action: Complete the inventory record: purpose, data touched, models, providers, integrations.
- `G03` No ZDR or equivalent protection, no sensitive data. — Sensitive data (S2+) flows to an external model without confirmed ZDR or structural compute assurance. Required action: Confirm a zero-data-retention agreement, move the workload to structural assurance (owned or attested compute), or downgrade the data sent.
- `G04` No training on institutional data. — Provider training on institutional/customer data is not contractually prohibited for an S2+ workload. Required action: Obtain a contractual prohibition on training with institutional and customer data before S2+ use.
- `G06` No audit trail, no production agent. — S2+ workload runs without append-only audit logging of initiator, prompt, model, data accessed, and result. Required action: Enable audit logging that can replay any decision and answer 'who touched what' before continued use.

**Advisory findings (sovereignty debt — remediate on a schedule):**

- `A01` ZDR alone is not enough — review derived metadata. — Retention of derived metadata (classifier outputs, monitoring logs, telemetry) has not been reviewed. Recommended action: Review provider terms for metadata and telemetry retention that falls outside content-only ZDR language.
- `A02` No model liquidity, no strategic dependency. — The system depends on a single model provider and cannot switch with low friction. Recommended action: Add model-agnostic routing and a documented exit path to restore negotiating leverage.
- `A03` Route every workload deliberately. — No documented routing decision (sensitivity -> assurance -> model path) exists for this workload. Recommended action: Record a model routing decision using templates/ai-model-routing-record.md.
- `A04` No owned context layer, no compounding institutional knowledge. — Workflow signal and know-how are captured inside a provider's system, not an organization-owned context layer. Recommended action: Capture decisions, actions, and structured context in an ontology/knowledge layer the organization owns.

### Sovereign Modeling Environment — PASS

Sensitivity: S4 (Sovereign / Core Institutional Knowledge). Compute assurance: tier1_owned. Control score: 100/100.

All hard gates and advisory controls satisfied.
