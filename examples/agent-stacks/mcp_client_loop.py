#!/usr/bin/env python3
"""MCP client loop: discover gaig-mcp tools over stdio and call each one.

Status: TESTED (tests/test_examples.py runs this file against the local server).
Run:    python examples/agent-stacks/mcp_client_loop.py           # server from the current environment
        python examples/agent-stacks/mcp_client_loop.py --uvx     # server via the pinned uvx command
"""
from __future__ import annotations

import asyncio
import os
import sys

from mcp import Client, StdioServerParameters

PINNED = "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.2.0"
EVAL = "2026-10-16T00:00:00Z"
CALLS = [
    ("check_inventory", {"use_sample": True, "evaluation_time": EVAL}),
    ("build_decision_pack", {"use_sample": True, "evaluation_time": EVAL}),
    ("validate_passport", {"example": "signed-unrevoked"}),
    ("validate_passport", {"example": "signed-revoked"}),
]


def server_params(use_uvx: bool) -> StdioServerParameters:
    if use_uvx:
        return StdioServerParameters(command="uvx", args=["--from", PINNED, "gaig-mcp"], env=dict(os.environ))
    return StdioServerParameters(command=sys.executable, args=["-m", "gaig_mcp.server"], env=dict(os.environ))


async def run(use_uvx: bool = False) -> int:
    async with Client(server_params(use_uvx)) as client:
        tools = (await client.list_tools()).tools
        print("tools:", ", ".join(t.name for t in tools))
        for name, args in CALLS:
            result = await client.call_tool(name, args)
            sc = result.structured_content or {}
            if result.is_error or sc.get("authority_effect") != "NONE":
                print(f"{name}: FAIL")
                return 1
            r = sc["result"]
            summary = (r.get("governance_gate_state") or r.get("decision_status")
                       or r.get("verification", {}).get("verification_primary_status"))
            print(f"{name} {args.get('example', '')}: {summary} (authority_effect NONE, {sc['human_decision_state']})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run("--uvx" in sys.argv[1:])))
