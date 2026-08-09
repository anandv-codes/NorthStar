from __future__ import annotations

from dataclasses import dataclass

from ..constants import INTENT_RETRIEVAL_HINTS, INTENT_TOOL_HINTS
from .contracts import IntentContext, IntentSignal, RouteKind
from .base import BaseIntentRule


@dataclass(slots=True)
class KeywordIntentRule(BaseIntentRule):
    hints: set[str]
    kind: RouteKind
    confidence: float
    prefix_bonus: float = 0.0
    follow_up_bonus: float = 0.0

    def score(self, context: IntentContext) -> IntentSignal | None:
        normalized = str(context.message or "").strip().lower()
        if not normalized:
            return None

        reasons: list[str] = []
        hits = 0
        for hint in self.hints:
            if hint in normalized:
                hits += 1
                reasons.append(f"{self.kind}:{hint}")

        if not hits and self.prefix_bonus <= 0:
            return None

        score = self.confidence
        if hits:
            score = min(1.0, score + (0.05 * hits))
        if self._has_prefix_match(normalized):
            score = min(1.0, score + self.prefix_bonus)
            reasons.append(f"{self.kind}:prefix")
        if self._looks_like_follow_up(context, normalized):
            score = min(1.0, score + self.follow_up_bonus)
            reasons.append(f"{self.kind}:follow_up")

        return IntentSignal(
            kind=self.kind,
            confidence=round(score, 2),
            reasons=reasons,
            needs_retrieval=self.kind in {"retrieval", "mixed"},
            needs_tools=self.kind in {"tool", "mixed"},
            direct_answer=self.kind in {"direct", "mixed"},
        )

    def _has_prefix_match(self, normalized: str) -> bool:
        if self.kind == "retrieval":
            prefixes = ("what did i", "what was", "show me", "find", "search", "remember")
        elif self.kind == "tool":
            prefixes = ("create", "update", "delete", "mark", "set")
        else:
            return False
        return any(normalized.startswith(prefix) for prefix in prefixes)

    def _looks_like_follow_up(self, context: IntentContext, normalized: str) -> bool:
        recent_user_messages = [
            item
            for item in context.recent_messages
            if str(item.get("role") or "") == "user"
        ]
        return bool(recent_user_messages and len(normalized.split()) <= 4)


def build_retrieval_rule() -> KeywordIntentRule:
    return KeywordIntentRule(
        hints=INTENT_RETRIEVAL_HINTS,
        kind="retrieval",
        confidence=0.72,
        prefix_bonus=0.12,
        follow_up_bonus=0.08,
    )


def build_tool_rule() -> KeywordIntentRule:
    return KeywordIntentRule(
        hints=INTENT_TOOL_HINTS,
        kind="tool",
        confidence=0.7,
        prefix_bonus=0.12,
    )
