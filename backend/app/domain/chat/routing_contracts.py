from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RouteKind = Literal["conversation", "note_search", "tool", "mixed", "abstain", "direct"]


@dataclass(slots=True)
class RoutingPlanStep:
    name: str
    description: str
    enabled: bool = True
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class GroundingSnapshot:
    status: str
    confidence: float
    allow_answer: bool
    top_claim: str | None = None
    summary: str = ""
    source_refs: list[str] = field(default_factory=list)
    fallback_message: str | None = None


@dataclass(slots=True)
class RoutingDecision:
    route: RouteKind
    intent_kind: str
    confidence: float
    needs_retrieval: bool
    needs_tools: bool
    direct_answer: bool
    allow_answer: bool
    grounding_mode: str = "none"
    reasons: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    fallback_message: str | None = None
    tool_name: str | None = None


@dataclass(slots=True)
class RoutingContext:
    user_id: str
    thread_id: str | None
    message: str
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    thread_summary: str | None = None
    knowledge_payload: dict[str, Any] | None = None
    grounding: GroundingSnapshot | None = None
    grounding_mode: str = "none"
    plan: list[RoutingPlanStep] = field(default_factory=list)
    tool_context: str = "No tool results."


@dataclass(slots=True)
class RoutingOutcome:
    decision: RoutingDecision
    context: RoutingContext
    assistant_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

