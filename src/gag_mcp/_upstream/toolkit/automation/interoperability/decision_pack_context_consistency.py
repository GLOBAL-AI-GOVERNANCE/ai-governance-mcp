"""Opt-in, local consistency check between an explicitly supplied Decision Pack handoff
and an Assurance Context Binding.

Does not generate Decision Packs, retrieve external artifacts, or confer authority.
The handoff schema is source-locked to the checked-in native contract.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from automation.interoperability.assurance_context_binding import validate_assurance_context_binding
from automation.scripts.contract_verifier import ContractError, validate_instance

_TRUSTED_HANDOFF_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "contracts" / "governance-decision-handoff.schema.json"
)


def _load_trusted_handoff_schema() -> dict[str, Any]:
    try:
        return json.loads(_TRUSTED_HANDOFF_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"trusted handoff schema unavailable: {exc}") from exc


def validate_decision_pack_context_consistency(
    handoff: dict[str, Any],
    handoff_schema: dict[str, Any] | None,
    manifest_bytes: bytes,
    portfolio_reference: dict[str, Any],
    binding_fixture: dict[str, Any],
    binding_schema: dict[str, Any],
    *,
    expected_subject_id: str,
    expected_configuration_digest: str,
    expected_context_boundary: str,
) -> dict[str, Any]:
    """Validate handoff, Context Binding, subject match, and artifact digest.

    Configuration relationship is reported as NOT VERIFIED unless an explicit,
    verifiable match against the expected configuration digest is supplied.
    Returns a non-authorizing result.
    """
    if not isinstance(handoff, dict):
        raise ContractError("handoff must be an object")
    if not isinstance(manifest_bytes, (bytes, bytearray)):
        raise ContractError("manifest_bytes must be bytes")

    trusted = _load_trusted_handoff_schema()
    if handoff_schema is not None:
        if not isinstance(handoff_schema, dict):
            raise ContractError("handoff_schema must be an object")
        # Require exact equivalence to the trusted native schema
        if json.dumps(handoff_schema, sort_keys=True) != json.dumps(trusted, sort_keys=True):
            raise ContractError("handoff_schema does not match trusted native contract")

    # Always validate against the trusted schema
    try:
        validate_instance(handoff, trusted, base=_TRUSTED_HANDOFF_SCHEMA_PATH.parent)
    except ContractError as exc:
        raise ContractError(f"handoff schema failure: {exc}") from exc

    if handoff.get("authority_effect") != "NONE":
        raise ContractError("handoff authority_effect must be NONE")
    if handoff.get("source_repository") != "global-ai-governance-toolkit":
        raise ContractError("handoff source_repository mismatch")
    if handoff.get("source_artifact_type") != "AI_GOVERNANCE_DECISION_PACK_REFERENCE":
        raise ContractError("handoff source_artifact_type mismatch")

    # Preserve and reuse the source-locked Context Binding validator
    binding_result = validate_assurance_context_binding(
        portfolio_reference,
        binding_fixture,
        binding_schema,
        expected_subject_id=expected_subject_id,
        expected_configuration_digest=expected_configuration_digest,
        expected_context_boundary=expected_context_boundary,
    )

    # Exact subject identity match
    if handoff.get("system_id") != binding_fixture.get("subject_id"):
        raise ContractError("system_id does not match binding subject_id")
    if handoff.get("system_id") != expected_subject_id:
        raise ContractError("system_id does not match expected subject")

    # Artifact digest integrity against supplied manifest bytes
    expected_digest = handoff.get("artifact_digest")
    if not isinstance(expected_digest, str) or not expected_digest.startswith("sha256:"):
        raise ContractError("artifact_digest malformed")
    actual = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
    if actual != expected_digest:
        raise ContractError("artifact_digest does not match supplied manifest bytes")

    # Configuration consistency only when explicitly proven
    handoff_config = handoff.get("configuration_ref")
    configuration_consistent: bool | str = "NOT VERIFIED"
    if handoff_config is not None:
        if handoff_config == expected_configuration_digest:
            configuration_consistent = True
        else:
            raise ContractError("configuration_ref does not match expected configuration digest")

    return {
        "subject_and_manifest_consistent": True,
        "configuration_consistent": configuration_consistent,
        "reference_only": True,
        "authority_effect": "NONE",
        "subject_id": expected_subject_id,
        "review_boundary": handoff.get("review_boundary"),
        "note": "Local consistency check only. Configuration relationship is NOT VERIFIED unless an explicit matching configuration_ref is supplied. Does not establish authenticity, current trust, operational validity, or approval.",
        "binding_result": binding_result,
    }
