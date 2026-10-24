#!/usr/bin/env bash
# Fetch the two public GLOBAL-AI-GOVERNANCE repos AI Governance MCP wraps.
# Defaults are exact source locks. Explicit TOOLKIT_REF / AGENTIC_REF overrides are caller-controlled and are not the default lock.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor"

DEFAULT_TOOLKIT_REF="4deb5b70b07d8f91cf157ef07d7ddd7dfe68731c"
DEFAULT_AGENTIC_REF="58bdfb291df0de7c9437b4476e370a609c4b1d5f"

TOOLKIT_REF="${TOOLKIT_REF:-$DEFAULT_TOOLKIT_REF}"
AGENTIC_REF="${AGENTIC_REF:-$DEFAULT_AGENTIC_REF}"

TOOLKIT_EXPECTED="$DEFAULT_TOOLKIT_REF"
AGENTIC_EXPECTED="$DEFAULT_AGENTIC_REF"
[[ "$TOOLKIT_REF" == "$DEFAULT_TOOLKIT_REF" ]] || TOOLKIT_EXPECTED=""
[[ "$AGENTIC_REF" == "$DEFAULT_AGENTIC_REF" ]] || AGENTIC_EXPECTED=""

mkdir -p "$VENDOR"

fetch() { # name url ref expected-default-sha-or-empty
  local name="$1" url="$2" ref="$3" expected="$4"
  local dir="$VENDOR/$name"

  if [[ -z "$expected" ]]; then
    printf 'NOTICE: %s uses an explicit caller override (%s); default exact source lock is bypassed for this fetch.\n' "$name" "$ref" >&2
  fi

  if [[ ! -d "$dir/.git" ]]; then
    git clone -q "$url" "$dir"
  fi

  git -C "$dir" fetch -q origin
  git -C "$dir" checkout -q "$ref"

  local resolved
  resolved="$(git -C "$dir" rev-parse HEAD)"

  if [[ -n "$expected" && "$resolved" != "$expected" ]]; then
    printf 'SOURCE LOCK MISMATCH: %s resolved %s, expected %s\n' "$name" "$resolved" "$expected" >&2
    exit 1
  fi

  printf '%s @ %s\n' "$name" "$resolved"
}

fetch global-ai-governance-toolkit https://github.com/GLOBAL-AI-GOVERNANCE/global-ai-governance-toolkit.git "$TOOLKIT_REF" "$TOOLKIT_EXPECTED"
fetch agentic-ai-governance https://github.com/GLOBAL-AI-GOVERNANCE/agentic-ai-governance.git "$AGENTIC_REF" "$AGENTIC_EXPECTED"
