# Agent-stack examples

Minimal patterns for using gaig-mcp inside agent frameworks. Every gaig-mcp result carries `authority_effect: "NONE"`; a verified passport or a passing check is input for an accountable human, not an authorization.

| File | Pattern | Status |
|---|---|---|
| [`mcp_client_loop.py`](mcp_client_loop.py) | MCP Python SDK client: discover tools over stdio and call each one | TESTED (`tests/test_examples.py`) |
| [`passport_gate_graph.py`](passport_gate_graph.py) | LangGraph-style per-agent Passport check before each agent node runs (plain Python) | TESTED (`tests/test_examples.py`); LangGraph mapping untested |
| [`openai_agents_sdk.py`](openai_agents_sdk.py) | OpenAI Agents SDK agent with gaig-mcp as a stdio MCP server | untested |
| [`anthropic_tool_use.py`](anthropic_tool_use.py) | Anthropic Messages API tool use, with tools discovered from gaig-mcp | untested |
| [`action_level_guard.py`](action_level_guard.py) | Decide before each tool call: Levels 0-3 allow, Level 4 asks a person, Level 5 is blocked, unknown tools count as Level 4 (standard library only) | TESTED (`tests/test_guards.py`) |
| [`openai_agents_guard.py`](openai_agents_guard.py) | OpenAI Agents SDK: `require_approval` callable for Level 4, tool input guardrail for Level 5 | TESTED offline with openai-agents 0.24.0, the real gaig-mcp stdio server, and a scripted stand-in model; not run against a live model |
| [`claude_agent_sdk_guard.py`](claude_agent_sdk_guard.py) | Claude Agent SDK: `PreToolUse` hook returning `ask` or `deny` | TESTED offline with claude-agent-sdk 0.2.174 (hook called directly); not run against Claude |
| [`tool_call_hook.py`](tool_call_hook.py) | Command hook for Claude Code and the Grok CLI; denies on any error | Hook contract TESTED with recorded-format input; not run inside Claude Code or the Grok CLI (untested) |
| [`remote_mcp_guard.py`](remote_mcp_guard.py) | Hosted MCP request bodies for the OpenAI Responses, Anthropic Messages, and xAI APIs, exposing only what the guard allows; answers OpenAI approval requests | Request shapes TESTED offline; no live provider request (untested) |

The untested files need third-party packages and model API access; they are configuration patterns, not verified integrations. The SDK guard tests skip when the SDK is not installed. Setup steps for each guard: [README](../../README.md#guard-agent-tool-calls-by-action-level).
