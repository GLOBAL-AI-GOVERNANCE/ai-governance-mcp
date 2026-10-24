"""Deterministic machine-output builders for the Wave A contract spine."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


GENERATOR_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
NORMALIZATION_VERSION = "1.0.0"
EVALUATION_TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_prefixed(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def validate_evaluation_time(value: str | None) -> None:
    if value is not None and EVALUATION_TIME_PATTERN.fullmatch(value) is None:
        raise ValueError("evaluation time must be UTC YYYY-MM-DDTHH:MM:SSZ")


def policy_identity(policy: Mapping[str, Any]) -> tuple[str, str]:
    policy_id = policy.get("policy_id")
    policy_version = policy.get("policy_version")
    if not isinstance(policy_id, str) or not policy_id:
        raise ValueError("policy_id is required")
    if not isinstance(policy_version, str) or not policy_version:
        raise ValueError("policy_version is required")
    return policy_id, policy_version


def finding_record(finding: Any) -> dict[str, str]:
    identity = {
        "rule_id": finding.rule_id,
        "system_id": finding.system_id,
        "severity": finding.severity.upper(),
        "message": finding.message,
    }
    return {
        "finding_id": sha256_prefixed(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")),
        "rule_id": finding.rule_id,
        "system_id": finding.system_id,
        "system_name": finding.system_name,
        "severity": finding.severity.upper(),
        "message": finding.message,
    }


def build_findings(normalized: Mapping[str, Any], policy: Mapping[str, Any], findings: Sequence[Any]) -> dict[str, Any]:
    policy_id, policy_version = policy_identity(policy)
    records = sorted((finding_record(item) for item in findings), key=lambda item: (item["severity"], item["system_id"], item["rule_id"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "input_digest": "sha256:" + normalized["source"]["sha256"],
        "findings": records,
    }


def gate_state(findings: Sequence[Any]) -> str:
    severities = {item.severity.upper() for item in findings}
    if "CRITICAL" in severities:
        return "BLOCKED"
    if severities:
        return "REVIEW_REQUIRED"
    return "PASSED_CURRENT_AUTOMATED_CHECKS"


def build_result(normalized: Mapping[str, Any], policy: Mapping[str, Any], findings: Sequence[Any], *, fail_on: str, evaluation_time: str | None) -> dict[str, Any]:
    validate_evaluation_time(evaluation_time)
    policy_id, policy_version = policy_identity(policy)
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "evaluation_time": evaluation_time,
        "input_digest": "sha256:" + normalized["source"]["sha256"],
        "validation_state": "VALID",
        "governance_gate_state": gate_state(findings),
        "human_decision_state": "PENDING_HUMAN_DECISION",
        "blocking_threshold": fail_on,
        "finding_count": len(findings),
        "system_ids": sorted({item["system_id"] for item in normalized["records"]}),
    }


def build_handoff(*, manifest_path: Path, result: Mapping[str, Any], findings_doc: Mapping[str, Any], target_repository: str) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_digest = sha256_prefixed(manifest_path.read_bytes())
    decision_pack_id = sha256_prefixed(canonical_bytes({
        "canonical_inventory_digest": manifest["canonical_inventory_digest"],
        "evaluation_time": result["evaluation_time"],
        "policy_id": result["policy_id"],
        "policy_version": result["policy_version"],
    }))
    handoff_id = sha256_prefixed(canonical_bytes({
        "decision_pack_id": decision_pack_id,
        "target_repository": target_repository,
    }))
    return {
        "schema_version": "1.0.0",
        "handoff_id": handoff_id,
        "source_repository": "global-ai-governance-toolkit",
        "source_artifact_type": "AI_GOVERNANCE_DECISION_PACK_REFERENCE",
        "decision_pack_id": decision_pack_id,
        "system_id": result["system_ids"][0] if len(result["system_ids"]) == 1 else "multiple-systems",
        "target_repository": target_repository,
        "artifact_digest": manifest_digest,
        "evidence_refs": [item["finding_id"] for item in findings_doc["findings"]],
        "authority_refs": [],
        "authority_effect": "NONE",
        "review_boundary": "Pending human review; this handoff grants no approval, authority, certification, or risk acceptance.",
        "configuration_ref": None,
    }
