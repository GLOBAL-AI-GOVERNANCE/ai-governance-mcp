#!/usr/bin/env bash
# Fetch the two public GLOBAL-AI-GOVERNANCE repos AI Governance MCP (gag-mcp) wraps, pinned to known commits.
# Read-only clones. Override pins with TOOLKIT_REF / AGENTIC_REF.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor"
TOOLKIT_REF="${TOOLKIT_REF:-cf906ef62c114a16b017a073c30f74933b8399e5}"
AGENTIC_REF="${AGENTIC_REF:-2124aea}"
mkdir -p "$VENDOR"
fetch() { # name url ref
  local dir="$VENDOR/$1"
  if [ ! -d "$dir/.git" ]; then git clone -q "$2" "$dir"; fi
  git -C "$dir" fetch -q origin
  git -C "$dir" checkout -q "$3"
  echo "$1 @ $(git -C "$dir" rev-parse --short HEAD)"
}
fetch global-ai-governance-toolkit https://github.com/GLOBAL-AI-GOVERNANCE/global-ai-governance-toolkit.git "$TOOLKIT_REF"
fetch agentic-ai-governance https://github.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance.git "$AGENTIC_REF"
