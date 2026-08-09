from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RouteKind = Literal["direct", "retrieval", "tool", "mixed", "abstain"]


@dataclass(slots=True)
class IntentContext:
    surface: str
    message: str
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    thread_summary: str | None = None


@dataclass(slots=True)
class IntentSignal:
    kind: RouteKind
    confidence: float
    reasons: list[str] = field(default_factory=list)
    needs_retrieval: bool = False
    needs_tools: bool = False
    direct_answer: bool = True


@dataclass(slots=True)
class IntentDecision:
    kind: RouteKind
    confidence: float
    needs_retrieval: bool
    needs_tools: bool
    direct_answer: bool
    reasons: list[str] = field(default_factory=list)

