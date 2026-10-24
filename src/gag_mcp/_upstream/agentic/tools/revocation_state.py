#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Explicit local continuity state for the reference revocation verifier."""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.strict_json import StrictJSONError, load_strict


STATE_FORMAT = "global-ai-governance.revocation-state.v1"
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_REQUIRED = {
    "format",
    "framework",
    "authority",
    "sequence_number",
    "list_id",
    "next_update",
    "revoked_passport_ids",
}


class RevocationStateError(ValueError):
    """A trusted state store cannot establish continuity."""


def _validate_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _REQUIRED:
        raise RevocationStateError("revocation state has an incompatible structure")
    if value.get("format") != STATE_FORMAT:
        raise RevocationStateError("revocation state has an unsupported format")
    for field in ("framework", "authority", "next_update"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise RevocationStateError(f"revocation state {field} is invalid")
    try:
        datetime.strptime(value["next_update"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise RevocationStateError("revocation state next_update is invalid") from exc
    sequence = value.get("sequence_number")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise RevocationStateError("revocation state sequence_number is invalid")
    if not isinstance(value.get("list_id"), str) or not _HASH.fullmatch(value["list_id"]):
        raise RevocationStateError("revocation state list_id is invalid")
    revoked = value.get("revoked_passport_ids")
    if (
        not isinstance(revoked, list)
        or revoked != sorted(set(revoked))
        or any(not isinstance(item, str) or not _HASH.fullmatch(item) for item in revoked)
    ):
        raise RevocationStateError("revocation state revoked_passport_ids is invalid")
    return value


def _state_from_list(revocation: dict[str, Any], revoked: set[str]) -> dict[str, Any]:
    return {
        "format": STATE_FORMAT,
        "framework": revocation["framework"],
        "authority": revocation["issuer_id"],
        "sequence_number": revocation["sequence_number"],
        "list_id": revocation["list_id"],
        "next_update": revocation["next_update"],
        "revoked_passport_ids": sorted(revoked),
    }


def _atomic_write(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def apply_revocation_state(
    path: Path,
    revocation: dict[str, Any],
    *,
    initialize: bool,
) -> set[str]:
    """Establish continuity, atomically persisting only initialization or advance."""
    presented = {entry["passport_id"] for entry in revocation["entries"]}
    if not path.exists():
        if not initialize:
            raise RevocationStateError(
                "revocation state does not exist; explicit initialization is required"
            )
        state = _state_from_list(revocation, presented)
        _atomic_write(path, state)
        return presented

    if initialize:
        raise RevocationStateError("revocation state already exists and cannot be reinitialized")
    try:
        state = _validate_state(load_strict(path, require_object=True))
    except (StrictJSONError, OSError, RevocationStateError) as exc:
        raise RevocationStateError(f"revocation state is unavailable or invalid: {exc}") from exc

    if state["framework"] != revocation["framework"] or state["authority"] != revocation["issuer_id"]:
        raise RevocationStateError("revocation state authority or framework does not match the supplied list")

    previous_sequence = state["sequence_number"]
    sequence = revocation["sequence_number"]
    if sequence < previous_sequence:
        raise RevocationStateError("revocation list sequence is lower than trusted state (rollback)")
    if sequence == previous_sequence:
        if revocation["list_id"] != state["list_id"]:
            raise RevocationStateError("revocation list conflicts with trusted state at the same sequence")
        return set(state["revoked_passport_ids"])
    if revocation["previous_list_hash"] != state["list_id"]:
        raise RevocationStateError("revocation list does not chain from the previously accepted list_id")

    retained = set(state["revoked_passport_ids"])
    if not retained.issubset(presented):
        raise RevocationStateError("cumulative revocation list omits a previously trusted revocation")
    cumulative = retained | presented
    _atomic_write(path, _state_from_list(revocation, cumulative))
    return cumulative
