"""Independent Assurance profile evaluator.

Non-authorizing. Assembles reference evidence only.
"""

from __future__ import annotations

from pathlib import Path

from .common import finding

PROFILE_ID = "independent-assurance-v0.1"
VERSION = "0.1.0"


def evaluate(data: dict, root: Path, evaluation_time: str | None = None) -> tuple[list, list, dict]:
    findings = []
    evidence = []

    subject = data.get("subject_id")
    if not subject or not isinstance(subject, str):
        findings.append(finding(PROFILE_ID, "SUBJECT_MISSING", "CRITICAL",
                                "Subject identity is required.",
                                "Supply exact subject_id."))

    if data.get("authority_effect") != "NONE":
        findings.append(finding(PROFILE_ID, "AUTHORITY_EFFECT", "CRITICAL",
                                "Authority effect must remain NONE.",
                                "Set authority_effect to NONE."))

    evaluator = data.get("evaluator") or {}
    if not evaluator.get("identity"):
        findings.append(finding(PROFILE_ID, "EVALUATOR_IDENTITY", "HIGH",
                                "Evaluator identity is missing.",
                                "Disclose evaluator identity."))
    if not evaluator.get("interests_disclosed"):
        findings.append(finding(PROFILE_ID, "INTERESTS", "HIGH",
                                "Evaluator interests not disclosed.",
                                "Disclose interests."))

    qual = data.get("qualification_evidence")
    if not isinstance(qual, dict):
        findings.append(finding(PROFILE_ID, "QUALIFICATION_MISSING", "HIGH",
                                "A submitted qualification summary is required before independent assurance can pass.",
                                "Supply a bounded Qualification Evidence summary. This profile does not authenticate the native artifact."))
    else:
        # Inclusive interval: qualified_from <= evaluation_time <= expires_at.
        # CONDITIONAL is not sufficient. This profile does not prove native authenticity.
        if qual.get("authority_effect") != "NONE":
            findings.append(finding(PROFILE_ID, "QUALIFICATION_AUTHORITY", "CRITICAL",
                                    "Qualification cannot confer authority.",
                                    "Set authority_effect to NONE."))
        if qual.get("outcome") != "QUALIFIED":
            findings.append(finding(PROFILE_ID, "QUALIFICATION_OUTCOME", "CRITICAL",
                                    "Only QUALIFIED satisfies independent assurance. CONDITIONAL is not sufficient.",
                                    "Supply a QUALIFIED outcome. Do not treat CONDITIONAL as QUALIFIED."))
        if qual.get("subject_id") != subject:
            findings.append(finding(PROFILE_ID, "QUALIFICATION_SUBJECT", "CRITICAL",
                                    "Qualification subject does not match the assurance subject.",
                                    "Bind the summary to the same subject."))
        if data.get("configuration_digest") and qual.get("configuration_digest") != data.get("configuration_digest"):
            findings.append(finding(PROFILE_ID, "QUALIFICATION_CONFIGURATION", "CRITICAL",
                                    "Qualification configuration does not match the assurance configuration.",
                                    "Bind the summary to the same configuration."))
        if qual.get("scope") != data.get("scope"):
            findings.append(finding(PROFILE_ID, "QUALIFICATION_SCOPE", "CRITICAL",
                                    "Qualification scope is not compatible with evaluation scope.",
                                    "Use the same scope. Compatibility in this profile is exact scope match."))
        start = qual.get("qualified_from")
        end = qual.get("expires_at")
        if not (isinstance(start, str) and isinstance(end, str) and start < end):
            findings.append(finding(PROFILE_ID, "QUALIFICATION_INTERVAL", "CRITICAL",
                                    "qualified_from must be strictly before expires_at.",
                                    "Correct the qualification interval."))
        elif evaluation_time is None or evaluation_time < start:
            findings.append(finding(PROFILE_ID, "QUALIFICATION_NOT_YET_EFFECTIVE", "CRITICAL",
                                    "Qualification is not yet effective or evaluation time is absent.",
                                    "Evaluate inside the inclusive interval. A future qualification is not current."))
        elif evaluation_time > end:
            findings.append(finding(PROFILE_ID, "QUALIFICATION_EXPIRED", "CRITICAL",
                                    "Qualification is expired.",
                                    "Requalify. An expired qualification cannot satisfy readiness."))
        refs = qual.get("competence_evidence_refs")
        if not isinstance(refs, list) or not refs:
            findings.append(finding(PROFILE_ID, "QUALIFICATION_COMPETENCE", "CRITICAL",
                                    "Competence evidence references are required.",
                                    "Supply competence_evidence_refs."))

    if not data.get("scope"):
        findings.append(finding(PROFILE_ID, "SCOPE", "MEDIUM",
                                "Evaluation scope is missing.",
                                "State evaluation scope."))

    validity_state = "VALID"
    revalidation_required = False
    trigger = None

    if data.get("material_change") or data.get("expired"):
        findings.append(finding(PROFILE_ID, "STALE", "CRITICAL",
                                "Prior assurance is stale.",
                                "Revalidate."))
        validity_state = "STALE"
        revalidation_required = True
        trigger = "MATERIAL_CHANGE" if data.get("material_change") else "EXPIRED"

    if data.get("unresolved_concern"):
        findings.append(finding(PROFILE_ID, "UNRESOLVED_CONCERN", "HIGH",
                                "Unresolved material concern affects assurance basis.",
                                "Investigate and revalidate."))
        if validity_state == "VALID":
            validity_state = "QUESTIONED"
        revalidation_required = True
        if trigger is None:
            trigger = "UNRESOLVED_CONCERN"

    if data.get("evaluator_conflict"):
        findings.append(finding(PROFILE_ID, "EVALUATOR_CONFLICT", "CRITICAL",
                                "Material independence conflict.",
                                "Resolve conflict and revalidate."))
        validity_state = "STALE"
        revalidation_required = True
        trigger = "EVALUATOR_CONFLICT"

    if data.get("high_consequence") and not data.get("shutdown_evidence_present"):
        findings.append(finding(PROFILE_ID, "SHUTDOWN_EVIDENCE", "CRITICAL",
                                "High-consequence subject lacks shutdown evidence.",
                                "Supply verified shutdown evidence."))
        validity_state = "STALE"
        revalidation_required = True
        if trigger is None:
            trigger = "SHUTDOWN_EVIDENCE"

    details = {
        "reference_only": True,
        "validity_state": validity_state,
        "revalidation_required": revalidation_required,
        "trigger": trigger,
        "qualification_basis": "submitted bounded summary; native Foundations authenticity is not established",
        "interval": "inclusive",
    }
    return findings, evidence, details
