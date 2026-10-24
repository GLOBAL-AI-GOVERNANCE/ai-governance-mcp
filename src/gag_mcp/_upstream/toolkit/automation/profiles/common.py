"""Shared deterministic profile result helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def finding(profile_id: str, code: str, severity: str, message: str, action: str) -> dict[str, str]:
    return {
        "id": f"{profile_id}:{code}",
        "severity": severity,
        "message": message,
        "action": action,
    }


def result(profile_id: str, version: str, source_digest: str, evaluation_time: str | None,
           findings: list[dict[str, str]], evidence: list[dict[str, str]], details: dict[str, object],
           manifest: dict[str, str] | None = None) -> dict[str, object]:
    ordered = sorted({item["id"]: item for item in findings}.values(), key=lambda item: item["id"])
    status = "FAIL" if any(item["severity"] == "CRITICAL" for item in ordered) else ("CONDITIONAL" if ordered else "PASS")
    summaries = {"PASS": "Submitted profile passed its bounded structural and integrity checks.",
                 "CONDITIONAL": "Submitted profile requires the listed accountable follow-up actions.",
                 "FAIL": "Submitted profile failed one or more fail-closed checks."}
    value: dict[str, object] = {
        "schema_version": "1.0.0", "profile_id": profile_id, "profile_version": version,
        "source_artifact_sha256": source_digest, "decision_pack_manifest": manifest,
        "authority_effect": "NONE", "evaluation_time": evaluation_time, "status": status,
        "summary": summaries[status], "findings": ordered,
        "evidence_references": sorted(evidence, key=lambda item: (item["type"], item["reference"])),
        "details": details,
    }
    return value


def safe_local_reference(root: Path, reference: str) -> bool:
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts:
        return False
    try:
        (root / path).resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
