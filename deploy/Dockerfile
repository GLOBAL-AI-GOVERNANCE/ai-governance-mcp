# AI Governance MCP (command: gaig-mcp) remote Streamable HTTP image. Not built or deployed by the maintainers; for Render / Cloud Run / any container host.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md MANIFEST.in ./
COPY src ./src
COPY scripts ./scripts
# Pinned toolkit and agentic files are bundled under src/gaig_mcp/_upstream; no fetch step is needed.
RUN pip install --no-cache-dir .
ENV HOST=0.0.0.0 PORT=8080
# Required in the host's environment (the server refuses to start on HOST=0.0.0.0 without both):
#   GAIG_MCP_ALLOWED_HOSTS=<your-hostname>   DNS-rebinding allow-list
#   GAIG_MCP_BEARER_TOKEN=<random secret, 32+ characters>   clients send Authorization: Bearer <secret>
# Optional: GAIG_MCP_CORS_ORIGINS for browser clients.
# Only GAIG_* names are read. A pre-v0.3.0 setting name left in the environment refuses to start.
EXPOSE 8080
USER nobody
CMD ["sh", "-c", "gaig-mcp --http --host $HOST --port $PORT"]
