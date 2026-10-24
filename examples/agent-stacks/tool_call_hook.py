#!/usr/bin/env python3
"""PreToolUse command hook for Claude Code and the Grok CLI, backed by action_level_guard.py.

Status: TESTED (tests/test_guards.py pipes recorded-format hook inputs through this script).
Not run inside Claude Code or the Grok CLI.

Reads one hook event as JSON on stdin and writes a decision on stdout:
- Claude Code input (`tool_name`): Level 0-3 allow, Level 4 "ask" (Claude Code prompts you), Level 5 "deny".
- Grok CLI input (`toolName`): Grok hooks cannot ask, so Level 4 and Level 5 are denied with the reason;
  run a Level 4 action yourself or approve it outside the agent.
Any error while deciding also denies, because the Grok CLI lets a call through when a hook crashes.

Optional policy file: `--policy action-levels.json` with `{"tool_name": level, ...}`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_level_guard import ALLOW, ASK, DENY, ActionLevelGuard  # noqa: E402


def decide(event: dict, guard: ActionLevelGuard) -> tuple[dict, int]:
    if "toolName" in event:  # Grok CLI contract
        d = guard.decide(str(event["toolName"]))
        if d.decision == ALLOW:
            return {}, 0
        return {"decision": "deny", "reason": d.reason}, 2
    d = guard.decide(str(event["tool_name"]))  # Claude Code contract
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
