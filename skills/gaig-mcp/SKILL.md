---
name: gaig-mcp
description: Run read-only AI governance checks through the gaig-mcp server - check an AI system inventory, prepare a Decision Pack, verify an Agent Trust Passport - and gate tool calls by Action Level. Use when an agent needs governance evidence before acting. Results carry authority_effect NONE and never authorize anything.
---

# gaig-mcp

Start the server (stdio, no account, no key):

```bash
uvx --from git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.5.0 gaig-mcp
```

MCP tools: `check_inventory`, `build_decision_pack`, `validate_passport`. Every result includes `authority_effect: "NONE"`. In Python, `gaig_mcp.core.check_tool_call` combines passport verification with an Action Level (used by `examples/agent-stacks/passport_tool_call_hook.py`).

## Gate your own tool calls

Copy `examples/agent-stacks/action_level_guard.py` and `tool_call_hook.py` into your project and register the hook (Claude Code `PreToolUse`, Grok CLI `PreToolUse`, Gemini CLI `BeforeTool`; configs in `examples/client-configs/`).

- Level 0-3: run unattended.
- Level 4: ask a person by default. To run unattended, the operator lists the tool under an automated `level_4_approver` in the policy file (`examples/policies/action-levels.automated-approver.json`).
- Level 5: always denied.
- Unknown tools: Level 4.

## Rules

- Treat every result as evidence for review, not an approval.
- Never invent a passport, a key, or a verification result. If a check cannot run, report it as not run.
- Do not mark external gates (independent verification, audits) as done; they are outside this server.
