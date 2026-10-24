<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Examples

All identities, keys, hashes, systems, inventories, profiles, and evidence are synthetic. The Ed25519 seed and key are test-only and must never be used operationally.

The examples use the supported reference evaluator `global-ai-governance.reference-validator` at `reference-validator-0.1.0-alpha.1` and the supported assessment policy `global-ai-governance.alpha1-reference-policy` at `0.1.0-alpha.1`.

The `inventories/` directory contains non-empty synthetic agent, MCP, and tool inventories validated by the Alpha.1 inventory schemas. The action-authority graph, profile descriptor, control profile, assessment, inventories, and data-authority evidence are all present in the canonical bundle manifest and cross-checked before a permitted disposition is possible.

Start with the [five-minute quickstart](quickstart/README.md).

## Core lifecycle

1. [`action-authority/readonly-graph.json`](action-authority/readonly-graph.json)
2. [`assessments/approved-readonly.json`](assessments/approved-readonly.json)
3. [`bundles/valid-bundle-manifest.json`](bundles/valid-bundle-manifest.json)
4. [`passports/signed-unrevoked.json`](passports/signed-unrevoked.json)
5. [`trusted-keys/test-ed25519-key.json`](trusted-keys/test-ed25519-key.json)
6. [`revocation/valid-revocation-list.json`](revocation/valid-revocation-list.json)

`passports/signed-revoked.json` is intentionally present in the example revocation list so users may observe a `REVOKED` decision.

The machine-readable profile descriptor at [`../profiles/mcp-governance-profile.json`](../profiles/mcp-governance-profile.json) binds the profile identity, policy, evaluator, supported control set, admitted data-authority scheme, trusted synthetic issuer, and profile-document hash.

Machine-readable JSON examples are licensed under Apache-2.0 as stated in `LICENSE_POLICY.md`.
