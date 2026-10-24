"""Bounded Auditable AI assurance-case evaluator."""

from __future__ import annotations

import re
import hashlib
from pathlib import Path

from .common import finding, safe_local_reference

PROFILE = "auditable-ai-v1"
VERSION = "1.0.0-rc.2"
APPROVING = {"CONTROLLED_TEST_READY", "LIMITED_PILOT_READY"}
DECISIONS = APPROVING | {"HOLD"}
EVIDENCE_TYPES = {"ARTIFACT_ID", "LOCAL_PATH", "URI"}


def evaluate(data: dict[str, object], root: Path, evaluation_time: str | None):
    issues = []
    add = lambda code, msg, action: issues.append(finding(PROFILE, code, "CRITICAL", msg, action))
    required = ("safety_claim", "control", "implementation", "test", "evidence", "human_review", "bounded_decision")
    for key in required:
        if not data.get(key):
            add("MISSING_" + key.upper(), f"Required assurance element '{key}' is missing.", f"Provide the {key.replace('_', ' ')} record.")
    claim, control = data.get("safety_claim", {}), data.get("control", {})
    implementation, test = data.get("implementation", {}), data.get("test", {})
    if all(isinstance(item, dict) for item in (claim, control, implementation, test)):
        links = (
            (control, "claim_id", claim.get("id"), "CONTROL_CLAIM_LINK_MISMATCH"),
            (implementation, "control_id", control.get("id"), "IMPLEMENTATION_CONTROL_LINK_MISMATCH"),
            (test, "implementation_id", implementation.get("id"), "TEST_IMPLEMENTATION_LINK_MISMATCH"),
        )
        for record, field, expected, code in links:
            if not expected or record.get(field) != expected:
                add(code, f"Assurance trace link '{field}' is missing or inconsistent.", "Restore the explicit claim-to-control-to-implementation-to-test link.")
        if control.get("policy_model") != test.get("policy_model"):
            add("POLICY_MODEL_MISMATCH", "Control and test policy/model identifiers do not match.", "Align the tested artifact with the declared control.")
        if test.get("prohibited_use_passed") is not True:
            add("PROHIBITED_USE_TEST_FAILED", "The prohibited-use test did not pass.", "Block advancement and remediate the prohibited-use control.")
        if int(test.get("critical_false_negatives", 0) or 0) > 0:
            add("CRITICAL_FALSE_NEGATIVE", "The submitted test records a critical false negative.", "Resolve and independently review the critical false negative.")
    evidence = data.get("evidence", [])
    refs = []
    if not isinstance(evidence, list) or not evidence:
        add("MISSING_EVIDENCE", "No evidence record was submitted.", "Attach bounded, traceable evidence.")
    else:
        seen_refs = set()
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                add("MALFORMED_EVIDENCE", f"Evidence reference {index} is not an object.", "Provide a typed evidence object with a non-empty reference.")
                continue
            ref, kind = str(item.get("reference", "")), str(item.get("type", ""))
            if not ref or kind not in EVIDENCE_TYPES:
                add("MALFORMED_EVIDENCE", f"Evidence reference {index} has a missing reference or unsupported type.", "Use ARTIFACT_ID, LOCAL_PATH, or URI with a non-empty reference.")
            identity = (kind, ref)
            if identity in seen_refs:
                add("DUPLICATE_EVIDENCE_REFERENCE", f"Evidence reference {index} duplicates an earlier reference.", "Remove the duplicate or reference a distinct artifact.")
            seen_refs.add(identity)
            refs.append({k: item[k] for k in ("type", "reference", "sha256") if k in item})
            if kind == "LOCAL_PATH":
                if not safe_local_reference(root, ref):
                    add("PATH_TRAVERSAL", f"Evidence reference {index} is not a path-safe local reference.", "Use a relative path contained by the assurance-case directory.")
                elif not (root / ref).is_file():
                    add("INVALID_ARTIFACT_REFERENCE", f"Evidence reference {index} does not identify a local file.", "Provide an existing file within the assurance-case directory.")
            pointer = item.get("json_pointer")
            if pointer is not None and (not isinstance(pointer, str) or (pointer != "" and not re.fullmatch(r"(?:/(?:[^~/]|~[01])*)+", pointer))):
                add("MALFORMED_JSON_POINTER", f"Evidence reference {index} has a malformed JSON Pointer.", "Use RFC 6901 pointer escaping.")
            digest = item.get("sha256")
            if digest is not None and not re.fullmatch(r"sha256:[0-9a-f]{64}", str(digest)):
                add("INVALID_ARTIFACT_REFERENCE", f"Evidence reference {index} has an invalid SHA-256.", "Provide a lowercase sha256:<64 hex> digest.")
            elif kind == "LOCAL_PATH" and digest is not None and safe_local_reference(root, ref) and (root / ref).is_file():
                actual = "sha256:" + hashlib.sha256((root / ref).read_bytes()).hexdigest()
                if digest != actual:
                    add("INVALID_ARTIFACT_REFERENCE", f"Evidence reference {index} digest does not match the local artifact.", "Use the referenced artifact's current SHA-256.")
            if evaluation_time and item.get("expires_at") and str(item["expires_at"]) < evaluation_time:
                add("STALE_EVIDENCE", f"Evidence reference {index} is expired at the evaluation time.", "Refresh the evidence before review.")
    if data.get("unresolved_critical_bypass") is True:
        add("UNRESOLVED_CRITICAL_BYPASS", "A critical bypass remains unresolved.", "Resolve and independently review the bypass.")
    review = data.get("human_review", {})
    if not isinstance(review, dict) or review.get("approved") is not True or not review.get("reviewer"):
        add("MISSING_APPROVING_REVIEW", "An approving named human review is missing.", "Record the accountable approving review.")
    decision = data.get("bounded_decision", {})
    state = decision.get("state") if isinstance(decision, dict) else None
    if state not in DECISIONS:
        add("INVALID_BOUNDED_DECISION", "The bounded decision is missing or outside the frozen state set.", "Use HOLD, CONTROLLED_TEST_READY, or LIMITED_PILOT_READY.")
    if state in APPROVING and issues:
        add("INAPPROPRIATE_ADVANCEMENT", "Advancement was declared while fail-closed gates remain unresolved.", "Set HOLD or resolve every hard failure and review again.")
    details = {"claim_id": data.get("case_id"), "bounded_decision": state, "chain": list(required),
               "verification_boundary": "Structure and integrity of the submitted assurance case; not universal technical truth."}
    return issues, refs, details
