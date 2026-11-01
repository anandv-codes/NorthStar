from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RouteKind = Literal["conversation", "note_search", "tool", "mixed", "abstain", "direct"]
IntentKind = Literal[
    "conversation",
    "note_content",
    "note_status",
    "action",
    "tool_read",
    "mixed",
    "ambiguous",
    "direct",
]
GroundingMode = Literal["none", "relevance", "claim"]


@dataclass(slots=True)
class IntentContext:
    surface: str
    message: str
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    thread_summary: str | None = None


@dataclass(slots=True)
class IntentSignal:
    kind: IntentKind
    confidence: float
    reasons: list[str] = field(default_factory=list)
    needs_retrieval: bool = False
    needs_tools: bool = False
    direct_answer: bool = True
    grounding_mode: GroundingMode = "none"
    tool_name: str | None = None


@dataclass(slots=True)
class IntentDecision:
    kind: IntentKind
    confidence: float
    needs_retrieval: bool
    needs_tools: bool
    direct_answer: bool
    reasons: list[str] = field(default_factory=list)
    grounding_mode: GroundingMode = "none"
    tool_name: str | None = None

    @property
    def grounding_required(self) -> bool:
        return self.grounding_mode != "none"
