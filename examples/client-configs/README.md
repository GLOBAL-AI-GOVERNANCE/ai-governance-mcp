# Client configurations (local stdio)

Each file starts the same command: `uvx --from git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.1.0 gag-mcp`. The pinned toolkit and agentic files are bundled in the package, so no other checkout or environment variable is needed. Requires [uv](https://docs.astral.sh/uv/).

| Client | Copy to | File | Status |
|---|---|---|---|
| Cursor | `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global) | [`cursor.mcp.json`](cursor.mcp.json) | Launch command TESTED with the MCP Python SDK stdio client; not tested inside Cursor (untested) |
| VS Code | `.vscode/mcp.json` | [`vscode.mcp.json`](vscode.mcp.json) | Launch command TESTED with the MCP Python SDK stdio client; not tested inside VS Code (untested) |
| Codex | `~/.codex/config.toml` | [`codex.config.toml`](codex.config.toml) | Launch command TESTED with the MCP Python SDK stdio client; not tested inside Codex with this file (untested) |

`tests/test_examples.py` parses every file and checks that it launches the pinned `v0.1.0` command. Results from every tool carry `authority_effect: "NONE"`; they support human review and do not authorize anything.
