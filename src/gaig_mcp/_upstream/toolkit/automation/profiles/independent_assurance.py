"""Independent Assurance profile evaluator.

Non-authorizing. Assembles reference evidence only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import finding

PROFILE_ID = "independent-assurance-v0.1"
VERSION = "0.2.0"

# Upper bound on the age of a shutdown test for an autonomous agent. A case may
# set a shorter max_shutdown_test_age_days; it can never extend this bound.
MAX_SHUTDOWN_TEST_AGE_DAYS = 90
SHUTDOWN_EVIDENCE_HINT = (
    "Supply shutdown_evidence with shutdown_tested_at, result PASSED, and evidence_refs. "
    "This profile checks the submitted record; it does not establish that the test occurred."
)


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _shutdown_evidence_findings(data: dict, evaluation_time: str | None) -> tuple[list, dict]:
    """Check structured shutdown-test evidence. Returns findings and details."""

    out: list = []
    evidence = data.get("shutdown_evidence")
    requested = data.get("max_shutdown_test_age_days")
    max_age = MAX_SHUTDOWN_TEST_AGE_DAYS
    if isinstance(requested, int) and not isinstance(requested, bool) and 0 < requested < max_age:
        max_age = requested
    detail: dict = {"max_age_days": max_age, "tested_at": None, "age_days": None, "state": "MISSING"}
    if not isinstance(evidence, dict):
        out.append(finding(PROFILE_ID, "SHUTDOWN_TEST_MISSING", "CRITICAL",
                           "Autonomous agent has no shutdown test evidence.", SHUTDOWN_EVIDENCE_HINT))
        return out, detail
    tested_at = _parse_utc(evidence.get("shutdown_tested_at"))
    refs = evidence.get("evidence_refs")
    detail["tested_at"] = evidence.get("shutdown_tested_at")
    if tested_at is None:
        out.append(finding(PROFILE_ID, "SHUTDOWN_TEST_MISSING", "CRITICAL",
                           "shutdown_tested_at is missing or not YYYY-MM-DDTHH:MM:SSZ.", SHUTDOWN_EVIDENCE_HINT))
        return out, detail
    if not (isinstance(refs, list) and refs and all(isinstance(r, str) and r.strip() for r in refs)):
        out.append(finding(PROFILE_ID, "SHUTDOWN_TEST_EVIDENCE_REFS", "CRITICAL",
                           "Shutdown test evidence references are required.", SHUTDOWN_EVIDENCE_HINT))
        detail["state"] = "INCOMPLETE"
    if evidence.get("result") != "PASSED":
        out.append(finding(PROFILE_ID, "SHUTDOWN_TEST_NOT_PASSED", "CRITICAL",
                           "The recorded shutdown test did not pass.",
                           "Repair the shutdown path and record a passing test before autonomous operation."))
        detail["state"] = "NOT_PASSED"
    now = _parse_utc(evaluation_time)
    if now is None:
        out.append(finding(PROFILE_ID, "SHUTDOWN_TEST_AGE_UNKNOWN", "CRITICAL",
                           "Shutdown test age cannot be checked without an evaluation time.",
                           "Run with --evaluation-time YYYY-MM-DDTHH:MM:SSZ."))
        if detail["state"] == "MISSING":
            detail["state"] = "AGE_UNKNOWN"
        return out, detail
    age = now - tested_at
    detail["age_days"] = age.days if age >= timedelta(0) else None
    if age < timedelta(0):
        out.append(finding(PROFILE_ID, "SHUTDOWN_TEST_IN_FUTURE", "CRITICAL",
                           "shutdown_tested_at is later than the evaluation time.",
                           "Correct the shutdown test timestamp."))
        detail["state"] = "IN_FUTURE"
    elif age > timedelta(days=max_age):
        out.append(finding(PROFILE_ID, "SHUTDOWN_TEST_STALE", "CRITICAL",
                           f"Shutdown test is older than {max_age} days.",
                           "Re-run and record the shutdown test. " + SHUTDOWN_EVIDENCE_HINT))
        detail["state"] = "STALE"
    elif detail["state"] == "MISSING":
        detail["state"] = "CURRENT"
    return out, detail


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

    autonomous = data.get("autonomous_agent") is True
    shutdown_findings, shutdown_detail = ([], None)
    if autonomous or isinstance(data.get("shutdown_evidence"), dict):
        shutdown_findings, shutdown_detail = _shutdown_evidence_findings(data, evaluation_time)

    if autonomous:
        passport = data.get("agent_passport_ref")
        if not (isinstance(passport, dict) and passport.get("passport_id") and passport.get("passport_digest")):
            findings.append(finding(PROFILE_ID, "AGENT_PASSPORT_MISSING", "CRITICAL",
                                    "Autonomous agent has no agent passport reference.",
                                    "Supply agent_passport_ref with passport_id and passport_digest. "
                                    "This profile checks the reference; validate the passport itself with the Agentic validator."))
            validity_state = "STALE"
            revalidation_required = True
            if trigger is None:
                trigger = "AGENT_PASSPORT"
        if shutdown_findings:
            findings.extend(shutdown_findings)
            validity_state = "STALE"
            revalidation_required = True
            if trigger is None:
                trigger = "SHUTDOWN_EVIDENCE"

    structured_shutdown_current = shutdown_detail is not None and not shutdown_findings
    if data.get("high_consequence") and not (data.get("shutdown_evidence_present") or structured_shutdown_current):
        findings.append(finding(PROFILE_ID, "SHUTDOWN_EVIDENCE", "CRITICAL",
                                "High-consequence subject lacks shutdown evidence.",
                                SHUTDOWN_EVIDENCE_HINT))
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
    if shutdown_detail is not None:
        details["shutdown_test"] = shutdown_detail
    if autonomous:
        details["autonomous_agent"] = True
    return findings, evidence, details
