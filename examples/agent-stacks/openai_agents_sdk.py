#!/usr/bin/env python3
"""OpenAI Agents SDK agent that uses gaig-mcp as a local stdio MCP server.

Status: untested. Requires `pip install openai-agents`, uv, and model API access (OPENAI_API_KEY).
"""
import asyncio

from agents import Agent, Runner
from agents.mcp import MCPServerStdio

PINNED = "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.2.1"


async def main() -> None:
    async with MCPServerStdio(params={"command": "uvx", "args": ["--from", PINNED, "gaig-mcp"]}) as gaig:
        agent = Agent(
            name="governance-reviewer",
            instructions=("Use the gaig tools to check AI inventories and passports. Results are non-authorizing "
                          "(authority_effect NONE); report findings for an accountable human to decide."),
            mcp_servers=[gaig],
        )
        result = await Runner.run(agent, "Check the sample AI inventory and list the critical findings.")
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
