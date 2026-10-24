# Auditable AI Assurance Profile

`auditable-ai-v1` (`1.0.0-rc.2`) checks the submitted assurance-case chain: Safety Claim → Control → Implementation → Test → Evidence → Human Review → Bounded Decision.

It verifies bounded structure, declared consistency, reference hygiene, and submitted evidence integrity. It does not establish universal technical truth, safety, certification, compliance, provider behavior, risk acceptance, or deployment approval. `CONTROLLED_TEST_READY` is a bounded human-reviewed advancement state, not production authorization.

Run `gag profile auditable-ai-v1 automation/assurance/auditable-ai/fixtures/pass.json --outdir PROFILE_OUTPUT`.

Local evidence paths must remain inside the assurance-case directory. Optional SHA-256 values protect artifact identity. Expiry checks require an explicit evaluation time.

The frozen machine-only gates for a future stable decision are in [`stable-acceptance-v1.json`](stable-acceptance-v1.json). They do not declare 1.0 stable; independent review and the final stable release decision remain external and unestablished.
