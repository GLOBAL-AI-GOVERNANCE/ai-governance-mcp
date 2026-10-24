# AI Governance MCP (command: gag-mcp) remote Streamable HTTP image. Not built or deployed by the maintainers; for Render / Cloud Run / any container host.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md MANIFEST.in ./
COPY src ./src
COPY scripts ./scripts
# Pinned toolkit and agentic files are bundled under src/gag_mcp/_upstream; no fetch step is needed.
RUN pip install --no-cache-dir .
ENV HOST=0.0.0.0 PORT=8080
# Required in the host's environment (the server refuses to start on HOST=0.0.0.0 without both):
#   GAG_MCP_ALLOWED_HOSTS=<your-hostname>   DNS-rebinding allow-list
#   GAG_MCP_BEARER_TOKEN=<random secret, 32+ characters>   clients send Authorization: Bearer <secret>
# Optional: GAG_MCP_CORS_ORIGINS for browser clients.
EXPOSE 8080
USER nobody
CMD ["sh", "-c", "gag-mcp --http --host $HOST --port $PORT"]
