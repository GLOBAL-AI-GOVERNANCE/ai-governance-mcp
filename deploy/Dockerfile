# gag-mcp remote (Streamable HTTP) image. NOT built or deployed yet; for Render / Cloud Run / any container host.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
RUN ./scripts/fetch_upstreams.sh && pip install --no-cache-dir .
ENV HOST=0.0.0.0 PORT=8080
# Set GAG_MCP_ALLOWED_HOSTS=<your-hostname> in the host's environment (DNS-rebinding allow-list).
# Optional: GAG_MCP_BEARER_TOKEN for private pilots; GAG_MCP_CORS_ORIGINS for browser clients.
EXPOSE 8080
USER nobody
CMD ["sh", "-c", "gag-mcp --http --host $HOST --port $PORT"]
