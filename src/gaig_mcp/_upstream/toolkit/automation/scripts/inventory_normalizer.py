#!/usr/bin/env python3
"""Normalize supported inventory CSV inputs into the canonical v1 contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


AUTOMATION = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = AUTOMATION / "contracts" / "v1"
SCHEMA_PATH = CONTRACT_ROOT / "canonical-inventory-record.schema.json"
MAPPING_PATH = CONTRACT_ROOT / "inventory-mapping.json"
SCHEMA_VERSION = "1.0.0"
NORMALIZATION_VERSION = "1.0.0"


@dataclass(frozen=True)
class NormalizationIssue:
    code: str
    source_column: str | None
    supplied_value: str | None
    expected: list[str]
    remediation: str


class NormalizationError(ValueError):
    """A stable machine-readable normalization failure."""

    def __init__(self, issue: NormalizationIssue):
        self.issue = issue
        super().__init__(json.dumps({
            "error": {
                "code": issue.code,
                "source_column": issue.source_column,
                "supplied_value": issue.supplied_value,
                "expected": issue.expected,
                "remediation": issue.remediation,
            }
        }, sort_keys=True))


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Contract root must be an object: {path}")
    return value


def _header_key(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def canonical_fields() -> list[str]:
    schema = _load(SCHEMA_PATH)
    return [field for field in schema["properties"] if field != "schema_version"]


def alias_map() -> dict[str, str]:
    mapping = _load(MAPPING_PATH)
    aliases: dict[str, str] = {}
    for canonical, definition in mapping["fields"].items():
        names = [canonical, definition["human_label"], *definition.get("aliases", [])]
        for name in names:
            key = _header_key(name)
            previous = aliases.get(key)
            if previous is not None and previous != canonical:
                raise ValueError(f"Ambiguous configured header alias: {name}")
            aliases[key] = canonical
    aliases["schema version"] = "schema_version"
    return aliases


def _enum_value(field: str, value: str, definition: dict[str, Any], mapping: dict[str, Any]) -> str:
    stripped = value.strip()
    allowed = definition.get("enum")
    if not allowed:
        return stripped
    if set(allowed) == {"Yes", "No"}:
        folded = stripped.lower()
        for canonical, variants in mapping["boolean_aliases"].items():
            if folded in variants:
                return canonical
    matches = [item for item in allowed if item.lower() == stripped.lower()]
    if len(matches) == 1:
        return matches[0]
    raise NormalizationError(NormalizationIssue(
        code="INVALID_ENUM_VALUE",
        source_column=field,
        supplied_value=value,
        expected=list(allowed),
        remediation="Use one of the declared canonical values.",
    ))


def normalize_inventory(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise NormalizationError(NormalizationIssue(
            "INPUT_NOT_FOUND", None, str(path), [], "Provide an existing CSV file.",
        ))
    raw = path.read_bytes()
    schema = _load(SCHEMA_PATH)
    mapping = _load(MAPPING_PATH)
    aliases = alias_map()

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            headers = next(reader)
        except StopIteration as exc:
            raise NormalizationError(NormalizationIssue(
                "EMPTY_INPUT", None, None, [], "Provide a header and at least one record.",
            )) from exc
        rows = list(reader)

    if not rows or all(not any(cell.strip() for cell in row) for row in rows):
        raise NormalizationError(NormalizationIssue(
            "EMPTY_INPUT", None, None, [], "Provide at least one inventory record.",
        ))
    if len(headers) != len(set(headers)):
        raise NormalizationError(NormalizationIssue(
            "DUPLICATE_HEADER", None, None, [], "Make every source header unique.",
        ))

    mapped_headers: list[str | None] = []
    mappings_applied: list[str] = []
    ignored_legacy = {_header_key(item) for item in mapping.get("legacy_ignored_columns", [])}
    ignored_headers: list[str] = []
    unknown: list[str] = []
    for header in headers:
        canonical = aliases.get(_header_key(header))
        if canonical is None:
            if _header_key(header) in ignored_legacy:
                mapped_headers.append(None)
                ignored_headers.append(header)
                mappings_applied.append(f"{header}->IGNORED_LEGACY_NONCANONICAL")
            else:
                unknown.append(header)
            continue
        mapped_headers.append(canonical)
        if header != canonical:
            mappings_applied.append(f"{header}->{canonical}")
    if unknown:
        raise NormalizationError(NormalizationIssue(
            "UNKNOWN_COLUMN", unknown[0], None, canonical_fields(),
            "Remove the column or add an explicit reviewed alias to inventory-mapping.json.",
        ))
    canonical_headers = [item for item in mapped_headers if item is not None]
    if len(canonical_headers) != len(set(canonical_headers)):
        raise NormalizationError(NormalizationIssue(
            "DUPLICATE_CANONICAL_COLUMN", None, None, [],
            "Remove source columns that map to the same canonical field.",
        ))

    supplied_version = None
    if "schema_version" in canonical_headers:
        version_index = mapped_headers.index("schema_version")
        versions = {row[version_index].strip() for row in rows if len(row) > version_index}
        if versions != {SCHEMA_VERSION}:
            raise NormalizationError(NormalizationIssue(
                "UNSUPPORTED_SCHEMA_VERSION", headers[version_index], ",".join(sorted(versions)),
                [SCHEMA_VERSION], "Use a supported canonical inventory schema version.",
            ))
        supplied_version = SCHEMA_VERSION

    required = [item for item in schema["required"] if item != "schema_version"]
    missing = [item for item in required if item not in canonical_headers]
    if missing:
        raise NormalizationError(NormalizationIssue(
            "MISSING_REQUIRED_COLUMN", None, None, missing,
            "Add every required canonical field or use the generated human template.",
        ))

    records: list[dict[str, str]] = []
    for row_number, values in enumerate(rows, start=2):
        if len(values) != len(headers):
            raise NormalizationError(NormalizationIssue(
                "ROW_WIDTH_MISMATCH", None, str(row_number), headers,
                "Provide exactly one value for every header.",
            ))
        source = {
            target: value
            for target, value in zip(mapped_headers, values)
            if target is not None
        }
        record: dict[str, str] = {"schema_version": SCHEMA_VERSION}
        for field in required:
            definition = schema["properties"][field]
            value = _enum_value(field, source[field], definition, mapping)
            if definition.get("minLength", 0) and not value:
                raise NormalizationError(NormalizationIssue(
                    "EMPTY_REQUIRED_VALUE", field, source[field], [],
                    "Supply a non-empty value.",
                ))
            record[field] = value
        records.append(record)

    records.sort(key=lambda item: (item["system_id"], item["system_name"]))
    ids = [item["system_id"] for item in records]
    if len(ids) != len(set(ids)):
        raise NormalizationError(NormalizationIssue(
            "DUPLICATE_SYSTEM_ID", "system_id", None, [],
            "Use one stable, unique system_id per record.",
        ))

    human_labels = {definition["human_label"] for definition in mapping["fields"].values()}
    if set(headers) == human_labels:
        source_format = "generated_human_csv"
    elif headers == canonical_fields() or supplied_version:
        source_format = "canonical_csv"
    else:
        source_format = "legacy_csv"
    warnings = []
    if not supplied_version:
        warnings.append("Source CSV did not declare schema_version; canonical v1 compatibility was applied.")
    for header in ignored_headers:
        warnings.append(f"Known legacy column was not part of canonical governance meaning and was ignored: {header}")
    return {
        "schema_version": SCHEMA_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "source": {
            "name": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "format": source_format,
        },
        "mappings_applied": sorted(set(mappings_applied)),
        "warnings": warnings,
        "records": records,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _write_csv(path: Path, records: list[dict[str, str]]) -> None:
    fields = canonical_fields()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({field: record[field] for field in fields})


def normalize_file(input_path: Path, output_json: Path, output_csv: Path | None = None) -> dict[str, Any]:
    value = normalize_inventory(input_path)
    _write_json(output_json, value)
    if output_csv is not None:
        _write_csv(output_csv, value["records"])
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize a supported AI inventory CSV.", allow_abbrev=False)
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()
    try:
        normalize_file(args.input_csv, args.output_json, args.output_csv)
    except (OSError, ValueError) as exc:
        print(f"Inventory normalization failed: {exc}")
        raise SystemExit(2) from exc
    print(f"Inventory normalized: {args.output_json}")


if __name__ == "__main__":
    main()
