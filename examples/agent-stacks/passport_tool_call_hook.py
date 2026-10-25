#!/usr/bin/env python3
"""PreToolUse command hook that checks the agent's passport and the tool's Action Level before each call.

Status: TESTED (tests/test_passport_guard.py). Not run inside Claude Code or the Grok CLI.
Requires gaig-mcp installed (`gaig_mcp.core.check_tool_call`); the levels come from action_level_guard.py.

One combined check per call, at this machine's clock (there is no caller-supplied time):
  1. the passport verifies VALID (signature, key trust, evidence bundle, validity window);
  2. the signed revocation list was supplied and the revocation check passed;
  3. the tool's Action Level is at or below the passport's reachable level
     (issued maximum, lowered by any temporary restriction).
Then Level 0-3 allow, Level 4 ask, Level 5 deny. Any failed check, missing input, or error denies.

Usage, in the client's hook command:
  passport_tool_call_hook.py --passport passport.json --trusted-key key.json --revocation-list list.json \
      --bundle-manifest bundle/manifest.json --bundle-root bundle [--policy action-levels.json]

Output contracts match tool_call_hook.py: Claude Code (`tool_name`) gets allow / ask / deny;
the Grok CLI (`toolName`) cannot ask, so ask and deny both exit 2 with the reason.
The hook only blocks or forwards calls; it never approves anything (authority_effect NONE).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_level_guard import ALLOW, ASK, DENY, ActionLevelGuard  # noqa: E402

REQUIRED = ("--passport", "--trusted-key", "--revocation-list")
OPTIONAL = ("--bundle-manifest", "--bundle-root", "--policy")


def parse_args(argv: list[str]) -> dict[str, str]:
    opts: dict[str, str] = {}
    it = iter(argv)
    for flag in it:
        if flag not in REQUIRED + OPTIONAL:
            raise ValueError(f"unknown option {flag}")
        opts[flag] = next(it)
    missing = [f for f in REQUIRED if f not in opts]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    return opts


def check(tool: str, opts: dict[str, str]) -> tuple[str, str]:
    from gaig_mcp.core import check_tool_call

    guard = ActionLevelGuard.from_json(opts["--policy"]) if "--policy" in opts else ActionLevelGuard()
    level = guard.decide(tool)
    read = lambda flag: Path(opts[flag]).read_text(encoding="utf-8")  # noqa: E731
    out = check_tool_call(tool, passport=read("--passport"), trusted_key=read("--trusted-key"),
                          revocation_list=read("--revocation-list"),
                          tool_level=level.level if level.level_source == "policy" else None,
                          bundle_manifest=opts.get("--bundle-manifest"), bundle_root=opts.get("--bundle-root"))
    result = out["result"]
    disposition, reason = result["call_disposition"], " ".join(result["reasons"])
    if disposition == ASK and level.approved_by:
        # The passport check passed and only Level 4 approval remained: the operator's automated approver answers it.
        return ALLOW, f"Passport VALID and revocation passed. {level.reason}"
    return disposition, reason


def decide(event: dict, opts: dict[str, str]) -> tuple[dict, int]:
    grok = "toolName" in event
    disposition, reason = check(str(event["toolName"] if grok else event["tool_name"]), opts)
    if disposition == ALLOW:
        return {}, 0
    if grok:
        return {"decision": "deny", "reason": reason}, 2
    out = {"hookEventName": "PreToolUse", "permissionDecision": ASK if disposition == ASK else DENY,
           "permissionDecisionReason": reason}
    return {"hookSpecificOutput": out}, 0


def main(argv: list[str]) -> int:
    try:
        output, code = decide(json.loads(sys.stdin.read()), parse_args(argv))
    except Exception as exc:  # fail closed
        reason = f"Passport guard error, call blocked: {type(exc).__name__}"
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
