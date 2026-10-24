#!/usr/bin/env python3
"""LangGraph-style per-agent Passport check, written as plain Python (no LangGraph dependency).

Each agent node in a multi-agent graph runs only after its Agent Trust Passport verifies.
A verified passport is a precondition, not an authorization: the node still hands its output
to an accountable human, and every gag-mcp result keeps authority_effect NONE.

Status: TESTED (tests/test_examples.py runs this file). The LangGraph mapping at the bottom is untested.
Run:    python examples/agent-stacks/passport_gate_graph.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable

from gag_mcp.core import validate_passport


@dataclass
class State:
    task: str
    outputs: dict[str, str] = field(default_factory=dict)
    held: dict[str, str] = field(default_factory=dict)


def passport_gate(agent: str, passport_example: str, node: Callable[[State], str]) -> Callable[[State], State]:
    """Wrap a node so it runs only when the agent's passport verifies as VALID."""
    def gated(state: State) -> State:
        out = validate_passport(example=passport_example)
        assert out["authority_effect"] == "NONE"
        status = out["result"]["verification"]["verification_primary_status"]
        if status != "VALID":
            state.held[agent] = f"held: passport status {status}; route to an accountable human"
            return state
        state.outputs[agent] = node(state)
        return state
    return gated


def researcher(state: State) -> str:
    return f"draft findings for: {state.task}"


def reviewer(state: State) -> str:
    return "review notes"


GRAPH = [
    passport_gate("researcher", "signed-unrevoked", researcher),
    passport_gate("reviewer", "signed-revoked", reviewer),
]


def main() -> int:
    state = State(task="summarize inventory gaps")
    for step in GRAPH:
        state = step(state)
    print("ran:", sorted(state.outputs))
    print("held:", state.held)
    print("human_decision_state: PENDING_HUMAN_DECISION")
    return 0 if "researcher" in state.outputs and "reviewer" in state.held else 1


# LangGraph mapping (untested): add each gated callable as a node, e.g.
#   graph.add_node("researcher", passport_gate("researcher", "signed-unrevoked", researcher))
# and pass a real passport, trusted key, and revocation list to validate_passport() instead of a
# built-in example. See the README "Known limits" for what caller-supplied passports can verify today.

if __name__ == "__main__":
    sys.exit(main())
