"""Compatibility guards: public names, inputs, CLI, import, env vars, and authority_effect NONE stay stable."""
import asyncio
import importlib.metadata
import pathlib
import subprocess
import sys

from mcp import Client

import gag_mcp
from gag_mcp.server import main, mcp
from conftest import assert_non_authorizing

DOCUMENTED_INPUTS = {
    "check_inventory": {"inventory_csv", "use_sample", "evaluation_time"},
    "build_decision_pack": {"inventory_csv", "use_sample", "evaluation_time", "include_documents"},
    "validate_passport": {"example", "passport_json", "trusted_key_json", "revocation_list_json", "at_time"},
}
SRC = pathlib.Path(gag_mcp.__file__).parent


def _tools():
    async def run():
        async with Client(mcp) as c:
            return (await c.list_tools()).tools
    return asyncio.run(run())


def test_tool_names_and_documented_inputs_unchanged():
    tools = {t.name: t for t in _tools()}
    assert set(tools) == set(DOCUMENTED_INPUTS)
    for name, tool in tools.items():
        assert set(tool.input_schema["properties"]) == DOCUMENTED_INPUTS[name], name
        assert tool.annotations.read_only_hint is True and tool.annotations.destructive_hint is False


def test_cli_entry_point_and_import():
    eps = {ep.name: ep.value for ep in importlib.metadata.entry_points(group="console_scripts")}
    assert eps.get("gag-mcp") == "gag_mcp.server:main"
    assert callable(main)
    out = subprocess.run([sys.executable, "-m", "gag_mcp.server", "--version"], capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip() == gag_mcp.__version__ if hasattr(gag_mcp, "__version__") \
        else out.returncode == 0


def test_env_var_names_unchanged():
    text = (SRC / "server.py").read_text() + (SRC / "core.py").read_text()
    for name in ("GAG_MCP_ALLOWED_HOSTS", "GAG_MCP_BEARER_TOKEN", "GAG_MCP_CORS_ORIGINS",
                 "GAG_TOOLKIT_PATH", "GAG_AGENTIC_PATH"):
        assert name in text, name


def test_existing_arguments_still_non_authorizing():
    async def run():
        async with Client(mcp) as c:
            return [await c.call_tool("check_inventory", {"use_sample": True}),
                    await c.call_tool("build_decision_pack", {"use_sample": True}),
                    await c.call_tool("validate_passport", {"example": "signed-revoked"})]
    for r in asyncio.run(run()):
        assert not r.is_error
        assert_non_authorizing(r.structured_content)
