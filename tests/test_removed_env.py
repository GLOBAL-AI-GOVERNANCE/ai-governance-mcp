"""GAIG_* settings are the only names read. A removed pre-v0.3.0 name refuses to start (fail closed)."""
import os
import subprocess
import sys

import pytest

from gaig_mcp import core, server
from gaig_mcp.server import build_http_app

GOOD_TOKEN = "t0k3n-" + "y" * 40
SUFFIXES = core.ENV_SETTINGS
OLD = core.REMOVED_ENV_PREFIX


def test_removed_prefix_is_the_pre_v0_3_0_name():
    assert OLD == "GAG_" and core.ENV_PREFIX == "GAIG_"


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_primary_name_is_read(monkeypatch, suffix):
    monkeypatch.setenv("GAIG_" + suffix, "primary-value")
    assert core.env_setting(suffix) == "primary-value"


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_removed_name_is_refused_and_never_read(monkeypatch, suffix):
    monkeypatch.setenv(OLD + suffix, "old-value")
    with pytest.raises(core.ConfigurationError) as exc:
        core.env_setting(suffix)
    msg = str(exc.value)
    assert OLD + suffix in msg and "GAIG_" + suffix in msg and "old-value" not in msg
    with pytest.raises(core.ConfigurationError):
        core.check_environment()


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_removed_name_refused_even_when_new_name_matches(monkeypatch, suffix):
    monkeypatch.setenv("GAIG_" + suffix, "same")
    monkeypatch.setenv(OLD + suffix, "same")
    with pytest.raises(core.ConfigurationError):
        core.check_environment()


def test_removed_name_set_to_empty_is_still_refused(monkeypatch):
    monkeypatch.setenv(OLD + "MCP_BEARER_TOKEN", "")
    with pytest.raises(core.ConfigurationError):
        core.check_environment()


@pytest.mark.parametrize("allowed", ["random-words.trycloudflare.com", "localhost,mcp.example.org"])
def test_old_tunnel_settings_cannot_open_an_unauthenticated_server(monkeypatch, allowed):
    """The documented fail-open risk: loopback behind a tunnel with the token under the old name."""
    monkeypatch.setenv("GAIG_MCP_ALLOWED_HOSTS", allowed)
    monkeypatch.setenv(OLD + "MCP_BEARER_TOKEN", GOOD_TOKEN)
    with pytest.raises(ValueError):  # ConfigurationError subclasses ValueError
        build_http_app("127.0.0.1")
    monkeypatch.delenv(OLD + "MCP_BEARER_TOKEN")
    with pytest.raises(ValueError, match="GAIG_MCP_BEARER_TOKEN"):
        build_http_app("127.0.0.1")
    monkeypatch.setenv("GAIG_MCP_BEARER_TOKEN", GOOD_TOKEN)
    assert build_http_app("127.0.0.1") is not None


@pytest.mark.parametrize("args", [[], ["--http"]])
@pytest.mark.parametrize("suffix", SUFFIXES)
def test_cli_refuses_to_start_with_removed_name(args, suffix):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GAIG_", OLD))}
    env[OLD + suffix] = "secret-old-value"
    proc = subprocess.run([sys.executable, "-m", "gaig_mcp.server", *args], env=env, capture_output=True,
                          text=True, timeout=20, stdin=subprocess.DEVNULL)
    assert proc.returncode != 0
    assert OLD + suffix in proc.stderr and "GAIG_" + suffix in proc.stderr
    assert "secret-old-value" not in proc.stderr


def test_program_name_is_gaig_mcp():
    assert server.PRIMARY_PROG == "gaig-mcp"
    assert not hasattr(server, "program_name")
