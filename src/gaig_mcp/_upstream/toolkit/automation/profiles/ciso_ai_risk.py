"""CISO decision/accountability profile evaluator."""

from __future__ import annotations

from pathlib import Path
from .common import finding

PROFILE = "ciso-ai-risk-v0.1"
VERSION = "0.1.0"
ROLES = ("business_owner", "technical_owner", "security_reviewer", "residual_risk_acceptance_authority", "privacy_reviewer", "legal_reviewer")


def evaluate(data: dict[str, object], root: Path, evaluation_time: str | None):
    issues = []
    add = lambda code, msg, action: issues.append(finding(PROFILE, code, "CRITICAL", msg, action))
    roles = data.get("accountable_roles", {})
    for role in ROLES:
        if not isinstance(roles, dict) or not roles.get(role):
            add("MISSING_ROLE_" + role.upper(), f"Required accountable role '{role}' is missing.", "Name the accountable person or function.")
    if not data.get("stop_condition"):
        add("MISSING_STOP_CONDITION", "A stop condition is required.", "Define the condition that requires use to stop or return to review.")
    evidence = data.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        add("MISSING_EVIDENCE", "Decision evidence is missing.", "Reference evidence supporting the bounded decision.")
        refs = []
    else:
        refs = [item for item in evidence if isinstance(item, dict)]
    expiration = data.get("decision_expiration")
    if evaluation_time and isinstance(expiration, str) and expiration < evaluation_time:
        add("DECISION_EXPIRED", "The decision expired before the explicit evaluation time.", "Return the record for accountable re-review.")
    dependencies = data.get("dependencies", [])
    details = {"current_decision": data.get("governance_decision"), "accountable_roles": roles,
               "top_condition": data.get("top_condition"), "stop_condition": data.get("stop_condition"),
               "evidence_state": "PRESENT" if refs else "MISSING", "review_expiration": expiration,
               "dependency_state": dependencies, "governed_system_reference": data.get("governed_system_reference")}
    return issues, refs, details
