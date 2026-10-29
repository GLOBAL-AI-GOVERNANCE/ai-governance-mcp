#!/usr/bin/env python3
"""OpenAI Agents SDK (Python): gate every gaig-mcp tool call by Action Level.

Status: TESTED offline with openai-agents 0.24.0 and a scripted stand-in model (no OpenAI API call);
see tests/test_guards.py, which skips when openai-agents is not installed. Not run against a live model.

- `require_approval=needs_person` pauses a Level 4 call: the run returns `result.interruptions`, and a
  person approves or rejects each one with `state.approve(item)` / `state.reject(item)` before resuming.
- `tool_input_guardrails=[block_level_5]` rejects a Level 5 call before it runs; the model sees the reason.
Run: `pip install openai-agents`, set OPENAI_API_KEY, then `python openai_agents_guard.py`.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from agents import Agent, Runner, ToolGuardrailFunctionOutput, tool_input_guardrail
from agents.mcp import MCPServerStdio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_level_guard import ASK, DENY, ActionLevelGuard  # noqa: E402

PINNED = "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.5.1"
GUARD = ActionLevelGuard()  # add your own tools: ActionLevelGuard({"send_external_email": 4, ...})


async def needs_person(run_context, agent, tool) -> bool:
    """MCP `require_approval` callable: True pauses the run for a person."""
    return GUARD.decide(tool.name).decision == ASK


@tool_input_guardrail
def block_level_5(data) -> ToolGuardrailFunctionOutput:
    decision = GUARD.decide(data.context.tool_name)
    if decision.decision == DENY:
        return ToolGuardrailFunctionOutput.reject_content(decision.reason, output_info=decision.as_record())
    return ToolGuardrailFunctionOutput.allow(output_info=decision.as_record())


def gaig_server(params: dict | None = None) -> MCPServerStdio:
    return MCPServerStdio(
        params=params or {"command": "uvx", "args": ["--from", PINNED, "gaig-mcp"]},
        require_approval=needs_person,
        tool_input_guardrails=[block_level_5],
    )


async def run_with_human_review(agent: Agent, prompt: str, approve) -> str:
    """Run, ask `approve(item) -> bool` for each paused Level 4 call, resume until done."""
    result = await Runner.run(agent, prompt)
    while result.interruptions:
        state = result.to_state()
        for item in result.interruptions:
            state.approve(item) if approve(item) else state.reject(item)
        result = await Runner.run(agent, state)
    return str(result.final_output)


async def main() -> None:
    async with gaig_server() as gaig:
        agent = Agent(name="governance-reviewer", mcp_servers=[gaig],
                      instructions="Use the gaig tools; results are non-authorizing (authority_effect NONE).")
        ask = lambda item: input(f"Approve {item.tool_name}? [y/N] ").strip().lower() == "y"  # noqa: E731
        print(await run_with_human_review(agent, "Check the sample AI inventory and list critical findings.", ask))


if __name__ == "__main__":
    asyncio.run(main())
