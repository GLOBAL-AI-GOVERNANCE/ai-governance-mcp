<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Five-Minute Quickstart

This synthetic scenario represents a read-only research agent that may retrieve approved public information and draft internal summaries. It may not publish externally, purchase anything, alter systems, or access confidential data.

## Artifacts

1. [Authority graph](../action-authority/readonly-graph.json): the reachable graph calculates Level 2 for approved public-information retrieval plus internal drafting.
2. [Assessment](../assessments/approved-readonly.json): the applicable controls pass.
3. [Bound-input manifest](../bundles/valid-bundle-manifest.json): the assessment, action-authority graph, non-empty synthetic inventories, machine-readable profile descriptor, profile document, and data-authority evidence are present, hash-bound, and cross-consistent.
4. [Signed passport](../passports/signed-unrevoked.json): the issuer signs the approved authority statement.
5. [Trusted key](../trusted-keys/test-ed25519-key.json): the synthetic Ed25519 verification key is active for the evaluation time.
6. [Revocation list](../revocation/valid-revocation-list.json): the supplied signed list revokes a different synthetic passport.

## Run

From the repository root:

```bash
python -m pip install -r requirements-dev.txt
python tools/validate_artifact.py \
  --kind passport \
  --trusted-key examples/trusted-keys/test-ed25519-key.json \
  --revocation-list examples/revocation/valid-revocation-list.json \
  --bundle-manifest examples/bundles/valid-bundle-manifest.json \
  --bundle-root . \
  --at-time 2026-07-18T12:00:00Z \
  examples/passports/signed-unrevoked.json
```

The result should report `issued_assessment_result: APPROVED`, `verification_primary_status: VALID`, and `operating_disposition: PERMITTED`. To see revocation enforcement, replace the final passport path with `examples/passports/signed-revoked.json`; that passport is present in the supplied list and reports `verification_primary_status: REVOKED` with `operating_disposition: NOT_PERMITTED`.

All keys and signatures in this example are test-only and must never be used outside conformance testing.

## What just happened

The validator strictly parsed the passport, checked supported versions and critical extensions, applied its JSON Schema and semantic rules, recomputed its content-derived identifier, verified the detached Ed25519 signature, evaluated the trusted key, verified the profile descriptor, evaluator, policy, inventories, action-authority graph, data-authority evidence, evidence references, assessment projection, and complete condition set, checked passport validity, verified the signed revocation list, and confirmed that the passport was not revoked.

The output preserves the three distinct state layers: the issued assessment remains `APPROVED`, presentation-time verification is `VALID`, and the reference operating policy returns `PERMITTED`.

> **Stateless revocation note:** this command evaluates only the revocation-list snapshot supplied to it. It does not retain the highest sequence seen across separate runs, so a production verifier must add persistent rollback protection.

