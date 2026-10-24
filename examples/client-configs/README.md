# Client configurations (local stdio)

Each file starts the same command: `uvx --from git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.4.0 gaig-mcp`. The pinned toolkit and agentic files are bundled in the package, so no other checkout or environment variable is needed. Requires [uv](https://docs.astral.sh/uv/).

| Client | Copy to | File | Status |
|---|---|---|---|
| Cursor | `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global) | [`cursor.mcp.json`](cursor.mcp.json) | Launch command TESTED with the MCP Python SDK stdio client; not tested inside Cursor (untested) |
| VS Code | `.vscode/mcp.json` | [`vscode.mcp.json`](vscode.mcp.json) | Launch command TESTED with the MCP Python SDK stdio client; not tested inside VS Code (untested) |
| Codex | `~/.codex/config.toml` | [`codex.config.toml`](codex.config.toml) | Launch command TESTED with the MCP Python SDK stdio client; not tested inside Codex with this file (untested) |
| Claude Code | `.mcp.json` (project); the Grok CLI reads it too | [`claude-code.mcp.json`](claude-code.mcp.json) | Launch command TESTED with the MCP Python SDK stdio client; not tested inside Claude Code (untested) |
| Grok CLI | `~/.grok/config.toml`, or `.grok/config.toml` in a project | [`grok-cli.config.toml`](grok-cli.config.toml) | Launch command TESTED with the MCP Python SDK stdio client; not tested inside the Grok CLI (untested) |

Action Level guard hooks (copy `tool_call_hook.py` and `action_level_guard.py` from [`../agent-stacks/`](../agent-stacks/) next to them):

| Client | Copy to | File | Status |
|---|---|---|---|
| Claude Code | merge into `.claude/settings.json`; scripts in `.claude/hooks/` | [`claude-code.settings.json`](claude-code.settings.json) | Hook contract TESTED with recorded-format input; not run inside Claude Code (untested) |
| Grok CLI | `.grok/hooks/`, then `/hooks-trust` | [`grok-cli.hooks.json`](grok-cli.hooks.json) | Hook contract TESTED with recorded-format input; not run inside the Grok CLI (untested) |

`tests/test_examples.py` and `tests/test_guards.py` parse every file and checks that it launches the pinned `v0.4.0` command. Results from every tool carry `authority_effect: "NONE"`; they support human review and do not authorize anything.
