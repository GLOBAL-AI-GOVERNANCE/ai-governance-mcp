#!/usr/bin/env python3
"""LangGraph StateGraph where each agent node runs only after its Agent Trust Passport verifies.

Status: TESTED (tests/test_interop.py compiles and invokes this graph with langgraph 1.2.17, offline,
using the built-in synthetic passports). Not run with caller-supplied passports or a model.

A node whose passport does not verify is held for an accountable person instead of running.
A verified passport is a precondition, not an authorization; gaig-mcp results keep authority_effect NONE.
Run:    python examples/agent-stacks/langgraph_passport_gate.py   (needs langgraph and gaig-mcp)
"""
from __future__ import annotations

import json
import operator
import sys
from typing import Annotated, Callable, TypedDict

from gaig_mcp.core import validate_passport


def _merge(a: dict, b: dict) -> dict:
    return {**a, **b}


class GraphState(TypedDict):
    task: str
    outputs: Annotated[dict, _merge]
    held: Annotated[dict, _merge]
    ledger: Annotated[list, operator.add]


def gated_node(agent: str, passport_example: str, work: Callable[[GraphState], str]):
    def node(state: GraphState) -> dict:
        out = validate_passport(example=passport_example)
        assert out["authority_effect"] == "NONE"
        status = out["result"]["verification"]["verification_primary_status"]
        entry = {"agent": agent, "passport_status": status}
        if status != "VALID":
            return {"held": {agent: f"passport status {status}; held for an accountable person"},
                    "ledger": [{**entry, "ran": False}]}
        return {"outputs": {agent: work(state)}, "ledger": [{**entry, "ran": True}]}
    return node


def build_graph(agents: list[tuple[str, str, Callable[[GraphState], str]]]):
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(GraphState)
    previous = START
    for name, example, work in agents:
        graph.add_node(name, gated_node(name, example, work))
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    return graph.compile()


AGENTS = [
    ("researcher", "signed-unrevoked", lambda s: f"draft findings for: {s['task']}"),
    ("reviewer", "signed-revoked", lambda s: "review notes"),
]


def main() -> int:
    final = build_graph(AGENTS).invoke({"task": "summarize inventory gaps", "outputs": {}, "held": {}, "ledger": []})
    print(json.dumps({"ran": sorted(final["outputs"]), "held": final["held"], "ledger": final["ledger"]}, indent=2))
    return 0 if "researcher" in final["outputs"] and "reviewer" in final["held"] else 1


if __name__ == "__main__":
    sys.exit(main())
