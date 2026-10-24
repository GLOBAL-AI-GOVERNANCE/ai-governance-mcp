<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# MCP Governance Profile

**Profile ID:** `global-ai-governance.mcp-governance`  
**Version:** `0.1.0-alpha.1`  
**Assessment policy:** `global-ai-governance.alpha1-reference-policy` / `0.1.0-alpha.1`  
**Reference evaluator:** `global-ai-governance.reference-validator` / `reference-validator-0.1.0-alpha.1`  
**Status:** Experimental public alpha profile. Not frozen. Not approved for production use.

This profile applies the Agentic AI Governance Framework to systems that declare MCP clients, hosts, servers, resources, prompts, tools, authorization boundaries, and transport-security assumptions.

The normative MCP protocol baseline is revision `2025-11-25`. MCP Security Best Practices is informative, mutable operational guidance rather than a normative Alpha.1 dependency. Implementations should record the exact guidance revision they rely upon.

The profile MUST apply reachable-action-graph analysis, reject undeclared MCP server and tool references, require explicit resource and tool scopes, and prohibit `APPROVED` or `APPROVED_WITH_CONDITIONS` for Level 5 authority.

## Alpha.1 reference control

The bundled conformance path implements control `AID-001`. The machine-readable profile descriptor binds this document, the supported control set, admitted data-authority scheme, trusted synthetic issuer, assessment policy, and evaluator identity. A relying implementation MUST validate that descriptor before issuing a permitted disposition.

## Canonical policy anchor

The reference validator pins the exact descriptor JCS hash and profile-document byte hash for this profile ID and version outside every submitted bundle. A bundle MUST NOT redefine the supported controls, issuers, schemes, evaluator, assessment policy, or production-use posture while retaining this profile identity.

## Alpha.1 authority vocabulary

The reference profile uses controlled machine-readable vocabularies for agent capabilities, MCP scopes, tool effects, and graph edge types. Each supported term maps to a deterministic minimum action level. Unknown terms fail schema validation. Every MCP server MUST be a reachable `MCP_SERVER` graph node, and its node level MUST cover every declared scope. Tool effects and agent capabilities MUST NOT exceed the graph, assessment, passport, or active-condition authority ceiling. `PUBLISHES` edges require `external_publication=true`; `DELEGATES` edges require `delegation=true`.

Data-authority evidence supporting an assessment MUST be valid both at the assessment's `evaluated_at` time and at the relying verifier's evaluation time. Scheme signature requirements come from the independently pinned reference-policy anchor.
