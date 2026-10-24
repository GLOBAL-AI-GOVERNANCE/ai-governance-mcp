#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reference validator for the implemented Agentic AI Governance Alpha.1 subset."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.binding_verification import verify_passport_bindings
from tools.reference_policy import (
    CURRENT_FRAMEWORK_ID,
    CURRENT_FRAMEWORK_VERSION,
    CURRENT_PROFILE_VERSION,
    CURRENT_SCHEMA_VERSION,
)
from tools.revocation_state import RevocationStateError, apply_revocation_state
from tools.crypto import trusted_key_errors, verify_jws
from tools.semantic_rules import (
    SUPPORTED_CRITICAL_EXTENSIONS,
    parse_time,
    validate_action_authority_semantics,
    validate_agent_inventory_semantics,
    validate_assessment_semantics,
    validate_bundle_semantics,
    validate_data_authority_semantics,
    validate_mcp_inventory_semantics,
    validate_passport_semantics,
    validate_profile_descriptor_semantics,
    validate_revocation_semantics,
    validate_tool_inventory_semantics,
    validate_verification_semantics,
)
from tools.strict_json import StrictJSONError, load_strict
from tools.verify_repository import id_errors, registry, validate_value_schema


KINDS = {
    "bundle": ("bundle-manifest.schema.json", validate_bundle_semantics),
    "passport": ("agent-trust-passport.schema.json", validate_passport_semantics),
    "assessment": ("assessment-result.schema.json", validate_assessment_semantics),
    "verification": ("verification-result.schema.json", validate_verification_semantics),
    "revocation": ("revocation-list.schema.json", validate_revocation_semantics),
    "action-authority": ("action-authority.schema.json", validate_action_authority_semantics),
    "data-authority": ("data-authority-evidence.schema.json", validate_data_authority_semantics),
    "agent-inventory": ("agent-inventory.schema.json", validate_agent_inventory_semantics),
    "mcp-inventory": ("mcp-inventory.schema.json", validate_mcp_inventory_semantics),
    "tool-inventory": ("tool-inventory.schema.json", validate_tool_inventory_semantics),
    "profile-descriptor": ("control-profile-descriptor.schema.json", validate_profile_descriptor_semantics),
    "trusted-key": ("trusted-key.schema.json", lambda _: []),
}
ID_KIND = {
    "bundle": "bundle",
    "passport": "passport",
    "assessment": "assessment",
    "revocation": "revocation",
}
CHECK_NAMES = (
    "parsing",
    "version",
    "schema",
    "semantics",
    "identifier",
    "critical_extensions",
    "signature",
    "signing_key_trust",
    "bindings",
    "validity",
    "revocation",
)


def _error(code: str, message: str, stage: str) -> dict[str, str]:
    return {"code": code, "stage": stage, "message": message}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _timestamp(value: str | None) -> datetime:
    if value is None:
        return _now_utc()
    return parse_time(value)


def _issuer_for(kind: str, value: dict[str, Any]) -> str | None:
    if kind == "passport":
        issuer = value.get("issuer")
        return issuer.get("issuer_id") if isinstance(issuer, dict) else None
    if kind == "revocation":
        return value.get("issuer_id")
    return None


def _version_errors(kind: str, value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if "schema_version" in value and value.get("schema_version") != CURRENT_SCHEMA_VERSION:
        errors.append(
            f"unsupported schema_version {value.get('schema_version')!r}; supported value is {CURRENT_SCHEMA_VERSION!r}"
        )
    if kind == "passport":
        framework = value.get("framework")
        profile = value.get("profile")
        if isinstance(framework, dict):
            if framework.get("id") != CURRENT_FRAMEWORK_ID:
                errors.append(f"unsupported framework id {framework.get('id')!r}")
            if framework.get("version") != CURRENT_FRAMEWORK_VERSION:
                errors.append(
                    f"unsupported framework version {framework.get('version')!r}; supported value is {CURRENT_FRAMEWORK_VERSION!r}"
                )
        if isinstance(profile, dict) and profile.get("version") != CURRENT_PROFILE_VERSION:
            errors.append(
                f"unsupported profile version {profile.get('version')!r}; supported value is {CURRENT_PROFILE_VERSION!r}"
            )
    return errors


def _artifact_validity(kind: str, value: dict[str, Any], at_time: datetime) -> tuple[str, str | None]:
    if kind == "passport":
        validity = value["validity"]
        not_before = parse_time(validity["not_before"])
        expires_at = parse_time(validity["expires_at"])
        if at_time < not_before:
            return "FAIL", "NOT_YET_VALID"
        if at_time >= expires_at:
            return "FAIL", "EXPIRED"
        return "PASS", None
    if kind == "revocation":
        issued_at = parse_time(value["issued_at"])
        next_update = parse_time(value["next_update"])
        if at_time < issued_at:
            return "FAIL", "NOT_YET_VALID"
        if at_time >= next_update:
            return "FAIL", "EXPIRED"
        return "PASS", None
    return "NOT_APPLICABLE", None


def _load_key(path: Path, store: Any) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        key = load_strict(path, require_object=True)
    except StrictJSONError as exc:
        return None, [_error("INVALID_TRUSTED_KEY_JSON", str(exc), "signing_key_trust")]
    errors = [
        _error("TRUSTED_KEY_SCHEMA", message, "signing_key_trust")
        for message in validate_value_schema(ROOT, "trusted-key.schema.json", key, store)
    ]
    return key, errors


def _evaluate_revocation(
    path: Path,
    *,
    passport: dict[str, Any],
    key: dict[str, Any],
    at_time: datetime,
    store: Any,
) -> tuple[str, list[dict[str, str]], bool, dict[str, Any] | None]:
    errors: list[dict[str, str]] = []
    try:
        revocation = load_strict(path, require_object=True)
    except StrictJSONError as exc:
        return "FAIL", [_error("INVALID_REVOCATION_JSON", str(exc), "revocation")], False, None

    for message in validate_value_schema(ROOT, "revocation-list.schema.json", revocation, store):
        errors.append(_error("REVOCATION_SCHEMA", message, "revocation"))
    if errors:
        return "FAIL", errors, False, None

    for message in validate_revocation_semantics(revocation):
        errors.append(_error("REVOCATION_SEMANTICS", message, "revocation"))
    for message in id_errors("revocation", revocation):
        errors.append(_error("REVOCATION_IDENTIFIER", message, "revocation"))

    issuer = passport["issuer"]["issuer_id"]
    if revocation.get("issuer_id") != issuer:
        errors.append(
            _error(
                "REVOCATION_ISSUER_MISMATCH",
                "revocation-list issuer does not match passport issuer",
                "revocation",
            )
        )

    for message in verify_jws(
        revocation,
        key,
        typ="atp-revocation+jws",
        cty="application/agent-revocation-list+json",
    ):
        errors.append(_error("REVOCATION_SIGNATURE", message, "revocation"))

    try:
        issued_at = parse_time(revocation["issued_at"])
        next_update = parse_time(revocation["next_update"])
        if at_time < issued_at:
            errors.append(
                _error(
                    "REVOCATION_LIST_NOT_YET_VALID",
                    "revocation list is not yet valid",
                    "revocation",
                )
            )
        if at_time >= next_update:
            errors.append(
                _error(
                    "REVOCATION_LIST_EXPIRED",
                    "revocation list is stale at the evaluation time",
                    "revocation",
                )
            )
    except Exception as exc:
        errors.append(_error("REVOCATION_TIME", str(exc), "revocation"))

    if errors:
        return "FAIL", errors, False, None

    passport_id = passport["passport_id"]
    revoked = any(entry.get("passport_id") == passport_id for entry in revocation.get("entries", []))
    return ("REVOKED" if revoked else "PASS"), [], revoked, revocation


def _artifact_validation_status(checks: dict[str, str]) -> str:
    core_names = (
        "parsing",
        "version",
        "schema",
        "semantics",
        "identifier",
        "critical_extensions",
        "bindings",
    )
    core = tuple(checks[name] for name in core_names)
    if any(value == "FAIL" for value in core):
        return "FAIL"
    if all(value in {"PASS", "NOT_APPLICABLE"} for value in core):
        return "PASS"
    return "INCOMPLETE"


def _issued_assessment_result(kind: str, value: dict[str, Any] | None) -> str | None:
    if not isinstance(value, dict):
        return None
    if kind == "passport":
        issued = value.get("issued_assessment")
        return issued.get("result") if isinstance(issued, dict) else None
    if kind == "assessment":
        result = value.get("result")
        return result if isinstance(result, str) else None
    if kind == "verification":
        result = value.get("issued_assessment_result")
        return result if isinstance(result, str) else None
    return None


def _key_failure_primary(errors: list[dict[str, str]]) -> str:
    messages = " ".join(error.get("message", "") for error in errors).lower()
    if "issuer does not match" in messages:
        return "UNTRUSTED_ISSUER"
    if "status is revoked" in messages:
        return "SIGNING_KEY_REVOKED"
    if "status is compromised" in messages:
        return "SIGNING_KEY_COMPROMISED"
    if "status is not_yet_valid" in messages or "not yet valid" in messages:
        return "SIGNING_KEY_NOT_YET_VALID"
    if "status is expired" in messages or "expired at the evaluation time" in messages:
        return "SIGNING_KEY_EXPIRED"
    return "UNKNOWN_SIGNING_KEY"


def _passport_states(
    value: dict[str, Any] | None,
    checks: dict[str, str],
    errors: list[dict[str, str]],
    result_hint: str,
) -> tuple[str | None, str | None, str]:
    issued = _issued_assessment_result("passport", value)
    error_codes = {error.get("code") for error in errors}

    if "INVALID_EVALUATION_TIME" in error_codes:
        return issued, None, "INDETERMINATE"
    if "UNSUPPORTED_VERSION" in error_codes:
        primary = "UNSUPPORTED_VERSION"
    elif "UNSUPPORTED_CRITICAL_EXTENSION" in error_codes:
        primary = "UNSUPPORTED_CRITICAL_EXTENSION"
    elif "BOUND_INPUTS_UNAVAILABLE" in error_codes:
        primary = "BOUND_INPUTS_UNAVAILABLE"
    elif "BOUND_INPUTS_INCOMPLETE" in error_codes:
        primary = "BOUND_INPUTS_INCOMPLETE"
    elif "INPUT_MISMATCH" in error_codes:
        primary = "INPUT_MISMATCH"
    elif "DATA_AUTHORITY_INVALID" in error_codes:
        primary = "DATA_AUTHORITY_INVALID"
    elif "DATA_AUTHORITY_UNKNOWN" in error_codes:
        primary = "DATA_AUTHORITY_UNKNOWN"
    elif "UNSUPPORTED_PROFILE" in error_codes:
        primary = "UNSUPPORTED_PROFILE"
    elif "UNSUPPORTED_EVALUATOR" in error_codes:
        primary = "UNSUPPORTED_EVALUATOR"
    elif "UNSUPPORTED_POLICY" in error_codes:
        primary = "UNSUPPORTED_POLICY"
    elif checks["parsing"] == "FAIL" or checks["schema"] == "FAIL" or checks["semantics"] == "FAIL":
        primary = "INVALID_STRUCTURE"
    elif checks["identifier"] == "FAIL":
        primary = "INVALID_IDENTIFIER"
    elif checks["signature"] == "FAIL":
        primary = "INVALID_SIGNATURE"
    elif checks["signature"] == "NOT_RUN" and isinstance(value, dict) and isinstance(value.get("proof"), dict):
        primary = "UNKNOWN_SIGNING_KEY"
    elif checks["signing_key_trust"] == "FAIL":
        primary = _key_failure_primary(errors)
    elif checks["validity"] == "FAIL" and result_hint in {"NOT_YET_VALID", "EXPIRED"}:
        primary = result_hint
    elif checks["revocation"] == "REVOKED":
        primary = "REVOKED"
    elif checks["revocation"] in {"FAIL", "NOT_RUN"} and isinstance(value, dict) and isinstance(value.get("proof"), dict):
        primary = "REVOCATION_STATUS_UNKNOWN"
    else:
        primary = "VALID"

    if primary != "VALID":
        disposition = "NOT_PERMITTED"
    else:
        attestation = None
        if isinstance(value, dict):
            assurance = value.get("assurance")
            if isinstance(assurance, dict):
                attestation = assurance.get("attestation_status")
        if attestation == "NONE":
            disposition = "INDETERMINATE"
        elif issued == "APPROVED":
            disposition = "PERMITTED"
        elif issued == "APPROVED_WITH_CONDITIONS":
            disposition = "PERMITTED_WITH_CONDITIONS"
        elif issued == "RESTRICTED":
            disposition = "RESTRICTED"
        elif issued == "REJECTED":
            disposition = "NOT_PERMITTED"
        else:
            disposition = "INDETERMINATE"
    return issued, primary, disposition


def _state_fields(
    kind: str,
    artifact: Path,
    checks: dict[str, str],
    errors: list[dict[str, str]],
    result_hint: str,
) -> tuple[str | None, str | None, str | None]:
    try:
        value = load_strict(artifact, require_object=True)
    except StrictJSONError:
        value = None
    if kind == "passport":
        return _passport_states(value, checks, errors, result_hint)
    if kind == "verification" and isinstance(value, dict):
        return (
            _issued_assessment_result(kind, value),
            value.get("primary_status"),
            value.get("operating_disposition"),
        )
    return _issued_assessment_result(kind, value), None, None


def _emit(
    *,
    kind: str,
    artifact: Path,
    at_time: datetime,
    checks: dict[str, str],
    errors: list[dict[str, str]],
    result_hint: str,
    structurally_valid: bool,
    fully_validated: bool,
    limitations: list[str] | None = None,
) -> int:
    issued_result, primary_status, operating_disposition = _state_fields(
        kind, artifact, checks, errors, result_hint
    )
    report = {
        "artifact_type": kind,
        "artifact": str(artifact),
        "evaluated_at": at_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifact_validation_status": _artifact_validation_status(checks),
        "structurally_valid": structurally_valid,
        "fully_validated": fully_validated,
        "valid": fully_validated,
        "issued_assessment_result": issued_result,
        "verification_primary_status": primary_status,
        "operating_disposition": operating_disposition,
        "checks": checks,
        "errors": errors,
        "limitations": limitations or [],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if fully_validated else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate an artifact using the implemented Agentic AI Governance Alpha.1 reference policy."
    )
    parser.add_argument("--kind", required=True, choices=sorted(KINDS))
    parser.add_argument("--trusted-key", type=Path, help="Trusted Ed25519 verification-key JSON.")
    parser.add_argument(
        "--revocation-list",
        type=Path,
        help="Current signed cumulative revocation-list JSON for passport trust validation.",
    )
    parser.add_argument(
        "--revocation-state",
        type=Path,
        help="Explicit trusted local revocation continuity-state JSON for passport validation.",
    )
    parser.add_argument(
        "--initialize-revocation-state",
        action="store_true",
        help="Initialize a missing --revocation-state after all supplied-list trust checks pass.",
    )
    parser.add_argument(
        "--bundle-manifest",
        type=Path,
        help="Canonical bound-input bundle manifest required for passport validation.",
    )
    parser.add_argument(
        "--bundle-root",
        type=Path,
        help="Directory against which bundle-manifest paths are resolved.",
    )
    parser.add_argument(
        "--at-time",
        help="Evaluation time in YYYY-MM-DDTHH:MM:SSZ form. Defaults to current UTC time.",
    )
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()

    if args.initialize_revocation_state and args.revocation_state is None:
        parser.error("--initialize-revocation-state requires --revocation-state")
    if args.revocation_state is not None and (args.kind != "passport" or args.revocation_list is None):
        parser.error("--revocation-state requires passport validation with --revocation-list")

    checks = {name: "NOT_RUN" for name in CHECK_NAMES}
    errors: list[dict[str, str]] = []
    limitations: list[str] = []
    try:
        at_time = _timestamp(args.at_time)
    except Exception as exc:
        at_time = _now_utc()
        checks["parsing"] = "FAIL"
        errors.append(_error("INVALID_EVALUATION_TIME", str(exc), "parsing"))
        return _emit(
            kind=args.kind,
            artifact=args.artifact,
            at_time=at_time,
            checks=checks,
            errors=errors,
            result_hint="INVALID",
            structurally_valid=False,
            fully_validated=False,
        )

    try:
        value = load_strict(args.artifact, require_object=True)
        checks["parsing"] = "PASS"
    except StrictJSONError as exc:
        checks["parsing"] = "FAIL"
        errors.append(_error("INVALID_JSON", str(exc), "parsing"))
        return _emit(
            kind=args.kind,
            artifact=args.artifact,
            at_time=at_time,
            checks=checks,
            errors=errors,
            result_hint="INVALID",
            structurally_valid=False,
            fully_validated=False,
        )

    version_errors = _version_errors(args.kind, value)
    if version_errors:
        checks["version"] = "FAIL"
        errors.extend(_error("UNSUPPORTED_VERSION", message, "version") for message in version_errors)
        return _emit(
            kind=args.kind,
            artifact=args.artifact,
            at_time=at_time,
            checks=checks,
            errors=errors,
            result_hint="UNSUPPORTED_VERSION",
            structurally_valid=False,
            fully_validated=False,
        )
    checks["version"] = "PASS"

    try:
        store = registry(ROOT)
        schema_name, semantic = KINDS[args.kind]
        schema_errors = validate_value_schema(ROOT, schema_name, value, store)
    except Exception as exc:
        checks["schema"] = "FAIL"
        errors.append(
            _error(
                "VALIDATOR_INTERNAL_ERROR",
                f"schema validation failed safely: {exc}",
                "schema",
            )
        )
        return _emit(
            kind=args.kind,
            artifact=args.artifact,
            at_time=at_time,
            checks=checks,
            errors=errors,
            result_hint="INVALID",
            structurally_valid=False,
            fully_validated=False,
        )

    if schema_errors:
        checks["schema"] = "FAIL"
        errors.extend(_error("SCHEMA_VALIDATION", message, "schema") for message in schema_errors)
        return _emit(
            kind=args.kind,
            artifact=args.artifact,
            at_time=at_time,
            checks=checks,
            errors=errors,
            result_hint="INVALID",
            structurally_valid=False,
            fully_validated=False,
        )
    checks["schema"] = "PASS"

    try:
        semantic_errors = semantic(value)
    except Exception as exc:
        semantic_errors = [f"semantic validation failed safely: {exc}"]
    if semantic_errors:
        checks["semantics"] = "FAIL"
        errors.extend(_error("SEMANTIC_VALIDATION", message, "semantics") for message in semantic_errors)
        return _emit(
            kind=args.kind,
            artifact=args.artifact,
            at_time=at_time,
            checks=checks,
            errors=errors,
            result_hint="INVALID",
            structurally_valid=False,
            fully_validated=False,
        )
    checks["semantics"] = "PASS"

    identifier_kind = ID_KIND.get(args.kind)
    if identifier_kind:
        identifier_errors = id_errors(identifier_kind, value)
        if identifier_errors:
            checks["identifier"] = "FAIL"
            errors.extend(_error("IDENTIFIER_MISMATCH", message, "identifier") for message in identifier_errors)
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint="INVALID",
                structurally_valid=False,
                fully_validated=False,
            )
        checks["identifier"] = "PASS"
    else:
        checks["identifier"] = "NOT_APPLICABLE"

    if args.kind == "passport":
        unsupported = sorted(set(value.get("critical_extensions", [])) - SUPPORTED_CRITICAL_EXTENSIONS)
        if unsupported:
            checks["critical_extensions"] = "FAIL"
            errors.extend(
                _error(
                    "UNSUPPORTED_CRITICAL_EXTENSION",
                    f"unsupported critical extension: {name}",
                    "critical_extensions",
                )
                for name in unsupported
            )
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint="UNSUPPORTED_CRITICAL_EXTENSION",
                structurally_valid=True,
                fully_validated=False,
            )
        checks["critical_extensions"] = "PASS"
    else:
        checks["critical_extensions"] = "NOT_APPLICABLE"

    structurally_valid = True

    if args.kind == "trusted-key":
        checks["signature"] = "NOT_APPLICABLE"
        checks["bindings"] = "NOT_APPLICABLE"
        checks["revocation"] = "NOT_APPLICABLE"
        trust_errors = trusted_key_errors(value, expected_issuer=None, at_time=at_time)
        if trust_errors:
            checks["signing_key_trust"] = "FAIL"
            checks["validity"] = "FAIL"
            errors.extend(
                _error("SIGNING_KEY_TRUST", message, "signing_key_trust")
                for message in trust_errors
            )
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint="INVALID",
                structurally_valid=True,
                fully_validated=False,
            )
        checks["signing_key_trust"] = "PASS"
        checks["validity"] = "PASS"
        return _emit(
            kind=args.kind,
            artifact=args.artifact,
            at_time=at_time,
            checks=checks,
            errors=[],
            result_hint="VALID",
            structurally_valid=True,
            fully_validated=True,
        )

    proof_present = isinstance(value.get("proof"), dict)
    if args.kind in {"passport", "revocation"} and proof_present:
        if args.trusted_key is None:
            checks["signature"] = "NOT_RUN"
            checks["signing_key_trust"] = "NOT_RUN"
            errors.append(
                _error(
                    "TRUSTED_KEY_REQUIRED",
                    "a trusted key is required for a signed artifact",
                    "signature",
                )
            )
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint="INDETERMINATE",
                structurally_valid=True,
                fully_validated=False,
            )

        key, key_load_errors = _load_key(args.trusted_key, store)
        if key_load_errors or key is None:
            checks["signature"] = "NOT_RUN"
            checks["signing_key_trust"] = "FAIL"
            errors.extend(key_load_errors)
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint="INDETERMINATE",
                structurally_valid=True,
                fully_validated=False,
            )

        typ, cty = (
            ("atp+jws", "application/agent-trust-passport+json")
            if args.kind == "passport"
            else ("atp-revocation+jws", "application/agent-revocation-list+json")
        )
        signature_errors = verify_jws(value, key, typ=typ, cty=cty)
        if signature_errors:
            checks["signature"] = "FAIL"
            errors.extend(_error("SIGNATURE_INVALID", message, "signature") for message in signature_errors)
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint="INVALID",
                structurally_valid=True,
                fully_validated=False,
            )
        checks["signature"] = "PASS"

        trust_errors = trusted_key_errors(
            key,
            expected_issuer=_issuer_for(args.kind, value),
            at_time=at_time,
        )
        if trust_errors:
            checks["signing_key_trust"] = "FAIL"
            errors.extend(
                _error("SIGNING_KEY_TRUST", message, "signing_key_trust")
                for message in trust_errors
            )
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint="INDETERMINATE",
                structurally_valid=True,
                fully_validated=False,
            )
        checks["signing_key_trust"] = "PASS"
    else:
        checks["signature"] = "NOT_APPLICABLE"
        checks["signing_key_trust"] = "NOT_APPLICABLE"
        key = None

    if args.kind == "passport":
        if args.bundle_manifest is None or args.bundle_root is None:
            checks["bindings"] = "NOT_RUN"
            errors.append(
                _error(
                    "BOUND_INPUTS_UNAVAILABLE",
                    "passport validation requires --bundle-manifest and --bundle-root",
                    "bindings",
                )
            )
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint="BOUND_INPUTS_UNAVAILABLE",
                structurally_valid=True,
                fully_validated=False,
            )
        binding_status, binding_errors = verify_passport_bindings(
            value,
            manifest_path=args.bundle_manifest,
            bundle_root=args.bundle_root,
            repository_root=ROOT,
            schema_store=store,
            at_time=at_time,
        )
        if binding_status != "PASS":
            checks["bindings"] = "FAIL"
            errors.extend(_error(binding_status, message, "bindings") for message in binding_errors)
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint=binding_status,
                structurally_valid=True,
                fully_validated=False,
            )
        checks["bindings"] = "PASS"
    else:
        checks["bindings"] = "NOT_APPLICABLE"

    if args.kind in {"passport", "revocation"}:
        validity_status, validity_decision = _artifact_validity(args.kind, value, at_time)
        checks["validity"] = validity_status
        if validity_status == "FAIL":
            errors.append(
                _error(
                    "ARTIFACT_VALIDITY",
                    f"artifact is {validity_decision}",
                    "validity",
                )
            )
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint=validity_decision or "INVALID",
                structurally_valid=True,
                fully_validated=False,
            )
    else:
        checks["validity"] = "NOT_APPLICABLE"

    if args.kind == "passport":
        attestation = value["assurance"]["attestation_status"]
        if attestation == "NONE":
            checks["revocation"] = "NOT_APPLICABLE"
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=[],
                result_hint="INDETERMINATE",
                structurally_valid=True,
                fully_validated=False,
                limitations=["Unsigned passports do not establish issuer authentication."],
            )
        if args.revocation_list is None:
            checks["revocation"] = "NOT_RUN"
            errors.append(
                _error(
                    "REVOCATION_LIST_REQUIRED",
                    "a current trusted revocation list is required for a complete signed-passport decision",
                    "revocation",
                )
            )
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint="INDETERMINATE",
                structurally_valid=True,
                fully_validated=False,
            )
        assert key is not None
        revocation_status, revocation_errors, revoked, revocation = _evaluate_revocation(
            args.revocation_list,
            passport=value,
            key=key,
            at_time=at_time,
            store=store,
        )
        checks["revocation"] = revocation_status
        errors.extend(revocation_errors)
        if revocation_errors:
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=errors,
                result_hint="INDETERMINATE",
                structurally_valid=True,
                fully_validated=False,
            )
        if args.revocation_state is not None:
            assert revocation is not None
            try:
                cumulative_revocations = apply_revocation_state(
                    args.revocation_state,
                    revocation,
                    initialize=args.initialize_revocation_state,
                )
            except (RevocationStateError, OSError) as exc:
                checks["revocation"] = "FAIL"
                errors.append(_error("REVOCATION_STATE_UNKNOWN", str(exc), "revocation"))
                return _emit(
                    kind=args.kind,
                    artifact=args.artifact,
                    at_time=at_time,
                    checks=checks,
                    errors=errors,
                    result_hint="INDETERMINATE",
                    structurally_valid=True,
                    fully_validated=False,
                )
            if value["passport_id"] in cumulative_revocations:
                checks["revocation"] = "REVOKED"
                return _emit(
                    kind=args.kind,
                    artifact=args.artifact,
                    at_time=at_time,
                    checks=checks,
                    errors=[],
                    result_hint="REVOKED",
                    structurally_valid=True,
                    fully_validated=False,
                )
            limitations.append(
                "Rollback continuity was evaluated relative to an intact explicitly supplied trusted local store."
            )
        else:
            limitations.append(
                "Revocation was evaluated against the supplied signed list; rollback state is not persisted by this stateless CLI."
            )
        if revoked:
            return _emit(
                kind=args.kind,
                artifact=args.artifact,
                at_time=at_time,
                checks=checks,
                errors=[],
                result_hint="REVOKED",
                structurally_valid=True,
                fully_validated=False,
                limitations=limitations,
            )
        return _emit(
            kind=args.kind,
            artifact=args.artifact,
            at_time=at_time,
            checks=checks,
            errors=[],
            result_hint="VALID",
            structurally_valid=True,
            fully_validated=True,
            limitations=limitations,
        )

    if args.kind == "revocation":
        checks["revocation"] = "NOT_APPLICABLE"
        return _emit(
            kind=args.kind,
            artifact=args.artifact,
            at_time=at_time,
            checks=checks,
            errors=[],
            result_hint="VALID",
            structurally_valid=True,
            fully_validated=True,
        )

    checks["revocation"] = "NOT_APPLICABLE"
    return _emit(
        kind=args.kind,
        artifact=args.artifact,
        at_time=at_time,
        checks=checks,
        errors=[],
        result_hint="VALID",
        structurally_valid=structurally_valid,
        fully_validated=True,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
