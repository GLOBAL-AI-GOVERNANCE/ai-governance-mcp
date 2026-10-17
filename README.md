# gag-mcp: Global AI Governance MCP server (non-authorizing)

**Status:** v0.1.0. Built and tested locally on the Grok Bot box, Oct 16, 2026. **Not published, not deployed, not pushed to GitHub.**

gag-mcp lets any MCP-capable assistant (Claude, ChatGPT, Grok, and others) call the real Global AI Governance reference tooling:

| Tool | What it does | Upstream code it runs |
|---|---|---|
| `check_inventory` | Policy-as-code governance checks on an AI system inventory CSV. Returns findings by severity | `global-ai-governance-toolkit` `run_pipeline` (pinned `cf906ef`) |
| `build_decision_pack` | Prepares the digest-listed Decision Pack, verifies its integrity, and returns the manifest, the reference-only handoff, and optional Markdown documents | toolkit `run_pipeline` + `verify_output_directory` |
| `validate_passport` | Verifies an Agent Trust Passport: schema, semantics, Ed25519 signature, key trust, validity window, and signed revocation | `agentic-ai-governance` `tools/validate_artifact.py` (pinned `2124aea`) |

**Authority boundary, enforced in code and tests.** Every result carries `authority_effect: "NONE"`, the `review_boundary` text, and `human_decision_state: "PENDING_HUMAN_DECISION"`. Upstream fields that an assistant could paraphrase as an authorization are relabeled, with their values left verbatim:
- `operating_disposition` → `reference_policy_disposition`
- `issued_assessment_result` → `assessment_result_recorded_in_artifact`

The test suite fails if any output contains an authorization-like key, a non-`NONE` authority effect, `conditionally_authorized`, or a `PERMITTED` value outside the relabeled field. All three tools are annotated `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false`, and each has a `title`. Both the OpenAI and Anthropic directories require these annotations.

Not affiliated with or endorsed by xAI, OpenAI, or Anthropic. Compatible with MCP-based agents.

## Install and run (local)

```bash
cd gag-mcp
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
./scripts/fetch_upstreams.sh          # read-only clones of the two public repos, pinned
gag-mcp                               # stdio
gag-mcp --http --port 8000            # Streamable HTTP at http://127.0.0.1:8000/mcp ; GET /health
pytest                                # 16 tests
python scripts/smoke_test.py --transcript docs/verification-transcript.md
```

Protocol: the official Python SDK `mcp==2.3.0`, which speaks MCP **2026-07-28** (the current spec revision). The smoke test also confirms that handshake-era clients (`initialize` with `2025-06-18` / `2025-11-25`) work over HTTP. HTTP mode is stateless with JSON responses, which suits serverless hosts.

Environment variables (HTTP mode):

| Var | Purpose |
|---|---|
| `GAG_MCP_ALLOWED_HOSTS` | Comma-separated Host allow-list (DNS-rebinding protection). **Set this on any public host.** |
| `GAG_MCP_CORS_ORIGINS` | Comma-separated origins for browser-based clients (e.g., MCP Inspector). Off by default |
| `GAG_MCP_BEARER_TOKEN` | Optional static bearer token for private pilots. This is **not OAuth**; see "Auth" below |
| `GAG_TOOLKIT_PATH`, `GAG_AGENTIC_PATH` | Use other checkouts instead of `vendor/` |
| `HOST`, `PORT` | Bind address (defaults `127.0.0.1:8000`) |

## Client configuration (copy-paste)

Replace `/ABS/PATH/gag-mcp` and `https://YOUR-HOST` with your own values. Remote platforms (ChatGPT, the Claude API and claude.ai, the OpenAI, Anthropic, and xAI APIs, grok.com) **cannot reach stdio or localhost**. They need a public HTTPS URL (see "Hosting").

### Claude Desktop (local, stdio)
`claude_desktop_config.json` (Settings → Developer → Edit Config):
```json
{
  "mcpServers": {
    "gag": {
      "command": "/ABS/PATH/gag-mcp/.venv/bin/gag-mcp",
      "env": {
        "GAG_TOOLKIT_PATH": "/ABS/PATH/gag-mcp/vendor/global-ai-governance-toolkit",
        "GAG_AGENTIC_PATH": "/ABS/PATH/gag-mcp/vendor/agentic-ai-governance"
      }
    }
  }
}
```
One-click desktop extension: `manifest.json` (MCPB `manifest_version` 0.4) passes `mcpb validate`. Packing a `.mcpb` still needs platform-specific dependency bundling (`cryptography` has native wheels). Consider switching to the `uv` server type. **Not yet tested in Claude Desktop.**

### Claude.ai / Claude Desktop / mobile (remote custom connector)
Settings → Connectors → Add custom connector → URL `https://YOUR-HOST/mcp`. No auth is needed for this public, no-user-data server. Which plans can add custom connectors: **unverified**; check the Claude Help Center.

### Anthropic Messages API (MCP connector)
```bash
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" -H "anthropic-beta: mcp-client-2026-09-15" \
  -d '{
    "model": "CLAUDE_MODEL_ID", "max_tokens": 1500,
    "messages": [{"role": "user", "content": "Use gag to check the sample AI inventory and summarize the critical findings."}],
    "mcp_servers": [{"type": "url", "name": "gag", "url": "https://YOUR-HOST/mcp"}],
    "tools": [{"type": "mcp_toolset", "mcp_server_name": "gag"}]
  }'
```
(`mcp-client-2025-11-20` is the previous header. Add `"authorization_token"` to the server entry if you enable a bearer token.)

### OpenAI Responses API (remote MCP tool)
```bash
curl https://api.openai.com/v1/responses \
  -H "content-type: application/json" -H "authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "OPENAI_MODEL_ID",
    "input": "Use gag to verify the signed-revoked example passport and explain the result.",
    "tools": [{
      "type": "mcp", "server_label": "gag", "server_url": "https://YOUR-HOST/mcp",
      "allowed_tools": ["check_inventory", "build_decision_pack", "validate_passport"],
      "require_approval": "never"
    }]
  }'
```
(Add `"authorization": "TOKEN"` if a bearer token is enabled. For a server that is never exposed publicly, OpenAI documents a Secure MCP Tunnel (`tunnel_id`). That path is untested here.)

### ChatGPT (developer mode / custom app)
Enable developer mode (workspace admin on Business/Enterprise/Edu; Pro users get read/fetch MCP only, per OpenAI Help). Then create an app or connector with MCP server URL `https://YOUR-HOST/mcp` and authentication "None". All three tools are read-only. Exact menu labels change often, so they are **unverified**. Public listing goes through the OpenAI plugin submission portal.

### xAI Grok API (remote MCP tool)
```bash
curl https://api.x.ai/v1/responses \
  -H "content-type: application/json" -H "authorization: Bearer $XAI_API_KEY" \
  -d '{
    "model": "GROK_MODEL_ID",
    "input": "Use gag to run check_inventory on the sample and list critical findings.",
    "tools": [{
      "type": "mcp", "server_label": "gag", "server_url": "https://YOUR-HOST/mcp",
      "server_description": "Non-authorizing AI governance checks (authority_effect NONE)",
      "allowed_tools": ["check_inventory", "build_decision_pack", "validate_passport"]
    }]
  }'
```
xAI supports only Streamable HTTP or SSE; `require_approval` is not supported. In the xAI Python SDK, use `mcp(server_url=..., server_label="gag", allowed_tool_names=[...])`.

### Grok (grok.com consumer connectors)
grok.com/connectors → New Connector → Custom → enter `https://YOUR-HOST/mcp`. The server must be reachable on the public internet.

## Auth
- **Local stdio:** no auth. The MCP spec says stdio servers take credentials from the environment.
- **Public demo endpoint:** no auth is acceptable. The tools are read-only, process only caller-supplied data, and store nothing. Anthropic's directory allows no-auth for servers without user-specific data.
- **Private pilots:** `GAG_MCP_BEARER_TOKEN` works with the API connectors (`authorization` / `authorization_token` fields).
- **OAuth 2.1:** only needed if a hosted version ever holds per-user data. The MCP spec then requires Protected Resource Metadata (RFC 9728) plus an authorization server. Not implemented.

## Hosting (needed for every remote platform; nothing has been deployed)

| Option | Cost (per provider docs, Oct 2026) | Fit |
|---|---|---|
| Cloudflare Quick Tunnel (`cloudflared tunnel --url http://localhost:8000`) | Free, no account | **Demos only.** Random temporary URL; xAI's own cookbook uses this pattern |
| Render free web service (`deploy/Dockerfile`) | $0; 512 MB; spins down after 15 min idle (about 1 min cold start) | Cheapest always-addressable URL; cold starts may time out some clients (unverified) |
| Google Cloud Run (`deploy/Dockerfile`) | Free tier of 2M requests/month; billing account required | **Recommended** for directory submission. Scales to zero, HTTPS, custom domain |

Directory submissions also need a stable HTTPS domain the owner controls (ideally on a GAG domain), a published privacy policy and terms (drafts in `docs/`), a support contact, and, for OpenAI, domain verification at `/.well-known/openai-apps-challenge`.

**Privacy note:** a hosted endpoint changes the toolkit's "LOCAL · NO UPLOAD" promise for that mode. Label it clearly, and keep stdio as the private default.

## Files
- `src/gag_mcp/core.py`: transport-independent logic plus the authority envelope
- `src/gag_mcp/server.py`: MCP server (stdio and Streamable HTTP, `/health`, CORS, optional bearer)
- `tests/`: 16 tests (core behavior, determinism, fail-closed input, non-authorizing invariants, in-process, stdio, and HTTP transports, bearer enforcement)
- `scripts/smoke_test.py`, `docs/verification-transcript.md`: real-client verification
- `scripts/fetch_upstreams.sh`: pinned upstream clones
- `manifest.json`: MCPB desktop-extension manifest (validated, not packed)
- `deploy/Dockerfile`: container for a remote host (not built)
- `docs/PRIVACY-DRAFT.md`, `docs/TERMS-DRAFT.md`: drafts for owner review

## Known limits
- Tool calls are synchronous and use process-global stdout redirection, so they are fine for low traffic. Add a worker pool before heavy use.
- `validate_passport` with caller-supplied JSON can't run full evidence-bundle binding checks, because no bundle is accepted over MCP yet. The output says this.
- The agentic validator is an experimental alpha, and toolkit `main` is ahead of tag v2.3.0. Pin to tags before publishing.

## Support and contact
Questions, integrations, and pilot requests: [GitHub Discussions](https://github.com/GLOBAL-AI-GOVERNANCE/gag-mcp/discussions). Security issues: see the [Global AI Governance security policy](https://github.com/GLOBAL-AI-GOVERNANCE/.github/blob/main/SECURITY.md).

## License
Apache-2.0. See [LICENSE](LICENSE). The pinned upstream repositories fetched by `scripts/fetch_upstreams.sh` keep their own licenses (toolkit: MIT; agentic: Apache-2.0). gag-mcp is compatible with MCP-based agents. It is not affiliated with or endorsed by any model provider.
