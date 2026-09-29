from __future__ import annotations

from .intent import ChatIntent
from .routing_contracts import RoutingPlanStep


def build_chat_plan(intent: ChatIntent) -> list[RoutingPlanStep]:
    plan: list[RoutingPlanStep] = []

    if intent.needs_retrieval:
        plan.append(
            RoutingPlanStep(
                name="knowledge_retrieval",
                description="Reuse the existing hybrid retrieval pipeline for note and memory context.",
            )
        )

    if intent.needs_tools:
        plan.append(
            RoutingPlanStep(
                name="tool_calls",
                description="Resolve tool requests through registered chat tools if available.",
            )
        )

    if not plan:
        plan.append(
            RoutingPlanStep(
                name="direct_llm",
                description="Answer directly from conversation context when no retrieval or tools are needed.",
            )
        )

    return plan
