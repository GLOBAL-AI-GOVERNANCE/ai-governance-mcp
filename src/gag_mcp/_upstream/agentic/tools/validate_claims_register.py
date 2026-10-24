#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DELIVERY_STATUSES = {"PROPOSED", "DEFINED", "SHIPPED"}
EVIDENCE_STATUSES = {"NOT_YET_ESTABLISHED", "VERIFIED"}
IGNORED_PARTS = {".git", ".pytest_cache", "__pycache__"}
SUPPORTED_REMOTE_EVIDENCE_SCHEMES = {"http", "https", "urn"}


def load_json_compatible_yaml(path: Path) -> Any:
    """Load governance YAML records that use the JSON-compatible YAML 1.2 subset."""
    return json.loads(path.read_text(encoding="utf-8"))


def schema_errors(instance: Any, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [error.message for error in validator.iter_errors(instance)]


def _safe_pattern(pattern: str) -> bool:
    path = Path(pattern)
    return (
        bool(pattern)
        and not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in pattern
    )


def matched_repository_paths(root: Path, patterns: Iterable[str]) -> set[str]:
    """Expand governed repository globs with real recursive-glob semantics."""
    root = root.resolve()
    matched: set[str] = set()
    for pattern in patterns:
        if not _safe_pattern(pattern):
            raise ValueError(f"unsafe repository glob: {pattern!r}")
        for path in root.glob(pattern):
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"repository glob escaped root: {pattern!r}") from exc
            if not resolved.is_file() or any(
                part in IGNORED_PARTS for part in relative.parts
            ):
                continue
            matched.add(relative.as_posix())
    return matched


def _repository_path_error(
    root: Path,
    reference: str,
    *,
    allow_directory: bool,
) -> str | None:
    if not reference or "\\" in reference:
        return "must be a nonempty POSIX-style repository-relative path"
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts:
        return "must remain inside the repository"
    if any(part in IGNORED_PARTS for part in relative.parts):
        return "may not reference ignored or temporary repository state"
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return "escapes the repository"
    if not resolved.exists():
        return "does not exist"
    if allow_directory:
        if not (resolved.is_file() or resolved.is_dir()):
            return "is not a regular file or directory"
    elif not resolved.is_file():
        return "must reference an existing file"
    return None


def _evidence_reference_error(root: Path, reference: str) -> str | None:
    if not reference or any(character.isspace() for character in reference):
        return "must be nonempty and contain no whitespace"
    parsed = urlsplit(reference)
    if parsed.scheme:
        scheme = parsed.scheme.lower()
        if scheme not in SUPPORTED_REMOTE_EVIDENCE_SCHEMES:
            return f"uses unsupported URI scheme {scheme!r}"
        if scheme in {"http", "https"} and not parsed.netloc:
            return "must include a network location"
        if scheme == "urn" and not parsed.path:
            return "must include a URN namespace-specific string"
        return None
    if "#" in reference:
        return "local evidence fragments are not supported in register version 1.0.0"
    if "?" in reference:
        return "local evidence query strings are not supported"
    return _repository_path_error(root, reference, allow_directory=False)


def prohibited_wording_errors(root: Path, prohibited: dict[str, Any]) -> list[str]:
    """Case-insensitive exact-phrase scanning over declared repository paths."""
    errors: list[str] = []
    for rule in prohibited.get("claims", []):
        if rule.get("enforcement") not in {"REPOSITORY_VERIFICATION", "BOTH"}:
            continue
        globs = rule.get("repository_globs", [])
        exclusions = rule.get("repository_exclusions", [])
        phrases = rule.get("prohibited_wording", [])
        try:
            matched = matched_repository_paths(root, globs)
            excluded = matched_repository_paths(root, exclusions)
        except ValueError as exc:
            errors.append(f"{rule.get('claim_id')}: {exc}")
            continue
        for pattern in globs:
            try:
                if not matched_repository_paths(root, [pattern]):
                    errors.append(
                        f"{rule.get('claim_id')}: active repository_glob matched no files: {pattern}"
                    )
            except ValueError as exc:
                errors.append(f"{rule.get('claim_id')}: {exc}")
        for relative_path in sorted(matched - excluded):
            path = root / relative_path
            text = path.read_text(encoding="utf-8", errors="replace").casefold()
            for phrase in phrases:
                if phrase.casefold() in text:
                    errors.append(
                        f"{rule.get('claim_id')}: prohibited wording {phrase!r} "
                        f"found in {relative_path}"
                    )
    return errors


def validate_register(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    claims_path = root / "governance/claims-register.yaml"
    prohibited_path = root / "governance/prohibited-claims.yaml"
    try:
        claims = load_json_compatible_yaml(claims_path)
    except Exception as exc:
        return [f"{claims_path.relative_to(root)}: {exc}"]
    try:
        prohibited = load_json_compatible_yaml(prohibited_path)
    except Exception as exc:
        return [f"{prohibited_path.relative_to(root)}: {exc}"]

    for error in schema_errors(claims, root / "governance/claims-register.schema.json"):
        errors.append(f"governance/claims-register.yaml: {error}")
    for error in schema_errors(prohibited, root / "governance/prohibited-claims.schema.json"):
        errors.append(f"governance/prohibited-claims.yaml: {error}")

    claim_ids = [claim.get("claim_id") for claim in claims.get("claims", [])]
    if len(claim_ids) != len(set(claim_ids)):
        errors.append("governance/claims-register.yaml: duplicate claim_id")
    prohibited_ids = [claim.get("claim_id") for claim in prohibited.get("claims", [])]
    if len(prohibited_ids) != len(set(prohibited_ids)):
        errors.append("governance/prohibited-claims.yaml: duplicate claim_id")

    for claim in claims.get("claims", []):
        claim_id = claim.get("claim_id")
        delivery = claim.get("delivery_status")
        evidence = claim.get("evidence_status")
        if delivery is not None and delivery not in DELIVERY_STATUSES:
            errors.append(f"{claim_id}: unsupported delivery_status {delivery!r}")
        if evidence not in EVIDENCE_STATUSES:
            errors.append(f"{claim_id}: unsupported evidence_status {evidence!r}")
        if claim.get("claim_kind") == "EXTERNAL_FACT" and "delivery_status" in claim:
            errors.append(f"{claim_id}: external facts must omit delivery_status")
        if claim.get("claim_kind") != "EXTERNAL_FACT" and "delivery_status" not in claim:
            errors.append(f"{claim_id}: project claims require delivery_status")
        if evidence == "VERIFIED":
            if not claim.get("verification_method"):
                errors.append(f"{claim_id}: VERIFIED claims require verification_method")
            if not claim.get("last_verified"):
                errors.append(f"{claim_id}: VERIFIED claims require last_verified")
            if not claim.get("evidence_refs"):
                errors.append(f"{claim_id}: VERIFIED claims require evidence_refs")
        if claim.get("claim_kind") != "EXTERNAL_FACT" and not claim.get("supporting_artifacts"):
            errors.append(f"{claim_id}: project claims require supporting_artifacts")

        for artifact in claim.get("supporting_artifacts", []):
            error = _repository_path_error(root, artifact, allow_directory=True)
            if error:
                errors.append(f"{claim_id}: supporting_artifact {artifact!r} {error}")
        for reference in claim.get("evidence_refs", []):
            error = _evidence_reference_error(root, reference)
            if error:
                errors.append(f"{claim_id}: evidence_ref {reference!r} {error}")

    errors.extend(prohibited_wording_errors(root, prohibited))
    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT).resolve()
    errors = validate_register(root)
    if errors:
        print("CLAIMS REGISTER FAILED")
        for error in errors:
            print("-", error)
        return 1
    claims = load_json_compatible_yaml(root / "governance/claims-register.yaml")
    prohibited = load_json_compatible_yaml(root / "governance/prohibited-claims.yaml")
    print("CLAIMS REGISTER PASSED")
    print("claims:", len(claims["claims"]))
    print("prohibited claims:", len(prohibited["claims"]))
    print("repository phrase scanning: active")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
