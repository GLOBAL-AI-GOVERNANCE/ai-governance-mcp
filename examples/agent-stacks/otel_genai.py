#!/usr/bin/env python3
"""OpenTelemetry GenAI attributes for Action Level guard decisions.

Status: TESTED (tests/test_interop.py records spans with opentelemetry-sdk 1.45.1 and an in-memory exporter).
Not run against a collector or a vendor backend.

Emits an `execute_tool {gen_ai.tool.name}` span (kind INTERNAL) with the GenAI semantic convention
attributes for tool execution (`gen_ai.operation.name`, `gen_ai.tool.name`, and when known
`gen_ai.agent.name`, `gen_ai.tool.call.id`, `gen_ai.tool.type`), plus `gaig.*` attributes for the
guard outcome. Tool arguments and results are not recorded (they are opt-in in the conventions and
often hold personal data). The GenAI conventions are in Development status and may change.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_level_guard import GuardDecision  # noqa: E402


def tool_span_attributes(decision: GuardDecision, *, agent_name: str | None = None,
                         call_id: str | None = None, tool_type: str | None = "function",
                         conversation_id: str | None = None) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": decision.tool,
        "gaig.action_level": decision.level,
        "gaig.action_level.source": decision.level_source,
        "gaig.guard.decision": decision.decision,
        "gaig.guard.reason": decision.reason,
        "gaig.authority_effect": "NONE",
    }
    optional = {"gen_ai.agent.name": agent_name, "gen_ai.tool.call.id": call_id,
                "gen_ai.tool.type": tool_type, "gen_ai.conversation.id": conversation_id,
                "gaig.guard.approved_by": decision.approved_by}
    attrs.update({k: v for k, v in optional.items() if v is not None})
    return attrs


def start_tool_span(tracer, decision: GuardDecision, **kwargs):
    """Context manager: `with start_tool_span(tracer, guard.decide(name), agent_name="lead"):` run the tool."""
    from opentelemetry.trace import SpanKind

    return tracer.start_as_current_span(f"execute_tool {decision.tool}", kind=SpanKind.INTERNAL,
                                        attributes=tool_span_attributes(decision, **kwargs))
