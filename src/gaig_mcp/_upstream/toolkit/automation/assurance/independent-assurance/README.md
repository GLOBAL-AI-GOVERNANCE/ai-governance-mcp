# Independent Assurance Profile

Optional, non-authorizing profile.

Assembles reference evidence for an independent evaluation without transferring authority.

## Scope

- Evaluator identity and interest disclosure
- Evaluation scope and method
- Competence basis
- Findings and limitations
- Residual risk statement
- Deployment-readiness opinion (non-binding)
- Validity period and revalidation triggers

## Autonomous agents (contract 0.2.0)

Set `autonomous_agent: true` for an agent that can act without per-action human approval. The case then fails with a CRITICAL finding unless it carries:

- `agent_passport_ref` with `passport_id` and a `sha256:` `passport_digest` (`AGENT_PASSPORT_MISSING`)
- `shutdown_evidence` with `shutdown_tested_at` (`YYYY-MM-DDTHH:MM:SSZ`), `result: PASSED`, and at least one `evidence_refs` entry (`SHUTDOWN_TEST_MISSING`, `SHUTDOWN_TEST_NOT_PASSED`, `SHUTDOWN_TEST_EVIDENCE_REFS`)
- a shutdown test no older than 90 days at `--evaluation-time` (`SHUTDOWN_TEST_STALE`). `max_shutdown_test_age_days` can shorten this bound, never extend it. A test dated after the evaluation time fails (`SHUTDOWN_TEST_IN_FUTURE`), and a run without an evaluation time fails closed (`SHUTDOWN_TEST_AGE_UNKNOWN`).

The legacy `shutdown_evidence_present` boolean still satisfies a non-autonomous high-consequence case, and current structured `shutdown_evidence` satisfies it too. It does not satisfy an autonomous agent. The result reports `details.shutdown_test` with the state, age, and bound.

The profile checks the submitted record. It does not establish that the shutdown test occurred or validate the passport itself; validate the passport with the Agentic AI Governance validator.

Fixtures: `agent_pass.json`, `agent_missing_passport.json`, `agent_missing_shutdown_test.json`, `agent_stale_shutdown_test.json`, `agent_failed_shutdown_test.json`, `agent_tighter_max_age.json`. They are evaluated at `2026-10-24T00:00:00Z` in the tests.

## Boundary

`authority_effect: NONE`

This profile produces evidence references only. It does not establish compliance, certification, production authorization, or operational authority.

Native artifacts remain owned by their originating repositories. The profile references them.
