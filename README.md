# AI Governance Model Context Protocol Server (AI Governance MCP)

Governance checks your AI agents can call. Start the server with one command, and your agent can check an AI system inventory, prepare a Decision Pack, or verify an Agent Trust Passport. Every result is read-only and leaves the decision with a person.

```bash
uvx --from git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.2.0 gaig-mcp
```

**Model Context Protocol (MCP)** is an open standard that lets AI assistants discover and call external tools through a common interface. This repository is a non-authorizing MCP server for Global AI Governance reference tooling.

**Status:** v0.2.0 preview. Source is public in this repository (formerly `gag-mcp`; the old URL redirects). **No hosted endpoint is operated**, and it has not been submitted to any platform directory.

**Names:** the console command is `gaig-mcp`, the import package is `gaig_mcp`, the MCP server name reported to clients is `gaig-mcp`, and environment variables use the `GAIG_MCP_` / `GAIG_` prefixes. The Python distribution name and the desktop-extension manifest `name` stay `gag-mcp` so existing installs upgrade in place.

**Deprecated aliases (kept so existing configurations keep working):** the `gag-mcp` command and `python -m gag_mcp.server` start the same server; `import gag_mcp` resolves to `gaig_mcp`; and each `GAG_*` environment variable is still read when its `GAIG_*` name is unset, with a deprecation warning on stderr. If both names are set to different values, the server refuses to start.

AI Governance MCP exposes the real Global AI Governance reference tooling to MCP clients:

| Tool | What it does | Upstream code it runs |
|---|---|---|
| `check_inventory` | Policy-as-code governance checks on an AI system inventory CSV. Returns findings by severity | `global-ai-governance-toolkit` `run_pipeline` (pinned `f454bf921b774f17982e70f28ce01a224d3c6410`, release v2.6.0) |
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
uvx --from git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.2.0 gaig-mcp      # stdio
```

TESTED in a clean environment. Copy-paste client configs for Cursor, VS Code, and Codex are in [`examples/client-configs/`](examples/client-configs/); agent-framework patterns are in [`examples/agent-stacks/`](examples/agent-stacks/).

From source:

```bash
git clone https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp.git
cd ai-governance-mcp
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
gaig-mcp                              # stdio
gaig-mcp --http --port 8000           # Streamable HTTP at http://127.0.0.1:8000/mcp ; GET /health
pytest                                # 94 tests
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

Expected last line: `VALID 0` (the toolkit also prints its progress lines). [`docs/examples/minimal-inventory.csv`](docs/examples/minimal-inventory.csv) holds the required header row and one synthetic system; replace the row with your own systems. The same file is installed with the package, so a pip or uvx install without a clone can use `from gaig_mcp.core import minimal_inventory_csv` and pass `minimal_inventory_csv()` as `inventory_csv`. If a column is missing, `check_inventory` fails closed with `MISSING_REQUIRED_COLUMN`, lists the required columns, and points to this file.

Package-only install (no clone): `pip install "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.2.0"`. The pinned upstream files are included. Running `scripts/smoke_test.py` against a package install also needs the dev extra: `pip install "gag-mcp[dev] @ git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp.git"`.

Protocol: the official Python SDK `mcp==2.3.0`, which speaks MCP **2026-07-28** (the current spec revision). The smoke test also confirms that handshake-era clients (`initialize` with `2025-06-18` / `2025-11-25`) work over HTTP. HTTP mode is stateless with JSON responses, which suits serverless hosts.

Environment variables (HTTP mode):

| Var | Purpose |
|---|---|
| `GAIG_MCP_ALLOWED_HOSTS` | Comma-separated Host allow-list (DNS-rebinding protection). **Required for any non-loopback bind:** with `HOST`/`--host` other than `127.0.0.1`, `localhost`, or `::1`, the server refuses to start until this is set. |
| `GAIG_MCP_CORS_ORIGINS` | Comma-separated origins for browser-based clients (e.g., MCP Inspector). Off by default |
| `GAIG_MCP_BEARER_TOKEN` | Static bearer token, at least 32 characters (for example `python -c "import secrets; print(secrets.token_urlsafe(32))"`). **Required whenever other machines can reach the server:** a non-loopback bind, or a `GAIG_MCP_ALLOWED_HOSTS` entry that is not loopback (reverse proxy or tunnel). Without it the server refuses to start. Optional for loopback-only use. This is **not OAuth**; see "Auth" below |
| `GAIG_TOOLKIT_PATH`, `GAIG_AGENTIC_PATH` | Use other checkouts instead of the bundled pinned files |
| `HOST`, `PORT` | Bind address (defaults `127.0.0.1:8000`) |

The deprecated `GAG_MCP_ALLOWED_HOSTS`, `GAG_MCP_CORS_ORIGINS`, `GAG_MCP_BEARER_TOKEN`, `GAG_TOOLKIT_PATH`, and `GAG_AGENTIC_PATH` names are still honored as fallbacks with the same fail-closed rules, including the loopback-plus-tunnel case.

## Client configuration (copy-paste)

Replace `https://YOUR-HOST` and `TOKEN` with your own values. Local stdio configs for Cursor, VS Code, and Codex: [`examples/client-configs/`](examples/client-configs/). Remote platforms (ChatGPT, the Claude API and claude.ai, the OpenAI, Anthropic, and xAI APIs, grok.com) **cannot reach stdio or localhost**. They need an HTTPS URL that you host yourself (see "Self-hosting") and must send `Authorization: Bearer TOKEN`, where `TOKEN` is your `GAIG_MCP_BEARER_TOKEN`. None of the remote recipes below has been tested against a live provider.

### Claude Desktop (local, stdio)
`claude_desktop_config.json` (Settings → Developer → Edit Config):
```json
{
  "mcpServers": {
    "gaig": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/GLOBAL-AI-GOVERNANCE/ai-governance-mcp@v0.2.0", "gaig-mcp"]
    }
  }
}
```
Launch command TESTED with the MCP Python SDK stdio client; this config is not tested inside Claude Desktop.

One-click desktop extension: `manifest.json` (MCPB `manifest_version` 0.4) passes `mcpb validate`. Packing a `.mcpb` still needs platform-specific dependency bundling (`cryptography` has native wheels). **Not yet tested in Claude Desktop.**

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
- `src/gaig_mcp/core.py`: transport-independent logic plus the authority envelope
- `src/gaig_mcp/server.py`: MCP server (stdio and Streamable HTTP, `/health`, CORS, bearer token required for network use)
- `src/gaig_mcp/_upstream/`: pinned toolkit and agentic files bundled into the package, with `UPSTREAM_LOCK.json` (commit, file count, tree digest per upstream)
- `src/gag_mcp/`: deprecated import alias of `gaig_mcp`
- `tests/`: 94 tests (core behavior, determinism, fail-closed input, non-authorizing invariants, in-process, stdio, and HTTP transports, bearer enforcement, and security regressions for host allow-listing, uniform 401s, sanitized errors, unknown-argument rejection, and the required bearer token for network exposure, plus compatibility guards, bundle-lock checks, and example and client-config checks)
- `scripts/smoke_test.py`, `docs/verification-transcript.md`: real-client verification
- `scripts/fetch_upstreams.sh`: pinned upstream clones; `scripts/bundle_upstreams.py`: copies them into the package and checks the bundle (`--check`, run in CI)
- `examples/client-configs/`, `examples/agent-stacks/`: copy-paste client configs and agent-framework patterns, each labelled TESTED or untested
- `.github/workflows/release-assets.yml`: builds the wheel and sdist from a release tag, installs them in a clean environment, and attaches them with `SHA256SUMS` to the release. For releases published after v0.2.0, it also attaches a CycloneDX SBOM of the clean install (`*.cdx.json`) and records a GitHub build-provenance attestation for every asset in `SHA256SUMS` (check with `gh attestation verify <file> --repo GLOBAL-AI-GOVERNANCE/ai-governance-mcp`). Releases up to and including v0.2.0 have no SBOM or attestation
- `manifest.json`: MCPB desktop-extension manifest (validated, not packed)
- `deploy/Dockerfile`: container for a remote host (build locally; no image is published)
- No managed endpoint is operated; no hosted-service privacy policy or terms are published.

## Known limits
- Input checks are strict: unsupported arguments are rejected (`additionalProperties: false`). Error messages give a category, the field name, and allowed values, never the value you sent; a rejected CSV reports the toolkit's error code, column, and remediation without the cell or header text. One exception comes from the MCP SDK itself: a call to a tool name that does not exist is answered with `Unknown tool: <name>`.
- Tool calls are synchronous and use process-global stdout redirection, so they are fine for low traffic. Add a worker pool before heavy use.
- `validate_passport` with caller-supplied JSON: pass `passport_json`, `trusted_key_json`, and optionally `revocation_list_json` as JSON text strings, and they reach the reference validator. No evidence bundle is accepted over MCP yet, so evidence-bundle binding cannot run, and the validator stops before its validity-window and revocation checks (each reported as `NOT_RUN`). For a passport that passes the structure and signature checks, expect `verification_primary_status: BOUND_INPUTS_UNAVAILABLE`, `artifact_validation_status: INCOMPLETE`, `fully_validated: false`, and `reference_policy_disposition: NOT_PERMITTED`. Supplying `revocation_list_json` or `at_time` does not currently produce a revocation or validity verdict in this mode, and the `REVOKED` result shown by `example: "signed-revoked"` (which runs with a bundled evidence set) does not carry over to caller-supplied passports. The output's `mode` field states this.
- The agentic validator is an experimental alpha. Pin an appropriate published [Global AI Governance Toolkit](https://github.com/GLOBAL-AI-GOVERNANCE/global-ai-governance-toolkit/releases/latest) tag for reproducible integrations.

## Security
This repository does not operate an external security-report intake. Do not place secrets, credentials, personal data, sensitive operational information, or vulnerability material in public GitHub surfaces.

## License
Apache-2.0. See [LICENSE](LICENSE). The bundled pinned upstream files keep their own licenses, included alongside them in `src/gaig_mcp/_upstream/` (toolkit: MIT; agentic: Apache-2.0).
