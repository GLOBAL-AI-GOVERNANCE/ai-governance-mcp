#!/usr/bin/env python3
"""CrewAI: gate every tool call by Action Level with a before_tool_call hook.

Status: TESTED offline with crewai 1.15.33 — the hook is registered and invoked with
real ToolCallHookContext objects (tests/test_guards.py); skipped when crewai is not
installed. Not run against a live model or a full Crew kickoff.

- Levels 0-3 return None (allow).
- Level 4 returns False (block) by default, or asks a person via
  ``context.request_human_input`` when ``ask_person=True``.
- Level 5 returns False (block).
- Tool output never changes the guard policy; register_after_tool_call keeps the
  decision ledger only.

Run: ``pip install crewai``, then ``python crewai_guard.py`` (demo registers the hook).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from crewai.hooks import (
    ToolCallHookContext,
    clear_before_tool_call_hooks,
    register_after_tool_call_hook,
    register_before_tool_call_hook,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_level_guard import ALLOW, ASK, DENY, ActionLevelGuard  # noqa: E402

PINNED = "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.5.1"
GUARD = ActionLevelGuard()  # add your own tools: ActionLevelGuard({"send_external_email": 4, ...})
DECISIONS: list[dict[str, Any]] = []


def make_before_tool_call(guard: ActionLevelGuard | None = None, *, ask_person: bool = False):
    """Return a CrewAI before_tool_call hook bound to ``guard`` (or the module GUARD)."""
    active = guard if guard is not None else GUARD

    def before_tool_call(context: ToolCallHookContext) -> bool | None:
        decision = active.decide(context.tool_name)
        record = decision.as_record()
        DECISIONS.append(record)
        if decision.decision == ALLOW:
            return None
        if decision.decision == ASK and ask_person:
            answer = context.request_human_input(
                prompt=f"Level 4: approve {context.tool_name}? [y/N]",
            )
            return None if str(answer).strip().lower() in {"y", "yes"} else False
        # ASK (no person) and DENY both block the tool.
        return False

    return before_tool_call


def make_after_tool_call():
    """Ledger-only after hook: never mutates policy, passports, or levels from tool output."""

    def after_tool_call(context: ToolCallHookContext) -> str | None:
        # Intentionally ignore context.tool_result content for policy. Returning None
        # leaves the tool result unchanged; we never rewrite authority or levels here.
        DECISIONS.append({
            "event": "after_tool_call",
            "tool_name": context.tool_name,
            "authority_effect": "NONE",
            "result_length": len(context.tool_result or ""),
        })
        return None

    return after_tool_call


def install(guard: ActionLevelGuard | None = None, *, ask_person: bool = False) -> None:
    """Register the Action Level before/after hooks globally for this process."""
    register_before_tool_call_hook(make_before_tool_call(guard, ask_person=ask_person))
    register_after_tool_call_hook(make_after_tool_call())


def uninstall() -> None:
    clear_before_tool_call_hooks()
    from crewai.hooks import clear_after_tool_call_hooks
    clear_after_tool_call_hooks()


def main() -> None:
    install()
    print("CrewAI Action Level hooks registered for gaig-mcp tools.")
    print(f"Pin MCP with: uvx --from {PINNED} gaig-mcp")
    print("authority_effect remains NONE; Level 5 is always blocked.")


if __name__ == "__main__":
    main()
