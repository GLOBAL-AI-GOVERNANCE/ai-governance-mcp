# AGENTS.md

Instructions for coding agents working in this repository.

## Setup and tests

```bash
python -m venv .venv && . .venv/bin/activate
./scripts/fetch_upstreams.sh            # pinned upstream sources
pip install -e ".[dev]"
python -m pytest
```

Interop tests (`tests/test_interop.py` and the SDK tests in `tests/test_guards.py`) skip unless the pinned SDKs are installed:
`pip install a2a-sdk==1.2.3 opentelemetry-sdk==1.45.1 langgraph==1.2.17 openai-agents==0.24.0 claude-agent-sdk==0.2.174`.

## Ground rules

- Every tool result keeps `authority_effect: "NONE"`. Do not add a code path that approves, certifies, or authorizes.
- Level 5 actions are always denied. Level 4 asks by default; only an operator-listed automated approver may answer it.
- Mark integrations TESTED only when a test in this repository runs them; otherwise say untested.
- Install instructions pin a release tag from GitHub (`@v0.5.1`), not a package index.
- Keep the upstream pins in `src/gaig_mcp/_upstream` in sync with `scripts/bundle_upstreams.py --check`.
