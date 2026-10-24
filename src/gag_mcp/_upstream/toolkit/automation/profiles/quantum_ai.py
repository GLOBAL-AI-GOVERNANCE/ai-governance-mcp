"""Fail-closed evaluator for the frozen synthetic magnetic-navigation exercise."""
from __future__ import annotations

import math
import re
from pathlib import Path
from .common import canonical_bytes, finding, sha256_bytes

PROFILE = "quantum-ai-convergence-v0.1"
VERSION = "0.1.0"
ALGORITHM = "classical-nearest-map-value-v1"
PROHIBITED = {
    "REAL_HARDWARE": (r"\b(real|physical|production)[ -]?(quantum )?hardware\b", r"\bquantum hardware\b"),
    "QUANTUM_ADVANTAGE": (r"\bquantum advantage\b",),
    "OPERATIONAL": (r"\boperational (accuracy|capability|deployment|navigation|readiness|system|use)\b",),
    "AUTONOMOUS_ACTION": (r"\bautonomous (action|control|decision|operation|navigation)\b",),
    "COUNTER_DETECTION": (r"\bcounter[ -]detection\b", r"\bevad(e|ing|es) detection\b"),
    "CERTIFICATION": (r"\bcertif(y|ies|ied|ication)\b",),
}

def _issue(code: str, message: str, action: str):
    return finding(PROFILE, code, "CRITICAL", message, action)

def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))

def evaluate(data: dict[str, object], root: Path, evaluation_time: str | None):
    del root, evaluation_time
    issues = []
    text = str(data).lower()
    for name, patterns in PROHIBITED.items():
        if any(re.search(pattern, text) for pattern in patterns):
            issues.append(_issue(f"UNSUPPORTED_CLAIM_{name}", "Unsupported claim exceeds the synthetic/emulated scope.", "Remove the claim and describe only the bounded synthetic exercise."))

    seed, measurements, reference = data.get("seed"), data.get("measurements"), data.get("reference_map")
    if not isinstance(seed, int) or isinstance(seed, bool):
        issues.append(_issue("MISSING_OR_INVALID_SEED", "A deterministic integer seed is required.", "Provide the declared synthetic seed."))
    measurements_ok = isinstance(measurements, list) and bool(measurements)
    if not measurements_ok:
        issues.append(_issue("MISSING_MEASUREMENTS", "Synthetic measurements are required.", "Provide at least one synthetic measurement.")); measurements = []
    elif any(not isinstance(x, dict) or not isinstance(x.get("id"), str) or not x.get("id") or not _number(x.get("value")) for x in measurements):
        issues.append(_issue("MALFORMED_MEASUREMENT", "Every measurement requires a non-empty id and finite numeric value.", "Repair the malformed synthetic measurement.")); measurements_ok = False
    reference_ok = isinstance(reference, list) and bool(reference)
    if not reference_ok or (isinstance(reference, list) and any(not isinstance(x, dict) or not isinstance(x.get("label"), str) or not x.get("label") or not _number(x.get("value")) for x in reference)):
        issues.append(_issue("CORRUPTED_REFERENCE_MAP", "The reference map is missing or malformed.", "Restore the declared synthetic reference map.")); reference_ok = False; reference = []
    elif len({x["label"] for x in reference}) != len(reference):
        issues.append(_issue("CORRUPTED_REFERENCE_MAP", "Reference-map labels must be unique.", "Restore unique labels in the synthetic reference map.")); reference_ok = False

    estimates, residuals = [], []
    if measurements_ok and reference_ok:
        for measurement in measurements:
            best = min(reference, key=lambda point: (abs(float(point["value"]) - float(measurement["value"])), str(point["label"])))
            error = round(abs(float(best["value"]) - float(measurement["value"])), 6)
            residuals.append(round(float(measurement["value"]) - float(best["value"]), 6))
            estimates.append({"measurement_id": measurement["id"], "matched_label": best["label"], "absolute_error": error})
        threshold = data.get("fixture_threshold")
        if not _number(threshold) or float(threshold) < 0:
            issues.append(_issue("INVALID_FIXTURE_THRESHOLD", "The research-fixture threshold must be a non-negative finite number.", "Restore the synthetic fixture threshold."))
        elif any(x["absolute_error"] > float(threshold) for x in estimates):
            issues.append(_issue("FIXTURE_THRESHOLD_EXCEEDED", "A synthetic estimate exceeded the fixture-specific research threshold.", "Review the synthetic measurements and classical baseline."))
        bias_limit = data.get("bias_limit")
        if not _number(bias_limit) or float(bias_limit) < 0:
            issues.append(_issue("INVALID_BIAS_LIMIT", "A non-negative synthetic bias limit is required.", "Restore the fixture-specific bias limit."))
        else:
            limit = float(bias_limit)
            if all(abs(v) > limit for v in residuals) and (all(v > 0 for v in residuals) or all(v < 0 for v in residuals)):
                issues.append(_issue("CONSTANT_BIAS", "Residuals show constant-direction bias beyond the fixture limit.", "Reject the mutated synthetic run."))
            midpoint = len(residuals) // 2
            if len(residuals) >= 4 and abs(sum(residuals[:midpoint]) / midpoint - sum(residuals[midpoint:]) / (len(residuals) - midpoint)) > 2 * limit:
                issues.append(_issue("STEP_BIAS", "Residuals show a step change beyond the fixture limit.", "Reject the mutated synthetic run."))

    quality = data.get("quality")
    if not isinstance(quality, dict):
        issues.append(_issue("MISSING_QUALITY_RECORD", "A structured synthetic quality record is required.", "Provide the declared quality record.")); quality = {}
    if quality.get("missing_count") != 0: issues.append(_issue("MISSING_MEASUREMENT_DECLARED", "The quality record declares missing measurements.", "Complete the synthetic measurement set."))
    if quality.get("saturation") is not False: issues.append(_issue("SATURATION", "The quality record does not rule out saturation.", "Reject the saturated or undeclared run."))
    if not _number(quality.get("clock_drift")) or float(quality.get("clock_drift", 0)) != 0: issues.append(_issue("CLOCK_DRIFT", "Clock drift must be finite and zero in this deterministic fixture.", "Correct the synthetic clock before replay."))
    if data.get("algorithm") != ALGORITHM: issues.append(_issue("ALGORITHM_SUBSTITUTION", "The declared classical algorithm is absent or substituted.", f"Use {ALGORITHM}."))
    calibration = data.get("calibration")
    if not isinstance(calibration, dict) or calibration.get("id") != "synthetic-v1" or calibration.get("status") != "CURRENT_FOR_FIXTURE": issues.append(_issue("STALE_CALIBRATION", "Calibration is missing, stale, or not the fixture calibration.", "Restore current synthetic fixture calibration."))
    confidence = data.get("confidence")
    if not isinstance(confidence, dict) or confidence.get("basis") != "SYNTHETIC_FIXTURE_ONLY" or confidence.get("level") != "BOUNDED": issues.append(_issue("FALSE_HIGH_CONFIDENCE", "Confidence is missing, overstated, or not bounded to the fixture.", "Declare bounded synthetic-fixture-only confidence."))

    run_evidence, evidence_digest = data.get("run_evidence"), data.get("evidence_digest")
    if not isinstance(evidence_digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", evidence_digest) or not isinstance(run_evidence, dict) or evidence_digest != sha256_bytes(canonical_bytes(run_evidence)):
        issues.append(_issue("EVIDENCE_DIGEST_MISMATCH", "The evidence digest is malformed or does not match canonical run evidence.", "Regenerate and verify the run-evidence digest."))
    snapshot = {"seed": seed, "measurements": measurements, "reference_map": reference, "algorithm": data.get("algorithm")}
    if not isinstance(run_evidence, dict) or run_evidence.get("input_snapshot") != snapshot: issues.append(_issue("RUN_EVIDENCE_TAMPERING", "Run evidence does not match the evaluated synthetic inputs.", "Reject and regenerate evidence from evaluated input."))
    human = data.get("human_boundary")
    if not isinstance(human, dict) or human.get("required") is not True or human.get("autonomous_action") is not False: issues.append(_issue("MISSING_HUMAN_BOUNDARY", "The required human-review/no-autonomous-action boundary is missing.", "Restore the human authority boundary."))
    handoff = data.get("handoff")
    if not isinstance(handoff, dict) or handoff.get("authority_effect") != "NONE": issues.append(_issue("AUTHORITY_CHANGING_HANDOFF", "The handoff is missing or could change authority.", "Set authority_effect to NONE."))
    fallback = data.get("fallback")
    if not isinstance(fallback, dict) or fallback.get("required") is not True or fallback.get("available") is not True: issues.append(_issue("FALLBACK_UNAVAILABLE", "The required synthetic fallback is unavailable.", "Restore the fixture fallback before replay."))

    details = {"exercise":"Synthetic Magnetic-Navigation Assurance Exercise","seed":seed,"algorithm":data.get("algorithm"),"estimates":estimates,"quality":data.get("quality"),"measurement_boundary":data.get("measurement_boundary"),
        "evidence_dimensions":{"basis":"E1_REPRODUCIBLE_SYNTHETIC_RUN","provenance":"PROJECT_GENERATED_FIXTURE","publication_status":"PUBLISHED_TOOLKIT_PROFILE","replication_status":"DETERMINISTIC_ARTIFACT_REPLAY_VERIFIED"},
        "replay_taxonomy":{"deterministic_artifact_replay":"VERIFIED","statistical_repeatability":"NOT_ASSESSED","independent_external_reproducibility":"NOT_REPORTED"},
        "experimental_evidence_states":{"usable":["E0","E1"],"reserved":["E2","E3","E4","E5"]},"threshold_boundary":"Fixture-specific research threshold; not an operational safety threshold and not generalizable.","authority_effect":"NONE","certification_semantics":"NONE"}
    evidence = [{"type":"ARTIFACT_ID","reference":str(data.get("run_evidence_id","synthetic-run"))}]
    if isinstance(evidence_digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", evidence_digest): evidence[0]["sha256"] = evidence_digest
    return issues, evidence, details
