#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independently trusted Alpha.1 reference-policy anchor and semantic vocabularies."""
from __future__ import annotations

CURRENT_SCHEMA_VERSION = "0.1.0-alpha.1"
CURRENT_FRAMEWORK_ID = "global-ai-governance.agentic-ai-governance"
CURRENT_FRAMEWORK_VERSION = "v0.1.0-alpha.1"

CURRENT_PROFILE_ID = "global-ai-governance.mcp-governance"
CURRENT_PROFILE_VERSION = "0.1.0-alpha.1"

CURRENT_EVALUATOR_ID = "global-ai-governance.reference-validator"
CURRENT_EVALUATOR_VERSION = "reference-validator-0.1.0-alpha.1"

CURRENT_ASSESSMENT_POLICY_ID = "global-ai-governance.alpha1-reference-policy"
CURRENT_ASSESSMENT_POLICY_VERSION = "0.1.0-alpha.1"

SUPPORTED_CONTROL_IDS: frozenset[str] = frozenset({"AID-001"})
TRUSTED_DATA_AUTHORITY_ISSUERS: frozenset[str] = frozenset({"global-ai-governance.test-issuer"})
DATA_AUTHORITY_SCHEME_POLICIES: dict[tuple[str, str], dict[str, bool]] = {
    ("global-ai-governance.synthetic-authority", "0.1.0"): {"requires_signature": False},
}
SUPPORTED_DATA_AUTHORITY_SCHEMES: frozenset[tuple[str, str]] = frozenset(DATA_AUTHORITY_SCHEME_POLICIES)

# Alpha.1 controlled semantic vocabulary and minimum authority levels.
AGENT_CAPABILITY_MIN_LEVEL: dict[str, int] = {
    "read:approved-public-information": 1,
    "draft:internal-summary": 2,
    "execute:arbitrary-code": 3,
    "publish:external": 4,
    "identity-admin:write": 4,
    "delete:data": 5,
    "execute:destructive": 5,
    "self-modify": 5,
}
MCP_SCOPE_MIN_LEVEL: dict[str, int] = {
    "public-information:read": 1,
    "code-execution:invoke": 3,
    "filesystem:write": 4,
    "secrets:read": 4,
    "identity-admin:write": 4,
    "external-publication:write": 4,
    "destructive:write": 5,
}
TOOL_EFFECT_MIN_LEVEL: dict[str, int] = {
    "read-only": 1,
    "draft-internal-content": 2,
    "execute-code": 3,
    "publish-externally": 4,
    "modify-credentials": 4,
    "delete-data": 5,
    "self-modification": 5,
}
EDGE_TYPE_MIN_LEVEL: dict[str, int] = {
    "READS": 1,
    "INVOKES": 1,
    "DELEGATES": 3,
    "WRITES": 3,
    "APPROVES": 3,
    "PUBLISHES": 4,
}
EDGE_REQUIRED_DIMENSION: dict[str, str] = {
    "DELEGATES": "delegation",
    "PUBLISHES": "external_publication",
}

# Filled from the canonical public profile files during the release build. These
# constants are trust anchors in the verifier, not values accepted from a bundle.
REFERENCE_PROFILE_DOCUMENT_SHA256 = "sha256:4e1d0ad65cd8652bec2e33de7e8ed1172e26de4e11ae31bd58262f6b19b50652"
REFERENCE_PROFILE_DESCRIPTOR_SHA256 = "sha256:a06b2455a4a4133c13f3cba32aed1b442f43f17828dede5bf110a9d802ae1d6d"
REFERENCE_PROFILE_ANCHOR = {
    "profile_id": CURRENT_PROFILE_ID,
    "profile_version": CURRENT_PROFILE_VERSION,
    "document_sha256": REFERENCE_PROFILE_DOCUMENT_SHA256,
    "descriptor_sha256": REFERENCE_PROFILE_DESCRIPTOR_SHA256,
    "supported_control_ids": SUPPORTED_CONTROL_IDS,
    "trusted_data_authority_issuers": TRUSTED_DATA_AUTHORITY_ISSUERS,
    "data_authority_scheme_policies": DATA_AUTHORITY_SCHEME_POLICIES,
    "evaluator_id": CURRENT_EVALUATOR_ID,
    "evaluator_version": CURRENT_EVALUATOR_VERSION,
    "assessment_policy_id": CURRENT_ASSESSMENT_POLICY_ID,
    "assessment_policy_version": CURRENT_ASSESSMENT_POLICY_VERSION,
    "production_use_permitted": False,
}
