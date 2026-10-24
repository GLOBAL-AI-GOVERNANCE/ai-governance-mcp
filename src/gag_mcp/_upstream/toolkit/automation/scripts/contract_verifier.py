"""Validate Wave A JSON contracts and Decision Pack integrity without network access."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


AUTOMATION = Path(__file__).resolve().parents[1]
CONTRACTS = AUTOMATION / "contracts"
V1 = CONTRACTS / "v1"


class ContractError(ValueError):
    pass


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "null": value is None,
        "boolean": isinstance(value, bool),
    }.get(expected, False)


def validate_instance(value: Any, schema: dict[str, Any], *, base: Path, location: str = "$") -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or "://" in ref or ref.startswith("#"):
            raise ContractError(f"{location}: unsupported reference {ref!r}")
        validate_instance(value, json.loads((base / ref).read_text(encoding="utf-8")), base=base, location=location)
        return
    expected = schema.get("type")
    if isinstance(expected, list):
        if not any(_type_matches(value, item) for item in expected):
            raise ContractError(f"{location}: unexpected type")
    elif isinstance(expected, str) and not _type_matches(value, expected):
        raise ContractError(f"{location}: expected {expected}")
    if "const" in schema and value != schema["const"]:
        raise ContractError(f"{location}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(f"{location}: unsupported value {value!r}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ContractError(f"{location}: string is too short")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise ContractError(f"{location}: pattern mismatch")
    if isinstance(value, int) and value < schema.get("minimum", value):
        raise ContractError(f"{location}: below minimum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ContractError(f"{location}: too few items")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            raise ContractError(f"{location}: duplicate items")
        if "items" in schema:
            for index, item in enumerate(value):
                validate_instance(item, schema["items"], base=base, location=f"{location}[{index}]")
    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = [item for item in required if item not in value]
        if missing:
            raise ContractError(f"{location}: missing {', '.join(missing)}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise ContractError(f"{location}: unknown properties {', '.join(unknown)}")
        for key, item in value.items():
            if key in properties:
                validate_instance(item, properties[key], base=base, location=f"{location}.{key}")


def validate_file(path: Path, schema_path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(str(exc)) from exc
    validate_instance(value, schema, base=schema_path.parent)
    return value


def _sha256_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_output_directory(outdir: Path) -> None:
    normalized = validate_file(outdir / "normalized-inventory.json", V1 / "normalized-inventory.schema.json")
    for record in normalized["records"]:
        validate_instance(record, json.loads((V1 / "canonical-inventory-record.schema.json").read_text(encoding="utf-8")), base=V1)
    validate_file(outdir / "governance-findings.json", V1 / "governance-findings.schema.json")
    validate_file(outdir / "governance-result.json", V1 / "governance-result.schema.json")
    manifest_path = outdir / "decision-pack" / "manifest.json"
    manifest = validate_file(manifest_path, V1 / "decision-pack-manifest.schema.json")
    handoff = validate_file(outdir / "governance-handoff.json", CONTRACTS / "governance-decision-handoff.schema.json")
    pack = manifest_path.parent
    for entry in manifest["generated_files"]:
        path = pack / entry["path"]
        if not path.is_file() or _sha256_text(path) != entry["sha256"]:
            raise ContractError(f"Decision Pack digest mismatch: {entry['path']}")
    resource_paths = {
        "ai-system-inventory.schema.json": AUTOMATION / "schemas" / "ai-system-inventory.schema.json",
        "governance-rules.yaml": AUTOMATION / "policy-as-code" / "governance-rules.yaml",
    }
    for entry in manifest["source_artifacts"]:
        path = outdir / entry["path"]
        if not path.is_file():
            path = resource_paths.get(entry["path"], path)
        if not path.is_file() or _sha256_text(path) != entry["sha256"]:
            raise ContractError(f"Decision Pack source digest mismatch: {entry['path']}")
    expected_manifest_digest = "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if handoff["artifact_digest"] != expected_manifest_digest:
        raise ContractError("Handoff artifact digest does not match Decision Pack manifest")
    if handoff["authority_effect"] != "NONE":
        raise ContractError("Handoff authority_effect must remain NONE")
    print("Wave A contracts and Decision Pack integrity verified.")
