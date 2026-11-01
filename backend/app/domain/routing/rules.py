from __future__ import annotations

import re
from dataclasses import dataclass

from ..constants import (
    INTENT_ACTION_HINTS,
    INTENT_CONVERSATION_PHRASES,
    INTENT_RETRIEVAL_HINTS,
    INTENT_STATUS_HINTS,
)
from .base import BaseIntentRule
from .contracts import GroundingMode, IntentContext, IntentKind, IntentSignal


def _grounding_mode(kind: IntentKind) -> GroundingMode:
    if kind == "note_content":
        return "relevance"
    if kind == "note_status":
        return "claim"
    return "none"


@dataclass(slots=True)
class KeywordIntentRule(BaseIntentRule):
    hints: set[str]
    kind: IntentKind
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
            if _contains_hint(normalized, hint):
                hits += 1
                reasons.append(f"{self.kind}:{hint}")

        has_prefix = self.prefix_bonus > 0 and self._has_prefix_match(normalized)
        if not hits and not has_prefix:
            return None

        score = self.confidence
        if hits:
            score = min(1.0, score + (0.05 * hits))
        if has_prefix:
            score = min(1.0, score + self.prefix_bonus)
            reasons.append(f"{self.kind}:prefix")
        if self._looks_like_follow_up(context, normalized):
            score = min(1.0, score + self.follow_up_bonus)
            reasons.append(f"{self.kind}:follow_up")

        return IntentSignal(
            kind=self.kind,
            confidence=round(score, 2),
            reasons=reasons,
            needs_retrieval=self.kind in {"note_content", "note_status", "mixed"},
            needs_tools=self.kind in {"action", "mixed"},
            direct_answer=self.kind in {"conversation", "mixed"},
            grounding_mode=_grounding_mode(self.kind),
        )

    def _has_prefix_match(self, normalized: str) -> bool:
        if self.kind == "note_content":
            prefixes = (
                "what did i",
                "what was",
                "show me",
                "find",
                "search",
                "remember",
                "recap",
                "summarize",
            )
        elif self.kind == "action":
            prefixes = (
                "create",
                "add",
                "mark",
                "complete",
                "close",
                "reopen",
                "start",
                "move",
                "set",
                "remind",
            )
        else:
            return False
        return any(normalized.startswith(prefix) for prefix in prefixes)

    def _looks_like_follow_up(self, context: IntentContext, normalized: str) -> bool:
        recent_user_messages = [
            item for item in context.recent_messages if str(item.get("role") or "") == "user"
        ]
        return bool(recent_user_messages and len(normalized.split()) <= 4)


READ_TOOL_PHRASES: dict[str, tuple[str, ...]] = {
    "get_open_loops": (
        "what am i forgetting",
        "what is still open",
        "what's still open",
        "whats still open",
        "which tasks are still open",
        "what tasks are still open",
        "open loops",
        "show me my open loops",
        "what needs my attention",
        "what's on my plate",
        "whats on my plate",
    ),
    "get_due_cards": (
        "what should i review",
        "what do i need to review",
        "what is due",
        "what's due",
        "whats due",
        "due cards",
        "review queue",
        "show me my due cards",
    ),
}


@dataclass(slots=True)
class ReadToolIntentRule(BaseIntentRule):
    phrases: dict[str, tuple[str, ...]]
    confidence: float = 0.9

    def score(self, context: IntentContext) -> IntentSignal | None:
        normalized = _normalize_read_tool_text(context.message)
        if not normalized:
            return None
        for tool_name, phrases in self.phrases.items():
            for phrase in phrases:
                if normalized == phrase or normalized.startswith(f"{phrase} "):
                    return IntentSignal(
                        kind="tool_read",
                        confidence=self.confidence,
                        reasons=[f"tool_read:{tool_name}"],
                        needs_retrieval=False,
                        needs_tools=True,
                        direct_answer=False,
                        grounding_mode="none",
                        tool_name=tool_name,
                    )
        return None


def _normalize_read_tool_text(text: str) -> str:
    normalized = str(text or "").lower().replace("’", "'")
    return " ".join(normalized.split()).strip(" .!?")


@dataclass(slots=True)
class ConversationIntentRule(BaseIntentRule):
    phrases: set[str]
    confidence: float = 0.95

    def score(self, context: IntentContext) -> IntentSignal | None:
        normalized = " ".join(str(context.message or "").strip().lower().split())
        normalized = normalized.strip(" .!?")
        if not normalized or normalized not in self.phrases:
            return None

        return IntentSignal(
            kind="conversation",
            confidence=self.confidence,
            reasons=["conversation:exact_phrase"],
            needs_retrieval=False,
            needs_tools=False,
            direct_answer=True,
            grounding_mode="none",
        )


def _contains_hint(normalized: str, hint: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(hint)}(?![a-z0-9])"
    return re.search(pattern, normalized) is not None


def build_retrieval_rule() -> KeywordIntentRule:
    return KeywordIntentRule(
        hints=INTENT_RETRIEVAL_HINTS,
        kind="note_content",
        confidence=0.72,
        prefix_bonus=0.12,
        follow_up_bonus=0.08,
    )


def build_status_rule() -> KeywordIntentRule:
    return KeywordIntentRule(
        hints=INTENT_STATUS_HINTS,
        kind="note_status",
        confidence=0.78,
        follow_up_bonus=0.06,
    )


def build_tool_rule() -> KeywordIntentRule:
    return KeywordIntentRule(
        hints=INTENT_ACTION_HINTS,
        kind="action",
        confidence=0.82,
    )


def build_read_tool_rule() -> ReadToolIntentRule:
    return ReadToolIntentRule(phrases=READ_TOOL_PHRASES)


def build_conversation_rule() -> ConversationIntentRule:
    return ConversationIntentRule(phrases=INTENT_CONVERSATION_PHRASES)
