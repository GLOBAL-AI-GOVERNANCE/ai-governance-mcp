#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deterministic, non-enforcing OPA bridge reference adapter.

The adapter consumes an already-established canonical validation result. It
does not parse passports, verify signatures, evaluate revocation lists, make
network calls, or enforce the returned policy disposition.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.strict_json import StrictJSONError, load_strict


CONTRACT_VERSION = "1.0.0"
POLICY_ID = "global-ai-governance.opa-enforcement-bridge"
POLICY_VERSION = "1.0.0-unreleased"
PROFILE_ID = "global-ai-governance.mcp-governance"
PROFILE_VERSION = "0.1.0-alpha.1"
RESULT_VERSION = "1.0.0"
HASH = re.compile(r"^sha256:[0-9a-f]{64}$")

DISPOSITIONS = {
    "PERMITTED",
    "PERMITTED_WITH_CONDITIONS",
    "RESTRICTED",
    "NOT_PERMITTED",
    "INDETERMINATE",
}
VALIDATED_KEYS = {
    "validation_state",
    "verification_result_ref",
    "passport_id",
    "verified_at",
    "valid_until",
    "primary_status",
    "operating_disposition",
    "revocation_status",
    "maximum_action_level",
    "allowed_actions",
    "allowed_resources",
    "evidence_refs",
}
TOP_LEVEL_KEYS = {
    "bridge_contract_version",
    "request_id",
    "evaluation_time",
    "validated_result",
    "request",
    "policy",
    "context",
}
REQUEST_KEYS = {"action", "resource", "action_level"}
POLICY_KEYS = {
    "policy_id",
    "policy_version",
    "profile_id",
    "profile_version",
    "allowed_actions",
    "allowed_resources",
    "denied_actions",
    "required_context",
    "approval_required_actions",
    "max_validation_age_seconds",
}


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be an RFC 3339 UTC string ending in Z")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("timestamp must be UTC")
    return parsed


def _nonempty_strings(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item) for item in value)
        and len(value) == len(set(value))
    )


def _base_result(document: object) -> dict[str, object]:
    request_id = "UNKNOWN"
    evaluated_at = "UNKNOWN"
    policy_id = "UNKNOWN"
    policy_version = "UNKNOWN"
    evidence_refs: list[str] = []
    if isinstance(document, dict):
        if isinstance(document.get("request_id"), str) and document["request_id"]:
            request_id = document["request_id"]
        if isinstance(document.get("evaluation_time"), str):
            evaluated_at = document["evaluation_time"]
        policy = document.get("policy")
        if isinstance(policy, dict):
            if isinstance(policy.get("policy_id"), str):
                policy_id = policy["policy_id"]
            if isinstance(policy.get("policy_version"), str):
                policy_version = policy["policy_version"]
        validated = document.get("validated_result")
        if isinstance(validated, dict) and isinstance(validated.get("evidence_refs"), list):
            evidence_refs = sorted(
                item for item in validated["evidence_refs"] if isinstance(item, str)
            )
    return {
        "bridge_result_version": RESULT_VERSION,
        "request_id": request_id,
        "evaluated_at": evaluated_at,
        "policy": {"policy_id": policy_id, "policy_version": policy_version},
        "operating_disposition": "NOT_PERMITTED",
        "reason_codes": ["BRIDGE_INPUT_INVALID"],
        "evidence_refs": evidence_refs,
        "external_enforcement": "NOT_PERFORMED",
    }


def _input_error(document: object) -> str | None:
    if isinstance(document, dict) and (
        any(key.startswith("raw_") for key in document) or "passport" in document
    ):
        return "RAW_DECLARATION_REJECTED"
    if not isinstance(document, dict) or set(document) != TOP_LEVEL_KEYS:
        return "BRIDGE_INPUT_INVALID"
    if document.get("bridge_contract_version") != CONTRACT_VERSION:
        return "BRIDGE_CONTRACT_UNSUPPORTED"
    if not isinstance(document.get("request_id"), str) or not document["request_id"]:
        return "BRIDGE_INPUT_INVALID"
    try:
        _parse_time(document.get("evaluation_time"))
    except (TypeError, ValueError):
        return "EVALUATION_TIME_INVALID"

    validated = document.get("validated_result")
    request = document.get("request")
    policy = document.get("policy")
    context = document.get("context")
    if not isinstance(validated, dict) or set(validated) != VALIDATED_KEYS:
        return "VALIDATED_RESULT_INVALID"
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        return "REQUEST_INVALID"
    if not isinstance(policy, dict) or set(policy) != POLICY_KEYS:
        return "POLICY_INPUT_INVALID"
    if not isinstance(context, dict):
        return "CONTEXT_INVALID"
    required_strings = (
        validated.get("verification_result_ref"),
        validated.get("passport_id"),
        request.get("action"),
        request.get("resource"),
    )
    if any(not isinstance(value, str) or not value for value in required_strings):
        return "BRIDGE_INPUT_INVALID"
    if not HASH.fullmatch(validated["verification_result_ref"]):
        return "VALIDATED_RESULT_INVALID"
    if not HASH.fullmatch(validated["passport_id"]):
        return "VALIDATED_RESULT_INVALID"
    if not isinstance(request.get("action_level"), int) or not 0 <= request["action_level"] <= 5:
        return "REQUEST_INVALID"
    if not isinstance(validated.get("maximum_action_level"), int) or not 0 <= validated["maximum_action_level"] <= 5:
        return "VALIDATED_RESULT_INVALID"
    for key in ("allowed_actions", "allowed_resources", "evidence_refs"):
        if not _nonempty_strings(validated.get(key)):
            return "VALIDATED_RESULT_INVALID"
    if any(not HASH.fullmatch(item) for item in validated["evidence_refs"]):
        return "VALIDATED_RESULT_INVALID"
    for key in (
        "allowed_actions",
        "allowed_resources",
        "denied_actions",
        "required_context",
        "approval_required_actions",
    ):
        value = policy.get(key)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            return "POLICY_INPUT_INVALID"
        if len(value) != len(set(value)):
            return "POLICY_INPUT_INVALID"
    if not isinstance(policy.get("max_validation_age_seconds"), int) or policy["max_validation_age_seconds"] < 0:
        return "POLICY_INPUT_INVALID"
    for key in ("verified_at", "valid_until"):
        try:
            _parse_time(validated.get(key))
        except (TypeError, ValueError):
            return "VALIDATED_RESULT_INVALID"
    return None


def evaluate(document: object) -> dict[str, object]:
    """Return a deterministic governed disposition; never perform enforcement."""

    result = _base_result(document)
    input_error = _input_error(document)
    if input_error:
        result["reason_codes"] = [input_error]
        return result

    assert isinstance(document, dict)
    validated = document["validated_result"]
    request = document["request"]
    policy = document["policy"]
    context = document["context"]
    assert isinstance(validated, dict)
    assert isinstance(request, dict)
    assert isinstance(policy, dict)
    assert isinstance(context, dict)

    reasons: list[str] = []
    if policy["policy_id"] != POLICY_ID or policy["policy_version"] != POLICY_VERSION:
        reasons.append("POLICY_UNSUPPORTED")
    if policy["profile_id"] != PROFILE_ID or policy["profile_version"] != PROFILE_VERSION:
        reasons.append("PROFILE_UNSUPPORTED")
    if validated["validation_state"] != "ESTABLISHED":
        reasons.append("VALIDATION_NOT_ESTABLISHED")
    if validated["primary_status"] != "VALID":
        reasons.append("CANONICAL_VALIDATION_NOT_VALID")
    if validated["operating_disposition"] not in DISPOSITIONS:
        reasons.append("CANONICAL_DISPOSITION_UNSUPPORTED")
    elif validated["operating_disposition"] not in {
        "PERMITTED",
        "PERMITTED_WITH_CONDITIONS",
    }:
        reasons.append("CANONICAL_DISPOSITION_NOT_PERMITTED")
    if validated["revocation_status"] != "CURRENT_NOT_REVOKED":
        reasons.append("REVOCATION_NOT_CURRENT")

    evaluated_at = _parse_time(document["evaluation_time"])
    verified_at = _parse_time(validated["verified_at"])
    valid_until = _parse_time(validated["valid_until"])
    if verified_at > evaluated_at or evaluated_at >= valid_until:
        reasons.append("VALIDATION_OUTSIDE_VALIDITY")
    elif (evaluated_at - verified_at).total_seconds() > policy["max_validation_age_seconds"]:
        reasons.append("VALIDATION_STALE")

    if request["action_level"] > validated["maximum_action_level"]:
        reasons.append("ACTION_LEVEL_EXCEEDS_AUTHORITY")
    if request["action"] not in validated["allowed_actions"]:
        reasons.append("ACTION_OUTSIDE_AUTHORITY")
    if request["resource"] not in validated["allowed_resources"]:
        reasons.append("RESOURCE_OUTSIDE_AUTHORITY")
    if request["action"] in policy["denied_actions"]:
        reasons.append("POLICY_DENIED")
    if request["action"] not in policy["allowed_actions"]:
        reasons.append("ACTION_NOT_ALLOWED_BY_POLICY")
    if request["resource"] not in policy["allowed_resources"]:
        reasons.append("RESOURCE_NOT_ALLOWED_BY_POLICY")
    missing_context = sorted(key for key in policy["required_context"] if key not in context)
    if missing_context:
        reasons.append("REQUIRED_CONTEXT_MISSING")

    result["reason_codes"] = sorted(set(reasons))
    if reasons:
        return result
    if request["action"] in policy["approval_required_actions"]:
        result["operating_disposition"] = "PERMITTED_WITH_CONDITIONS"
        result["reason_codes"] = ["POLICY_APPROVAL_REQUIRED"]
    elif validated["operating_disposition"] == "PERMITTED_WITH_CONDITIONS":
        result["operating_disposition"] = "PERMITTED_WITH_CONDITIONS"
        result["reason_codes"] = ["CANONICAL_CONDITIONS_RETAINED"]
    else:
        result["operating_disposition"] = "PERMITTED"
        result["reason_codes"] = ["POLICY_AND_AUTHORITY_MATCH"]
    result["evidence_refs"] = sorted(
        set([*validated["evidence_refs"], validated["verification_result_ref"]])
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        document = load_strict(args.input, require_object=True)
    except (OSError, StrictJSONError) as exc:
        document = None
        result = _base_result(document)
        result["reason_codes"] = ["BRIDGE_INPUT_INVALID"]
        result["input_error"] = str(exc)
    else:
        result = evaluate(document)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["operating_disposition"] in {
        "PERMITTED",
        "PERMITTED_WITH_CONDITIONS",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
