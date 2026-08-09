from __future__ import annotations

from dataclasses import dataclass, field

from .intent import ChatIntent


@dataclass(slots=True)
class PlannedAction:
    name: str
    description: str
    enabled: bool = True
    metadata: dict[str, str] = field(default_factory=dict)


def build_chat_plan(intent: ChatIntent) -> list[PlannedAction]:
    plan: list[PlannedAction] = []

    if intent.needs_retrieval:
        plan.append(
            PlannedAction(
                name="knowledge_retrieval",
                description="Reuse the existing hybrid retrieval pipeline for note and memory context.",
            )
        )

    if intent.needs_tools:
        plan.append(
            PlannedAction(
                name="tool_calls",
                description="Resolve tool requests through registered chat tools if available.",
            )
        )

    if not plan:
        plan.append(
            PlannedAction(
                name="direct_llm",
                description="Answer directly from conversation context when no retrieval or tools are needed.",
            )
        )

    return plan
