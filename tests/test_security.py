"""Security regressions: fail-closed HTTP binding, uniform 401, sanitized errors, unknown-argument rejection."""
import asyncio
import os
import subprocess
import sys

import httpx
import pytest
from mcp import Client

from gag_mcp import core
from gag_mcp.server import build_http_app, mcp
from conftest import GAP_CSV, assert_non_authorizing

SECRET = "sk-REGRESSION-SECRET-7731"


def _call(name, args):
    async def run():
        async with Client(mcp) as c:
            return await c.call_tool(name, args)
    return asyncio.run(run())


def _text(result):
    return " ".join(getattr(part, "text", "") for part in result.content)


# A. Host / DNS-rebinding ----------------------------------------------------
def test_non_loopback_bind_without_allowed_hosts_fails_closed(monkeypatch):
    monkeypatch.delenv("GAG_MCP_ALLOWED_HOSTS", raising=False)
    with pytest.raises(ValueError, match="GAG_MCP_ALLOWED_HOSTS"):
        build_http_app("0.0.0.0")


def test_non_loopback_bind_with_allowed_hosts_starts(monkeypatch):
    monkeypatch.setenv("GAG_MCP_ALLOWED_HOSTS", "mcp.example.org")
    assert build_http_app("0.0.0.0") is not None


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_loopback_default_unchanged(monkeypatch, host):
    monkeypatch.delenv("GAG_MCP_ALLOWED_HOSTS", raising=False)
    assert build_http_app(host) is not None


def test_cli_refuses_public_bind_without_allowed_hosts():
    env = {k: v for k, v in os.environ.items() if k != "GAG_MCP_ALLOWED_HOSTS"}
    proc = subprocess.run([sys.executable, "-m", "gag_mcp.server", "--http", "--host", "0.0.0.0", "--port", "0"],
                          env=env, capture_output=True, text=True, timeout=20)
    assert proc.returncode != 0
    assert "GAG_MCP_ALLOWED_HOSTS" in proc.stderr


# B. Bearer auth: uniform 401, token never echoed -----------------------------
def test_unauthorized_responses_are_uniform(http_server):
    token = "correct-token-abc"
    base = http_server({"GAG_MCP_BEARER_TOKEN": token})
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    accept = "application/json, text/event-stream"
    variants = [{}, {"authorization": f"Bearer {SECRET}"}, {"authorization": f"Basic {SECRET}"},
                {"authorization": "Bearer " + token[:-1]}]
    seen = set()
    for extra in variants:
        r = httpx.post(base + "/mcp", json=body, headers={"accept": accept, **extra})
        assert r.status_code == 401
        assert SECRET not in r.text and token not in r.text
        seen.add((r.text, r.headers.get("www-authenticate")))
    assert seen == {('{"error": "unauthorized"}', "Bearer")}
    ok = httpx.post(base + "/mcp", headers={"accept": accept, "authorization": f"Bearer {token}"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "t", "version": "1"}}})
    assert ok.status_code == 200


# C. Error data never reflects caller values, paths, or tracebacks -------------
def test_toolkit_enum_error_keeps_category_not_value():
    with pytest.raises(core.GagInputError) as exc:
        core.check_inventory(GAP_CSV.replace("Regulated,Yes", f"Regulated,{SECRET}"))
    msg = str(exc.value)
    assert SECRET not in msg
    assert "INVALID_ENUM_VALUE" in msg and "impact_people" in msg and "Yes" in msg


def test_toolkit_unknown_column_error_does_not_echo_header():
    header = GAP_CSV.splitlines()[0].replace("owner", f"owner_{SECRET}")
    with pytest.raises(core.GagInputError) as exc:
        core.check_inventory(header + "\n" + GAP_CSV.splitlines()[1] + "\n")
    assert SECRET not in str(exc.value) and "UNKNOWN_COLUMN" in str(exc.value)


def test_validator_stderr_is_not_returned(monkeypatch):
    leak = f"Traceback (most recent call last):\n  File \"/srv/private/{SECRET}.py\""
    monkeypatch.setattr(core.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="", stderr=leak))
    with pytest.raises(core.GagInputError) as exc:
        core.validate_passport(example="signed-revoked")
    assert SECRET not in str(exc.value) and "Traceback" not in str(exc.value)


def test_argument_type_error_does_not_echo_value():
    r = _call("check_inventory", {"use_sample": SECRET})
    assert r.is_error and SECRET not in _text(r) and "use_sample" in _text(r)


def test_enum_argument_error_lists_allowed_values_not_value():
    r = _call("validate_passport", {"example": SECRET})
    assert r.is_error and SECRET not in _text(r)
    assert "signed-revoked" in _text(r)


# D. Unknown arguments are rejected; documented argument shapes still work -----
def test_unknown_argument_rejected_without_echo():
    r = _call("check_inventory", {"use_sample": True, SECRET: True})
    assert r.is_error and SECRET not in _text(r) and "unsupported argument" in _text(r)


def test_schemas_forbid_additional_properties():
    async def run():
        async with Client(mcp) as c:
            return (await c.list_tools()).tools
    for tool in asyncio.run(run()):
        assert tool.input_schema.get("additionalProperties") is False, tool.name


def test_strict_profile_argument_shape_still_accepted():
    for name, args in [
        ("check_inventory", {"inventory_csv": None, "use_sample": True, "evaluation_time": None}),
        ("build_decision_pack", {"inventory_csv": None, "use_sample": True, "evaluation_time": None,
                                 "include_documents": False}),
        ("validate_passport", {"example": "signed-revoked", "passport_json": None, "trusted_key_json": None,
                               "revocation_list_json": None, "at_time": None}),
    ]:
        r = _call(name, args)
        assert not r.is_error, _text(r)
        assert_non_authorizing(r.structured_content)
