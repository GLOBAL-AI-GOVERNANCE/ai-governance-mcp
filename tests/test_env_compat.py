"""GAIG_* settings are primary; deprecated GAG_* settings are honored, never silently ignored, and never conflict."""
import os
import subprocess
import sys

import pytest

from gaig_mcp import core, server
from gaig_mcp.server import build_http_app, program_name

GOOD_TOKEN = "t0k3n-" + "y" * 40
SUFFIXES = core.ENV_SETTINGS


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for suffix in SUFFIXES:
        monkeypatch.delenv("GAIG_" + suffix, raising=False)
        monkeypatch.delenv("GAG_" + suffix, raising=False)
    core._warned.clear()


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_primary_name_is_read(monkeypatch, suffix):
    monkeypatch.setenv("GAIG_" + suffix, "primary-value")
    assert core.env_setting(suffix) == "primary-value"


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_deprecated_name_falls_back_with_warning(monkeypatch, capsys, suffix):
    monkeypatch.setenv("GAG_" + suffix, "old-value")
    assert core.env_setting(suffix) == "old-value"
    err = capsys.readouterr().err
    assert f"GAG_{suffix} is deprecated" in err and f"GAIG_{suffix}" in err
    assert "old-value" not in err


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_conflicting_values_are_refused(monkeypatch, suffix):
    monkeypatch.setenv("GAIG_" + suffix, "a-value")
    monkeypatch.setenv("GAG_" + suffix, "b-value")
    with pytest.raises(core.ConfigurationError) as exc:
        core.env_setting(suffix)
    assert "a-value" not in str(exc.value) and "b-value" not in str(exc.value)
    with pytest.raises(core.ConfigurationError):
        core.check_environment()


def test_identical_values_are_accepted(monkeypatch):
    monkeypatch.setenv("GAIG_MCP_ALLOWED_HOSTS", "mcp.example.org")
    monkeypatch.setenv("GAG_MCP_ALLOWED_HOSTS", "mcp.example.org")
    assert core.env_setting("MCP_ALLOWED_HOSTS") == "mcp.example.org"


def test_deprecated_names_still_fail_closed_on_public_bind(monkeypatch):
    monkeypatch.setenv("GAG_MCP_ALLOWED_HOSTS", "mcp.example.org")
    with pytest.raises(ValueError, match="GAIG_MCP_BEARER_TOKEN"):
        build_http_app("0.0.0.0")
    monkeypatch.setenv("GAG_MCP_BEARER_TOKEN", GOOD_TOKEN)
    assert build_http_app("0.0.0.0") is not None


@pytest.mark.parametrize("allowed", ["random-words.trycloudflare.com", "localhost,mcp.example.org"])
def test_deprecated_names_loopback_plus_tunnel_requires_token(monkeypatch, allowed):
    """A tunnel to a loopback bind configured with the old names is still network exposure."""
    monkeypatch.setenv("GAG_MCP_ALLOWED_HOSTS", allowed)
    with pytest.raises(ValueError, match="GAIG_MCP_BEARER_TOKEN"):
        build_http_app("127.0.0.1")
    monkeypatch.setenv("GAG_MCP_BEARER_TOKEN", GOOD_TOKEN)
    assert build_http_app("127.0.0.1") is not None


def test_mixed_old_and_new_names_combine(monkeypatch):
    monkeypatch.setenv("GAIG_MCP_ALLOWED_HOSTS", "random-words.trycloudflare.com")
    monkeypatch.setenv("GAG_MCP_BEARER_TOKEN", GOOD_TOKEN)
    assert build_http_app("127.0.0.1") is not None


def test_conflicting_bearer_token_refuses_http_app(monkeypatch):
    monkeypatch.setenv("GAIG_MCP_ALLOWED_HOSTS", "mcp.example.org")
    monkeypatch.setenv("GAIG_MCP_BEARER_TOKEN", GOOD_TOKEN)
    monkeypatch.setenv("GAG_MCP_BEARER_TOKEN", "z" * 40)
    with pytest.raises(ValueError, match="different values"):
        build_http_app("0.0.0.0")


@pytest.mark.parametrize("module", ["gaig_mcp.server", "gag_mcp.server"])
def test_cli_refuses_to_start_on_conflict(module):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GAIG_", "GAG_"))}
    env["GAIG_MCP_CORS_ORIGINS"] = "https://a.example"
    env["GAG_MCP_CORS_ORIGINS"] = "https://b.example"
    proc = subprocess.run([sys.executable, "-m", module], env=env, capture_output=True, text=True,
                          timeout=20, stdin=subprocess.DEVNULL)
    assert proc.returncode != 0
    assert "GAIG_MCP_CORS_ORIGINS" in proc.stderr and "different values" in proc.stderr
    assert "a.example" not in proc.stderr and "b.example" not in proc.stderr


def test_program_name_follows_invoked_alias():
    assert program_name("/usr/bin/gaig-mcp") == "gaig-mcp"
    assert program_name("/usr/bin/gag-mcp") == "gag-mcp"
    assert program_name("C:\\venv\\Scripts\\gag-mcp.exe".replace("\\", "/")) == "gag-mcp"
    assert program_name("server.py") == "gaig-mcp"
    assert server.PRIMARY_PROG == "gaig-mcp" and server.DEPRECATED_PROG == "gag-mcp"
