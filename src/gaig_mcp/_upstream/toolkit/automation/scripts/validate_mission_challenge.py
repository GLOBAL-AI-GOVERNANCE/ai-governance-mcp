"""Offline validator for the synthetic mission-assurance challenge. No network."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THREAD_PATH = ROOT / "automation/assurance/mission-assurance/challenge/golden-thread.json"
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
COMMIT = re.compile(r"^[a-f0-9]{40}$")
ALLOWED = {
    "ai-governance-os",
    "global-ai-governance-toolkit",
    "agentic-ai-governance",
    "governed-systems-administration",
    "verified-vulnerability-governance",
    "ai-cyber-resilience-framework",
    "peace-os",
}
REQUIRED_SCENARIOS = {
    "normal",
    "adversarial-failure",
    "dependency-failure",
    "recovery-failure",
    "succession-failure",
    "material-change",
    "initial-result-after-material-change",
    "institutional-qualified-support",
    "qualification-conditional",
    "qualification-not-qualified",
    "qualification-not-yet-effective",
    "qualification-expired",
    "qualification-wrong-subject",
    "qualification-wrong-configuration",
    "qualification-missing-competence",
    "decision-blocking-open",
    "decision-blocking-escalated",
    "decision-expired",
    "decision-wrong-subject",
    "decision-wrong-configuration",
    "decision-resolved-without-reference",
    "concern-questioned-revalidation",
    "concern-hold",
    "concern-stale",
    "concern-active-not-resolved",
    "concern-wrong-subject",
    "concern-wrong-configuration",
    "concern-closed-without-evidence",
    "absence-not-nonexistence",
}
REFERENCE_KEYS = {
    "reference_id",
    "source_repository",
    "source_commit",
    "artifact_path",
    "artifact_type",
    "artifact_digest",
    "authority_effect",
}
OPTIONAL_REFERENCE_KEYS = {"subject_id", "configuration_digest", "expected_outcome"}
BINDING_TYPES = {"SAME_SUBJECT", "COMPONENT_OF", "SUPPORTING_EVIDENCE_FOR"}
BINDING_KEYS = {
    "binding_id",
    "reference_id",
    "binding_type",
    "thread_subject_id",
    "thread_configuration_digest",
    "native_subject_id",
    "native_configuration_digest",
    "limitations",
    "authority_effect",
}


class ChallengeError(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ChallengeError(message)


def validate_thread(thread: dict) -> dict:
    _require(isinstance(thread, dict), "thread must be an object")
    _require(thread.get("reference_only") is True, "reference_only must be true")
    _require(thread.get("authority_effect") == "NONE", "authority_effect must be NONE")
    _require(thread.get("synthetic") is True, "thread must be synthetic")
    _require(thread.get("automatic_requalification") is False, "automatic requalification is not permitted")
    _require(isinstance(thread.get("subject_id"), str) and thread["subject_id"].strip(), "subject_id required")
    _require(DIGEST.fullmatch(str(thread.get("configuration_digest", ""))), "configuration_digest malformed")
    scenarios = thread.get("scenarios")
    _require(isinstance(scenarios, list), "scenarios required")
    by_id = {}
    for item in scenarios:
        _require(isinstance(item, dict) and item.get("id"), "scenario id required")
        _require(item["id"] not in by_id, f"duplicate scenario {item['id']}")
        by_id[item["id"]] = item
        _require(item.get("expect") in {"PASS", "FAIL", "NOT_CURRENT"}, "unsupported scenario expectation")
    missing = REQUIRED_SCENARIOS - set(by_id)
    _require(not missing, f"missing scenarios: {', '.join(sorted(missing))}")
    _require(by_id["normal"]["expect"] == "PASS", "normal scenario must expect PASS")
    _require(by_id["material-change"].get("material_change") is True, "material change must invalidate current assurance")
    _require(by_id["material-change"]["expect"] == "FAIL", "material change must fail")
    _require(by_id["initial-result-after-material-change"]["expect"] == "NOT_CURRENT", "initial result must not stay current")
    references = thread.get("references")
    _require(isinstance(references, list) and references, "references required")
    seen = {}
    for ref in references:
        _require(isinstance(ref, dict), "reference must be an object")
        extra = set(ref) - REFERENCE_KEYS - OPTIONAL_REFERENCE_KEYS
        _require(not extra, f"unsupported reference fields: {', '.join(sorted(extra))}")
        _require(REFERENCE_KEYS <= set(ref), "reference is missing required fields")
        _require(ref["source_repository"] in ALLOWED, f"unsupported repository {ref['source_repository']}")
        _require(COMMIT.fullmatch(ref["source_commit"]), "source_commit must be 40 lowercase hex")
        _require(DIGEST.fullmatch(ref["artifact_digest"]), "artifact_digest malformed")
        _require(ref["authority_effect"] == "NONE", "reference cannot transfer authority")
        _require(isinstance(ref["artifact_path"], str) and ref["artifact_path"] and "://" not in ref["artifact_path"], "artifact_path required")
        if "subject_id" in ref:
            _require(isinstance(ref["subject_id"], str) and ref["subject_id"].strip(), "subject_id malformed")
        if "configuration_digest" in ref:
            _require(DIGEST.fullmatch(ref["configuration_digest"]), "reference configuration malformed")
        _require(ref["reference_id"] not in seen, "duplicate reference")
        seen[ref["reference_id"]] = ref
    dependency = by_id["dependency-failure"].get("native_reference")
    succession = by_id["succession-failure"].get("native_reference")
    _require(dependency in seen and seen[dependency]["artifact_path"].endswith("synthetic-exit-failed.json"), "dependency failure must name the native failed exit record")
    _require(succession in seen and seen[succession]["artifact_path"].endswith("succession-evidence-failed.json"), "succession failure must name the native failed succession record")
    _require(seen[dependency]["expected_outcome"] == "FAILED", "dependency failure cannot be PASS")
    _require(seen[succession]["expected_outcome"] == "FAILED", "succession failure cannot be PASS")
    for name in (
        "qualification-evidence-record",
        "unresolved-decision-record",
        "protected-concern-disposition-record",
    ):
        _require(name in seen, f"missing institutional reference {name}")
        _require(seen[name]["source_repository"] == "ai-governance-os", "institutional reference must stay native")
        _require(seen[name]["authority_effect"] == "NONE", "institutional reference cannot transfer authority")
    _require(by_id["institutional-qualified-support"]["expect"] == "PASS", "current qualification may support the structural path")
    _require(by_id["institutional-qualified-support"].get("native_reference") == "qualification-evidence-record", "positive case must name the qualification candidate")
    _require(by_id["absence-not-nonexistence"]["expect"] == "PASS", "absence is not itself a failure")
    for scenario_id, item in by_id.items():
        if scenario_id.startswith(("qualification-", "decision-", "concern-")):
            _require(item["expect"] == "FAIL", f"{scenario_id} must not pass")
    summary = thread.get("qualification_summary")
    _require(isinstance(summary, dict), "qualification summary required")
    qual = seen["qualification-evidence-record"]
    _require(summary.get("outcome") == "QUALIFIED", "qualification summary must be QUALIFIED")
    _require(summary.get("outcome") == qual.get("expected_outcome"), "qualification summary diverges from the native candidate")
    _require(summary.get("subject_id") == qual["subject_id"], "qualification summary rewrites the native subject")
    _require(summary.get("configuration_digest") == qual["configuration_digest"], "qualification summary rewrites the native configuration")
    _require(summary.get("authority_effect") == "NONE", "qualification summary cannot transfer authority")
    _require(summary.get("qualified_from", "") < summary.get("expires_at", ""), "qualification interval is invalid")
    _require(isinstance(summary.get("competence_evidence_refs"), list) and summary["competence_evidence_refs"], "competence evidence required")
    decision = thread.get("decision_summary")
    concern = thread.get("concern_summary")
    _require(isinstance(decision, dict) and decision.get("status") == "OPEN" and decision.get("blocking") is True, "decision summary must remain the blocking open candidate")
    _require(decision.get("subject_id") == seen["unresolved-decision-record"]["subject_id"], "decision summary rewrites the native subject")
    _require(decision.get("configuration_digest") == seen["unresolved-decision-record"]["configuration_digest"], "decision summary rewrites the native configuration")
    _require(isinstance(decision.get("owner_ref"), str) and decision["owner_ref"].strip(), "decision summary requires an owner")
    _require(isinstance(decision.get("escalation_route_ref"), str) and decision["escalation_route_ref"].strip(), "decision summary requires an escalation route")
    _require(decision.get("authority_effect") == "NONE", "decision summary cannot transfer authority")
    _require(isinstance(concern, dict) and concern.get("status") == "ACTIVE", "concern summary must remain active")
    _require(concern.get("assurance_effect") == "QUESTIONED" and concern.get("revalidation_required") is True, "concern summary must retain questioned revalidation")
    _require(concern.get("subject_id") == seen["protected-concern-disposition-record"]["subject_id"], "concern summary rewrites the native subject")
    _require(concern.get("configuration_digest") == seen["protected-concern-disposition-record"]["configuration_digest"], "concern summary rewrites the native configuration")
    _require(concern.get("authority_effect") == "NONE", "concern summary cannot transfer authority")
    limitations = " ".join(thread.get("limitations") or []).lower()
    _require("no unresolved decision exists" in limitations, "absence of a decision reference must not be treated as proof")
    _require("no protected concern exists" in limitations, "absence of a concern reference must not be treated as proof")
    bindings = thread.get("subject_bindings")
    _require(isinstance(bindings, list), "subject_bindings required")
    by_binding = {}
    seen_binding_ids = set()
    for binding in bindings:
        _require(isinstance(binding, dict) and set(binding) == BINDING_KEYS, "unsupported binding fields")
        _require(isinstance(binding["binding_id"], str) and binding["binding_id"].strip(), "binding_id required")
        _require(binding["binding_id"] not in seen_binding_ids, "duplicate binding_id")
        seen_binding_ids.add(binding["binding_id"])
        ref_id = binding["reference_id"]
        _require(ref_id in seen, "binding points to a nonexistent reference")
        _require(ref_id not in by_binding, "duplicate binding")
        ref = seen[ref_id]
        _require("subject_id" in ref or "configuration_digest" in ref, "binding requires a subject-bearing reference")
        _require(binding["binding_type"] != "AUTHORIZES", "binding cannot grant authority")
        _require(binding["binding_type"] in BINDING_TYPES, "unsupported binding_type")
        _require(binding["authority_effect"] == "NONE", "binding authority_effect must be NONE")
        _require(binding["thread_subject_id"] == thread["subject_id"], "thread_subject_id differs from the golden thread")
        _require(
            binding["thread_configuration_digest"] == thread["configuration_digest"],
            "thread_configuration_digest differs from the golden thread",
        )
        _require(DIGEST.fullmatch(binding["thread_configuration_digest"]), "thread_configuration_digest malformed")
        _require(isinstance(binding["native_subject_id"], str) and binding["native_subject_id"].strip(), "native_subject_id required")
        _require(DIGEST.fullmatch(binding["native_configuration_digest"]), "native_configuration_digest malformed")
        if "subject_id" in ref:
            _require(binding["native_subject_id"] == ref["subject_id"], "native_subject_id differs from the reference")
        if "configuration_digest" in ref:
            _require(
                binding["native_configuration_digest"] == ref["configuration_digest"],
                "native_configuration_digest differs from the reference",
            )
        if binding["binding_type"] == "SAME_SUBJECT":
            _require(
                binding["native_subject_id"] == binding["thread_subject_id"]
                and binding["native_configuration_digest"] == binding["thread_configuration_digest"],
                "SAME_SUBJECT declared while identifiers or configurations differ",
            )
            _require(isinstance(binding["limitations"], list), "limitations must be an array")
        else:
            limitations = binding["limitations"]
            _require(isinstance(limitations, list) and limitations, "limitations are missing")
            _require(all(isinstance(item, str) and item.strip() for item in limitations), "limitations malformed")
            text = " ".join(limitations).lower()
            _require("synthetic declared binding" in text, "limitation must state synthetic declared binding")
            _require("not external proof" in text, "limitation must deny external proof of real-world system identity")
        by_binding[ref_id] = binding
    for ref_id, ref in seen.items():
        if "subject_id" in ref or "configuration_digest" in ref:
            _require(ref_id in by_binding, "reference with subject/configuration lacks a binding")
    for scenario_id in ("dependency-failure", "succession-failure"):
        native_ref = by_id[scenario_id].get("native_reference")
        _require(native_ref in by_binding, "unbound failure scenario")
    return {
        "valid": True,
        "authority_effect": "NONE",
        "scenarios": len(scenarios),
        "references": len(references),
        "bindings": len(bindings),
    }


def validate_thread_file(path: Path | None = None) -> dict:
    path = path or THREAD_PATH
    return validate_thread(json.loads(path.read_text(encoding="utf-8")))


def main() -> None:
    print(json.dumps(validate_thread_file(), sort_keys=True))


if __name__ == "__main__":
    main()
