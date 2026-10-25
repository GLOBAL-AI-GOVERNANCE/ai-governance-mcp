"""Operator-designated automated Level 4 approver: listed Level 4 tools run, everything else is unchanged."""
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).parents[1]
STACKS = ROOT / "examples" / "agent-stacks"
POLICY = ROOT / "examples" / "policies" / "action-levels.automated-approver.json"
sys.path.insert(0, str(STACKS))

from action_level_guard import ActionLevelGuard  # noqa: E402


def test_policy_file_routes_only_listed_level_4_tools():
    guard = ActionLevelGuard.from_json(POLICY)
    approved = guard.decide("mcp__github__open_pull_request")
    assert (approved.decision, approved.level, approved.approved_by) == ("allow", 4, "operator.ci-approver")
    assert "automated approver operator.ci-approver" in approved.reason
    asked = guard.decide("send_external_email")
    assert (asked.decision, asked.approved_by) == ("ask", None)
    assert guard.decide("delete_records").decision == "deny"
    assert guard.decide("draft_reply").decision == "allow" and guard.decide("draft_reply").approved_by is None


def test_unknown_tools_are_never_auto_approved():
    guard = ActionLevelGuard({"open_pull_request": 4},
                             {"type": "automated", "approver_id": "operator.ci", "approve": ["open_pull_request"]})
    assert guard.decide("brand_new_tool").decision == "ask"


def test_default_and_person_approver_keep_asking():
    assert ActionLevelGuard({"open_pull_request": 4}).decide("open_pull_request").decision == "ask"
    person = ActionLevelGuard({"open_pull_request": 4}, {"type": "person"})
    assert person.decide("open_pull_request").decision == "ask"


@pytest.mark.parametrize("config, message", [
    ({"type": "automated", "approver_id": "op", "approve": ["delete_records"]}, "must be listed at Level 4"),
    ({"type": "automated", "approver_id": "op", "approve": ["draft_reply"]}, "must be listed at Level 4"),
    ({"type": "automated", "approver_id": "op", "approve": ["not_in_policy"]}, "must be listed at Level 4"),
    ({"type": "automated", "approve": ["open_pull_request"]}, "needs an approver_id"),
    ({"type": "robot", "approver_id": "op"}, "must be 'person' or 'automated'"),
])
def test_approver_cannot_widen_beyond_level_4(config, message):
    with pytest.raises(ValueError, match=message):
        ActionLevelGuard({"open_pull_request": 4, "delete_records": 5, "draft_reply": 2}, config)


def _hook(event):
    return subprocess.run([sys.executable, str(STACKS / "tool_call_hook.py"), "--policy", str(POLICY)],
                          input=json.dumps(event), capture_output=True, text=True, timeout=30)


def test_claude_code_hook_allows_approved_level_4_with_reason():
    proc = _hook({"hook_event_name": "PreToolUse", "tool_name": "mcp__github__open_pull_request", "tool_input": {}})
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    assert proc.returncode == 0 and out["permissionDecision"] == "allow"
    assert "operator.ci-approver" in out["permissionDecisionReason"]
    asked = json.loads(_hook({"hook_event_name": "PreToolUse", "tool_name": "send_external_email"}).stdout)
    assert asked["hookSpecificOutput"]["permissionDecision"] == "ask"
    denied = json.loads(_hook({"hook_event_name": "PreToolUse", "tool_name": "delete_records"}).stdout)
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_grok_cli_hook_allows_approved_level_4_only():
    assert _hook({"hookEventName": "PreToolUse", "toolName": "github__open_pull_request"}).returncode == 0
    assert _hook({"hookEventName": "PreToolUse", "toolName": "crm__send_external_email"}).returncode == 2
    assert _hook({"hookEventName": "PreToolUse", "toolName": "crm__delete_records"}).returncode == 2
