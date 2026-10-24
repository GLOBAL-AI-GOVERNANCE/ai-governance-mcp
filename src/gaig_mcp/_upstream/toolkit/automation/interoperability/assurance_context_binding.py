"""Local, read-only consumer for an explicitly supplied Assurance Context Binding reference.

Does not retrieve external artifacts, transfer authority, or establish operational validity.
The trusted schema fingerprint is anchored to the pinned foundational commit and is not supplied by the caller.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from automation.scripts.contract_verifier import ContractError, validate_instance

EXPECTED_HANDOFF = "foundation-to-toolkit"
EXPECTED_SOURCE = "ai-governance-os"
EXPECTED_TARGET = "global-ai-governance-toolkit"
EXPECTED_COMMIT = "fad094618e723acec14a8cdc905d1cfcbdf58813"
EXPECTED_ARTIFACT = "sample-data/assurance-context-binding.json"
# Canonical JSON SHA-256 of the Assurance Context Binding schema at the pinned commit.
TRUSTED_SCHEMA_FINGERPRINT = "aef003eb728314aca48ae8f40f813b181b7085f0af530f9f4faca60057050fbb"
ALLOWED_REFERENCE_KEYS = {
    "schema_version",
    "handoff_id",
    "source_repository",
    "target_repository",
    "source_artifact_type",
    "source_artifact_id",
    "source_version",
    "reference_only",
    "authority_effect",
}


def _canonical_fingerprint(schema: dict[str, Any]) -> str:
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_assurance_context_binding(
    portfolio_reference: dict[str, Any],
    binding_fixture: dict[str, Any],
    binding_schema: dict[str, Any],
    *,
    expected_subject_id: str,
    expected_configuration_digest: str,
    expected_context_boundary: str,
) -> dict[str, Any]:
    """Validate portfolio reference and binding fixture. Returns non-authorizing result.

    Expected subject, configuration digest, and context boundary are required.
    The supplied schema must match the anchored fingerprint of the pinned foundational schema.
    """
    if not isinstance(portfolio_reference, dict):
        raise ContractError("portfolio reference must be an object")
    unknown = set(portfolio_reference) - ALLOWED_REFERENCE_KEYS
    if unknown:
        raise ContractError(f"unsupported portfolio reference fields: {', '.join(sorted(unknown))}")
    if portfolio_reference.get("handoff_id") != EXPECTED_HANDOFF:
        raise ContractError("handoff_id must be foundation-to-toolkit")
    if portfolio_reference.get("source_repository") != EXPECTED_SOURCE:
        raise ContractError("source_repository must be ai-governance-os")
    if portfolio_reference.get("target_repository") != EXPECTED_TARGET:
        raise ContractError("target_repository must be global-ai-governance-toolkit")
    if portfolio_reference.get("source_version") != EXPECTED_COMMIT:
        raise ContractError("source_version must match pinned upstream commit")
    if portfolio_reference.get("source_artifact_id") != EXPECTED_ARTIFACT:
        raise ContractError("source_artifact_id mismatch")
    if portfolio_reference.get("source_artifact_type") != "Assurance Context Binding fixture":
        raise ContractError("source_artifact_type mismatch")
    if portfolio_reference.get("reference_only") is not True:
        raise ContractError("portfolio reference must be reference_only")
    if portfolio_reference.get("authority_effect") != "NONE":
        raise ContractError("portfolio reference authority_effect must be NONE")
    if portfolio_reference.get("schema_version") != "1.0.0":
        raise ContractError("portfolio reference schema_version mismatch")

    if not isinstance(binding_schema, dict):
        raise ContractError("binding schema must be an object")
    if _canonical_fingerprint(binding_schema) != TRUSTED_SCHEMA_FINGERPRINT:
        raise ContractError("binding schema does not match trusted pinned foundational schema")

    if not isinstance(binding_fixture, dict):
        raise ContractError("binding fixture must be an object")

    # Reuse existing schema validator for the fixture only after fingerprint match
    try:
        validate_instance(binding_fixture, binding_schema, base=Path("."))
    except ContractError as exc:
        raise ContractError(f"binding fixture schema failure: {exc}") from exc

    if binding_fixture.get("reference_only") is not True:
        raise ContractError("binding fixture must be reference_only")
    if binding_fixture.get("authority_effect") != "NONE":
        raise ContractError("binding fixture authority_effect must be NONE")

    if binding_fixture.get("subject_id") != expected_subject_id:
        raise ContractError("subject_id mismatch")
    if binding_fixture.get("configuration_digest") != expected_configuration_digest:
        raise ContractError("configuration_digest mismatch")
    if binding_fixture.get("context_boundary") != expected_context_boundary:
        raise ContractError("context_boundary mismatch")

    return {
        "valid": True,
        "reference_only": True,
        "authority_effect": "NONE",
        "subject_id": binding_fixture.get("subject_id"),
        "source_commit": EXPECTED_COMMIT,
        "note": "Local validation only. Does not establish external authenticity, current trust, or operational validity.",
    }
