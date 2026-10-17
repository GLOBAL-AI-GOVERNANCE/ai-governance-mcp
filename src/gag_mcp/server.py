"""gag-mcp MCP server: stdio and Streamable HTTP.

Run:
  gag-mcp                      # stdio (Claude Desktop, local clients)
  gag-mcp --http --port 8000   # Streamable HTTP at http://127.0.0.1:8000/mcp
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
from typing import Annotated, Any, Literal

from pydantic import Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from . import __version__, core

INSTRUCTIONS = (
    "Global AI Governance reference tools. check_inventory finds governance gaps in an AI system "
    "inventory CSV; build_decision_pack prepares a digest-listed Decision Pack for an accountable "
    "human; validate_passport verifies an Agent Trust Passport against a trusted key and revocation "
    "list. Every result carries authority_effect NONE: nothing here approves deployment, certifies "
    "compliance, grants authorization, or accepts risk. Relay review_boundary to the user verbatim."
)

READ_ONLY = dict(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

mcp = MCPServer(
    name="gag-mcp",
    title="Global AI Governance (non-authorizing)",
    description="Local-first AI governance checks, Decision Packs, and Agent Trust Passport verification.",
    instructions=INSTRUCTIONS,
    website_url="https://global-ai-governance.github.io/global-ai-governance-toolkit/",
    version=__version__,
)


def _guard(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        return fn(*args, **kwargs)
    except core.GagInputError as exc:
        raise ToolError(f"{exc} (authority_effect: NONE; nothing was evaluated as approved)") from exc


@mcp.tool(
    title="Check AI inventory for governance gaps",
    description=(
        "Run the Global AI Governance toolkit's policy-as-code checks on an AI system inventory CSV "
        "(toolkit template columns) and return findings by severity. Set use_sample=true to run the "
        "synthetic sample. Output is non-authorizing (authority_effect NONE)."
    ),
    annotations=ToolAnnotations(title="Check AI inventory for governance gaps", **READ_ONLY),
)
def check_inventory(inventory_csv: Annotated[str | None, Field(description="AI system inventory as CSV text with a header row (toolkit template columns: system_id, system_name, owner, ... evidence_complete). Max 1 MB. Omit when use_sample is true.")] = None,
                    use_sample: Annotated[bool, Field(description="Run the toolkit's synthetic sample inventory instead of caller CSV.")] = False,
                    evaluation_time: Annotated[str | None, Field(description="Optional fixed UTC time (ISO 8601, e.g. 2026-10-16T00:00:00Z) for byte-reproducible output.")] = None) -> dict[str, Any]:
    return _guard(core.check_inventory, inventory_csv, use_sample, evaluation_time)


@mcp.tool(
    title="Prepare a Decision Pack for human review",
    description=(
        "Run the toolkit pipeline and return the Decision Pack manifest (files + SHA-256 digests), the "
        "integrity-check result, and the reference-only handoff. include_documents=true also returns the "
        "Markdown documents for the decision-maker. The pack prepares a decision; it is not the decision."
    ),
    annotations=ToolAnnotations(title="Prepare a Decision Pack for human review", **READ_ONLY),
)
def build_decision_pack(inventory_csv: Annotated[str | None, Field(description="AI system inventory as CSV text with a header row (toolkit template columns: system_id, system_name, owner, ... evidence_complete). Max 1 MB. Omit when use_sample is true.")] = None,
                        use_sample: Annotated[bool, Field(description="Run the toolkit's synthetic sample inventory instead of caller CSV.")] = False,
                        evaluation_time: Annotated[str | None, Field(description="Optional fixed UTC time (ISO 8601, e.g. 2026-10-16T00:00:00Z) for byte-reproducible output.")] = None,
                        include_documents: Annotated[bool, Field(description="Also return the Markdown documents for the decision-maker (each capped at 20,000 chars).")] = False) -> dict[str, Any]:
    return _guard(core.build_decision_pack, inventory_csv, use_sample, evaluation_time, include_documents)


@mcp.tool(
    title="Verify an Agent Trust Passport",
    description=(
        "Verify an Agent Trust Passport (agentic-ai-governance reference validator): schema, semantics, "
        "Ed25519 signature, key trust, validity window, and signed revocation. Use example='signed-unrevoked' "
        "or 'signed-revoked' for synthetic demos, or pass passport_json and trusted_key_json (and optionally "
        "revocation_list_json) as JSON strings. Verification is not authorization (authority_effect NONE)."
    ),
    annotations=ToolAnnotations(title="Verify an Agent Trust Passport", **READ_ONLY),
)
def validate_passport(example: Annotated[Literal["signed-unrevoked", "signed-revoked"] | None, Field(description="Synthetic demo passport (test-only keys). Omit to verify caller-supplied JSON.")] = None,
                      passport_json: Annotated[str | None, Field(description="Agent Trust Passport as a JSON string.")] = None,
                      trusted_key_json: Annotated[str | None, Field(description="Trusted Ed25519 verification key as a JSON string (required with passport_json).")] = None,
                      revocation_list_json: Annotated[str | None, Field(description="Signed revocation list as a JSON string (optional).")] = None,
                      at_time: Annotated[str | None, Field(description="Evaluation time, UTC ISO 8601. Defaults to the example's fixed time or now.")] = None) -> dict[str, Any]:
    return _guard(core.validate_passport, example, passport_json, trusted_key_json, revocation_list_json, at_time)


@mcp.custom_route("/health", methods=["GET"])
async def health(request):  # pragma: no cover - exercised by smoke test
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok", "server": "gag-mcp", "version": __version__, "authority_effect": "NONE"})


# ----------------------------------------------------------------------------- HTTP app
class _BearerAuth:
    """Optional static bearer token (GAG_MCP_BEARER_TOKEN). Not OAuth; see README for directory listings."""

    def __init__(self, app, token: str):
        self.app, self.token = app, token.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith("/mcp") and scope.get("method") != "OPTIONS":
            auth = dict(scope.get("headers") or []).get(b"authorization", b"")
            if not (auth.startswith(b"Bearer ") and hmac.compare_digest(auth[7:], self.token)):
                body = json.dumps({"error": "unauthorized"}).encode()
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def build_http_app(host: str = "127.0.0.1"):
    allowed_hosts = [h.strip() for h in os.environ.get("GAG_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    origins = [o.strip() for o in os.environ.get("GAG_MCP_CORS_ORIGINS", "").split(",") if o.strip()]
    security = None
    if allowed_hosts:
        security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                             allowed_hosts=allowed_hosts, allowed_origins=origins)
    elif host not in ("127.0.0.1", "localhost", "::1"):
        # Public bind without an allow-list: the operator must set GAG_MCP_ALLOWED_HOSTS.
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    app = mcp.streamable_http_app(stateless_http=True, json_response=True, transport_security=security, host=host)
    if origins:
        from starlette.middleware.cors import CORSMiddleware
        app = CORSMiddleware(app, allow_origins=origins, allow_methods=["GET", "POST", "OPTIONS"],
                             allow_headers=["*"], expose_headers=["Mcp-Session-Id", "MCP-Protocol-Version"])
    token = os.environ.get("GAG_MCP_BEARER_TOKEN")
    if token:
        app = _BearerAuth(app, token)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(prog="gag-mcp", description="Non-authorizing Global AI Governance MCP server.")
    parser.add_argument("--http", action="store_true", help="Serve Streamable HTTP instead of stdio.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()
    if not args.http:
        mcp.run("stdio")
        return
    import uvicorn
    uvicorn.run(build_http_app(args.host), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
