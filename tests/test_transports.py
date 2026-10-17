"""Real MCP client calls over in-process, stdio, and Streamable HTTP transports."""
import asyncio
import os
import socket
import sys
import threading
import time

import httpx
import pytest
import uvicorn
from mcp import Client, StdioServerParameters

from gag_mcp.server import build_http_app, mcp
from conftest import EVAL_TIME, assert_non_authorizing

TOOLS = {"check_inventory", "build_decision_pack", "validate_passport"}
CALLS = [
    ("check_inventory", {"use_sample": True, "evaluation_time": EVAL_TIME}),
    ("build_decision_pack", {"use_sample": True, "evaluation_time": EVAL_TIME}),
    ("validate_passport", {"example": "signed-revoked"}),
]


async def _exercise(client):
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        a = t.annotations
        assert a.title and a.read_only_hint is True and a.destructive_hint is False
    for name, args in CALLS:
        r = await client.call_tool(name, args)
        assert not r.is_error, r.content
        assert_non_authorizing(r.structured_content)
    bad = await client.call_tool("check_inventory", {"inventory_csv": "a,b\n1,2\n"})
    assert bad.is_error


def test_in_process():
    async def run():
        async with Client(mcp) as c:
            await _exercise(c)
    asyncio.run(run())


def test_stdio_subprocess():
    params = StdioServerParameters(command=sys.executable, args=["-m", "gag_mcp.server"], env=dict(os.environ))
    async def run():
        async with Client(params) as c:
            await _exercise(c)
    asyncio.run(run())


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture
def http_server(monkeypatch):
    def start(env=None):
        for k, v in (env or {}).items():
            monkeypatch.setenv(k, v)
        port = _free_port()
        server = uvicorn.Server(uvicorn.Config(build_http_app(), host="127.0.0.1", port=port, log_level="error"))
        th = threading.Thread(target=server.run, daemon=True); th.start()
        for _ in range(100):
            if server.started: break
            time.sleep(0.05)
        started.append(server)
        return f"http://127.0.0.1:{port}"
    started = []
    yield start
    for s in started:
        s.should_exit = True


def test_streamable_http(http_server):
    base = http_server()
    assert httpx.get(base + "/health").json()["authority_effect"] == "NONE"
    async def run():
        async with Client(base + "/mcp") as c:
            await _exercise(c)
    asyncio.run(run())


def test_http_bearer_token_enforced(http_server):
    base = http_server({"GAG_MCP_BEARER_TOKEN": "test-token-123"})
    r = httpx.post(base + "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                   headers={"accept": "application/json, text/event-stream"})
    assert r.status_code == 401
    assert httpx.get(base + "/health").status_code == 200
