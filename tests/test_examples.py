import json
import pathlib
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).parents[1]
CONFIGS = ROOT / "examples" / "client-configs"
STACKS = ROOT / "examples" / "agent-stacks"
PINNED = ["--from", "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.1.0", "gag-mcp"]


def test_cursor_config_launches_pinned_command():
    server = json.loads((CONFIGS / "cursor.mcp.json").read_text())["mcpServers"]["gag"]
    assert server["command"] == "uvx" and server["args"] == PINNED


def test_vscode_config_launches_pinned_command():
    server = json.loads((CONFIGS / "vscode.mcp.json").read_text())["servers"]["gag"]
    assert server["type"] == "stdio" and server["command"] == "uvx" and server["args"] == PINNED


def test_codex_config_launches_pinned_command():
    server = tomllib.loads((CONFIGS / "codex.config.toml").read_text())["mcp_servers"]["gag"]
    assert server["command"] == "uvx" and server["args"] == PINNED


def _run(name: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(STACKS / name)], capture_output=True, text=True, timeout=120)


def test_mcp_client_loop_example():
    proc = _run("mcp_client_loop.py")
    assert proc.returncode == 0, proc.stderr
    assert "validate_passport signed-revoked: REVOKED" in proc.stdout
    assert "validate_passport signed-unrevoked: VALID" in proc.stdout


def test_passport_gate_example():
    proc = _run("passport_gate_graph.py")
    assert proc.returncode == 0, proc.stderr
    assert "ran: ['researcher']" in proc.stdout
    assert "passport status REVOKED" in proc.stdout


def test_untested_examples_are_labelled():
    for name in ("openai_agents_sdk.py", "anthropic_tool_use.py"):
        assert "Status: untested." in (STACKS / name).read_text()
