#!/usr/bin/env python3
"""
AI inventory schema validator.

Consumes the repository's JSON schema before risk calculation.
The implementation intentionally supports the flat object keywords used by
the checked-in schema and fails closed when unsupported keywords appear.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Mapping, Sequence


SUPPORTED_TOP_LEVEL_KEYS = {
    "$schema",
    "title",
    "type",
    "additionalProperties",
    "required",
    "properties",
}
SUPPORTED_PROPERTY_KEYS = {
    "type",
    "enum",
    "minLength",
    "description",
}


class SchemaValidationError(ValueError):
    """Raised when the schema or inventory cannot be safely evaluated."""


def load_schema(path: Path) -> Dict[str, object]:
    if not path.is_file():
        raise SchemaValidationError(f"Schema file not found: {path}")

    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            f"Schema file is not valid JSON: {path}: {exc}"
        ) from exc

    if not isinstance(schema, dict):
        raise SchemaValidationError("Schema root must be an object.")

    unsupported = set(schema) - SUPPORTED_TOP_LEVEL_KEYS
    if unsupported:
        raise SchemaValidationError(
            "Unsupported top-level schema keywords: "
            + ", ".join(sorted(unsupported))
        )

    if schema.get("type") != "object":
        raise SchemaValidationError(
            "Schema root type must be 'object'."
        )

    required = schema.get("required")
    properties = schema.get("properties")

    if not isinstance(required, list) or not all(
        isinstance(item, str) for item in required
    ):
        raise SchemaValidationError(
            "Schema 'required' must be a list of field names."
        )

    if not isinstance(properties, dict):
        raise SchemaValidationError(
            "Schema 'properties' must be an object."
        )

    unknown_required = set(required) - set(properties)
    if unknown_required:
        raise SchemaValidationError(
            "Required fields missing property definitions: "
            + ", ".join(sorted(unknown_required))
        )

    for field, definition in properties.items():
        if not isinstance(field, str) or not isinstance(definition, dict):
            raise SchemaValidationError(
                "Every property must have an object definition."
            )

        unsupported_property_keys = (
            set(definition) - SUPPORTED_PROPERTY_KEYS
        )
        if unsupported_property_keys:
            raise SchemaValidationError(
                f"{field}: unsupported schema keywords: "
                + ", ".join(sorted(unsupported_property_keys))
            )

        if definition.get("type") != "string":
            raise SchemaValidationError(
                f"{field}: only string fields are supported."
            )

        enum = definition.get("enum")
        if enum is not None and (
            not isinstance(enum, list)
            or not enum
            or not all(isinstance(item, str) for item in enum)
        ):
            raise SchemaValidationError(
                f"{field}: enum must be a non-empty string list."
            )

        min_length = definition.get("minLength")
        if min_length is not None and (
            not isinstance(min_length, int) or min_length < 0
        ):
            raise SchemaValidationError(
                f"{field}: minLength must be a non-negative integer."
            )

    if schema.get("additionalProperties") not in (True, False, None):
        raise SchemaValidationError(
            "additionalProperties must be true or false."
        )

    return schema


def read_csv(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    if not path.is_file():
        raise SchemaValidationError(
            f"Inventory file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file_handle:
        reader = csv.DictReader(file_handle)

        if reader.fieldnames is None:
            raise SchemaValidationError(
                "Inventory CSV has no header row."
            )

        fieldnames = list(reader.fieldnames)

        if len(fieldnames) != len(set(fieldnames)):
            raise SchemaValidationError(
                "Inventory CSV contains duplicate column names."
            )

        raw_rows = list(reader)

    if not raw_rows:
        raise SchemaValidationError(
            "Inventory CSV has no data rows."
        )

    rows: List[Dict[str, str]] = []

    for row_number, row in enumerate(raw_rows, start=2):
        if None in row:
            raise SchemaValidationError(
                f"Row {row_number} contains more values than headers."
            )

        normalized: Dict[str, str] = {}
        for key, value in row.items():
            normalized[key] = "" if value is None else str(value)
        rows.append(normalized)

    return fieldnames, rows


def validate_inventory(
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    schema: Mapping[str, object],
) -> List[str]:
    errors: List[str] = []
    required = set(schema["required"])
    properties = schema["properties"]
    additional_allowed = schema.get("additionalProperties", True)

    missing_columns = sorted(required - set(fieldnames))
    for field in missing_columns:
        errors.append(f"Header: missing required field '{field}'.")

    if additional_allowed is False:
        extra_columns = sorted(set(fieldnames) - set(properties))
        for field in extra_columns:
            errors.append(f"Header: unexpected field '{field}'.")

    if missing_columns:
        return errors

    for row_index, row in enumerate(rows, start=2):
        for field in sorted(required):
            if field not in row:
                errors.append(
                    f"Row {row_index}: missing required field '{field}'."
                )

        for field, definition in properties.items():
            if field not in row:
                continue

            value = row[field]

            min_length = definition.get("minLength")
            if min_length is not None and len(value) < min_length:
                errors.append(
                    f"Row {row_index}, field '{field}': "
                    f"minimum length is {min_length}."
                )

            enum = definition.get("enum")
            if enum is not None and value not in enum:
                allowed = ", ".join(enum)
                errors.append(
                    f"Row {row_index}, field '{field}': "
                    f"value '{value}' is not allowed; expected one of: "
                    f"{allowed}."
                )

    return errors


def write_report(
    report_path: Path,
    schema_path: Path,
    input_path: Path,
    errors: Sequence[str],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Inventory Schema Validation Report",
        "",
        f"- Schema: `{schema_path.name}`",
        f"- Inventory: `{input_path.name}`",
        "",
    ]

    if errors:
        lines.extend(["## Errors", ""])
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("Inventory schema validation passed.")

    report_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def validate_csv(
    input_path: Path,
    schema_path: Path,
    report_path: Path,
) -> List[str]:
    schema = load_schema(schema_path)
    fieldnames, rows = read_csv(input_path)
    errors = validate_inventory(fieldnames, rows, schema)
    write_report(
        report_path,
        schema_path,
        input_path,
        errors,
    )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate AI inventory CSV records against the "
            "runtime inventory schema."
        )
    )
    parser.add_argument(
        "input_csv",
        type=Path,
        help="Path to AI inventory CSV.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        required=True,
        help="Path to the JSON inventory schema.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Output Markdown report path.",
    )
    args = parser.parse_args()

    try:
        errors = validate_csv(
            args.input_csv,
            args.schema,
            args.report,
        )
    except SchemaValidationError as exc:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            "# Inventory Schema Validation Report\n\n"
            f"Configuration or input error: {exc}\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"Schema validation failed: {exc}")
        raise SystemExit(2) from exc

    if errors:
        print(
            "Schema validation blocked the inventory: "
            f"{len(errors)} error(s)."
        )
        raise SystemExit(2)

    print(f"Schema validation passed: {args.report}")


if __name__ == "__main__":
    main()
