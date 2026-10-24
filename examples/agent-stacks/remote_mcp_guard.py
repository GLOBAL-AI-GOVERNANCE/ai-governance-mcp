#!/usr/bin/env python3
"""Hosted MCP tools (OpenAI Responses API, Anthropic Messages API, xAI API) gated by Action Level.

Status: TESTED (tests/test_guards.py builds each request body and answers mocked OpenAI
`mcp_approval_request` items). No live provider request was made; these are request shapes from
each provider's public documentation.

With hosted MCP, the provider calls your server, so your code cannot intercept each call. The guard
works in two ways:
1. Only tools the guard allows unattended (Levels 0-3) are exposed without review. Level 5 tools are
   never exposed.
2. OpenAI: Level 4 tools are exposed with `require_approval`; OpenAI returns an
   `mcp_approval_request`, and `answer_openai_approvals` asks a person. Anthropic and xAI document no
   per-call approval for MCP tools, so Level 4 tools are not exposed there; run them from your own
   client loop with the guard (see openai_agents_guard.py or claude_agent_sdk_guard.py).
xAI documents an empty `allowed_tools` list as allowing every tool, so these helpers refuse to build
a tool entry with nothing allowed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_level_guard import ALLOW, ASK, ActionLevelGuard  # noqa: E402

GAIG_TOOLS = ["check_inventory", "build_decision_pack", "validate_passport"]


def _split(guard: ActionLevelGuard, tool_names: Iterable[str]) -> tuple[list[str], list[str]]:
    names = list(tool_names)
    unattended = [n for n in names if guard.decide(n).decision == ALLOW]
    review = [n for n in names if guard.decide(n).decision == ASK]
    if not unattended and not review:
        raise ValueError("no tool may be exposed; an empty allowed_tools list would allow every tool")
    return unattended, review


def openai_mcp_tool(server_url: str, token: str, tool_names: Iterable[str] = GAIG_TOOLS,
                    guard: ActionLevelGuard | None = None, label: str = "gaig") -> dict:
    unattended, review = _split(guard or ActionLevelGuard(), tool_names)
    tool = {"type": "mcp", "server_label": label, "server_url": server_url,
            "headers": {"Authorization": f"Bearer {token}"}, "allowed_tools": unattended + review}
    tool["require_approval"] = {"never": {"tool_names": unattended}} if unattended else "always"
    return tool


def answer_openai_approvals(output_items: Iterable[dict], approve: Callable[[dict], bool],
                            guard: ActionLevelGuard | None = None) -> list[dict]:
    """Turn `mcp_approval_request` items into `mcp_approval_response` inputs. Level 5 is never approved."""
    guard = guard or ActionLevelGuard()
    answers = []
    for item in output_items:
        if item.get("type") != "mcp_approval_request":
            continue
        decision = guard.decide(item["name"])
        ok = decision.decision != "deny" and bool(approve(item))
        answers.append({"type": "mcp_approval_response", "approval_request_id": item["id"], "approve": ok})
    return answers


def anthropic_mcp_request_parts(server_url: str, token: str, tool_names: Iterable[str] = GAIG_TOOLS,
                                guard: ActionLevelGuard | None = None, name: str = "gaig") -> dict:
    """`mcp_servers` and `tools` for the Messages API (send header `anthropic-beta: mcp-client-2026-09-15`)."""
    unattended, _ = _split(guard or ActionLevelGuard(), tool_names)
    if not unattended:
        raise ValueError("no tool is allowed unattended; Anthropic documents no per-call MCP approval")
    return {
        "mcp_servers": [{"type": "url", "url": server_url, "name": name, "authorization_token": token}],
        "tools": [{"type": "mcp_toolset", "mcp_server_name": name, "default_config": {"enabled": False},
                   "configs": {n: {"enabled": True} for n in unattended}}],
    }


def xai_mcp_tool(server_url: str, token: str, tool_names: Iterable[str] = GAIG_TOOLS,
                 guard: ActionLevelGuard | None = None, label: str = "gaig") -> dict:
    """Responses API tool for https://api.x.ai/v1/responses. xAI does not support `require_approval`."""
    unattended, _ = _split(guard or ActionLevelGuard(), tool_names)
    if not unattended:
        raise ValueError("no tool is allowed unattended; xAI does not support require_approval")
    return {"type": "mcp", "server_label": label, "server_url": server_url,
            "server_description": "Non-authorizing AI governance checks (authority_effect NONE)",
            "headers": {"Authorization": f"Bearer {token}"}, "allowed_tools": unattended}


if __name__ == "__main__":
    import json
    guard = ActionLevelGuard({"validate_passport": 4})
    print(json.dumps(openai_mcp_tool("https://YOUR-HOST/mcp", "TOKEN", guard=guard), indent=2))
