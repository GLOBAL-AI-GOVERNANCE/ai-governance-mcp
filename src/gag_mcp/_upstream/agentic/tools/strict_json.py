#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Strict JSON loading for the Agentic AI Governance I-JSON profile."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SAFE_INTEGER = 2**53 - 1


class StrictJSONError(ValueError):
    """Raised when JSON violates the repository's strict input profile."""


def _pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"duplicate object key: {key}")
        result[key] = value
    return result


def _parse_int(text: str) -> int:
    value = int(text)
    if not (-SAFE_INTEGER <= value <= SAFE_INTEGER):
        raise StrictJSONError("integer outside the interoperable I-JSON safe range")
    return value


def _parse_float(_: str) -> float:
    raise StrictJSONError("fractional numbers are prohibited by this framework profile")


def _parse_constant(value: str) -> None:
    raise StrictJSONError(f"nonfinite number is prohibited: {value}")


def _validate_strings(value: Any) -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
            raise StrictJSONError("lone UTF-16 surrogate is prohibited by I-JSON")
    elif isinstance(value, list):
        for item in value:
            _validate_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate_strings(key)
            _validate_strings(item)


def loads_strict(data: str | bytes, *, require_object: bool = False) -> Any:
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise StrictJSONError(
                f"invalid UTF-8 at byte {exc.start}"
            ) from exc
    elif isinstance(data, str):
        text = data
    else:
        raise TypeError("JSON input must be text or bytes")

    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_hook,
            parse_int=_parse_int,
            parse_float=_parse_float,
            parse_constant=_parse_constant,
        )
    except StrictJSONError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictJSONError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    _validate_strings(value)
    if require_object and not isinstance(value, dict):
        raise StrictJSONError("top-level JSON value must be an object")
    return value


def load_strict(path: Path, *, require_object: bool = False) -> Any:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise StrictJSONError(f"unable to read {path}: {exc}") from exc
    return loads_strict(data, require_object=require_object)
