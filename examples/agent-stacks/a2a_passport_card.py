#!/usr/bin/env python3
"""Agent Trust Passport reference for A2A Agent Cards, and a pre-delegation check.

Status: TESTED (tests/test_interop.py parses the card with a2a-sdk 1.2.3 `a2a.types.AgentCard`, which
rejects unknown fields). No A2A server or client was run.

`with_passport_extension(card, ...)` adds an entry to `capabilities.extensions` that points at the
agent's passport, the public key that signs it, and the signed revocation list. A delegating agent
can call `delegation_decision(card, skill_id, guard)` before it sends a task: a card without the
extension is treated like an unknown tool (Level 4), and the skill's Action Level then maps to
allow, ask, or deny exactly as in action_level_guard.py. The extension is only a pointer; the
delegating agent still has to fetch and verify the passport (for example with the gaig-mcp
`validate_passport` tool). A card or a verified passport is a precondition, never an authorization.

Serve the card at `/.well-known/agent-card.json` (A2A well-known path).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_level_guard import ASK, ActionLevelGuard, GuardDecision  # noqa: E402

PASSPORT_EXTENSION_URI = ("https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/main/"
                          "docs/A2A_PASSPORT_EXTENSION.md")
WELL_KNOWN_PATH = "/.well-known/agent-card.json"


def with_passport_extension(card: dict, *, passport_url: str, trusted_key_url: str,
                            revocation_list_url: str, max_action_level: int, required: bool = False) -> dict:
    if not isinstance(max_action_level, int) or not 0 <= max_action_level <= 5:
        raise ValueError("max_action_level must be an integer from 0 to 5")
    out = copy.deepcopy(card)
    extensions = out.setdefault("capabilities", {}).setdefault("extensions", [])
    extensions[:] = [e for e in extensions if e.get("uri") != PASSPORT_EXTENSION_URI]
    extensions.append({
        "uri": PASSPORT_EXTENSION_URI,
        "description": "Agent Trust Passport: verify before delegating; a verified passport is not an authorization.",
        "required": required,
        "params": {"passportUrl": passport_url, "trustedKeyUrl": trusted_key_url,
                   "revocationListUrl": revocation_list_url, "maxActionLevel": max_action_level,
                   "authorityEffect": "NONE"},
    })
    return out


def passport_reference(card: dict) -> dict | None:
    for ext in (card.get("capabilities") or {}).get("extensions") or []:
        if ext.get("uri") == PASSPORT_EXTENSION_URI:
            return ext.get("params") or {}
    return None


def delegation_decision(card: dict, skill_id: str, guard: ActionLevelGuard) -> GuardDecision:
    """Decide whether to delegate `skill_id` to the agent behind `card`."""
    if skill_id not in {s.get("id") for s in card.get("skills") or []}:
        return GuardDecision(skill_id, 4, ASK, "Skill not on the agent card; ask before delegating", "card")
    ref = passport_reference(card)
    if ref is None:
        return GuardDecision(skill_id, 4, ASK, "No Agent Trust Passport on the card; treat as Level 4", "card")
    decision = guard.decide(skill_id)
    ceiling = ref.get("maxActionLevel")
    if isinstance(ceiling, int) and decision.level > ceiling and decision.decision != "deny":
        return GuardDecision(skill_id, decision.level, "deny",
                             f"Level {decision.level} is above the card's passport ceiling {ceiling}", decision.level_source)
    return decision
