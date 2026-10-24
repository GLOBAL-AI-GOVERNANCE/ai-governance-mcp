"""Action Level guard examples: core decisions, hook contracts, hosted-MCP request shapes, SDK adapters."""
import asyncio
import json
import pathlib
import subprocess
import sys
import tomllib

import pytest

ROOT = pathlib.Path(__file__).parents[1]
STACKS = ROOT / "examples" / "agent-stacks"
CONFIGS = ROOT / "examples" / "client-configs"
PINNED = ["--from", "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.3.0", "gaig-mcp"]
sys.path.insert(0, str(STACKS))

from action_level_guard import ActionLevelGuard  # noqa: E402
import remote_mcp_guard as remote  # noqa: E402

POLICY = {"send_external_email": 4, "delete_records": 5, "draft_reply": 2}


def test_levels_map_to_allow_ask_deny():
    guard = ActionLevelGuard(POLICY)
    assert [guard.decide(n).decision for n in ("draft_reply", "send_external_email", "delete_records")] == [
        "allow", "ask", "deny"]
    for name in ("check_inventory", "build_decision_pack", "validate_passport"):
        assert guard.decide(name).level == 1


def test_unknown_tools_wait_for_a_person():
    decision = ActionLevelGuard().decide("brand_new_tool")
    assert (decision.level, decision.decision, decision.level_source) == (4, "ask", "unknown-tool default")


def test_client_prefixes_and_qualified_entries():
    guard = ActionLevelGuard({**POLICY, "mcp__sandbox__delete_records": 3})
    assert guard.decide("mcp__gaig__check_inventory").decision == "allow"
    assert guard.decide("gaig__check_inventory").decision == "allow"
    assert guard.decide("crm__delete_records").decision == "deny"
    assert guard.decide("mcp__sandbox__delete_records").decision == "allow"


@pytest.mark.parametrize("bad", [6, -1, True, "4", 2.5])
def test_invalid_levels_are_rejected(bad):
    with pytest.raises(ValueError):
        ActionLevelGuard({"tool": bad})


def _hook(event, *args):
    return subprocess.run([sys.executable, str(STACKS / "tool_call_hook.py"), *args],
                          input=event if isinstance(event, str) else json.dumps(event),
                          capture_output=True, text=True, timeout=30)


def test_claude_code_hook_contract(tmp_path):
    policy = tmp_path / "levels.json"
    policy.write_text(json.dumps(POLICY))
    base = {"hook_event_name": "PreToolUse", "tool_input": {}, "tool_use_id": "t1"}
    allowed = _hook({**base, "tool_name": "mcp__gaig__check_inventory"}, "--policy", str(policy))
    assert (allowed.returncode, allowed.stdout) == (0, "")
    for tool, expected in (("mcp__crm__send_external_email", "ask"), ("mcp__crm__delete_records", "deny")):
        proc = _hook({**base, "tool_name": tool}, "--policy", str(policy))
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        assert proc.returncode == 0 and out["hookEventName"] == "PreToolUse"
        assert out["permissionDecision"] == expected and out["permissionDecisionReason"]


def test_grok_cli_hook_contract():
    base = {"hookEventName": "PreToolUse", "toolInput": {}}
    assert _hook({**base, "toolName": "gaig__validate_passport"}).returncode == 0
    proc = _hook({**base, "toolName": "crm__send_external_email"})
    assert proc.returncode == 2 and json.loads(proc.stdout)["decision"] == "deny"


def test_hook_fails_closed_on_bad_input():
    for event in ("not json", "{}"):
        proc = _hook(event)
        out = json.loads(proc.stdout)
        assert proc.returncode == 2 and out["decision"] == "deny"
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hosted_mcp_request_shapes():
    guard = ActionLevelGuard({"validate_passport": 4, "build_decision_pack": 5})
    openai = remote.openai_mcp_tool("https://h/mcp", "T", guard=guard)
    assert openai["allowed_tools"] == ["check_inventory", "validate_passport"]
    assert openai["require_approval"] == {"never": {"tool_names": ["check_inventory"]}}
    anthropic = remote.anthropic_mcp_request_parts("https://h/mcp", "T", guard=guard)
    toolset = anthropic["tools"][0]
    assert toolset["type"] == "mcp_toolset" and toolset["default_config"] == {"enabled": False}
    assert toolset["configs"] == {"check_inventory": {"enabled": True}}
    assert anthropic["mcp_servers"][0]["authorization_token"] == "T"
    xai = remote.xai_mcp_tool("https://h/mcp", "T", guard=guard)
    assert xai["allowed_tools"] == ["check_inventory"] and "require_approval" not in xai
    only_l4 = ActionLevelGuard({n: 4 for n in remote.GAIG_TOOLS})
    assert remote.openai_mcp_tool("https://h/mcp", "T", guard=only_l4)["require_approval"] == "always"
    for build in (remote.anthropic_mcp_request_parts, remote.xai_mcp_tool):
        with pytest.raises(ValueError):
            build("https://h/mcp", "T", guard=only_l4)
    with pytest.raises(ValueError):
        remote.openai_mcp_tool("https://h/mcp", "T", guard=ActionLevelGuard({n: 5 for n in remote.GAIG_TOOLS}))


def test_openai_approval_answers_never_approve_level_5():
    guard = ActionLevelGuard(POLICY)
    items = [{"type": "mcp_approval_request", "id": "a1", "name": "send_external_email", "arguments": "{}"},
             {"type": "mcp_approval_request", "id": "a2", "name": "delete_records", "arguments": "{}"},
             {"type": "message", "id": "m1"}]
    answers = remote.answer_openai_approvals(items, approve=lambda item: True, guard=guard)
    assert answers == [{"type": "mcp_approval_response", "approval_request_id": "a1", "approve": True},
                       {"type": "mcp_approval_response", "approval_request_id": "a2", "approve": False}]
    assert remote.answer_openai_approvals(items[:1], approve=lambda item: False, guard=guard)[0]["approve"] is False


def test_new_client_configs():
    server = json.loads((CONFIGS / "claude-code.mcp.json").read_text())["mcpServers"]["gaig"]
    assert server["command"] == "uvx" and server["args"] == PINNED
    grok = tomllib.loads((CONFIGS / "grok-cli.config.toml").read_text())["mcp_servers"]["gaig"]
    assert grok["command"] == "uvx" and grok["args"] == PINNED
    for name, script in (("claude-code.settings.json", ".claude/hooks/tool_call_hook.py"),
                         ("grok-cli.hooks.json", ".grok/hooks/tool_call_hook.py")):
        hook = json.loads((CONFIGS / name).read_text())["hooks"]["PreToolUse"][0]["hooks"][0]
        assert hook["type"] == "command" and script in hook["command"]


def test_claude_agent_sdk_hook():
    pytest.importorskip("claude_agent_sdk")
    import claude_agent_sdk_guard as claude

    claude.GUARD = ActionLevelGuard(POLICY)
    run = lambda name: asyncio.run(claude.action_level_hook(  # noqa: E731
        {"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": {}}, "t1", None))
    assert run("mcp__gaig__check_inventory") == {}
    assert run("mcp__crm__send_external_email")["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert run("mcp__crm__delete_records")["hookSpecificOutput"]["permissionDecision"] == "deny"
    matcher = claude.options().hooks["PreToolUse"][0]
    assert matcher.matcher == "mcp__.*" and matcher.hooks == [claude.action_level_hook]


def test_openai_agents_sdk_end_to_end_with_scripted_model():
    """Real gaig-mcp stdio server and real Agents SDK runner; only the model is scripted."""
    pytest.importorskip("agents")
    from agents import Agent, set_tracing_disabled
    from agents.items import ModelResponse
    from agents.models.interface import Model
    from agents.usage import Usage
    from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

    import openai_agents_guard as oa

    set_tracing_disabled(True)
    oa.GUARD = ActionLevelGuard({"validate_passport": 4, "build_decision_pack": 5})
    seen = {}

    class ScriptedModel(Model):
        def __init__(self):
            self.turn = 0

        async def get_response(self, *args, **kwargs):
            self.turn += 1
            if self.turn == 1:
                calls = [ResponseFunctionToolCall(type="function_call", id=f"fc{i}", call_id=f"c{i}", name=n,
                                                  arguments=a, status="completed")
                         for i, (n, a) in enumerate((("check_inventory", "{\"use_sample\": true}"), ("validate_passport", "{}"),
                                                     ("build_decision_pack", "{}")))]
                return ModelResponse(output=calls, usage=Usage(), response_id=None)
            for item in kwargs["input"]:
                if isinstance(item, dict) and item.get("type") == "function_call_output":
                    seen[item["call_id"]] = str(item["output"])
            text = ResponseOutputText(type="output_text", text="done", annotations=[])
            msg = ResponseOutputMessage(type="message", id="m", role="assistant", status="completed", content=[text])
            return ModelResponse(output=[msg], usage=Usage(), response_id=None)

        def stream_response(self, *args, **kwargs):
            raise NotImplementedError

    async def scenario():
        server = oa.gaig_server({"command": sys.executable, "args": ["-m", "gaig_mcp.server"]})
        async with server:
            agent = Agent(name="t", mcp_servers=[server], model=ScriptedModel())
            asked = []
            final = await oa.run_with_human_review(agent, "go", lambda item: asked.append(item.tool_name) or False)
            return final, asked

    final, asked = asyncio.run(scenario())
    assert final == "done"
    assert asked == ["validate_passport"]
    assert '"authority_effect": "NONE"' in seen["c0"].replace("\\", "")  # Level 1 ran
    assert "authority_effect" not in seen["c1"]  # Level 4 rejected by the person
    assert "Level 5: blocked" in seen["c2"]  # Level 5 rejected by the guardrail
