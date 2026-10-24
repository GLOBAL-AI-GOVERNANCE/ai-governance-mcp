"""Compose native artifact references without redefining native semantics or authority."""
from __future__ import annotations

import re
from typing import Iterable

OWNERS = {
    "agent-trust-passport": "GLOBAL-AI-GOVERNANCE/agentic-ai-governance",
    "governed-closure-receipt": "GLOBAL-AI-GOVERNANCE/verified-vulnerability-governance",
    "change-impact": "GLOBAL-AI-GOVERNANCE/ai-cyber-resilience-framework",
    "operating-disposition": "GLOBAL-AI-GOVERNANCE/ai-cyber-resilience-framework",
}
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REFERENCE_KEYS = {
    "source_repository",
    "artifact_type",
    "artifact_id",
    "schema_version",
    "subject_id",
    "artifact_digest",
    "generated_at",
    "authority_effect",
}


def _text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value


def build_native_reference(
    *,
    source_repository: str,
    artifact_type: str,
    artifact_id: str,
    schema_version: str,
    subject_id: str,
    artifact_digest: str,
    generated_at: str,
) -> dict[str, str]:
    expected_owner = OWNERS.get(artifact_type)
    if expected_owner is None:
        raise ValueError("unsupported native artifact type")
    if source_repository != expected_owner:
        raise ValueError("native artifact ownership mismatch")
    if DIGEST.fullmatch(artifact_digest) is None:
        raise ValueError("artifact_digest must be sha256:<64 lowercase hex>")
    if TIMESTAMP.fullmatch(generated_at) is None:
        raise ValueError("generated_at must be UTC YYYY-MM-DDTHH:MM:SSZ")
    return {
        "source_repository": source_repository,
        "artifact_type": artifact_type,
        "artifact_id": _text("artifact_id", artifact_id),
        "schema_version": _text("schema_version", schema_version),
        "subject_id": _text("subject_id", subject_id),
        "artifact_digest": artifact_digest,
        "generated_at": generated_at,
        "authority_effect": "NONE",
    }


def _validated_reference(value: dict[str, str], subject_id: str) -> dict[str, str]:
    if set(value) != REFERENCE_KEYS:
        raise ValueError("native reference contract mismatch")
    rebuilt = build_native_reference(
        source_repository=value["source_repository"],
        artifact_type=value["artifact_type"],
        artifact_id=value["artifact_id"],
        schema_version=value["schema_version"],
        subject_id=value["subject_id"],
        artifact_digest=value["artifact_digest"],
        generated_at=value["generated_at"],
    )
    if rebuilt["authority_effect"] != "NONE" or value.get("authority_effect") != "NONE":
        raise ValueError("native reference attempted authority transfer")
    if rebuilt["subject_id"] != subject_id:
        raise ValueError("subject binding mismatch")
    return rebuilt


def compose_reference_envelope(subject_id: str, references: Iterable[dict[str, str]]) -> dict[str, object]:
    subject_id = _text("subject_id", subject_id)
    checked = [_validated_reference(dict(item), subject_id) for item in references]
    if not checked:
        raise ValueError("at least one native reference is required")
    identities = [
        (r["source_repository"], r["artifact_type"], r["artifact_id"], r["artifact_digest"])
        for r in checked
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate native reference")
    checked.sort(key=lambda r: (r["source_repository"], r["artifact_type"], r["artifact_id"], r["artifact_digest"]))
    return {
        "subject_id": subject_id,
        "reference_only": True,
        "native_artifact_references": checked,
        "authority_effect": "NONE",
        "human_decision_required": True,
    }
