<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Agent Incident Readiness

This directory contains a deterministic **synthetic** reference trace for the current-main lifecycle demonstration:

> Authorized → Policy-Denied → Revoked → Rollback-Rejected → New-Passport Reauthorized

Run it locally:

```console
python tools/agent_incident_readiness.py examples/agent-incident-readiness/synthetic-lifecycle.json
```

## Human-readable sequence

| State | Decision | Consequence | Remaining risk | Next action | Timeline | Technical evidence |
|---|---|---|---|---|---|---|
| Authorized | The current validated passport and bounded policy permit the synthetic read request. | The reference returns `PERMITTED`; it performs no external action. | External systems could ignore the decision. | Preserve the decision and evidence references. | T0 | Canonical validation result plus OPA bridge result. |
| Policy-Denied | Context policy denies a synthetic peer-command request while the passport remains current. | The reference returns `NOT_PERMITTED`; revocation state does not change. | Policy denial alone does not terminate credentials or sessions. | Human authority evaluates whether revocation is warranted. | T1 | `POLICY_DENIED`, without `REVOCATION_NOT_CURRENT`. |
| Revoked | A subsequent trusted cumulative revocation update includes the original passport. | Reuse of that passport fails closed. | The local continuity boundary depends on an intact trusted store. | Retain terminal revocation and reject the old identity artifact. | T2 | Current trusted sequence 2 and `REVOCATION_NOT_CURRENT`. |
| Rollback-Rejected | An older sequence and a conflicting same-sequence state are rejected. | The trusted sequence remains 2. | This is not host-level rollback resistance. | Repair or re-establish trusted current evidence through human-governed operations. | T3 | Stateful Revocation continuity result. |
| New-Passport Reauthorized | A genuinely new validated passport with bounded authority is evaluated. | The new passport may receive `PERMITTED`; the old passport remains revoked. | The result is a reference policy decision, not runtime enforcement. | External accountable systems decide whether and how to act. | T4 | Distinct passport identifiers, validated binding, current revocation evidence, and OPA bridge result. |

The trace reuses existing passport-validation result semantics, OPA bridge contract, operating dispositions, reason codes, and Stateful Revocation continuity rules. It introduces no schema and does not alter any Alpha.1 or Alpha.2 artifact.

It is not proof of external enforcement, production containment, production IAM, credential or session termination, autonomous restoration, certification, compliance, or real-world effectiveness.
