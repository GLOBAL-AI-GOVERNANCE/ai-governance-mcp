"""Organizational AI maturity evidence evaluator.

A human process selects maturity. This evaluator checks whether submitted
evidence can carry that determination. It does not decide organizational maturity.
Unregistered. authority_effect remains NONE.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import finding

PROFILE_ID = "organizational-ai-maturity-v0.1"
VERSION = "0.1.0"
LEVELS = ("BASIC", "READY", "DYNAMIC", "ADVANCED")
CARRY_STATUSES = ("ACCEPTED", "ACCEPTED_WITH_CONDITIONS")
OPEN_STATUSES = ("PENDING", "REJECTED", "RETURNED_FOR_REASSESSMENT")
CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "frameworks"
    / "unesco-ai-maturity-2025"
    / "category-catalog.json"
)
LEVEL_MEANING = (
    "evidence_supported_level repeats a human-determined level only when "
    "submitted evidence passes bounded checks. It is not an independent maturity determination."
)


def parse_time(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def load_catalog() -> dict[str, Any]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    pillars = {item["id"]: item for item in catalog["pillars"]}
    categories = {}
    for pillar in catalog["pillars"]:
        for category in pillar["categories"]:
            categories[category["id"]] = {**category, "pillar_id": pillar["id"]}
    return {"raw": catalog, "pillars": pillars, "categories": categories}


def evaluate(data: dict, root: Path, evaluation_time: str | None = None) -> tuple[list, list, dict]:
    del root
    findings: list[dict] = []
    evidence: list[dict] = []
    catalog = load_catalog()
    eval_dt = parse_time(evaluation_time)
    framework_ids = list(catalog["categories"])
    details: dict[str, Any] = {
        "categories": [],
        "overall_synthesis": "PENDING_HUMAN_SYNTHESIS",
        "human_determination": "PENDING",
        "authority_effect": "NONE",
        "evidence_supported_level_meaning": LEVEL_MEANING,
        "assessment_coverage": data.get("assessment_coverage"),
        "coverage_status": "INCOMPLETE",
        "assessed_category_count": 0,
        "framework_category_count": len(framework_ids),
        "missing_category_ids": framework_ids,
    }

    if data.get("authority_effect") not in (None, "NONE"):
        findings.append(finding(PROFILE_ID, "AUTHORITY_EFFECT", "CRITICAL",
                                "Authority effect must remain NONE.",
                                "Set authority_effect to NONE."))
    if data.get("framework_version") != "2025":
        findings.append(finding(PROFILE_ID, "FRAMEWORK_VERSION", "CRITICAL",
                                "Only framework version 2025 is supported by this adapter.",
                                "Use the 2025 adapter."))
    coverage = data.get("assessment_coverage")
    if coverage not in ("PARTIAL", "FULL_FRAMEWORK"):
        findings.append(finding(PROFILE_ID, "ASSESSMENT_COVERAGE", "CRITICAL",
                                "Assessment coverage must be PARTIAL or FULL_FRAMEWORK.",
                                "Declare coverage. Partial coverage is not framework completion."))

    categories = data.get("categories") or []
    if not isinstance(categories, list) or not categories:
        findings.append(finding(PROFILE_ID, "CATEGORIES_MISSING", "CRITICAL",
                                "At least one category assessment is required.",
                                "Supply category records."))
        return findings, evidence, details

    seen: set[str] = set()
    for cat in categories:
        if not isinstance(cat, dict):
            findings.append(finding(PROFILE_ID, "CATEGORY_SHAPE", "CRITICAL",
                                    "Each category assessment must be an object.",
                                    "Supply a category object."))
            continue
        cat_result = evaluate_category(cat, data, catalog, eval_dt, findings, evidence, seen)
        if cat_result is not None:
            details["categories"].append(cat_result)

    assessed = [item["category_id"] for item in details["categories"] if item.get("known")]
    unique = list(dict.fromkeys(assessed))
    missing = [item for item in framework_ids if item not in unique]
    details["assessed_category_count"] = len(unique)
    details["missing_category_ids"] = missing
    if coverage == "FULL_FRAMEWORK" and missing:
        details["coverage_status"] = "INCOMPLETE"
        findings.append(finding(PROFILE_ID, "COVERAGE_INCOMPLETE", "CRITICAL",
                                "Full-framework coverage is missing one or more official categories.",
                                "Submit every official category once, or declare PARTIAL coverage."))
    elif coverage == "FULL_FRAMEWORK":
        details["coverage_status"] = "COMPLETE"
    elif coverage == "PARTIAL":
        details["coverage_status"] = "PARTIAL"
    return findings, evidence, details


def evaluate_category(cat: dict, data: dict, catalog: dict, eval_dt, findings: list, evidence: list, seen: set[str]) -> dict | None:
    pillar_id = cat.get("pillar_id")
    category_id = cat.get("category_id")
    pillar = catalog["pillars"].get(pillar_id)
    category = catalog["categories"].get(category_id)
    if pillar is None:
        findings.append(finding(PROFILE_ID, "UNKNOWN_PILLAR", "CRITICAL",
                                "Pillar is not in the framework catalog.",
                                "Use a pillar identifier from the adapter catalog."))
        return None
    if category is None:
        findings.append(finding(PROFILE_ID, "UNKNOWN_CATEGORY", "CRITICAL",
                                "Category is not in the framework catalog.",
                                "Use a category identifier from the adapter catalog."))
        return None
    if category["pillar_id"] != pillar_id:
        findings.append(finding(PROFILE_ID, "CATEGORY_PILLAR_MISMATCH", "CRITICAL",
                                "Category does not belong to the submitted pillar.",
                                "Submit the category under its catalog pillar."))
        return None
    if category_id in seen:
        findings.append(finding(PROFILE_ID, "DUPLICATE_CATEGORY", "CRITICAL",
                                "Category is repeated in this assessment.",
                                "Submit each official category at most once."))
        return None
    seen.add(category_id)

    claimed = cat.get("claimed_level")
    human = cat.get("human_determination") if isinstance(cat.get("human_determination"), dict) else None
    human_status = human.get("status") if human else None
    human_level = human.get("level") if human else None
    conditions = list(human.get("conditions") or []) if human else []
    established = human_status in CARRY_STATUSES and human_level in LEVELS
    result = {
        "known": True,
        "pillar_id": pillar_id,
        "pillar": pillar["label"],
        "category_id": category_id,
        "category": category["label"],
        "claimed_level": claimed,
        "target_level": cat.get("target_level"),
        "human_determination_status": human_status,
        "human_determined_level": human_level if established else None,
        "conditions": conditions if human_status == "ACCEPTED_WITH_CONDITIONS" else [],
        "evidence_supported_level": None,
        "level_support_state": "NOT_DETERMINED",
        "support_status": "UNSUPPORTED",
        "freshness_status": "CURRENT",
        "assessment_state": "CURRENT",
        "confidence": "LOW",
        "contradictions": cat.get("contradictions") or [],
        "gaps": cat.get("gaps") or [],
        "corrective_actions": cat.get("corrective_actions") or [],
        "reassessment_triggers": cat.get("reassessment_triggers") or [],
        "material_change_events": cat.get("material_change_events") or [],
    }
    if claimed not in LEVELS:
        findings.append(finding(PROFILE_ID, "INVALID_LEVEL", "CRITICAL",
                                "Claimed level must be BASIC, READY, DYNAMIC, or ADVANCED.",
                                "Use only the four source vocabulary levels."))
    if human is not None:
        if human_status not in CARRY_STATUSES + OPEN_STATUSES:
            findings.append(finding(PROFILE_ID, "HUMAN_DETERMINATION", "CRITICAL",
                                    "Human determination status is not recognized.",
                                    "Use a defined determination status."))
        if parse_time(human.get("determined_at")) is None:
            findings.append(finding(PROFILE_ID, "HUMAN_DETERMINATION", "CRITICAL",
                                    "Human determination time must be an RFC3339 timestamp.",
                                    "Supply a timestamp with Z or an explicit offset."))
        if not human.get("accountable_role"):
            findings.append(finding(PROFILE_ID, "HUMAN_DETERMINATION", "CRITICAL",
                                    "Human determination requires an accountable role.",
                                    "Name the accountable function, not a person."))

    evs = cat.get("evidence") or []
    has_operating = has_representative = has_policy = has_pilot = False
    synthetic_only = bool(evs)
    scope_mismatch = stale = integrity_fail = False
    for ev in evs:
        if not isinstance(ev, dict):
            continue
        if ev.get("reference"):
            evidence.append({"type": "URI", "reference": ev.get("reference"), "sha256": ev.get("sha256")})
        cls = ev.get("evidence_class")
        if cls != "SYNTHETIC":
            synthetic_only = False
        if cls == "OPERATING":
            has_operating = True
            if ev.get("is_representative") is True:
                has_representative = True
        elif cls == "POLICY":
            has_policy = True
        elif cls == "PILOT":
            has_pilot = True
        elif cls == "SYNTHETIC":
            findings.append(finding(PROFILE_ID, "SYNTHETIC_MISUSE", "HIGH",
                                    "Synthetic evidence cannot prove operating practice.",
                                    "Label synthetic evidence and do not treat it as operational proof."))
        if ev.get("scope") and ev.get("scope") != data.get("assessment_scope"):
            scope_mismatch = True
            findings.append(finding(PROFILE_ID, "SCOPE_MISMATCH", "HIGH",
                                    "Evidence scope does not match the assessment scope.",
                                    "Evidence must cover the submitted scope."))
        valid_through = parse_time(ev.get("valid_through"))
        if valid_through and eval_dt and valid_through < eval_dt:
            stale = True
            findings.append(finding(PROFILE_ID, "STALE", "HIGH",
                                    "Evidence is past its validity time.",
                                    "Reassess. Stale evidence is not current."))
        elif ev.get("valid_through") and parse_time(ev.get("valid_through")) is None:
            findings.append(finding(PROFILE_ID, "INVALID_TIME", "CRITICAL",
                                    "Evidence validity time is not a usable timestamp.",
                                    "Use RFC3339 with Z or an explicit offset."))
        if ev.get("integrity_asserted") and not ev.get("sha256"):
            integrity_fail = True
            findings.append(finding(PROFILE_ID, "INTEGRITY_FAIL", "HIGH",
                                    "Integrity was asserted without a digest.",
                                    "Supply sha256 or remove the integrity assertion."))

    if result["contradictions"]:
        result["support_status"] = "CONTRADICTED"
        findings.append(finding(PROFILE_ID, "CONTRADICTED", "HIGH",
                                "Contradictory evidence is present and is not averaged away.",
                                "Resolve contradictions before treating the determination as supported."))
    elif not evs:
        result["support_status"] = "UNSUPPORTED"
        findings.append(finding(PROFILE_ID, "MISSING_EVIDENCE", "HIGH",
                                "No evidence was submitted for this category.",
                                "Supply evidence before carrying a maturity determination."))
    elif scope_mismatch or integrity_fail or synthetic_only:
        result["support_status"] = "UNSUPPORTED"
    elif has_policy and not has_operating and claimed in ("DYNAMIC", "ADVANCED"):
        result["support_status"] = "PARTIAL"
        findings.append(finding(PROFILE_ID, "POLICY_ONLY_OVERCLAIM", "HIGH",
                                "A policy record alone does not support a Dynamic or Advanced position.",
                                "Supply representative operating evidence."))
    elif has_pilot and not has_representative:
        result["support_status"] = "PARTIAL"
        findings.append(finding(PROFILE_ID, "PILOT_AS_ENTERPRISE", "HIGH",
                                "Pilot evidence does not establish organization-wide practice.",
                                "Supply representative operating evidence for that scope."))
    elif has_operating and not has_representative:
        result["support_status"] = "PARTIAL"
        findings.append(finding(PROFILE_ID, "NON_REPRESENTATIVE", "MEDIUM",
                                "Operating evidence is not marked representative.",
                                "State whether the evidence represents typical practice."))
    elif has_operating and has_representative and not scope_mismatch and not integrity_fail:
        result["support_status"] = "SUPPORTED"
        result["confidence"] = "MEDIUM"
    else:
        result["support_status"] = "UNSUPPORTED"

    if stale:
        result["freshness_status"] = "STALE"
        result["assessment_state"] = "REASSESSMENT_REQUIRED"
    if result["material_change_events"]:
        result["assessment_state"] = "REASSESSMENT_REQUIRED"
        findings.append(finding(PROFILE_ID, "REASSESSMENT_REQUIRED", "MEDIUM",
                                "An observed material-change event requires reassessment.",
                                "Reassess before treating the prior determination as current."))
    if cat.get("organization_defined_critical") and not cat.get("critical_rationale"):
        findings.append(finding(PROFILE_ID, "CRITICAL_RATIONALE", "MEDIUM",
                                "An organization-defined critical category needs a rationale.",
                                "Record the organization's own reason."))

    blocked = (
        result["support_status"] != "SUPPORTED"
        or result["freshness_status"] != "CURRENT"
        or result["assessment_state"] != "CURRENT"
        or bool(result["contradictions"])
    )
    if result["contradictions"]:
        result["level_support_state"] = "EVIDENCE_CONTRADICTED"
    elif stale:
        result["level_support_state"] = "EVIDENCE_STALE"
    elif blocked or human_status in OPEN_STATUSES or human is None:
        result["level_support_state"] = "NOT_DETERMINED" if human_status in OPEN_STATUSES or human is None else "EVIDENCE_INSUFFICIENT"
    elif established and not blocked:
        result["level_support_state"] = "HUMAN_DETERMINATION_SUPPORTED"
        result["evidence_supported_level"] = human_level
    else:
        result["level_support_state"] = "EVIDENCE_INSUFFICIENT"
    result["authority_effect"] = "NONE"
    return result
