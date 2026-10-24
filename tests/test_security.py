"""Security regressions: fail-closed HTTP binding, uniform 401, sanitized errors, unknown-argument rejection."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from mcp import Client

from gaig_mcp import core
from gaig_mcp.server import build_http_app, mcp
from conftest import GAP_CSV, assert_non_authorizing

SECRET = "sk-REGRESSION-SECRET-7731"
GOOD_TOKEN = "t0k3n-" + "x" * 40


def _call(name, args):
    async def run():
        async with Client(mcp) as c:
            return await c.call_tool(name, args)
    return asyncio.run(run())


def _text(result):
    return " ".join(getattr(part, "text", "") for part in result.content)


# A. Host / DNS-rebinding ----------------------------------------------------
def test_non_loopback_bind_without_allowed_hosts_fails_closed(monkeypatch):
    monkeypatch.delenv("GAIG_MCP_ALLOWED_HOSTS", raising=False)
    with pytest.raises(ValueError, match="GAIG_MCP_ALLOWED_HOSTS"):
        build_http_app("0.0.0.0")


def test_non_loopback_bind_with_allowed_hosts_and_token_starts(monkeypatch):
    monkeypatch.setenv("GAIG_MCP_ALLOWED_HOSTS", "mcp.example.org")
    monkeypatch.setenv("GAIG_MCP_BEARER_TOKEN", GOOD_TOKEN)
    assert build_http_app("0.0.0.0") is not None


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_loopback_default_unchanged(monkeypatch, host):
    monkeypatch.delenv("GAIG_MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("GAIG_MCP_BEARER_TOKEN", raising=False)
    assert build_http_app(host) is not None


def test_cli_refuses_public_bind_without_allowed_hosts():
    env = {k: v for k, v in os.environ.items() if k != "GAIG_MCP_ALLOWED_HOSTS"}
    env["GAIG_MCP_BEARER_TOKEN"] = GOOD_TOKEN
    proc = subprocess.run([sys.executable, "-m", "gaig_mcp.server", "--http", "--host", "0.0.0.0", "--port", "0"],
                          env=env, capture_output=True, text=True, timeout=20)
    assert proc.returncode != 0
    assert "GAIG_MCP_ALLOWED_HOSTS" in proc.stderr


# B. Bearer auth: uniform 401, token never echoed -----------------------------
def test_unauthorized_responses_are_uniform(http_server):
    token = "correct-token-abc"
    base = http_server({"GAIG_MCP_BEARER_TOKEN": token})
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
    with pytest.raises(core.GaigInputError) as exc:
        core.check_inventory(GAP_CSV.replace("Regulated,Yes", f"Regulated,{SECRET}"))
    msg = str(exc.value)
    assert SECRET not in msg
    assert "INVALID_ENUM_VALUE" in msg and "impact_people" in msg and "Yes" in msg


def test_toolkit_unknown_column_error_does_not_echo_header():
    header = GAP_CSV.splitlines()[0].replace("owner", f"owner_{SECRET}")
    with pytest.raises(core.GaigInputError) as exc:
        core.check_inventory(header + "\n" + GAP_CSV.splitlines()[1] + "\n")
    assert SECRET not in str(exc.value) and "UNKNOWN_COLUMN" in str(exc.value)


def test_validator_stderr_is_not_returned(monkeypatch):
    leak = f"Traceback (most recent call last):\n  File \"/srv/private/{SECRET}.py\""
    monkeypatch.setattr(core.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="", stderr=leak))
    with pytest.raises(core.GaigInputError) as exc:
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


# E. Non-loopback HTTP requires a bearer token (secure by default) --------------
def test_non_loopback_bind_without_token_fails_closed(monkeypatch):
    monkeypatch.setenv("GAIG_MCP_ALLOWED_HOSTS", "mcp.example.org")
    monkeypatch.delenv("GAIG_MCP_BEARER_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GAIG_MCP_BEARER_TOKEN"):
        build_http_app("0.0.0.0")


@pytest.mark.parametrize("weak", ["", "   ", "short-token", SECRET])
def test_non_loopback_bind_with_weak_token_fails_closed_without_echo(monkeypatch, weak):
    monkeypatch.setenv("GAIG_MCP_ALLOWED_HOSTS", "mcp.example.org")
    monkeypatch.setenv("GAIG_MCP_BEARER_TOKEN", weak)
    with pytest.raises(ValueError, match="GAIG_MCP_BEARER_TOKEN") as exc:
        build_http_app("0.0.0.0")
    if weak.strip():
        assert weak not in str(exc.value)


def test_cli_refuses_public_bind_without_token():
    env = {k: v for k, v in os.environ.items() if k != "GAIG_MCP_BEARER_TOKEN"}
    env["GAIG_MCP_ALLOWED_HOSTS"] = "mcp.example.org"
    proc = subprocess.run([sys.executable, "-m", "gaig_mcp.server", "--http", "--host", "0.0.0.0", "--port", "0"],
                          env=env, capture_output=True, text=True, timeout=20)
    assert proc.returncode == 2
    assert "GAIG_MCP_BEARER_TOKEN" in proc.stderr


def test_cli_weak_token_error_does_not_echo_token():
    env = dict(os.environ, GAIG_MCP_ALLOWED_HOSTS="mcp.example.org", GAIG_MCP_BEARER_TOKEN=SECRET)
    proc = subprocess.run([sys.executable, "-m", "gaig_mcp.server", "--http", "--host", "0.0.0.0", "--port", "0"],
                          env=env, capture_output=True, text=True, timeout=20)
    assert proc.returncode == 2
    assert SECRET not in proc.stderr + proc.stdout


def test_network_bind_enforces_token_and_hosts(http_server):
    """Real non-loopback bind (0.0.0.0): missing/wrong token -> uniform 401 with no echo; foreign Host rejected."""
    base = http_server({"GAIG_MCP_ALLOWED_HOSTS": "mcp.example.org", "GAIG_MCP_BEARER_TOKEN": GOOD_TOKEN},
                       bind="0.0.0.0")
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    accept = "application/json, text/event-stream"
    good_host = {"accept": accept, "host": "mcp.example.org"}
    for extra in ({}, {"authorization": f"Bearer {SECRET}"}, {"authorization": SECRET}):
        r = httpx.post(base + "/mcp", json=init, headers={**good_host, **extra})
        assert r.status_code == 401 and r.text == '{"error": "unauthorized"}'
        assert SECRET not in r.text and GOOD_TOKEN not in r.text
    auth = {"authorization": f"Bearer {GOOD_TOKEN}"}
    bad = httpx.post(base + "/mcp", json=init, headers={"accept": accept, "host": f"{SECRET}.evil.test", **auth})
    assert bad.status_code in (400, 421) and SECRET not in bad.text
    ok = httpx.post(base + "/mcp", json=init, headers={**good_host, **auth})
    assert ok.status_code == 200


def test_loopback_without_token_still_serves(http_server, monkeypatch):
    monkeypatch.delenv("GAIG_MCP_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("GAIG_MCP_ALLOWED_HOSTS", raising=False)
    base = http_server()
    r = httpx.post(base + "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                   headers={"accept": "application/json, text/event-stream"})
    assert r.status_code == 200


@pytest.mark.parametrize("allowed", ["random-words.trycloudflare.com", "localhost,mcp.example.org"])
def test_loopback_bind_with_public_allowed_host_requires_token(monkeypatch, allowed):
    """A tunnel or proxy to a loopback bind is still network exposure: no anonymous mode."""
    monkeypatch.setenv("GAIG_MCP_ALLOWED_HOSTS", allowed)
    monkeypatch.delenv("GAIG_MCP_BEARER_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GAIG_MCP_BEARER_TOKEN"):
        build_http_app("127.0.0.1")
    monkeypatch.setenv("GAIG_MCP_BEARER_TOKEN", GOOD_TOKEN)
    assert build_http_app("127.0.0.1") is not None


@pytest.mark.parametrize("allowed", ["localhost", "127.0.0.1:8000", "[::1]:*", "localhost:*,127.0.0.1"])
def test_loopback_bind_with_loopback_allowed_hosts_needs_no_token(monkeypatch, allowed):
    monkeypatch.setenv("GAIG_MCP_ALLOWED_HOSTS", allowed)
    monkeypatch.delenv("GAIG_MCP_BEARER_TOKEN", raising=False)
    assert build_http_app("127.0.0.1") is not None


def test_foreign_host_rejected_on_default_loopback(http_server, monkeypatch):
    monkeypatch.delenv("GAIG_MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("GAIG_MCP_BEARER_TOKEN", raising=False)
    base = http_server()
    r = httpx.post(base + "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                   headers={"accept": "application/json, text/event-stream", "host": "random-words.trycloudflare.com"})
    assert r.status_code == 421


def test_caller_supplied_passport_json_strings_reach_the_validator():
    # Regression: the SDK pre-parsed JSON-object strings in optional text fields into dicts, which were then
    # rejected as "Input should be a valid string", so caller-supplied passports could never be verified.
    examples = core.agentic_root() / "examples"
    args = {"passport_json": (examples / "passports/signed-unrevoked.json").read_text(),
            "trusted_key_json": (examples / "trusted-keys/test-ed25519-key.json").read_text(),
            "revocation_list_json": (examples / "revocation/valid-revocation-list.json").read_text(),
            "at_time": "2026-07-01T00:00:00Z"}
    result = _call("validate_passport", args)
    assert not result.is_error, _text(result)
    out = result.structured_content
    assert_non_authorizing(out)
    assert out["result"]["mode"].startswith("caller-supplied passport")
    assert out["result"]["verification"]["fully_validated"] is False
    assert out["result"]["verification"]["reference_policy_disposition"] == "NOT_PERMITTED"


def test_caller_supplied_passport_object_is_still_rejected():
    result = _call("validate_passport", {"passport_json": {"schema": "x"}, "trusted_key_json": "{}"})
    assert result.is_error
    assert "valid string" in _text(result)


def test_missing_required_column_points_to_example_without_echo():
    with pytest.raises(core.GaigInputError) as exc:
        core.check_inventory(f"system_id,system_name\nA-1,{SECRET}\n")
    msg = str(exc.value)
    assert SECRET not in msg
    prefix, _, hint = msg.partition("}} ")
    error = json.loads(prefix.removeprefix("Inventory rejected by toolkit validation: ") + "}}")["error"]
    assert error["code"] == "MISSING_REQUIRED_COLUMN" and "owner" in error["expected"]
    assert core.MINIMAL_INVENTORY_EXAMPLE in hint and "use_sample=true" in hint
    assert "Required header row: system_id,system_name,owner," in hint and "schema_version" not in hint


def test_minimal_inventory_example_is_valid():
    example = Path(__file__).resolve().parents[1] / core.MINIMAL_INVENTORY_EXAMPLE
    out = core.check_inventory(example.read_text(encoding="utf-8"), evaluation_time="2026-10-16T00:00:00Z")
    assert out["authority_effect"] == "NONE"
    assert out["result"]["validation_state"] == "VALID"
    assert example.read_text(encoding="utf-8").splitlines()[0].split(",") == core._required_inventory_columns()


def test_packaged_minimal_inventory_matches_docs_copy():
    docs_copy = Path(__file__).resolve().parents[1] / core.MINIMAL_INVENTORY_EXAMPLE
    assert core.PACKAGED_MINIMAL_INVENTORY.is_file()
    assert core.minimal_inventory_csv() == docs_copy.read_text(encoding="utf-8")


def test_packaged_minimal_inventory_is_valid_and_named_in_hint():
    out = core.check_inventory(core.minimal_inventory_csv(), evaluation_time="2026-10-16T00:00:00Z")
    assert out["authority_effect"] == "NONE"
    assert out["result"]["validation_state"] == "VALID"
    with pytest.raises(core.GaigInputError) as exc:
        core.check_inventory("system_id,system_name\nA-1,Example\n")
    assert "gaig_mcp.core.minimal_inventory_csv()" in str(exc.value)


def test_packaged_minimal_inventory_is_declared_package_data():
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert '"examples/*.csv"' in pyproject

