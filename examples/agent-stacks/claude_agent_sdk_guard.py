#!/usr/bin/env python3
"""Claude Agent SDK (Python): gate every tool call by Action Level with a PreToolUse hook.

Status: TESTED offline with claude-agent-sdk 0.2.174: the hook is called with recorded-format
PreToolUse inputs and the options object is built (tests/test_guards.py, skipped when the SDK is not
installed). Not run against Claude.

Level 0-3 calls continue through the SDK's normal permission flow, Level 4 returns "ask" so a person
decides, and Level 5 returns "deny". gaig-mcp tools appear to Claude as `mcp__gaig__<tool>`.
Run: `pip install claude-agent-sdk`, sign in or set ANTHROPIC_API_KEY, then `python claude_agent_sdk_guard.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_level_guard import ALLOW, ActionLevelGuard  # noqa: E402

PINNED = "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.4.0"
GUARD = ActionLevelGuard()  # add your own tools: ActionLevelGuard({"mcp__crm__send_email": 4, ...})


async def action_level_hook(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
    decision = GUARD.decide(input_data["tool_name"])
    if decision.decision == ALLOW:
        return {}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision.decision,
                                   "permissionDecisionReason": decision.reason}}


def options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        mcp_servers={"gaig": {"type": "stdio", "command": "uvx", "args": ["--from", PINNED, "gaig-mcp"]}},
        hooks={"PreToolUse": [HookMatcher(matcher="mcp__.*", hooks=[action_level_hook])]},
    )


async def main() -> None:
    from claude_agent_sdk import query
    async for message in query(prompt="Use gaig to check the sample AI inventory and list critical findings.",
                               options=options()):
        print(message)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
