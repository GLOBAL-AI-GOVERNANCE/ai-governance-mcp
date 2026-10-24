"""Machine learning assurance profile.

Non-authorizing. A PASS is structural consistency of submitted references only.
It does not mean a model is safe, accurate, approved, certified, or authorized.
"""
from __future__ import annotations

import re
from pathlib import Path

from .common import finding

PROFILE_ID = "machine-learning-assurance-v0.1"
VERSION = "0.1.0"
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REFERENCES = (
    "dataset_reference",
    "model_reference",
    "evaluation_reference",
    "context_binding_reference",
)


def _critical(findings: list, code: str, message: str, action: str) -> None:
    findings.append(finding(PROFILE_ID, code, "CRITICAL", message, action))


def _bind(reference: dict, data: dict, findings: list, label: str, evaluation_time: str | None) -> None:
    if not isinstance(reference, dict):
        _critical(findings, f"{label}_INVALID", f"{label} must be an evidence reference.", "Supply a complete evidence reference.")
        return
    if reference.get("authority_effect") != "NONE":
        _critical(findings, f"{label}_AUTHORITY", f"{label} cannot confer authority.", "Set authority_effect to NONE.")
    if reference.get("subject_id") != data.get("subject_id"):
        _critical(findings, f"{label}_SUBJECT", f"{label} subject does not match.", "Bind the reference to the same subject.")
    if reference.get("configuration_digest") != data.get("configuration_digest"):
        _critical(findings, f"{label}_CONFIGURATION", f"{label} configuration does not match.", "Bind the reference to the same configuration.")
    if not DIGEST.fullmatch(str(reference.get("artifact_digest", ""))):
        _critical(findings, f"{label}_DIGEST", f"{label} artifact digest is malformed.", "Supply a sha256 digest.")
    expires = reference.get("expires_at")
    if evaluation_time and expires and TIMESTAMP.fullmatch(str(expires)) and TIMESTAMP.fullmatch(evaluation_time) and expires < evaluation_time:
        _critical(findings, "STALE_EVIDENCE", f"{label} is expired at the evaluation time.", "Supply current evidence or requalify.")


def _evidence(reference: dict) -> dict:
    pointer = "/".join(str(reference.get(field, "")) for field in ("source", "artifact_type", "artifact_id", "schema_version"))
    return {"type": "ARTIFACT_ID", "reference": pointer, "sha256": str(reference.get("artifact_digest", ""))}


def evaluate(data: dict, root: Path, evaluation_time: str | None = None) -> tuple[list, list, dict]:
    findings: list = []
    evidence: list = []
    if data.get("reference_only") is not True:
        _critical(findings, "REFERENCE_ONLY", "Profile input must remain reference-only.", "Set reference_only to true.")
    if data.get("authority_effect") != "NONE":
        _critical(findings, "AUTHORITY_EFFECT", "Automated output cannot create authority.", "Set authority_effect to NONE.")
    if data.get("human_review_required") is not True:
        _critical(findings, "HUMAN_REVIEW", "Human review remains required.", "Set human_review_required to true.")
    if not DIGEST.fullmatch(str(data.get("configuration_digest", ""))):
        _critical(findings, "CONFIGURATION_DIGEST", "configuration_digest is malformed.", "Supply a sha256 digest.")
    if data.get("evidence_stale") is True:
        _critical(findings, "STALE_EVIDENCE", "Stale evidence cannot support a current result.", "Replace or requalify the evidence.")
    if data.get("material_drift") is True:
        _critical(findings, "MATERIAL_DRIFT", "Material drift requires reassessment.", "Requalify before treating the result as current.")
    if data.get("automatic_requalification") is True or data.get("automatic_promotion") is True:
        _critical(findings, "AUTOMATIC_REQUALIFICATION", "The profile cannot requalify or promote a model.", "Record a new human-reviewed evaluation.")
    blocking = data.get("blocking_unknowns") if isinstance(data.get("blocking_unknowns"), list) else []
    if blocking:
        _critical(findings, "BLOCKING_UNKNOWN", "Blocking unknowns prevent a passing result.", "Resolve or explicitly re-scope the unknowns.")
    for key in REFERENCES:
        reference = data.get(key)
        if not isinstance(reference, dict):
            _critical(findings, f"MISSING_{key.upper()}", f"{key} is required.", "Supply the native reference.")
            continue
        _bind(reference, data, findings, key.upper(), evaluation_time)
        evidence.append(_evidence(reference))
    drift = data.get("drift_reference")
    if data.get("material_drift") is True and not isinstance(drift, dict):
        _critical(findings, "MISSING_DRIFT_REFERENCE", "Material drift requires a drift reference.", "Supply the drift event reference. Do not invent one for a stable system.")
    if isinstance(drift, dict):
        _bind(drift, data, findings, "DRIFT", evaluation_time)
        evidence.append(_evidence(drift))
    evidence.sort(key=lambda item: (item["type"], item["reference"], item["sha256"]))
    details = {
        "reference_only": True,
        "authority_effect": "NONE",
        "requalification_required": data.get("material_drift") is True,
        "pass_means": "Structural, identity, configuration-binding, and integrity consistency of submitted references only.",
        "does_not_mean": [
            "the model is safe",
            "the model is accurate in operation",
            "deployment is approved",
            "certification",
            "compliance",
            "legal authorization",
            "automatic retraining",
            "automatic promotion",
        ],
    }
    return findings, evidence, details
