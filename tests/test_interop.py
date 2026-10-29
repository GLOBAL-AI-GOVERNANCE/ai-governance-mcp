"""Interop adapters: MCP registry server.json, A2A card, OpenTelemetry GenAI spans, LangGraph, Gemini CLI, SKILL.md.

SDK-backed tests skip unless the pinned SDKs are installed (see AGENTS.md); CI installs them in the interop job.
"""
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).parents[1]
STACKS = ROOT / "examples" / "agent-stacks"
CONFIGS = ROOT / "examples" / "client-configs"
POLICY = ROOT / "examples" / "policies" / "action-levels.automated-approver.json"
PINNED = ["--from", "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.5.1", "gaig-mcp"]
sys.path.insert(0, str(STACKS))

from action_level_guard import ActionLevelGuard  # noqa: E402


def test_server_json_validates_against_registry_schema():
    import jsonschema
    import tomllib

    schema = json.loads((ROOT / "tests/fixtures/mcp-registry/server.schema.2025-12-11.json").read_text())
    server = json.loads((ROOT / "server.json").read_text())
    jsonschema.validate(server, schema)
    assert server["$schema"] == schema["$id"]
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert server["version"] == version
    assert "packages" not in server  # no package-index install; the README pins a GitHub tag
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**server, "name": "no-slash"}, schema)


def test_skill_md_frontmatter():
    text = (ROOT / "skills/gaig-mcp/SKILL.md").read_text()
    assert text.startswith("---\n")
    front = dict(line.split(": ", 1) for line in text.split("---\n")[1].strip().splitlines())
    assert front["name"] == "gaig-mcp" and len(front["description"]) <= 1024
    assert "@v0.5.1" in text and "authority_effect" in text


def test_agents_md_present():
    text = (ROOT / "AGENTS.md").read_text()
    assert "python -m pytest" in text and "authority_effect" in text


def _hook(event, *args):
    return subprocess.run([sys.executable, str(STACKS / "tool_call_hook.py"), *args], input=json.dumps(event),
                          capture_output=True, text=True, timeout=30)


def test_gemini_cli_settings_and_before_tool_contract():
    settings = json.loads((CONFIGS / "gemini-cli.settings.json").read_text())
    server = settings["mcpServers"]["gaig"]
    assert server["command"] == "uvx" and server["args"] == PINNED and server["trust"] is False
    group = settings["hooks"]["BeforeTool"][0]
    assert group["matcher"] == "mcp_.*" and "tool_call_hook.py" in group["hooks"][0]["command"]
    base = {"hook_event_name": "BeforeTool", "tool_input": {}, "session_id": "s", "cwd": "."}
    allowed = _hook({**base, "tool_name": "mcp_gaig_check_inventory"})
    assert (allowed.returncode, allowed.stdout) == (0, "")
    for tool in ("mcp_crm_send_external_email", "mcp_crm_delete_records", "brand_new_tool"):
        proc = _hook({**base, "tool_name": tool}, "--policy", str(POLICY))
        out = json.loads(proc.stdout)
        assert proc.returncode == 0 and out["decision"] == "deny" and out["reason"]
    approved = _hook({**base, "tool_name": "mcp_github_open_pull_request"}, "--policy", str(POLICY))
    assert (approved.returncode, approved.stdout) == (0, "")


def test_a2a_card_with_passport_extension_parses_in_a2a_sdk():
    pytest.importorskip("a2a")
    from a2a.types import AgentCard
    from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
    from google.protobuf import json_format

    import a2a_passport_card as card_mod

    assert card_mod.WELL_KNOWN_PATH == AGENT_CARD_WELL_KNOWN_PATH
    base = {
        "name": "Research agent", "description": "Drafts findings for review", "version": "1.0.0",
        "supportedInterfaces": [{"url": "https://agents.example.com/research", "protocolBinding": "JSONRPC",
                                 "protocolVersion": "1.0"}],
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text/plain"], "defaultOutputModes": ["text/plain"],
        "skills": [{"id": "draft_findings", "name": "Draft findings", "description": "Draft", "tags": ["research"]},
                   {"id": "send_external_email", "name": "Send email", "description": "Send", "tags": ["email"]},
                   {"id": "publish_report", "name": "Publish", "description": "Publish", "tags": ["report"]}],
    }
    card = card_mod.with_passport_extension(
        base, passport_url="https://agents.example.com/research/passport.json",
        trusted_key_url="https://agents.example.com/keys/passport.pub.pem",
        revocation_list_url="https://agents.example.com/revocations.json", max_action_level=3)
    parsed = json_format.ParseDict(card, AgentCard())  # rejects unknown fields
    ext = parsed.capabilities.extensions[0]
    assert ext.uri == card_mod.PASSPORT_EXTENSION_URI and ext.params["maxActionLevel"] == 3
    assert base["capabilities"] == {"streaming": False}  # input not mutated
    again = card_mod.with_passport_extension(card, passport_url="p", trusted_key_url="k",
                                             revocation_list_url="r", max_action_level=2)
    assert len(again["capabilities"]["extensions"]) == 1

    guard = ActionLevelGuard({"draft_findings": 2, "send_external_email": 4, "publish_report": 4})
    assert card_mod.delegation_decision(card, "draft_findings", guard).decision == "allow"
    over = card_mod.delegation_decision(card, "send_external_email", guard)
    assert over.decision == "deny" and "ceiling 3" in over.reason
    assert card_mod.delegation_decision(base, "draft_findings", guard).decision == "ask"
    assert card_mod.delegation_decision(card, "not_on_card", guard).decision == "ask"
    with pytest.raises(ValueError):
        card_mod.with_passport_extension(base, passport_url="p", trusted_key_url="k", revocation_list_url="r",
                                         max_action_level=6)


def test_otel_genai_tool_span_attributes():
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.trace import SpanKind

    import otel_genai

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("gaig-guard-test")
    guard = ActionLevelGuard.from_json(POLICY)
    for name in ("draft_reply", "mcp__github__open_pull_request", "delete_records"):
        with otel_genai.start_tool_span(tracer, guard.decide(name), agent_name="lead", call_id=f"call_{name}"):
            pass
    spans = exporter.get_finished_spans()
    assert [s.name for s in spans] == ["execute_tool draft_reply", "execute_tool mcp__github__open_pull_request",
                                       "execute_tool delete_records"]
    for span in spans:
        attrs = dict(span.attributes)
        assert span.kind == SpanKind.INTERNAL
        assert attrs["gen_ai.operation.name"] == "execute_tool" and attrs["gen_ai.agent.name"] == "lead"
        assert attrs["gen_ai.tool.call.id"].startswith("call_") and attrs["gaig.authority_effect"] == "NONE"
        assert "gen_ai.tool.call.arguments" not in attrs and "gen_ai.tool.call.result" not in attrs
    assert [dict(s.attributes)["gaig.guard.decision"] for s in spans] == ["allow", "allow", "deny"]
    assert dict(spans[1].attributes)["gaig.guard.approved_by"] == "operator.ci-approver"
    assert "gaig.guard.approved_by" not in dict(spans[0].attributes)


def test_langgraph_passport_gate_runs_in_langgraph():
    pytest.importorskip("langgraph")
    import langgraph_passport_gate as lg

    final = lg.build_graph(lg.AGENTS).invoke({"task": "t", "outputs": {}, "held": {}, "ledger": []})
    assert sorted(final["outputs"]) == ["researcher"] and "REVOKED" in final["held"]["reviewer"]
    assert [e["ran"] for e in final["ledger"]] == [True, False]
