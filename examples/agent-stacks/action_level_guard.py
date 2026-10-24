#!/usr/bin/env python3
"""Action Level guard: decide before each agent tool call whether it may run, needs a person, or is blocked.

Status: TESTED (tests/test_guards.py). Standard library only; copy this file next to your agent code.

Levels follow the Agentic AI Governance action-authority spec (spec/08-action-authority.md):

  0 advisory output            1 read-only access          2 drafts or proposals only
  3 bounded, logged, reversible internal action            4 privileged or externally consequential
  5 destructive, financial, legal, employment, human-safety, critical-infrastructure, or irreversible high-impact

Decisions: Levels 0-3 "allow", Level 4 "ask" (an accountable person approves or rejects the call),
Level 5 "deny". A tool missing from your policy is treated as Level 4, so new or renamed tools wait
for a person instead of running unattended. The guard never approves a Level 4 call by itself.

Tool names are matched as given and after removing a client prefix, so one policy covers
`check_inventory`, `mcp__gaig__check_inventory` (Claude), and `gaig__check_inventory` (Grok CLI).
A fully qualified entry wins over a bare tool name.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

ALLOW, ASK, DENY = "allow", "ask", "deny"
UNKNOWN_TOOL_LEVEL = 4
MAX_UNATTENDED_LEVEL = 3

# gaig-mcp tools are read-only and non-authorizing (authority_effect NONE).
GAIG_MCP_LEVELS: dict[str, int] = {"check_inventory": 1, "build_decision_pack": 1, "validate_passport": 1}


@dataclass(frozen=True)
class GuardDecision:
    tool: str
    level: int
    decision: str
    reason: str
    level_source: str  # "policy" or "unknown-tool default"

    def as_record(self) -> dict:
        return asdict(self)


def bare_name(tool_name: str) -> str:
    """`mcp__gaig__check_inventory` and `gaig__check_inventory` become `check_inventory`."""
    return tool_name.rsplit("__", 1)[-1]


class ActionLevelGuard:
    def __init__(self, levels: Mapping[str, int] | None = None) -> None:
        merged = dict(GAIG_MCP_LEVELS)
        merged.update(levels or {})
        for name, level in merged.items():
            if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= 5:
                raise ValueError(f"Action Level for {name!r} must be an integer from 0 to 5")
        self.levels = merged

    @classmethod
    def from_json(cls, path: str | Path) -> "ActionLevelGuard":
        """Load `{"tool_name": level, ...}` from a JSON file."""
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def level_of(self, tool_name: str) -> tuple[int, str]:
        for key in (tool_name, bare_name(tool_name)):
            if key in self.levels:
                return self.levels[key], "policy"
        return UNKNOWN_TOOL_LEVEL, "unknown-tool default"

    def decide(self, tool_name: str) -> GuardDecision:
        level, source = self.level_of(tool_name)
        if level >= 5:
            return GuardDecision(tool_name, level, DENY, f"Level {level}: blocked; agents may not take this action", source)
        if level == 4:
            return GuardDecision(tool_name, level, ASK, f"Level 4: needs approval from an accountable person ({source})", source)
        return GuardDecision(tool_name, level, ALLOW, f"Level {level}: within unattended limit (Level {MAX_UNATTENDED_LEVEL})", source)

    def unattended_tools(self, tool_names: Iterable[str]) -> list[str]:
        """Tools that may run without a person. Use for `allowed_tools` on hosted MCP connectors."""
        return [name for name in tool_names if self.decide(name).decision == ALLOW]


if __name__ == "__main__":
    guard = ActionLevelGuard({"send_external_email": 4, "delete_records": 5})
    for name in ("mcp__gaig__check_inventory", "send_external_email", "delete_records", "brand_new_tool"):
        print(json.dumps(guard.decide(name).as_record()))
