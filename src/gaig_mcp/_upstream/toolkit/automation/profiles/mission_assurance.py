"""Mission Assurance interoperability profile.

Non-authorizing. Assembles submitted references only.
A PASS means the selected stage's structural checks passed.
It does not validate native source artifacts or authorize use.
"""
from __future__ import annotations

import re
from pathlib import Path

from .common import finding

PROFILE_ID = "mission-assurance-v0.1"
VERSION = "0.1.0"
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
STAGES = ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]
STAGE_INDEX = {stage: index for index, stage in enumerate(STAGES)}


def _critical(findings: list, code: str, message: str, action: str) -> None:
    findings.append(finding(PROFILE_ID, code, "CRITICAL", message, action))


def _bind(reference: dict, data: dict, findings: list, label: str) -> None:
    if not isinstance(reference, dict):
        _critical(findings, f"{label}_INVALID", f"{label} must be an evidence reference.", "Supply a complete evidence reference.")
        return
    if reference.get("authority_effect") != "NONE":
        _critical(findings, f"{label}_AUTHORITY", f"{label} cannot confer authority.", "Set authority_effect to NONE.")
    if reference.get("subject_id") != data.get("subject_id"):
        _critical(findings, f"{label}_SUBJECT", f"{label} subject does not match the mission subject.", "Bind the reference to the same subject.")
    if reference.get("configuration_digest") != data.get("configuration_digest"):
        _critical(findings, f"{label}_CONFIGURATION", f"{label} configuration does not match.", "Bind the reference to the same configuration.")
    if not DIGEST.fullmatch(str(reference.get("artifact_digest", ""))):
        _critical(findings, f"{label}_DIGEST", f"{label} artifact digest is malformed.", "Supply a sha256 digest.")


def evaluate(data: dict, root: Path, evaluation_time: str | None = None) -> tuple[list, list, dict]:
    findings: list = []
    evidence: list = []
    target = data.get("target_stage")
    required_through = STAGE_INDEX.get(target, -1)
    if required_through < 0:
        _critical(findings, "TARGET_STAGE", "target_stage is unsupported.", "Select G0 through G8.")
        required_through = -1
    if data.get("reference_only") is not True:
        _critical(findings, "REFERENCE_ONLY", "Profile input must remain reference-only.", "Set reference_only to true.")
    if data.get("human_decision_required") is not True:
        _critical(findings, "HUMAN_DECISION", "Human decision remains required.", "Set human_decision_required to true.")
    if data.get("authority_effect") != "NONE":
        _critical(findings, "AUTHORITY_EFFECT", "Automated output cannot create authority.", "Set authority_effect to NONE.")
    if not DIGEST.fullmatch(str(data.get("configuration_digest", ""))):
        _critical(findings, "CONFIGURATION_DIGEST", "configuration_digest is malformed.", "Supply a sha256 digest.")

    known = data.get("known_unknowns") if isinstance(data.get("known_unknowns"), list) else []
    blocking = data.get("blocking_unknowns") if isinstance(data.get("blocking_unknowns"), list) else []
    if blocking:
        _critical(findings, "BLOCKING_UNKNOWN", "Blocking unknowns prevent the selected stage.", "Resolve or explicitly re-scope the blocking unknowns.")

    if data.get("material_change") is True:
        _critical(findings, "MATERIAL_CHANGE", "Prior assurance cannot establish current assurance after material change.", "Requalify the current subject and configuration.")

    checks = {
        0: ("MISSION", bool(data.get("mission_id") and data.get("mission_objective") and data.get("accountable_human_ref")), "mission identity"),
        1: ("BASELINE", isinstance(data.get("baseline_reference"), dict), "baseline reference"),
        2: ("AUTHORITY_DATA", isinstance(data.get("authority_data_references"), list) and bool(data.get("authority_data_references")), "authority/data reference"),
        3: ("QUALIFICATION", isinstance(data.get("qualification_reference"), dict), "qualification reference"),
        4: ("ADVERSARIAL_ASSURANCE", isinstance(data.get("adversarial_assurance_reference"), dict), "adversarial assurance reference"),
        5: ("HUMAN_READINESS", isinstance(data.get("human_readiness_reference"), dict), "human readiness reference"),
        6: ("OPERATIONAL_ACCEPTANCE", isinstance(data.get("operational_acceptance_reference"), dict), "operational acceptance reference"),
        7: ("SUSTAINMENT", all(isinstance(data.get(key), dict) for key in ("degraded_mode_reference", "recovery_reference", "support_owner_reference")), "sustainment references"),
        8: ("SUCCESSION", isinstance(data.get("succession_reference"), dict), "succession reference"),
    }
    for index in range(required_through + 1):
        code, present, label = checks[index]
        if not present:
            _critical(findings, f"MISSING_{code}", f"Required {label} is absent for {target}.", f"Supply the {label} before claiming this stage.")
    bindings = [
        (1, "baseline_reference", "BASELINE"),
        (3, "qualification_reference", "QUALIFICATION"),
        (4, "adversarial_assurance_reference", "ADVERSARIAL"),
        (5, "human_readiness_reference", "HUMAN_READINESS"),
        (6, "operational_acceptance_reference", "OPERATIONAL_ACCEPTANCE"),
        (7, "degraded_mode_reference", "DEGRADED_MODE"),
        (7, "recovery_reference", "RECOVERY"),
        (7, "support_owner_reference", "SUPPORT_OWNER"),
        (8, "succession_reference", "SUCCESSION"),
    ]
    for index, key, label in bindings:
        if index <= required_through and isinstance(data.get(key), dict):
            _bind(data[key], data, findings, label)
    if required_through >= 2 and isinstance(data.get("authority_data_references"), list):
        for item in data["authority_data_references"]:
            _bind(item, data, findings, "AUTHORITY_DATA")

    stage_keys = {
        1: ["baseline_reference"],
        2: ["authority_data_references"],
        3: ["qualification_reference"],
        4: ["adversarial_assurance_reference"],
        5: ["human_readiness_reference"],
        6: ["operational_acceptance_reference"],
        7: ["degraded_mode_reference", "recovery_reference", "support_owner_reference"],
        8: ["succession_reference"],
    }
    seen = set()
    for index in range(1, required_through + 1):
        for key in stage_keys.get(index, []):
            value = data.get(key)
            items = value if isinstance(value, list) else [value]
            for item in items:
                if not isinstance(item, dict):
                    continue
                reference = "/".join(str(item.get(field, "")) for field in ("source", "artifact_type", "artifact_id", "schema_version"))
                sha = str(item.get("artifact_digest", ""))
                marker = (reference, sha)
                if marker in seen:
                    continue
                seen.add(marker)
                evidence.append({"type": "ARTIFACT_ID", "reference": reference, "sha256": sha})
    evidence.sort(key=lambda item: (item["type"], item["reference"], item["sha256"]))

    # Consume optional submitted summaries. Absence is not proof of absence.
    # Native authenticity is not established here. Inclusive qualification interval.
    for qual in data.get("qualification_evidence_refs") or []:
        if not isinstance(qual, dict):
            _critical(findings, "QUAL_MALFORMED", "Qualification summary must be an object.", "Supply a complete summary.")
            continue
        if qual.get("authority_effect") != "NONE":
            _critical(findings, "QUAL_AUTHORITY", "Qualification cannot confer authority.", "Set authority_effect to NONE.")
        if qual.get("subject_id") != data.get("subject_id"):
            _critical(findings, "QUAL_SUBJECT", "Qualification subject does not match the mission subject.", "Bind the same subject.")
        if qual.get("configuration_digest") != data.get("configuration_digest"):
            _critical(findings, "QUAL_CONFIGURATION", "Qualification configuration does not match.", "Bind the same configuration.")
        start = qual.get("qualified_from")
        end = qual.get("expires_at")
        outcome = qual.get("outcome")
        if not (isinstance(start, str) and isinstance(end, str) and start < end):
            _critical(findings, "QUAL_INTERVAL", "qualified_from must be strictly before expires_at.", "Correct the interval.")
        elif evaluation_time is None or evaluation_time < start:
            _critical(findings, "QUAL_NOT_YET", "Qualification is not yet effective.", "Do not treat a future qualification as current.")
        elif evaluation_time > end:
            _critical(findings, "QUAL_EXPIRED", "Expired qualification cannot satisfy readiness.", "Requalify.")
        elif outcome == "QUALIFIED":
            pass
        elif outcome == "CONDITIONAL":
            _critical(findings, "QUAL_CONDITIONAL", "CONDITIONAL qualification cannot satisfy readiness in this profile.", "Do not promote CONDITIONAL to QUALIFIED.")
        else:
            _critical(findings, "QUAL_NOT_QUALIFIED", "NOT_QUALIFIED cannot satisfy readiness.", "Supply a current QUALIFIED outcome.")
        if not qual.get("competence_evidence_refs"):
            _critical(findings, "QUAL_COMPETENCE", "Competence evidence is required.", "Supply competence_evidence_refs.")

    for dec in data.get("unresolved_decision_refs") or []:
        if not isinstance(dec, dict):
            _critical(findings, "DEC_MALFORMED", "Decision summary must be an object.", "Supply a complete summary.")
            continue
        if dec.get("authority_effect") != "NONE":
            _critical(findings, "DEC_AUTHORITY", "Decision record cannot confer authority.", "Set authority_effect to NONE.")
        if dec.get("subject_id") != data.get("subject_id"):
            _critical(findings, "DEC_SUBJECT", "Decision subject does not match the mission subject.", "Bind the same subject.")
        if dec.get("configuration_digest") != data.get("configuration_digest"):
            _critical(findings, "DEC_CONFIGURATION", "Decision configuration does not match.", "Bind the same configuration.")
        if not isinstance(dec.get("owner_ref"), str) or not dec.get("owner_ref", "").strip():
            _critical(findings, "DEC_OWNER", "Decision debt requires an owner.", "Supply owner_ref.")
        if not isinstance(dec.get("deadline"), str) or not dec.get("deadline"):
            _critical(findings, "DEC_DEADLINE", "Decision debt requires a governed deadline.", "Supply deadline.")
        status = dec.get("status")
        if evaluation_time and status == "OPEN" and isinstance(dec.get("deadline"), str) and evaluation_time > dec["deadline"]:
            status = "EXPIRED"
        if status in ("OPEN", "ESCALATED") and not (isinstance(dec.get("escalation_route_ref"), str) and dec["escalation_route_ref"].strip()):
            _critical(findings, "DEC_ESCALATION", "OPEN or ESCALATED decision requires an escalation route.", "Supply escalation_route_ref.")
        if dec.get("blocking") is True and status in ("OPEN", "ESCALATED", "EXPIRED"):
            _critical(findings, "DEC_BLOCKING", "Blocking decision unresolved or expired cannot satisfy readiness.", "Resolve the decision. Silence is not approval.")
        if status == "RESOLVED" and not (isinstance(dec.get("resolution_reference"), str) and dec["resolution_reference"].strip()):
            _critical(findings, "DEC_RESOLUTION", "RESOLVED requires resolution_reference.", "Supply the resolution reference. Resolution does not authorize operation.")
        if status == "WITHDRAWN":
            # Withdrawal is not approval and does not confer authority.
            pass

    for conc in data.get("protected_concern_disposition_refs") or []:
        if not isinstance(conc, dict):
            _critical(findings, "CONCERN_MALFORMED", "Concern disposition must be an object.", "Supply a complete public disposition.")
            continue
        if conc.get("authority_effect") != "NONE":
            _critical(findings, "CONCERN_AUTHORITY", "Concern disposition cannot confer authority.", "Set authority_effect to NONE.")
        if conc.get("subject_id") != data.get("subject_id"):
            _critical(findings, "CONCERN_SUBJECT", "Concern subject does not match the mission subject.", "Bind the same subject.")
        if conc.get("configuration_digest") != data.get("configuration_digest"):
            _critical(findings, "CONCERN_CONFIGURATION", "Concern configuration does not match.", "Bind the same configuration.")
        effect = conc.get("assurance_effect")
        if conc.get("revalidation_required") is True:
            _critical(findings, "CONCERN_REVALIDATION", "Required revalidation prevents a current pass.", "Complete governed revalidation. A disposition does not establish allegation truth.")
        if effect == "HOLD":
            _critical(findings, "CONCERN_HOLD", "HOLD cannot pass and cannot become authorization.", "Resolve the disposition.")
        if effect == "STALE":
            _critical(findings, "CONCERN_STALE", "STALE cannot pass.", "Revalidate.")
            if conc.get("revalidation_required") is not True:
                _critical(findings, "CONCERN_STALE_REVALIDATION", "STALE requires revalidation.", "Set revalidation_required.")
        if conc.get("status") == "ACTIVE":
            _critical(findings, "CONCERN_ACTIVE", "An ACTIVE concern is not resolved.", "Do not treat an active disposition as closed.")
        if conc.get("status") == "CLOSED":
            refs = conc.get("closure_evidence_refs")
            if not isinstance(refs, list) or not refs:
                _critical(findings, "CONCERN_CLOSURE", "Closure requires bounded evidence reference.", "Supply closure_evidence_refs.")

    details = {
        "reference_only": True,
        "authority_effect": "NONE",
        "target_stage": target,
        "known_unknowns": known,
        "blocking_unknowns": blocking,
        "requalification_required": data.get("material_change") is True,
        "native_authenticity": "not established",
        "pass_means": "Selected-stage structural, identity, configuration-binding, and integrity checks only.",
        "does_not_mean": [
            "operational readiness",
            "legal authority",
            "certification",
            "compliance",
            "factual truth of source evidence",
            "native validation of referenced artifacts",
            "production approval",
            "endorsement",
            "mission success",
            "allegation truth",
        ],
    }
    return findings, evidence, details
