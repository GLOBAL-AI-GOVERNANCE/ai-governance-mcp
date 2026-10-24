#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry

from tools.canonical_json import canonicalize
from tools.crypto import trusted_key_errors, verify_jws
from tools.schema_catalog import catalog_schema_paths, full_registry
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
    validate_protected_header,
    validate_revocation_semantics,
    validate_tool_inventory_semantics,
    validate_verification_semantics,
)
from tools.strict_json import StrictJSONError, load_strict
from tools.validate_claims_register import validate_register
from tools.public_release_scrub import canonical_identity_errors

PUBLIC_SAFETY_PATTERNS = {
    "private-key material": r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    "AWS access-key identifier": r"AKIA[0-9A-Z]{16}",
    "AWS signed-request credential": r"(?:X-Amz-Credential|AWSAccessKeyId)=",
    "AWS signed-request signature": r"X-Amz-" r"Signature=",
    "GitHub token-shaped secret": r"gh[pousr]_[A-Za-z0-9]{20,}",
}

SCHEMA_BY_KIND = {
    "bundle": "bundle-manifest.schema.json",
    "passport": "agent-trust-passport.schema.json",
    "assessment": "assessment-result.schema.json",
    "verification": "verification-result.schema.json",
    "revocation": "revocation-list.schema.json",
    "action": "action-authority.schema.json",
    "data-authority": "data-authority-evidence.schema.json",
    "agent-inventory": "agent-inventory.schema.json",
    "mcp-inventory": "mcp-inventory.schema.json",
    "tool-inventory": "tool-inventory.schema.json",
    "profile-descriptor": "control-profile-descriptor.schema.json",
    "trusted-key": "trusted-key.schema.json",
}

SEMANTIC_BY_KIND = {
    "bundle": validate_bundle_semantics,
    "passport": validate_passport_semantics,
    "assessment": validate_assessment_semantics,
    "verification": validate_verification_semantics,
    "revocation": validate_revocation_semantics,
    "action": validate_action_authority_semantics,
    "data-authority": validate_data_authority_semantics,
    "agent-inventory": validate_agent_inventory_semantics,
    "mcp-inventory": validate_mcp_inventory_semantics,
    "tool-inventory": validate_tool_inventory_semantics,
    "profile-descriptor": validate_profile_descriptor_semantics,
}

REQUIRED_PATHS = [
    "README.md",
    "CONFORMANCE.md",
    "LICENSE",
    "LICENSE_POLICY.md",
    "SECURITY.md",
    "governance/DEVELOPMENT.md",
    "GOVERNANCE.md",
    "ROADMAP.md",
    ".gitignore",
    ".github/CODEOWNERS",
    ".github/workflows/ci.yml",
    "CITATION.cff",
    "governance/PROGRAM_BASELINE.md",
    "governance/VV_POLICY.md",
    "governance/RELEASE_GATE.md",
    "governance/claims-register.yaml",
    "governance/claims-register.schema.json",
    "governance/prohibited-claims.yaml",
    "governance/prohibited-claims.schema.json",
    "requirements/deferred-requirements.md",
    "requirements/deferred-agent-governance-decision-record.md",
    "schemas/schema-catalog.json",
    "schemas/schema-catalog.schema.json",
    "tests/test_claims_register.py",
    "tests/test_public_release_scrub.py",
    "tests/test_schema_catalog.py",
    "tests/test_agent_incident_readiness.py",
    "tests/test_independent_verifier_kit.py",
    "tests/negative/index.json",
    "tools/validate_claims_register.py",
    "tools/public_release_scrub.py",
    "tools/schema_catalog.py",
    "tools/strict_json.py",
    "tools/agent_incident_readiness.py",
    "tools/crypto.py",
    "tools/binding_verification.py",
    "tools/reference_policy.py",
    "examples/quickstart/README.md",
    "examples/agent-incident-readiness/README.md",
    "examples/agent-incident-readiness/synthetic-lifecycle.json",
    "conformance/independent-verifier/README.md",
    "conformance/independent-verifier/manifest.json",
    "conformance/independent-verifier/DISCREPANCY_REPORT.md",
    "conformance/independent-verifier/INDEPENDENT_RECEIPT_TEMPLATE.json",
    "examples/passports/signed-unrevoked.json",
    "examples/inventories/agent.json",
    "examples/inventories/mcp.json",
    "examples/inventories/tools.json",
    "examples/action-authority/readonly-graph.json",
    "profiles/mcp-governance-profile.json",
    "decisions/DR-001-public-stewardship.md",
    "decisions/DR-002-licensing-boundary.md",
    "decisions/DR-003-assurance-boundary.md",
    "decisions/DR-004-decision-state-model.md",
    "decisions/DR-005-release-sequencing.md",
    "decisions/DR-006-continuous-vv-and-program-sequencing.md",
]


def load(path: Path) -> Any:
    return load_strict(path, require_object=path.suffix.lower() == ".json")


def domain_id(domain: str, label: str, value: Any) -> str:
    payload = {"domain": domain, label: value}
    return "sha256:" + hashlib.sha256(canonicalize(payload)).hexdigest()


def registry(root: Path) -> Registry:
    """Backward-compatible schema registry used by the Alpha.1 validator and tests."""
    return full_registry(root)


def validate_value_schema(
    root: Path,
    schema_name: str,
    value: Any,
    store: Registry,
) -> list[str]:
    validator = Draft202012Validator(
        load(root / "schemas" / schema_name),
        registry=store,
        format_checker=FormatChecker(),
    )
    return [error.message for error in validator.iter_errors(value)]


def validate_schema(
    root: Path,
    schema_name: str,
    path: Path,
    store: Registry,
) -> list[str]:
    return validate_value_schema(root, schema_name, load(path), store)


def id_errors(kind: str, value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if kind == "bundle":
        source = {key: item for key, item in value.items() if key != "bundle_id"}
        expected = domain_id(
            "global-ai-governance.agentic-assessment-bundle.identifier.v1",
            "manifest",
            source,
        )
        if value.get("bundle_id") != expected:
            errors.append("bundle_id mismatch")
    elif kind == "assessment":
        source = {key: item for key, item in value.items() if key != "assessment_id"}
        expected = domain_id(
            "global-ai-governance.agentic-assessment.identifier.v1",
            "assessment",
            source,
        )
        if value.get("assessment_id") != expected:
            errors.append("assessment_id mismatch")
    elif kind == "passport":
        source = {
            key: item
            for key, item in value.items()
            if key not in {"passport_id", "proof"}
        }
        expected = domain_id(
            "global-ai-governance.agent-trust-passport.identifier.v1",
            "passport",
            source,
        )
        if value.get("passport_id") != expected:
            errors.append("passport_id mismatch")
    elif kind == "revocation":
        for index, entry in enumerate(value.get("entries", [])):
            source = {
                key: item for key, item in entry.items() if key != "revocation_id"
            }
            expected = domain_id(
                "global-ai-governance.agent-trust-passport.revocation-entry.identifier.v1",
                "entry",
                source,
            )
            if entry.get("revocation_id") != expected:
                errors.append(f"entries[{index}].revocation_id mismatch")
        source = {
            key: item
            for key, item in value.items()
            if key not in {"list_id", "proof"}
        }
        expected = domain_id(
            "global-ai-governance.agent-trust-passport.revocation-list.identifier.v1",
            "list",
            source,
        )
        if value.get("list_id") != expected:
            errors.append("list_id mismatch")
    return errors


def check_required_paths(root: Path) -> list[str]:
    return [f"missing {relative}" for relative in REQUIRED_PATHS if not (root / relative).exists()]


def check_public_safety(root: Path) -> list[str]:
    errors: list[str] = []
    ignored = {".git", "__pycache__", ".pytest_cache"}
    allowed_suffixes = {".md", ".py", ".yml", ".yaml", ".json", ".toml", ".cff"}
    for path in root.rglob("*"):
        if not path.is_file() or any(part in ignored for part in path.parts):
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in PUBLIC_SAFETY_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                errors.append(f"{label} detected in {path.relative_to(root)}")
    if (root / "vv").exists():
        errors.append("internal vv directory must not be public")
    return errors


def check_dependencies(root: Path) -> list[str]:
    requirements = (root / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
    pinned = {
        line.strip()
        for line in requirements
        if line.strip() and not line.startswith("#")
    }
    errors: list[str] = []
    if "pytest==9.0.3" not in pinned:
        errors.append("pytest must be pinned to patched version 9.0.3")
    if any(line.lower().startswith("pyyaml") for line in pinned):
        errors.append("unused PyYAML dependency must not be present")
    return errors


def check_hosting_files(root: Path) -> list[str]:
    errors: list[str] = []
    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for action in re.findall(r"uses:\s*([^\s#]+)", ci):
        if "@" not in action or not re.fullmatch(r"[0-9a-f]{40}", action.split("@", 1)[1]):
            errors.append(f"GitHub Action is not pinned to a full SHA: {action}")
    if "persist-credentials: false" not in ci:
        errors.append("checkout must set persist-credentials: false")
    if "timeout-minutes:" not in ci:
        errors.append("CI job must set timeout-minutes")

    codeowners = (root / ".github/CODEOWNERS").read_text(encoding="utf-8")
    if "@GLOBAL-AI-GOVERNANCE/maintainers" in codeowners:
        errors.append("CODEOWNERS must not reference a nonexistent organization team")
    if "@GLOBAL-AI-GOVERNANCE" not in codeowners:
        errors.append("CODEOWNERS must reference the repository-owning account")
    return errors


def check_project_metadata(root: Path) -> list[str]:
    errors: list[str] = []
    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    if not all(marker in citation for marker in ["Apache-2.0", "CC-BY-4.0", "file-scoped"]):
        errors.append("CITATION.cff must disclose the file-scoped mixed-license policy")
    roadmap = (root / "ROADMAP.md").read_text(encoding="utf-8")
    for marker in [
        "Stateful Revocation",
        "OPA Enforcement Bridge",
        "Agent Governance Decision Record Profile",
        "Infrastructure Trust Profile",
    ]:
        if marker not in roadmap:
            errors.append(f"ROADMAP.md missing locked sequence marker: {marker}")
    decisions_readme = (root / "decisions/README.md").read_text(encoding="utf-8")
    if "DR-006-continuous-vv-and-program-sequencing.md" not in decisions_readme:
        errors.append("decisions/README.md must reference DR-006")
    return errors


def validate_positive_examples(root: Path, store: Registry) -> list[str]:
    errors: list[str] = []
    valid = [
        ("bundle", "examples/bundles/valid-bundle-manifest.json"),
        ("passport", "examples/passports/unsigned-valid.json"),
        ("passport", "examples/passports/signed-revoked.json"),
        ("passport", "examples/passports/signed-unrevoked.json"),
        ("trusted-key", "examples/trusted-keys/test-ed25519-key.json"),
        ("revocation", "examples/revocation/valid-revocation-list.json"),
        ("verification", "examples/verification/unsigned-valid-result.json"),
        ("verification", "examples/verification/signed-valid-result.json"),
        ("assessment", "examples/assessments/approved-readonly.json"),
        ("action", "examples/action-authority/readonly-graph.json"),
        ("data-authority", "examples/data-authority/synthetic-evidence.json"),
        ("agent-inventory", "examples/inventories/agent.json"),
        ("mcp-inventory", "examples/inventories/mcp.json"),
        ("tool-inventory", "examples/inventories/tools.json"),
        ("profile-descriptor", "profiles/mcp-governance-profile.json"),
    ]
    for kind, relative in valid:
        value = load(root / relative)
        for error in validate_schema(root, SCHEMA_BY_KIND[kind], root / relative, store):
            errors.append(f"{relative}: schema: {error}")
        semantic = SEMANTIC_BY_KIND.get(kind)
        if semantic:
            for error in semantic(value):
                errors.append(f"{relative}: semantic: {error}")
        for error in id_errors(kind, value):
            errors.append(f"{relative}: identifier: {error}")
    return errors


def validate_signatures(root: Path) -> list[str]:
    errors: list[str] = []
    key = load(root / "examples/trusted-keys/test-ed25519-key.json")
    signed = [
        (
            "examples/passports/signed-revoked.json",
            "atp+jws",
            "application/agent-trust-passport+json",
        ),
        (
            "examples/revocation/valid-revocation-list.json",
            "atp-revocation+jws",
            "application/agent-revocation-list+json",
        ),
    ]
    for relative, typ, cty in signed:
        for error in verify_jws(load(root / relative), key, typ=typ, cty=cty):
            errors.append(f"{relative}: crypto: {error}")
    return errors


def check_canonicalization() -> list[str]:
    vector = {
        "€": "Euro Sign",
        "\r": "Carriage Return",
        "דּ": "Hebrew Letter Dalet With Dagesh",
        "1": "One",
        "😀": "Emoji: Grinning Face",
        "\u0080": "Control",
        "ö": "Latin Small Letter O With Diaeresis",
    }
    expected = (
        '{"\\r":"Carriage Return","1":"One","\u0080":"Control",'
        '"ö":"Latin Small Letter O With Diaeresis","€":"Euro Sign",'
        '"😀":"Emoji: Grinning Face","דּ":"Hebrew Letter Dalet With Dagesh"}'
    ).encode()
    if canonicalize(vector) != expected:
        return ["RFC 8785 UTF-16 property-order vector mismatch"]
    return []


def validate_negative_fixtures(root: Path, store: Registry) -> tuple[list[str], int]:
    errors: list[str] = []
    key = load(root / "examples/trusted-keys/test-ed25519-key.json")
    index = load(root / "tests/negative/index.json")
    listed = [case["file"] for case in index["cases"]]
    actual = sorted(
        path.name
        for path in (root / "tests/negative").glob("*.json")
        if path.name != "index.json"
    )
    if sorted(listed) != actual:
        errors.append(f"negative index mismatch: listed={len(listed)} actual={len(actual)}")

    for case in index["cases"]:
        relative = "tests/negative/" + case["file"]
        value = load(root / relative)
        rejected: list[str] = []
        validator = case["validator"]
        kind = case["kind"]
        if validator == "artifact":
            schema_kind = "passport" if kind == "timestamp-passport" else kind
            rejected += validate_schema(root, SCHEMA_BY_KIND[schema_kind], root / relative, store)
            semantic = SEMANTIC_BY_KIND.get(schema_kind)
            if semantic:
                rejected += semantic(value)
        elif validator == "semantic":
            rejected += SEMANTIC_BY_KIND[kind](value)
        elif validator == "identifier":
            rejected += id_errors(kind, value)
        elif validator == "protected_header":
            rejected += validate_protected_header(
                value,
                content_type="application/agent-trust-passport+json",
                type_value="atp+jws",
            )
            if value.get("kid") != key.get("kid"):
                rejected.append("protected header kid does not match trusted key")
        elif validator == "critical_extensions":
            unsupported = sorted(
                set(value.get("critical_extensions", [])) - SUPPORTED_CRITICAL_EXTENSIONS
            )
            rejected += [f"unsupported critical extension: {name}" for name in unsupported]
        elif validator == "version":
            if value.get("schema_version") != "0.1.0-alpha.1":
                rejected.append("unsupported schema version")
        elif validator == "trusted_key":
            rejected += trusted_key_errors(
                value,
                expected_issuer=None,
                at_time=parse_time("2026-07-18T12:00:00Z"),
            )
        if not rejected:
            errors.append(f"negative accepted: {relative}")
    return errors, len(index["cases"])


def validate_strict_json_fixtures(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in [
        "malformed.json",
        "duplicate-key.json",
        "nonfinite.json",
        "unsafe-integer.json",
        "top-level-list.json",
        "invalid-utf8.bin",
    ]:
        try:
            load_strict(root / "tests/cli-negative" / relative, require_object=True)
        except StrictJSONError:
            continue
        errors.append(f"strict JSON fixture accepted: tests/cli-negative/{relative}")
    return errors


def validate_end_user_cli(root: Path) -> list[str]:
    command = [
        sys.executable,
        str(root / "tools/validate_artifact.py"),
        "--kind",
        "passport",
        "--trusted-key",
        str(root / "examples/trusted-keys/test-ed25519-key.json"),
        "--revocation-list",
        str(root / "examples/revocation/valid-revocation-list.json"),
        "--bundle-manifest",
        str(root / "examples/bundles/valid-bundle-manifest.json"),
        "--bundle-root",
        str(root),
        "--at-time",
        "2026-07-18T12:00:00Z",
        str(root / "examples/passports/signed-unrevoked.json"),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        return ["end-user signed-passport validation did not produce VALID"]
    try:
        report = json.loads(result.stdout)
    except Exception as exc:
        return [f"end-user validator output is not JSON: {exc}"]
    expected = (
        report.get("fully_validated")
        and report.get("issued_assessment_result") == "APPROVED"
        and report.get("verification_primary_status") == "VALID"
        and report.get("operating_disposition") == "PERMITTED"
        and "decision" not in report
    )
    if not expected:
        return [
            "end-user validator did not preserve the three-layer "
            "APPROVED / VALID / PERMITTED result"
        ]
    return []


def check_generated_distribution(root: Path) -> list[str]:
    result = subprocess.run(
        [sys.executable, str(root / "tools/build_dist.py"), "--check", str(root)],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return [result.stdout.strip() or result.stderr.strip()]
    return []


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    errors: list[str] = []
    errors.extend(check_required_paths(root))
    errors.extend(check_public_safety(root))
    errors.extend(check_dependencies(root))
    errors.extend(check_hosting_files(root))
    errors.extend(check_project_metadata(root))

    schema_ready = False
    schema_paths: list[Path] = []
    store = Registry()
    try:
        schema_paths = catalog_schema_paths(root)
        store = full_registry(root)
        schema_ready = True
    except Exception as exc:
        errors.append(f"schema catalog: {exc}")

    errors.extend(validate_register(root))
    errors.extend(canonical_identity_errors(root))
    if schema_ready:
        errors.extend(validate_positive_examples(root, store))
    errors.extend(validate_signatures(root))
    errors.extend(check_canonicalization())
    negative_count = 0
    if schema_ready:
        negative_errors, negative_count = validate_negative_fixtures(root, store)
        errors.extend(negative_errors)
    errors.extend(validate_strict_json_fixtures(root))
    if schema_ready:
        errors.extend(validate_end_user_cli(root))
    errors.extend(check_generated_distribution(root))

    if errors:
        print("CONFORMANCE FAILED")
        for error in errors:
            print("-", error)
        return 1

    print("CONFORMANCE PASSED")
    print("schemas:", len(schema_paths))
    print("negative fixtures:", negative_count)
    print("repository invariants: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
