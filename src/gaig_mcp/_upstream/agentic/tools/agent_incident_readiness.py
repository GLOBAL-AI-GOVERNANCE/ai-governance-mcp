#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate the deterministic, synthetic Agent Incident Readiness trace.

This reference orchestrator consumes existing canonical validation-result,
OPA-bridge, and Stateful Revocation semantics. It performs no external action.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.opa_bridge import evaluate
from tools.strict_json import StrictJSONError, load_strict


TRACE_VERSION = "1.0.0-unreleased"
HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
TOP_KEYS = {
    "trace_version", "scenario", "synthetic", "external_enforcement",
    "human_authority", "passports", "revocation_continuity", "events",
    "non_claims",
}
EVENT_KEYS = {
    "state", "at", "decision", "consequence", "remaining_risk",
    "next_action", "timeline", "technical_evidence", "bridge_input",
}
STATES = [
    "AUTHORIZED", "POLICY_DENIED", "REVOKED", "ROLLBACK_REJECTED",
    "NEW_PASSPORT_REAUTHORIZED",
]
FORBIDDEN_CLAIMS = {
    "external enforcement", "runtime containment", "production iam",
}


def _fail(code: str, detail: str) -> dict[str, Any]:
    return {
        "trace_result_version": "1.0.0",
        "scenario": "Agent Incident Readiness",
        "status": "NOT_VERIFIED",
        "reason_codes": [code],
        "detail": detail,
        "synthetic": True,
        "external_enforcement": "NOT_PERFORMED",
    }


def verify_trace(trace: object) -> dict[str, Any]:
    if not isinstance(trace, dict) or set(trace) != TOP_KEYS:
        return _fail("MALFORMED_LIFECYCLE_EVIDENCE", "top-level contract mismatch")
    if trace.get("trace_version") != TRACE_VERSION:
        return _fail("LIFECYCLE_VERSION_UNSUPPORTED", "unsupported trace version")
    if trace.get("scenario") != "Agent Incident Readiness" or trace.get("synthetic") is not True:
        return _fail("SYNTHETIC_BOUNDARY_INVALID", "scenario must be explicitly synthetic")
    if trace.get("external_enforcement") != "NOT_PERFORMED":
        return _fail("EXTERNAL_ENFORCEMENT_CLAIM_UNSUPPORTED", "OPA decisions are non-enforcing")

    authority = trace.get("human_authority")
    if not isinstance(authority, dict) or set(authority) != {"authority_id", "approval_ref", "attribution_verified"}:
        return _fail("HUMAN_AUTHORITY_INVALID", "human authority evidence is malformed")
    if not all(isinstance(authority.get(k), str) and authority[k] for k in ("authority_id", "approval_ref")):
        return _fail("HUMAN_AUTHORITY_INVALID", "human authority is absent")
    if authority.get("attribution_verified") is not True or not HASH.fullmatch(authority["approval_ref"]):
        return _fail("APPROVAL_UNATTRIBUTED", "approval attribution is not established")

    passports = trace.get("passports")
    if not isinstance(passports, dict) or set(passports) != {"revoked", "replacement"}:
        return _fail("PASSPORT_EVIDENCE_INVALID", "passport evidence is malformed")
    old = passports.get("revoked")
    new = passports.get("replacement")
    required_passport = {"passport_id", "source_artifact", "trust", "signature", "binding", "authority_actions", "authority_resources"}
    if not isinstance(old, dict) or not isinstance(new, dict) or set(old) != required_passport or set(new) != required_passport:
        return _fail("PASSPORT_EVIDENCE_INVALID", "passport contract mismatch")
    if not HASH.fullmatch(str(old.get("passport_id", ""))) or not HASH.fullmatch(str(new.get("passport_id", ""))):
        return _fail("PASSPORT_EVIDENCE_INVALID", "passport identifier is invalid")
    if old["passport_id"] == new["passport_id"]:
        return _fail("NEW_PASSPORT_REQUIRED", "reauthorization cannot restore the revoked passport")
    for label, passport in (("revoked", old), ("replacement", new)):
        if not isinstance(passport.get("source_artifact"), str) or not passport["source_artifact"].startswith("examples/passports/"):
            return _fail("PASSPORT_EVIDENCE_INVALID", f"{label} passport artifact reference is invalid")
        if passport.get("trust") != "VALIDATED" or passport.get("signature") != "VALID" or passport.get("binding") != "VALID":
            return _fail("PASSPORT_VALIDATION_INVALID", f"{label} passport trust/signature/binding is invalid")
        if not isinstance(passport.get("authority_actions"), list) or not isinstance(passport.get("authority_resources"), list):
            return _fail("PASSPORT_AUTHORITY_INVALID", f"{label} passport authority is malformed")

    continuity = trace.get("revocation_continuity")
    required_continuity = {
        "authority", "trusted_sequence", "trusted_list_id", "previous_list_id",
        "revoked_passport_ids", "rollback_attempt_sequence", "rollback_result",
        "same_sequence_conflict_result", "current_evidence",
    }
    if not isinstance(continuity, dict) or set(continuity) != required_continuity:
        return _fail("REVOCATION_EVIDENCE_UNKNOWN", "current revocation evidence is absent or malformed")
    if continuity.get("current_evidence") != "TRUSTED" or continuity.get("trusted_sequence") != 2:
        return _fail("REVOCATION_EVIDENCE_UNKNOWN", "trusted current revocation state is not established")
    if continuity.get("rollback_attempt_sequence") >= continuity["trusted_sequence"] or continuity.get("rollback_result") != "REJECTED":
        return _fail("ROLLBACK_NOT_REJECTED", "older revocation state was not rejected")
    if continuity.get("same_sequence_conflict_result") != "REJECTED":
        return _fail("REVOCATION_SEQUENCE_CONFLICT", "same-sequence conflict was not rejected")
    revoked_ids = continuity.get("revoked_passport_ids")
    if not isinstance(revoked_ids, list) or old["passport_id"] not in revoked_ids:
        return _fail("REVOKED_PASSPORT_RESTORED", "revoked passport is not terminally retained")
    if new["passport_id"] in revoked_ids:
        return _fail("NEW_PASSPORT_REVOKED", "replacement passport is revoked")

    events = trace.get("events")
    if not isinstance(events, list) or [event.get("state") for event in events if isinstance(event, dict)] != STATES:
        return _fail("LIFECYCLE_SEQUENCE_INVALID", "required lifecycle order is not exact")
    decisions: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict) or set(event) != EVENT_KEYS:
            return _fail("MALFORMED_LIFECYCLE_EVIDENCE", "event contract mismatch")
        for key in ("at", "decision", "consequence", "remaining_risk", "next_action", "timeline", "technical_evidence"):
            if not isinstance(event.get(key), str) or not event[key]:
                return _fail("MALFORMED_LIFECYCLE_EVIDENCE", f"event {key} is missing")
        bridge_input = event.get("bridge_input")
        if event["state"] in {"AUTHORIZED", "POLICY_DENIED", "REVOKED", "NEW_PASSPORT_REAUTHORIZED"}:
            if not isinstance(bridge_input, dict):
                return _fail("MALFORMED_LIFECYCLE_EVIDENCE", "bridge input is required")
            decision = evaluate(bridge_input)
            decisions.append(decision)
        elif bridge_input is not None:
            return _fail("MALFORMED_LIFECYCLE_EVIDENCE", "rollback event cannot claim a policy decision")

    by_state = dict(zip([state for state in STATES if state != "ROLLBACK_REJECTED"], decisions))
    if by_state["AUTHORIZED"]["operating_disposition"] != "PERMITTED":
        return _fail("AUTHORIZED_REQUEST_REJECTED", "initial request is not authorized")
    denied = by_state["POLICY_DENIED"]
    if denied["reason_codes"] != ["POLICY_DENIED"] or denied["operating_disposition"] != "NOT_PERMITTED":
        return _fail("POLICY_DENIAL_INVALID", "bounded policy denial is not demonstrated")
    if "REVOCATION_NOT_CURRENT" in denied["reason_codes"]:
        return _fail("POLICY_DENIAL_MUTATED_REVOCATION", "policy denial was treated as revocation")
    revoked = by_state["REVOKED"]
    if "REVOCATION_NOT_CURRENT" not in revoked["reason_codes"]:
        return _fail("REVOKED_USE_NOT_REJECTED", "revoked passport use did not fail closed")
    reauthorized = by_state["NEW_PASSPORT_REAUTHORIZED"]
    if reauthorized["operating_disposition"] != "PERMITTED":
        return _fail("NEW_PASSPORT_NOT_AUTHORIZED", "new passport is not authorized")

    requested = events[-1]["bridge_input"]["request"]
    if requested["action"] not in new["authority_actions"]:
        return _fail("ACTION_OUTSIDE_NEW_PASSPORT_AUTHORITY", "new passport lacks action authority")
    if requested["resource"] not in new["authority_resources"]:
        return _fail("RESOURCE_OUTSIDE_NEW_PASSPORT_AUTHORITY", "new passport lacks resource authority")
    if events[-1]["bridge_input"]["validated_result"]["passport_id"] != new["passport_id"]:
        return _fail("NEW_PASSPORT_REQUIRED", "reauthorization did not use the replacement passport")
    if events[0]["bridge_input"]["validated_result"]["passport_id"] != old["passport_id"]:
        return _fail("PASSPORT_BINDING_INVALID", "initial authorization does not bind the original passport")

    non_claims = trace.get("non_claims")
    if not isinstance(non_claims, list) or not FORBIDDEN_CLAIMS.issubset({str(v).lower() for v in non_claims}):
        return _fail("NON_CLAIMS_INCOMPLETE", "required assurance limitations are absent")

    return {
        "trace_result_version": "1.0.0",
        "scenario": trace["scenario"],
        "status": "VERIFIED",
        "states": STATES,
        "reason_codes": ["SYNTHETIC_LIFECYCLE_VERIFIED"],
        "revoked_passport_id": old["passport_id"],
        "replacement_passport_id": new["passport_id"],
        "revoked_passport_remains_revoked": True,
        "synthetic": True,
        "external_enforcement": "NOT_PERFORMED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args(argv)
    try:
        trace = load_strict(args.trace, require_object=True)
    except (OSError, StrictJSONError) as exc:
        result = _fail("MALFORMED_LIFECYCLE_EVIDENCE", str(exc))
    else:
        result = verify_trace(trace)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
