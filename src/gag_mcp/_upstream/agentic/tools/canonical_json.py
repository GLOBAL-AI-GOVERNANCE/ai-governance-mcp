#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""RFC 8785 JSON Canonicalization Scheme for the framework's I-JSON subset."""
from __future__ import annotations

import json
from typing import Any

SAFE_INTEGER = 2**53 - 1


def _validate_string(value: str) -> None:
    for ch in value:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            raise ValueError("lone UTF-16 surrogate is prohibited by I-JSON")


def _utf16_sort_key(value: str) -> bytes:
    _validate_string(value)
    return value.encode("utf-16-be")


def _serialize_string(value: str) -> str:
    _validate_string(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _serialize(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int) and not isinstance(value, bool):
        if not (-SAFE_INTEGER <= value <= SAFE_INTEGER):
            raise ValueError("integer outside the interoperable I-JSON safe range")
        return str(value)
    if isinstance(value, float):
        raise TypeError("fractional numbers are prohibited by this framework profile")
    if isinstance(value, str):
        return _serialize_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            _validate_string(key)
        items = sorted(value.items(), key=lambda item: _utf16_sort_key(item[0]))
        return "{" + ",".join(_serialize_string(key) + ":" + _serialize(item) for key, item in items) + "}"
    raise TypeError(f"unsupported JSON value type: {type(value).__name__}")


def canonicalize(value: Any) -> bytes:
    """Return RFC 8785-compatible UTF-8 bytes for the supported I-JSON subset."""
    return _serialize(value).encode("utf-8")
