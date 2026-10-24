# Agent-stack examples

Minimal patterns for using gaig-mcp inside agent frameworks. Every gaig-mcp result carries `authority_effect: "NONE"`; a verified passport or a passing check is input for an accountable human, not an authorization.

| File | Pattern | Status |
|---|---|---|
| [`mcp_client_loop.py`](mcp_client_loop.py) | MCP Python SDK client: discover tools over stdio and call each one | TESTED (`tests/test_examples.py`) |
| [`passport_gate_graph.py`](passport_gate_graph.py) | LangGraph-style per-agent Passport check before each agent node runs (plain Python) | TESTED (`tests/test_examples.py`); LangGraph mapping untested |
| [`openai_agents_sdk.py`](openai_agents_sdk.py) | OpenAI Agents SDK agent with gaig-mcp as a stdio MCP server | untested |
| [`anthropic_tool_use.py`](anthropic_tool_use.py) | Anthropic Messages API tool use, with tools discovered from gaig-mcp | untested |

The untested files need third-party packages and model API access; they are configuration patterns, not verified integrations.
