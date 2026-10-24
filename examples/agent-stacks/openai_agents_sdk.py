#!/usr/bin/env python3
"""OpenAI Agents SDK agent that uses gag-mcp as a local stdio MCP server.

Status: untested. Requires `pip install openai-agents`, uv, and model API access (OPENAI_API_KEY).
"""
import asyncio

from agents import Agent, Runner
from agents.mcp import MCPServerStdio

PINNED = "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.1.0"


async def main() -> None:
    async with MCPServerStdio(params={"command": "uvx", "args": ["--from", PINNED, "gag-mcp"]}) as gag:
        agent = Agent(
            name="governance-reviewer",
            instructions=("Use the gag tools to check AI inventories and passports. Results are non-authorizing "
                          "(authority_effect NONE); report findings for an accountable human to decide."),
            mcp_servers=[gag],
        )
        result = await Runner.run(agent, "Check the sample AI inventory and list the critical findings.")
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
