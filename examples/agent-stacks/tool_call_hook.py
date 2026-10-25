#!/usr/bin/env python3
"""PreToolUse / BeforeTool command hook for Claude Code, the Grok CLI and the Gemini CLI, backed by action_level_guard.py.

Status: TESTED (tests/test_guards.py pipes recorded-format hook inputs through this script).
Not run inside Claude Code, the Grok CLI or the Gemini CLI.

Reads one hook event as JSON on stdin and writes a decision on stdout:
- Claude Code input (`tool_name`): Level 0-3 allow, Level 4 "ask" (Claude Code prompts you), Level 5 "deny".
- Grok CLI input (`toolName`): Grok hooks cannot ask, so Level 4 and Level 5 are denied with the reason,
  unless the operator's automated approver lists that Level 4 tool.
- Gemini CLI input (`hook_event_name` "BeforeTool"): Gemini hooks allow or deny, so Level 4 and Level 5
  are denied with the reason (JSON on stdout, exit 0), unless the automated approver lists that Level 4 tool.
Any error while deciding also denies, because the Grok CLI lets a call through when a hook crashes.

Optional policy file: `--policy action-levels.json` with `{"tool_name": level, ...}`, or the form with
`level_4_approver` (see action_level_guard.py). A Level 4 tool the operator's automated approver lists is
allowed with the approver named in the reason, in every client contract above.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_level_guard import ALLOW, ASK, DENY, ActionLevelGuard  # noqa: E402


def gemini_name(tool_name: str) -> str:
    """Gemini CLI names MCP tools `mcp_<server>_<tool>`; map to `mcp__<server>__<tool>` (server alias without `_`)."""
    if tool_name.startswith("mcp_") and "__" not in tool_name and tool_name.count("_") >= 2:
        _, server, tool = tool_name.split("_", 2)
        return f"mcp__{server}__{tool}"
    return tool_name


def decide(event: dict, guard: ActionLevelGuard) -> tuple[dict, int]:
    if event.get("hook_event_name") == "BeforeTool":  # Gemini CLI contract: allow or deny, no ask
        d = guard.decide(gemini_name(str(event["tool_name"])))
        if d.decision == ALLOW:
            return {}, 0
        return {"decision": "deny", "reason": d.reason}, 0
    if "toolName" in event:  # Grok CLI contract
        d = guard.decide(str(event["toolName"]))
        if d.decision == ALLOW:
            return {}, 0
        return {"decision": "deny", "reason": d.reason}, 2
    d = guard.decide(str(event["tool_name"]))  # Claude Code contract
    if d.decision == ALLOW and d.approved_by:  # Level 4 approved by the operator's automated approver
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                       "permissionDecisionReason": d.reason}}, 0
    if d.decision == ALLOW:
        return {}, 0
    out = {"hookEventName": "PreToolUse", "permissionDecision": ASK if d.decision == ASK else DENY,
           "permissionDecisionReason": d.reason}
    return {"hookSpecificOutput": out}, 0


def main(argv: list[str]) -> int:
    try:
        guard = ActionLevelGuard.from_json(argv[argv.index("--policy") + 1]) if "--policy" in argv else ActionLevelGuard()
        output, code = decide(json.loads(sys.stdin.read()), guard)
    except Exception as exc:  # fail closed
        reason = f"Action Level guard error, call blocked: {type(exc).__name__}"
        output = {"decision": "deny", "reason": reason,
                  "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                         "permissionDecisionReason": reason}}
        code = 2
    if output:
        print(json.dumps(output))
    if code:
        print(output.get("reason") or output["hookSpecificOutput"]["permissionDecisionReason"], file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
