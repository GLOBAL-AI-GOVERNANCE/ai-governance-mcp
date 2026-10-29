# Agent-stack examples

Minimal patterns for using gaig-mcp inside agent frameworks. Every gaig-mcp result carries `authority_effect: "NONE"`; a verified passport or a passing check is input for an accountable human, not an authorization.

| File | Pattern | Status |
|---|---|---|
| [`mcp_client_loop.py`](mcp_client_loop.py) | MCP Python SDK client: discover tools over stdio and call each one | TESTED (`tests/test_examples.py`) |
| [`passport_gate_graph.py`](passport_gate_graph.py) | LangGraph-style per-agent Passport check before each agent node runs (plain Python) | TESTED (`tests/test_examples.py`); for a real LangGraph graph see `langgraph_passport_gate.py` |
| [`openai_agents_sdk.py`](openai_agents_sdk.py) | OpenAI Agents SDK agent with gaig-mcp as a stdio MCP server | untested |
| [`anthropic_tool_use.py`](anthropic_tool_use.py) | Anthropic Messages API tool use, with tools discovered from gaig-mcp | untested |
| [`action_level_guard.py`](action_level_guard.py) | Decide before each tool call: Levels 0-3 allow, Level 4 asks a person unless the operator's automated approver lists the tool, Level 5 is blocked, unknown tools count as Level 4 and are never auto-approved (standard library only) | TESTED (`tests/test_guards.py`, `tests/test_automated_approver.py`) |
| [`openai_agents_guard.py`](openai_agents_guard.py) | OpenAI Agents SDK: `require_approval` callable for Level 4, tool input guardrail for Level 5 | TESTED offline with openai-agents 0.24.0, the real gaig-mcp stdio server, and a scripted stand-in model; not run against a live model |
| [`claude_agent_sdk_guard.py`](claude_agent_sdk_guard.py) | Claude Agent SDK: `PreToolUse` hook returning `ask` or `deny` | TESTED offline with claude-agent-sdk 0.2.174 (hook called directly); not run against Claude |
| [`crewai_guard.py`](crewai_guard.py) | CrewAI: `before_tool_call` / `after_tool_call` hooks gate by Action Level; tool output never changes policy | TESTED offline with crewai 1.15.33 (hook invoked with real ToolCallHookContext); not run against a live model |
| [`tool_call_hook.py`](tool_call_hook.py) | Command hook for Claude Code (`PreToolUse`), the Grok CLI and the Gemini CLI (`BeforeTool`); honors the automated Level 4 approver; denies on any error | Hook contracts TESTED with recorded- and documented-format input; not run inside Claude Code, the Grok CLI or the Gemini CLI (untested) |
| [`passport_tool_call_hook.py`](passport_tool_call_hook.py) | Command hook for Claude Code and the Grok CLI that runs `check_tool_call`: passport `VALID`, revocation passed, and the tool's Action Level within the passport's reachable level, all at this machine's clock; denies on any error | Hook contract TESTED (`tests/test_passport_guard.py`); not run inside Claude Code or the Grok CLI (untested) |
| [`remote_mcp_guard.py`](remote_mcp_guard.py) | Hosted MCP request bodies for the OpenAI Responses, Anthropic Messages, and xAI APIs, exposing only what the guard allows; answers OpenAI approval requests | Request shapes TESTED offline; no live provider request (untested) |
| [`langgraph_passport_gate.py`](langgraph_passport_gate.py) | LangGraph `StateGraph`: each agent node runs only after its passport verifies; others are held | TESTED offline with langgraph 1.2.17 and the built-in synthetic passports (`tests/test_interop.py`); no model |
| [`a2a_passport_card.py`](a2a_passport_card.py) | A2A Agent Card extension pointing at the agent's passport, plus a pre-delegation Action Level check ([spec](../../docs/A2A_PASSPORT_EXTENSION.md)) | Card shape TESTED with a2a-sdk 1.2.3 (`AgentCard` parse rejects unknown fields); no A2A server or client run |
| [`otel_genai.py`](otel_genai.py) | OpenTelemetry `execute_tool` spans with GenAI semantic-convention attributes plus `gaig.*` guard attributes; no arguments or results recorded | TESTED with opentelemetry-sdk 1.45.1 and an in-memory exporter; no collector |

The untested files need third-party packages and model API access; they are configuration patterns, not verified integrations. The SDK tests skip when the SDK is not installed locally; the CI `interop` job installs the pinned SDKs and fails on any skip. Setup steps for each guard: [README](../../README.md#guard-agent-tool-calls-by-action-level).
