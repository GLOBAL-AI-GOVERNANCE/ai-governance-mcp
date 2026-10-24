"""Compatibility guards: public names, inputs, CLI, import, env vars, and authority_effect NONE stay stable."""
import asyncio
import importlib.metadata
import subprocess
import sys

from mcp import Client

import gaig_mcp
from gaig_mcp.server import main, mcp
from conftest import assert_non_authorizing

DOCUMENTED_INPUTS = {
    "check_inventory": {"inventory_csv", "use_sample", "evaluation_time"},
    "build_decision_pack": {"inventory_csv", "use_sample", "evaluation_time", "include_documents"},
    "validate_passport": {"example", "passport_json", "trusted_key_json", "revocation_list_json", "at_time"},
}


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


def test_cli_entry_points_primary_and_deprecated_alias():
    eps = {ep.name: ep.value for ep in importlib.metadata.entry_points(group="console_scripts")}
    assert eps.get("gaig-mcp") == "gaig_mcp.server:main"
    assert eps.get("gag-mcp") == "gaig_mcp.server:main"
    assert callable(main)


def test_module_entry_points_primary_and_deprecated_alias():
    for module in ("gaig_mcp.server", "gag_mcp.server"):
        out = subprocess.run([sys.executable, "-m", module, "--version"], capture_output=True, text=True)
        assert out.returncode == 0, (module, out.stderr)
        assert out.stdout.strip() == gaig_mcp.__version__, module


def test_deprecated_import_package_is_the_same_module():
    import gag_mcp
    import gag_mcp.core
    import gag_mcp.server
    import gaig_mcp.core
    import gaig_mcp.server
    assert gag_mcp.__version__ == gaig_mcp.__version__
    assert gag_mcp.core is gaig_mcp.core
    assert gag_mcp.server is gaig_mcp.server
    assert gaig_mcp.core.GagInputError is gaig_mcp.core.GaigInputError


def test_existing_arguments_still_non_authorizing():
    async def run():
        async with Client(mcp) as c:
            return [await c.call_tool("check_inventory", {"use_sample": True}),
                    await c.call_tool("build_decision_pack", {"use_sample": True}),
                    await c.call_tool("validate_passport", {"example": "signed-revoked"})]
    for r in asyncio.run(run()):
        assert not r.is_error
        assert_non_authorizing(r.structured_content)
