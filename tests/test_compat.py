"""Interface guards: public names, inputs, CLI, import, and authority_effect NONE stay stable."""
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


def test_cli_entry_point_is_gaig_mcp_only():
    eps = {ep.name: ep.value for ep in importlib.metadata.entry_points(group="console_scripts")
           if ep.value.startswith("gaig_mcp.")}
    assert eps == {"gaig-mcp": "gaig_mcp.server:main"}
    assert callable(main)
    assert importlib.metadata.metadata("gaig-mcp")["Name"] == "gaig-mcp"


def test_module_entry_point():
    out = subprocess.run([sys.executable, "-m", "gaig_mcp.server", "--version"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == gaig_mcp.__version__


def test_removed_import_package_is_absent():
    import importlib.util
    import gaig_mcp.core
    assert importlib.util.find_spec("gag_mcp") is None
    assert not hasattr(gaig_mcp.core, "GagInputError")


def test_existing_arguments_still_non_authorizing():
    async def run():
        async with Client(mcp) as c:
            return [await c.call_tool("check_inventory", {"use_sample": True}),
                    await c.call_tool("build_decision_pack", {"use_sample": True}),
                    await c.call_tool("validate_passport", {"example": "signed-revoked"})]
    for r in asyncio.run(run()):
        assert not r.is_error
        assert_non_authorizing(r.structured_content)
