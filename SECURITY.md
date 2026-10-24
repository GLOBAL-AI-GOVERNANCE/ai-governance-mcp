# Security Policy

This repository does not operate an external security-report intake. Do not place secrets, credentials, personal data, sensitive operational information, or vulnerability material in public GitHub surfaces.

## Security Scope

Security-relevant failure classes for this repository include:

- A tool that writes, executes, or authorizes anything (all tools are read-only and non-authorizing)
- Network transport that starts without `GAIG_MCP_ALLOWED_HOSTS` and `GAIG_MCP_BEARER_TOKEN` when reachable beyond loopback
- Bearer-token, Host allow-list, or CORS checks that can be bypassed
- Vendored Toolkit or Agentic files that diverge from their pinned upstream releases
- Inventory or passport content leaking into logs or error messages
- Misleading approval, compliance, or certification behavior
- Workflow and package supply-chain risk

## Principle

> No trust without verification.
