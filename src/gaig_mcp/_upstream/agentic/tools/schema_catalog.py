#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from tools.strict_json import load_strict

CATALOG_PATH = Path("schemas/schema-catalog.json")
CATALOG_SCHEMA_PATH = Path("schemas/schema-catalog.schema.json")

# These schema identities and raw-file digests existed when the final GOVERN
# baseline was established. They prevent a released identifier from silently
# serving different content. A later versioned governance decision may add a new
# schema identity, but ordinary catalog edits cannot weaken this baseline.
PROTECTED_SCHEMA_METADATA: dict[str, tuple[str, str]] = {
    "governance/claims-register.schema.json": (
        "urn:global-ai-governance:agentic-ai-governance:schema:claims-register:1.0.0",
        "5bfa2d97b4351c185cfc84074454d1199b0e77e0cdda0dc36d456247c8718be9",
    ),
    "governance/prohibited-claims.schema.json": (
        "urn:global-ai-governance:agentic-ai-governance:schema:prohibited-claims:1.0.0",
        "e200ce42c9663cd6506dc3031799c5ff18f3db77d95d4853d8fe13b57865303e",
    ),
    "schemas/action-authority.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/action-authority.schema.json",
        "09a9d349465af91926c9a945485eaf057a9782c2e9edea755fd8c65acc546263",
    ),
    "schemas/agent-inventory.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/agent-inventory.schema.json",
        "e37fbf6ae54cfc26202048ba9832bec7d872fa02a95f302a57dd571118767b36",
    ),
    "schemas/agent-trust-passport.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/agent-trust-passport.schema.json",
        "f8b9186d15853c8491ae3f419e7266935d7bc1248e3d2d5152d1fd29149ff970",
    ),
    "schemas/assessment-result.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/assessment-result.schema.json",
        "155c820d2f9033af290864e8d910706c7ba427ac039639d6071bb5f17d433720",
    ),
    "schemas/bundle-manifest.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/bundle-manifest.schema.json",
        "ec484cc7a4d3abb623589a09a4c30b7e05d92960d48c2161e6db74be046a0fad",
    ),
    "schemas/common.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/common.schema.json",
        "b76fda4974265e67e7df9e90da4e7080e2337743588152d64d2748f42ab50a92",
    ),
    "schemas/control-profile-descriptor.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/control-profile-descriptor.schema.json",
        "ad70578c9fdf07d37cc8d9269c4661547fcbd028cf2a5dea7ca30565d537dfe5",
    ),
    "schemas/data-authority-evidence.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/data-authority-evidence.schema.json",
        "057131725866f7be67eee487831875168504dd9ff8b19234ffea468024203625",
    ),
    "schemas/mcp-inventory.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/mcp-inventory.schema.json",
        "1f5c8adda16a5bc2cafec710f93df4b7d3e61a51569e697ed89ecf6d4942a60d",
    ),
    "schemas/revocation-entry.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/revocation-entry.schema.json",
        "772673a7b0154640a745829e18dca381e0803f143a2d8278758cf4555f22900c",
    ),
    "schemas/revocation-list.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/revocation-list.schema.json",
        "359c72860859732bc8c1948d4aba40427fb31609fa7fd3b997f0371e1229516d",
    ),
    "schemas/schema-catalog.schema.json": (
        "urn:global-ai-governance:agentic-ai-governance:schema:schema-catalog:1.0.0",
        "24ac94f005a591444e2c9e5022df794770c355be10106b3cd8882bd26eb4ea46",
    ),
    "schemas/tool-inventory.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/tool-inventory.schema.json",
        "7882d822d6bcde27f913ced43ccb4b338d6f90f1f32ee79cc7a6146f933179b9",
    ),
    "schemas/trusted-key.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/trusted-key.schema.json",
        "6c8dc07e184edf8c1a33dbad21849a6bb586e47832f92d23b6b77111ff8fd705",
    ),
    "schemas/verification-result.schema.json": (
        "https://raw.githubusercontent.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/v0.1.0-alpha.1/schemas/verification-result.schema.json",
        "9f70aa81762ef08addd0d04aaedf7330addf87276bad43a47533037c80ca7f1b",
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    return load_strict(path, require_object=True)


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schema_catalog(root: Path) -> dict[str, Any]:
    schema_path = root / CATALOG_SCHEMA_PATH
    catalog_path = root / CATALOG_PATH
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    catalog = load_json(catalog_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(error.message for error in validator.iter_errors(catalog))
    if errors:
        raise ValueError("schema catalog validation failed: " + "; ".join(errors))
    return catalog


def _iter_refs(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            yield ref
        for nested in value.values():
            yield from _iter_refs(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_refs(nested)


def catalog_schema_paths(root: Path) -> list[Path]:
    root = root.resolve()
    catalog = schema_catalog(root)
    paths: list[Path] = []
    seen_files: set[str] = set()
    seen_ids: set[str] = set()
    entries_by_file: dict[str, dict[str, Any]] = {}

    for entry in catalog["entries"]:
        relative = entry["schema_file"]
        schema_id = entry["schema_id"]
        if relative in seen_files:
            raise ValueError(f"duplicate schema_file in catalog: {relative}")
        if schema_id in seen_ids:
            raise ValueError(f"duplicate schema_id in catalog: {schema_id}")
        seen_files.add(relative)
        seen_ids.add(schema_id)
        entries_by_file[relative] = entry

        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"schema path escapes repository: {relative}") from exc
        if not path.is_file():
            raise ValueError(f"cataloged schema missing: {relative}")
        digest = raw_sha256(path)
        if digest != entry["content_sha256"]:
            raise ValueError(f"schema content digest mismatch: {relative}")
        schema = load_json(path)
        Draft202012Validator.check_schema(schema)
        if schema.get("$id") != schema_id:
            raise ValueError(f"{relative}: $id does not match catalog")
        paths.append(path)

    actual = {
        path.resolve()
        for path in root.rglob("*.schema.json")
        if ".git" not in path.parts
    }
    cataloged = set(paths)
    if cataloged != actual:
        uncataloged = sorted(str(path.relative_to(root)) for path in actual - cataloged)
        nonexistent = sorted(str(path.relative_to(root)) for path in cataloged - actual)
        raise ValueError(
            f"schema catalog mismatch: uncataloged={uncataloged} nonexistent={nonexistent}"
        )

    for relative, (expected_id, expected_digest) in PROTECTED_SCHEMA_METADATA.items():
        entry = entries_by_file.get(relative)
        if entry is None:
            raise ValueError(f"protected active schema removed from catalog: {relative}")
        if entry["schema_id"] != expected_id:
            raise ValueError(f"protected schema identifier changed: {relative}")
        if entry["content_sha256"] != expected_digest:
            raise ValueError(f"protected schema content changed: {relative}")
        if entry["status"] != "ACTIVE":
            raise ValueError(f"protected schema may not be silently deprecated: {relative}")

    resolve_all_references(root, paths)
    return paths


def registry_for_paths(paths: list[Path]) -> Registry:
    resources: list[tuple[str, Resource[Any]]] = []
    for path in paths:
        schema = load_json(path)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def resolve_all_references(root: Path, paths: list[Path]) -> None:
    registry = registry_for_paths(paths)
    for path in paths:
        schema = load_json(path)
        resolver = registry.resolver(schema["$id"])
        for reference in _iter_refs(schema):
            try:
                resolver.lookup(reference)
            except Exception as exc:
                relative = path.resolve().relative_to(root.resolve())
                raise ValueError(f"unresolved $ref in {relative}: {reference}: {exc}") from exc


def protocol_schema_paths(root: Path) -> list[Path]:
    catalog = schema_catalog(root)
    paths_by_relative = {
        path.resolve().relative_to(root.resolve()).as_posix(): path
        for path in catalog_schema_paths(root)
    }
    return [
        paths_by_relative[entry["schema_file"]]
        for entry in catalog["entries"]
        if entry["artifact_kind"] == "PROTOCOL_SCHEMA"
    ]


def full_registry(root: Path) -> Registry:
    return registry_for_paths(catalog_schema_paths(root))
