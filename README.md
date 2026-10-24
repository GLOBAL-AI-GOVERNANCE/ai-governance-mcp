# AI Governance Model Context Protocol Server (AI Governance MCP)

<!-- gaig:nav -->
**[Global AI Governance](https://ai-governance.solutions/)** · `v0.4.0 · released` · `authority_effect: NONE`

[Connect your agent](https://ai-governance.solutions/connect.html#agents) · [Specifications](https://ai-governance.solutions/connect.html#spec) · [All products](https://ai-governance.solutions/#products)
<!-- /gaig:nav -->

Governance checks your AI agents can call. Start the server with one command, and your agent can check an AI system inventory, prepare a Decision Pack, or verify an Agent Trust Passport. Every result is read-only and leaves the decision with a person.

```bash
uvx --from git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.4.0 gaig-mcp
```

**Model Context Protocol (MCP)** is an open standard that lets AI assistants discover and call external tools through a common interface. This repository is a non-authorizing MCP server for Global AI Governance reference tooling.

**Status:** Released · `v0.4.0`. Run it locally with the command above or self-host it. **No hosted endpoint is operated**, and it is not listed in any platform directory.

**Names:** the console command is `gaig-mcp`, the import package is `gaig_mcp`, the MCP server name reported to clients is `gaig-mcp`, and environment variables use the `GAIG_MCP_` / `GAIG_` prefixes. The Python distribution and the desktop-extension manifest `name` are also `gaig-mcp` (wheel `gaig_mcp`).

**v0.3.0 removed the older names.** Only the names above work. If an environment variable from before v0.3.0 is still set, the server refuses to start and names the `GAIG_*` variable to use instead, so a security setting is never silently dropped.

AI Governance MCP exposes the real Global AI Governance reference tooling to MCP clients:

| Tool | What it does | Upstream code it runs |
|---|---|---|
| `check_inventory` | Policy-as-code governance checks on an AI system inventory CSV. Returns findings by severity | `global-ai-governance-toolkit` `run_pipeline` (pinned `cc5f5997a9d44958099b292a2081c86b52ee515c`, release v2.7.2) |
| `build_decision_pack` | Prepares the digest-listed Decision Pack, verifies its integrity, and returns the manifest, the reference-only handoff, and optional Markdown documents | toolkit `run_pipeline` + `verify_output_directory` |
| `validate_passport` | Verifies an Agent Trust Passport: schema, semantics, Ed25519 signature, key trust, validity window, and signed revocation (all checks run for the built-in examples; caller-supplied JSON has limits, see "Known limits") | `agentic-ai-governance` `tools/validate_artifact.py` (pinned `58bdfb291df0de7c9437b4476e370a609c4b1d5f`) |

**Authority boundary, enforced in code and tests.** Every result carries `authority_effect: "NONE"`, the `review_boundary` text, and `human_decision_state: "PENDING_HUMAN_DECISION"`. Upstream fields that an assistant could paraphrase as an authorization are relabeled, with their values left verbatim:
- `operating_disposition` → `reference_policy_disposition`
- `issued_assessment_result` → `assessment_result_recorded_in_artifact`

The test suite fails if any output contains an authorization-like key, a non-`NONE` authority effect, `conditionally_authorized`, or a `PERMITTED` value outside the relabeled field. All three tools are annotated `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false`, and each has a `title`.

Compatible with MCP-based agents. Not affiliated with or endorsed by xAI, OpenAI, Anthropic, or any other model provider.

**What has been tested, and what has not:**
- **Protocol compatibility: tested** with the official MCP Python SDK client (`mcp==2.3.0`, stdio and Streamable HTTP, `scripts/smoke_test.py`) and the MCP Inspector CLI (2.11.0, stdio, and HTTP with a bearer token).
- **Simulated provider schema checks: none performed.**
- **Provider-client connectivity: one recorded test run.** Codex CLI 0.151.0, local stdio, at commit `c71457b9660608f0135d8e6169d60f6bfdbe0013` (merged as `9abb2061a7a60e065ba999157787ae6091cb8581`): discovery, tool listing, `check_inventory`, and `validate_passport` with caller-supplied JSON strings. This is one TESTED run, not independently reproduced, and does not establish broader OpenAI compatibility, ChatGPT remote connectivity, Claude integration, or Grok connectivity. The provider sections below are configuration guidance from each provider's public documentation, not tested connections.

## Install and run (local)

No clone needed. The pinned toolkit and agentic files are bundled in the package (`src/gaig_mcp/_upstream/`, source lock in `UPSTREAM_LOCK.json`), so this runs with no other checkout:

```bash
uvx --from git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.4.0 gaig-mcp      # stdio
```

TESTED in a clean environment. Copy-paste client configs for Cursor, VS Code, Codex, Claude Code, and the Grok CLI are in [`examples/client-configs/`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/tree/v0.4.0/examples/client-configs); agent-framework patterns and the Action Level guard are in [`examples/agent-stacks/`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/tree/v0.4.0/examples/agent-stacks).

From source:

```bash
git clone https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp.git
cd ai-governance-mcp
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
gaig-mcp                              # stdio
gaig-mcp --http --port 8000           # Streamable HTTP at http://127.0.0.1:8000/mcp ; GET /health
pytest                                # 144 tests
python scripts/smoke_test.py --transcript docs/verification-transcript.md
```

## Sample call

After the from-source install steps above.

Success — synthetic sample, pinned evaluation time used by the test suite:

```bash
python -c 'from gaig_mcp.core import check_inventory
out = check_inventory(use_sample=True, evaluation_time="2026-10-16T00:00:00Z")
assert out["authority_effect"] == "NONE"
assert out["human_decision_state"] == "PENDING_HUMAN_DECISION"
assert out["tool"] == "check_inventory"
r = out["result"]
assert r["validation_state"] == "VALID"
assert r["finding_count"] == len(r["findings"]) > 0
assert r["findings_by_severity"].get("CRITICAL", 0) >= 1
print(r["validation_state"], r["finding_count"])'
```

Expected: `VALID` and a finding count greater than zero, including at least one `CRITICAL` finding. `authority_effect` stays `NONE`. `human_decision_state` stays `PENDING_HUMAN_DECISION`. The findings are reference results for human review. They do not authorize deployment.

Failure — both inputs at once:

```bash
python -c 'from gaig_mcp.core import check_inventory, GaigInputError
try:
    check_inventory(inventory_csv="a,b\n", use_sample=True)
except GaigInputError as exc:
    print(exc)'
```

Expected: `Provide inventory_csv or use_sample=true, not both.`

Failure — no input:

```bash
python -c 'from gaig_mcp.core import check_inventory, GaigInputError
try:
    check_inventory()
except GaigInputError as exc:
    print(exc)'
```

Expected: `inventory_csv is empty. Supply CSV text or set use_sample=true.`

Your own inventory — start from the minimal valid example:

```bash
python -c 'from pathlib import Path
from gaig_mcp.core import check_inventory
out = check_inventory(inventory_csv=Path("docs/examples/minimal-inventory.csv").read_text(), evaluation_time="2026-10-16T00:00:00Z")
print(out["result"]["validation_state"], out["result"]["finding_count"])'
```

Expected last line: `VALID 0` (the toolkit also prints its progress lines). [`docs/examples/minimal-inventory.csv`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/docs/examples/minimal-inventory.csv) holds the required header row and one synthetic system; replace the row with your own systems. The same file is installed with the package, so a pip or uvx install without a clone can use `from gaig_mcp.core import minimal_inventory_csv` and pass `minimal_inventory_csv()` as `inventory_csv`. If a column is missing, `check_inventory` fails closed with `MISSING_REQUIRED_COLUMN`, lists the required columns, and points to this file.

Package-only install (no clone): `pip install "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.4.0"`. The pinned upstream files are included. Running `scripts/smoke_test.py` against a package install also needs the dev extra: `pip install "gaig-mcp[dev] @ git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp.git"`.

Protocol: the official Python SDK `mcp==2.3.0`, which speaks MCP **2026-07-28** (the current spec revision). The smoke test also confirms that handshake-era clients (`initialize` with `2025-06-18` / `2025-11-25`) work over HTTP. HTTP mode is stateless with JSON responses, which suits serverless hosts.

Environment variables (HTTP mode):

| Var | Purpose |
|---|---|
| `GAIG_MCP_ALLOWED_HOSTS` | Comma-separated Host allow-list (DNS-rebinding protection). **Required for any non-loopback bind:** with `HOST`/`--host` other than `127.0.0.1`, `localhost`, or `::1`, the server refuses to start until this is set. |
| `GAIG_MCP_CORS_ORIGINS` | Comma-separated origins for browser-based clients (e.g., MCP Inspector). Off by default |
| `GAIG_MCP_BEARER_TOKEN` | Static bearer token, at least 32 characters (for example `python -c "import secrets; print(secrets.token_urlsafe(32))"`). **Required whenever other machines can reach the server:** a non-loopback bind, or a `GAIG_MCP_ALLOWED_HOSTS` entry that is not loopback (reverse proxy or tunnel). Without it the server refuses to start. Optional for loopback-only use. This is **not OAuth**; see "Auth" below |
| `GAIG_TOOLKIT_PATH`, `GAIG_AGENTIC_PATH` | Use other checkouts instead of the bundled pinned files |
| `HOST`, `PORT` | Bind address (defaults `127.0.0.1:8000`) |

Only these `GAIG_*` names are read. A setting name from before v0.3.0 makes the server refuse to start, with a message naming its `GAIG_*` replacement. This keeps the loopback-plus-tunnel case fail-closed.

## Client configuration (copy-paste)

Replace `https://YOUR-HOST` and `TOKEN` with your own values. Local stdio configs for Cursor, VS Code, Codex, Claude Code, and the Grok CLI: [`examples/client-configs/`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/tree/v0.4.0/examples/client-configs). Remote platforms (ChatGPT, the Claude API and claude.ai, the OpenAI, Anthropic, and xAI APIs, grok.com) **cannot reach stdio or localhost**. They need an HTTPS URL that you host yourself (see "Self-hosting") and must send `Authorization: Bearer TOKEN`, where `TOKEN` is your `GAIG_MCP_BEARER_TOKEN`. None of the remote recipes below has been tested against a live provider.

### Claude Desktop (local, stdio)
`claude_desktop_config.json` (Settings → Developer → Edit Config):
```json
{
  "mcpServers": {
    "gaig": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.4.0", "gaig-mcp"]
    }
  }
}
```
Launch command TESTED with the MCP Python SDK stdio client; this config is not tested inside Claude Desktop.

One-click desktop extension: `manifest.json` (MCPB `manifest_version` 0.4) passes `mcpb validate`. Packing a `.mcpb` still needs platform-specific dependency bundling (`cryptography` has native wheels). **Not yet tested in Claude Desktop.**

### Claude Code (local, stdio)
```bash
claude mcp add gaig --scope project -- uvx --from git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.4.0 gaig-mcp
```
This writes a project `.mcp.json` like [`examples/client-configs/claude-code.mcp.json`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/client-configs/claude-code.mcp.json). Tools appear as `mcp__gaig__check_inventory` and so on. Launch command TESTED with the MCP Python SDK stdio client; not tested inside Claude Code (untested).

### Grok CLI (local, stdio)
```bash
grok mcp add gaig -- uvx --from git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.4.0 gaig-mcp
```
Or add [`examples/client-configs/grok-cli.config.toml`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/client-configs/grok-cli.config.toml) to `~/.grok/config.toml`. The Grok CLI also reads a project `.mcp.json`, so the Claude Code file works there too; check with `grok mcp doctor`. Tools appear as `gaig__check_inventory` and so on. Launch command TESTED with the MCP Python SDK stdio client; not tested inside the Grok CLI (untested).

### Claude.ai / Claude Desktop / mobile (remote custom connector)
Add custom connector → URL `https://YOUR-HOST/mcp`, sign-in "None", then under **Request headers** add `authorization` with the value `Bearer TOKEN`. Anthropic documents request headers as a beta available to a limited set of organizations. If your organization does not see that section, Claude.ai cannot connect to this server: it does not implement OAuth and does not accept anonymous network requests. Which plans can add custom connectors: **unverified**; check the Claude Help Center.

### Anthropic Messages API (MCP connector)
```bash
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" -H "anthropic-beta: mcp-client-2026-09-15" \
  -d '{
    "model": "CLAUDE_MODEL_ID", "max_tokens": 1500,
    "messages": [{"role": "user", "content": "Use gaig to check the sample AI inventory and summarize the critical findings."}],
    "mcp_servers": [{"type": "url", "name": "gaig", "url": "https://YOUR-HOST/mcp", "authorization_token": "TOKEN"}],
    "tools": [{"type": "mcp_toolset", "mcp_server_name": "gaig"}]
  }'
```
(`mcp-client-2025-11-20` is the previous header. `authorization_token` is required, because the server rejects requests without the token.)

### OpenAI Responses API (remote MCP tool)
```bash
curl https://api.openai.com/v1/responses \
  -H "content-type: application/json" -H "authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "OPENAI_MODEL_ID",
    "input": "Use gaig to verify the signed-revoked example passport and explain the result.",
    "tools": [{
      "type": "mcp", "server_label": "gaig", "server_url": "https://YOUR-HOST/mcp",
      "headers": {"Authorization": "Bearer TOKEN"},
      "allowed_tools": ["check_inventory", "build_decision_pack", "validate_passport"],
      "require_approval": "never"
    }]
  }'
```
`"require_approval": "never"` is a documented OpenAI value that skips OpenAI's per-call approval prompt, which otherwise asks before data is sent to the server. It is used here only because all three tools are read-only and non-authorizing; it grants no authority, and every result still carries `authority_effect: "NONE"` and waits for a human decision. Set it to `"always"` to review each call.

(OpenAI also documents an `authorization` field for OAuth access tokens; the `headers` form above sends the static token verbatim. For a server that is never exposed publicly, OpenAI documents a Secure MCP Tunnel (`tunnel_id`). That path is untested here.)

### ChatGPT (developer mode / custom app)
**Not currently supported.** OpenAI documents the authentication options for a custom MCP server in ChatGPT as OAuth, no authentication, or mixed; there is no field for a static bearer token. This server requires a token for any remote use and does not implement OAuth, so ChatGPT on the web cannot connect to it. Use the OpenAI Responses API above instead.

### xAI Grok API (remote MCP tool)
```bash
curl https://api.x.ai/v1/responses \
  -H "content-type: application/json" -H "authorization: Bearer $XAI_API_KEY" \
  -d '{
    "model": "GROK_MODEL_ID",
    "input": "Use gaig to run check_inventory on the sample and list critical findings.",
    "tools": [{
      "type": "mcp", "server_label": "gaig", "server_url": "https://YOUR-HOST/mcp",
      "server_description": "Non-authorizing AI governance checks (authority_effect NONE)",
      "headers": {"Authorization": "Bearer TOKEN"},
      "allowed_tools": ["check_inventory", "build_decision_pack", "validate_passport"]
    }]
  }'
```
xAI supports only Streamable HTTP or SSE; `require_approval` is not supported. In the xAI Python SDK, use `mcp(server_url=..., server_label="gaig", allowed_tool_names=[...], extra_headers={"Authorization": "Bearer TOKEN"})`.

### Grok (grok.com consumer connectors)
grok.com/connectors → New Connector → Custom → enter `https://YOUR-HOST/mcp`. The server must be reachable on the public internet. Whether this connector can send a static `Authorization: Bearer` header is **unverified**. If it cannot, grok.com cannot connect to this server; use the xAI API above instead.

## Guard agent tool calls by Action Level

gaig-mcp tools are read-only, but the agents that call them usually have other tools too. [`examples/agent-stacks/action_level_guard.py`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/agent-stacks/action_level_guard.py) (standard library only) checks every tool call before it runs, using the Action Levels in the [action-authority spec](https://github.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance/blob/main/spec/08-action-authority.md):

| Level | Meaning | Guard decision |
|---|---|---|
| 0-3 | Advisory, read-only, drafts, or bounded reversible internal actions | allow |
| 4 | Privileged or externally consequential | ask: an accountable person approves or rejects the call |
| 5 | Destructive, financial, legal, employment, human-safety, critical-infrastructure, or irreversible high-impact | deny |
| not in your policy | New or renamed tool | treated as Level 4 |

You list your tools and their levels (`ActionLevelGuard({"send_external_email": 4, "delete_records": 5})`); the three gaig-mcp tools are Level 1. The guard never approves a Level 4 call itself. One policy covers `send_external_email`, `mcp__crm__send_external_email` (Claude), and `crm__send_external_email` (Grok CLI).

| Stack | File | How Level 4 and Level 5 are enforced | Status |
|---|---|---|---|
| OpenAI Agents SDK (Python) | [`openai_agents_guard.py`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/agent-stacks/openai_agents_guard.py) | `require_approval` callable pauses Level 4 for `state.approve` / `state.reject`; a tool input guardrail rejects Level 5 | TESTED offline: openai-agents 0.24.0 runner, real gaig-mcp stdio server, scripted stand-in model |
| Claude Agent SDK (Python) | [`claude_agent_sdk_guard.py`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/agent-stacks/claude_agent_sdk_guard.py) | `PreToolUse` hook returns `ask` or `deny` | TESTED offline: claude-agent-sdk 0.2.174 hook called directly; not run against Claude |
| Claude Code | [`tool_call_hook.py`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/agent-stacks/tool_call_hook.py) + [`claude-code.settings.json`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/client-configs/claude-code.settings.json) | `PreToolUse` command hook returns `ask` or `deny` | Hook contract TESTED with recorded-format input; not run inside Claude Code (untested) |
| Grok CLI | same hook + [`grok-cli.hooks.json`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/client-configs/grok-cli.hooks.json) | Grok hooks can only deny, so Level 4 and Level 5 are denied with the reason | Hook contract TESTED with recorded-format input; not run inside the Grok CLI (untested) |
| OpenAI Responses API (hosted MCP) | [`remote_mcp_guard.py`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/agent-stacks/remote_mcp_guard.py) | `require_approval` for Level 4; `mcp_approval_response` never approves Level 5; Level 5 tools are not exposed | Request shapes and approval answers TESTED offline; no live request (untested) |
| Anthropic Messages API (MCP connector) | same file | Only Level 0-3 tools are enabled in `mcp_toolset` | Request shape TESTED offline; no live request (untested) |
| xAI API (remote MCP) | same file | Only Level 0-3 tools in `allowed_tools`; xAI has no `require_approval` | Request shape TESTED offline; no live request (untested) |

Setup for Claude Code: copy `tool_call_hook.py` and `action_level_guard.py` into `.claude/hooks/`, and merge `claude-code.settings.json` into `.claude/settings.json`. For the Grok CLI: copy both files into `.grok/hooks/`, copy `grok-cli.hooks.json` there too, and trust the project hooks with `/hooks-trust`. Pass your own levels with `--policy action-levels.json`. The hook denies on any error, because the Grok CLI lets a call through when a hook fails; in Claude Code v2.1.295 or later you can also add `"onFailure": "block"` to the hook entry.

Hosted MCP connectors (OpenAI, Anthropic, xAI) call your server from the provider, so your code cannot check each call there; expose only the tools the guard allows, and run Level 4 actions from your own client loop. The guard limits what an agent can do unattended; it does not make any action authorized. Tests: `tests/test_guards.py`.

## Check the passport and the Action Level before each tool call

New in v0.4.0. `gaig_mcp.core.check_tool_call` runs one combined check before a tool call, at this server's own clock:

1. The agent's passport verifies `VALID`: schema, Ed25519 signature, key trust, evidence-bundle binding, and validity window.
2. A signed revocation list was supplied, and the revocation check passed. A missing or stale list means deny.
3. The tool's Action Level is at or below the passport's reachable level. That level is the passport's `issued_assessment.maximum_action_level`, lowered by any condition's `temporary_restriction.maximum_action_level`.

If all three pass, Levels 0-3 give `allow`, Level 4 gives `ask` (an accountable person decides), and Level 5 gives `deny`. Every other outcome is `deny`. A tool without a stated level counts as Level 4. The result is `call_disposition` with its `reasons`, inside the usual envelope (`authority_effect: "NONE"`). `allow` means no check stopped the call; it is not an approval.

**Time basis.** `check_tool_call` has no time input. It always evaluates at `server_clock()` and reports `evaluated_at` and `time_basis: "server_clock"`, and it denies if the validator did not evaluate at that time. `validate_passport` keeps its `at_time` argument for historical validation ("did this passport verify at that time?"), and now reports `time_basis`: `caller_at_time`, `example_fixed_time`, or `server_clock`. A caller-supplied time is never used for a pre-call decision.

```python
from gaig_mcp.core import check_tool_call
out = check_tool_call("send_external_email", passport=passport_json, trusted_key=key_json,
                      revocation_list=revocation_json, tool_level=4,
                      bundle_manifest="bundle/manifest.json", bundle_root="bundle")
out["result"]["call_disposition"]   # "allow", "ask", or "deny"
```

For Claude Code and the Grok CLI, [`passport_tool_call_hook.py`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/agent-stacks/passport_tool_call_hook.py) wraps this check as a `PreToolUse` command hook, takes tool levels from [`action_level_guard.py`](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/examples/agent-stacks/action_level_guard.py), and denies on any error. It needs gaig-mcp installed and `--passport`, `--trusted-key`, and `--revocation-list` files; add `--bundle-manifest` and `--bundle-root`, or the passport cannot reach `VALID`. Status: TESTED (`tests/test_passport_guard.py`); not run inside Claude Code or the Grok CLI. The existing `tool_call_hook.py` and the other guards are unchanged.

`check_tool_call` is a Python function and a hook, not an MCP tool: the MCP tool list is unchanged. The evidence bundle is read from local paths, so it is not accepted over MCP.

## Auth
- **Local stdio:** no auth. The MCP spec says stdio servers take credentials from the environment.
- **Loopback HTTP** (`127.0.0.1`, `localhost`, `::1`, with no public `GAIG_MCP_ALLOWED_HOSTS` entry): the token is optional, as before.
- **Any network exposure** (non-loopback bind, reverse proxy, or tunnel): `GAIG_MCP_BEARER_TOKEN` is **required**, and the server refuses to start without it. There is no anonymous mode. An authenticating gateway in front of the server does not replace the token, because the server cannot verify a gateway's claim.
- **Bearer token:** sent as `Authorization: Bearer TOKEN` (`authorization_token` in the Anthropic API, `headers` in the OpenAI and xAI APIs). It is one static shared secret for every caller: no rotation (restart with a new value), no per-user identity, no scopes, and no expiry. It is compared in constant time, every rejection gets the same `401` body, and the presented value is never echoed. Serve it only over HTTPS.
- **OAuth 2.1:** not implemented. Clients that offer only OAuth or no authentication cannot connect. Adding OAuth would require Protected Resource Metadata (RFC 9728) plus an authorization server.

## Self-hosting (needed for every remote platform; Global AI Governance operates no endpoint)

Every remote deployment needs, at minimum: HTTPS, `GAIG_MCP_ALLOWED_HOSTS=<the hostname clients use>`, and `GAIG_MCP_BEARER_TOKEN=<random secret of 32+ characters>`. The server refuses to start on a non-loopback bind, or with a non-loopback allow-list entry, unless both are set.

| Option | Cost (per provider docs, Oct 2026) | Fit |
|---|---|---|
| Cloudflare Quick Tunnel (`cloudflared tunnel --url http://localhost:8000`) | Free, no account | **Testing only.** Random temporary URL. Set `GAIG_MCP_ALLOWED_HOSTS` to the tunnel hostname and set `GAIG_MCP_BEARER_TOKEN` |
| Render free web service (`deploy/Dockerfile`) | $0; 512 MB; spins down after 15 min idle (about 1 min cold start) | Cheapest always-addressable URL; cold starts may time out some clients (unverified) |
| Google Cloud Run (`deploy/Dockerfile`) | Free tier of 2M requests/month; billing account required | Scales to zero, HTTPS, custom domain |

**Privacy note:** a hosted endpoint changes the toolkit's "LOCAL · NO UPLOAD" promise for that mode. Label it clearly, and keep stdio as the private default.

## Files
- `src/gaig_mcp/core.py`: transport-independent logic, the authority envelope, and `check_tool_call`
- `src/gaig_mcp/server.py`: MCP server (stdio and Streamable HTTP, `/health`, CORS, bearer token required for network use)
- `src/gaig_mcp/_upstream/`: pinned toolkit and agentic files bundled into the package, with `UPSTREAM_LOCK.json` (commit, file count, tree digest per upstream)
- `tests/`: 144 tests (combined pre-call passport and Action Level guard, core behavior, determinism, fail-closed input, non-authorizing invariants, in-process, stdio, and HTTP transports, bearer enforcement, and security regressions for host allow-listing, uniform 401s, sanitized errors, unknown-argument rejection, and the required bearer token for network exposure, plus interface guards, refusal of removed setting names, bundle-lock checks, and example and client-config checks)
- `scripts/smoke_test.py`, `docs/verification-transcript.md`: real-client verification
- `scripts/fetch_upstreams.sh`: pinned upstream clones; `scripts/bundle_upstreams.py`: copies them into the package and checks the bundle (`--check`, run in CI)
- `examples/client-configs/`, `examples/agent-stacks/`: copy-paste client configs and agent-framework patterns, each labelled TESTED or untested
- `.github/workflows/release-assets.yml`: builds the wheel and sdist from a release tag, installs them in a clean environment, and attaches them with `SHA256SUMS` to the release. For releases published after v0.3.0, it also attaches a CycloneDX SBOM of the clean install (`*.cdx.json`) and records a GitHub build-provenance attestation for every asset in `SHA256SUMS` (check with `gh attestation verify <file> --repo GLOBAL-AI-GOVERNANCE/ai-governance-mcp`). Releases up to and including v0.3.0 have no SBOM or attestation
- `manifest.json`: MCPB desktop-extension manifest (validated, not packed)
- `deploy/Dockerfile`: container for a remote host (build locally; no image is published)
- No managed endpoint is operated; no hosted-service privacy policy or terms are published.

## Known limits
- Input checks are strict: unsupported arguments are rejected (`additionalProperties: false`). Error messages give a category, the field name, and allowed values, never the value you sent; a rejected CSV reports the toolkit's error code, column, and remediation without the cell or header text. One exception comes from the MCP SDK itself: a call to a tool name that does not exist is answered with `Unknown tool: <name>`.
- Tool calls are synchronous and use process-global stdout redirection, so they are fine for low traffic. Add a worker pool before heavy use.
- `validate_passport` with caller-supplied JSON: pass `passport_json`, `trusted_key_json`, and optionally `revocation_list_json` as JSON text strings, and they reach the reference validator. No evidence bundle is accepted over MCP yet, so evidence-bundle binding cannot run, and the validator stops before its validity-window and revocation checks (each reported as `NOT_RUN`). For a passport that passes the structure and signature checks, expect `verification_primary_status: BOUND_INPUTS_UNAVAILABLE`, `artifact_validation_status: INCOMPLETE`, `fully_validated: false`, and `reference_policy_disposition: NOT_PERMITTED`. Supplying `revocation_list_json` or `at_time` does not currently produce a revocation or validity verdict in this mode (use `check_tool_call` with a local evidence bundle for a full check), and the `REVOKED` result shown by `example: "signed-revoked"` (which runs with a bundled evidence set) does not carry over to caller-supplied passports. The output's `mode` field states this.
- Passport checks use the Agentic AI Governance `v0.1.0-alpha.2` validator, whose schemas stay open to change until an independent verifier confirms them. Pin an appropriate published [Global AI Governance Toolkit](https://github.com/GLOBAL-AI-GOVERNANCE/global-ai-governance-toolkit/releases/latest) tag for reproducible integrations.

## Security
This repository does not operate an external security-report intake. Do not place secrets, credentials, personal data, sensitive operational information, or vulnerability material in public GitHub surfaces.

## License
Apache-2.0. See [LICENSE](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp/blob/v0.4.0/LICENSE). The bundled pinned upstream files keep their own licenses, included alongside them in `src/gaig_mcp/_upstream/` (toolkit: MIT; agentic: Apache-2.0).

<!-- gaig:footer -->
## Part of Global AI Governance

AI Governance MCP is the agent interface: the Toolkit and Agentic AI Governance checks, callable by any MCP-capable agent.

**[ai-governance.solutions](https://ai-governance.solutions/)** · [Connect your agent](https://ai-governance.solutions/connect.html#agents) · [Specifications](https://ai-governance.solutions/connect.html#spec) · [All products](https://ai-governance.solutions/#products)

For agents: [llms.txt](https://ai-governance.solutions/llms.txt) · [machine-interface.json](https://ai-governance.solutions/machine-interface.json) · [AI Governance MCP](https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp) (`gaig-mcp`). Compatible with Model Context Protocol (MCP) based agents.

Framework-neutral and jurisdiction-neutral. Outputs are non-authorizing (`authority_effect: NONE`). Not affiliated with or endorsed by any AI lab or platform.
<!-- /gaig:footer -->
