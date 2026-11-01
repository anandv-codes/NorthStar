from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

from ...infrastructure.llm.prompt_logger import append_pipeline_log
from .base import BaseIntentClassifier, BaseIntentRule
from .contracts import (
    GroundingMode,
    IntentContext,
    IntentDecision,
    IntentKind,
    IntentSignal,
)
from .embedding_intent import (
    LocalSemanticIntentClassifier,
    SemanticIntentMatch,
    build_default_semantic_intent_classifier,
)
from .rules import (
    build_conversation_rule,
    build_read_tool_rule,
    build_retrieval_rule,
    build_status_rule,
    build_tool_rule,
)


class SemanticIntentClassifier(Protocol):
    def classify(self, message: str) -> SemanticIntentMatch | None: ...


@dataclass(slots=True)
class RuleBasedIntentClassifier(BaseIntentClassifier):
    rules: Sequence[BaseIntentRule] = field(
        default_factory=lambda: (
            build_tool_rule(),
            build_read_tool_rule(),
            build_status_rule(),
            build_retrieval_rule(),
            build_conversation_rule(),
        )
    )

    def classify(self, context: IntentContext) -> IntentDecision:
        return HybridIntentClassifier(rules=self.rules).classify(context)


@dataclass(slots=True)
class HybridIntentClassifier(BaseIntentClassifier):
    rules: Sequence[BaseIntentRule]
    semantic_classifier: SemanticIntentClassifier | None = None

    def classify(self, context: IntentContext) -> IntentDecision:
        normalized = str(context.message or "").strip()
        if not normalized:
            raise ValueError("message is required")

        append_pipeline_log(
            "intent classifier",
            [
                "planning intent",
                f"surface: {context.surface}",
                f"message: {self._shorten(normalized)}",
            ],
        )

        signals = self._rule_signals(context)
        semantic = self._semantic_match(normalized)
        decision = self._merge_signals(normalized, signals, semantic)

        append_pipeline_log(
            "intent classifier",
            [
                f"intent decided as {decision.kind}",
                f"confidence: {decision.confidence:.2f}",
                f"grounding_mode: {decision.grounding_mode}",
                f"needs_retrieval: {decision.needs_retrieval}",
                f"needs_tools: {decision.needs_tools}",
            ],
        )
        return decision

    def _rule_signals(self, context: IntentContext) -> list[IntentSignal]:
        signals: list[IntentSignal] = []
        for rule in self.rules:
            signal = rule.score(context)
            if signal:
                signals.append(signal)
        return signals

    def _semantic_match(self, message: str) -> SemanticIntentMatch | None:
        if self.semantic_classifier is None:
            return None
        try:
            return self.semantic_classifier.classify(message)
        except Exception:
            return None

    def _merge_signals(
        self,
        message: str,
        signals: Sequence[IntentSignal],
        semantic: SemanticIntentMatch | None,
    ) -> IntentDecision:
        action = self._best(signals, "action")
        read_tool = self._best(signals, "tool_read")
        status = self._best(signals, "note_status")
        content = self._best(signals, "note_content")
        conversation = self._best(signals, "conversation")
        reasons = self._combine_reasons(signals)

        if semantic is not None:
            reasons.append(f"semantic:{semantic.label}:{semantic.confidence:.2f}")

        if action is not None and not self._is_question(message):
            return self._decision(action, reasons)

        if read_tool is not None:
            return self._decision(read_tool, reasons)

        is_summary_request = self._is_summary_request(message)
        if status is not None and not is_summary_request:
            return self._decision(status, reasons)

        if semantic is not None:
            if semantic.label == "note_status":
                return self._semantic_decision("note_status", semantic, reasons)
            if semantic.label == "note_content":
                return self._semantic_decision("note_content", semantic, reasons)
            if semantic.label == "conversation" and content is None:
                return self._semantic_decision("conversation", semantic, reasons)

        if content is not None:
            return self._decision(content, reasons)
        if status is not None:
            return self._decision(status, reasons)
        if conversation is not None:
            return self._decision(conversation, reasons)
        if semantic is not None:
            return self._semantic_decision(semantic.label, semantic, reasons)

        return IntentDecision(
            kind="ambiguous",
            confidence=0.35,
            needs_retrieval=False,
            needs_tools=False,
            direct_answer=True,
            reasons=reasons or ["no_high_confidence_intent"],
            grounding_mode="none",
        )

    def _semantic_decision(
        self,
        kind: IntentKind,
        semantic: SemanticIntentMatch,
        reasons: Sequence[str],
    ) -> IntentDecision:
        return IntentDecision(
            kind=kind,
            confidence=semantic.confidence,
            needs_retrieval=kind in {"note_content", "note_status"},
            needs_tools=kind == "action",
            direct_answer=kind == "conversation",
            reasons=list(reasons),
            grounding_mode=_grounding_mode(kind),
        )

    def _decision(self, signal: IntentSignal, reasons: Sequence[str]) -> IntentDecision:
        return IntentDecision(
            kind=signal.kind,
            confidence=signal.confidence,
            needs_retrieval=signal.needs_retrieval,
            needs_tools=signal.needs_tools,
            direct_answer=signal.direct_answer,
            reasons=list(reasons),
            grounding_mode=signal.grounding_mode,
            tool_name=signal.tool_name,
        )

    def _best(self, signals: Sequence[IntentSignal], kind: IntentKind) -> IntentSignal | None:
        matches = [signal for signal in signals if signal.kind == kind]
        if not matches:
            return None
        return max(matches, key=lambda signal: signal.confidence)

    def _combine_reasons(self, signals: Sequence[IntentSignal]) -> list[str]:
        reasons: list[str] = []
        for signal in signals:
            for reason in signal.reasons:
                if reason not in reasons:
                    reasons.append(reason)
        return reasons

    @staticmethod
    def _is_summary_request(message: str) -> bool:
        normalized = " ".join(str(message or "").lower().split())
        return normalized.startswith(("summarize", "recap", "give me a summary", "overview"))

    @staticmethod
    def _is_question(message: str) -> bool:
        normalized = " ".join(str(message or "").lower().split())
        return normalized.startswith(
            (
                "did i",
                "do i",
                "is ",
                "are ",
                "has ",
                "have i",
                "what",
                "which",
                "who",
                "when",
                "where",
                "why",
                "how",
            )
        )

    def _shorten(self, text: str, limit: int = 96) -> str:
        cleaned = " ".join(str(text or "").split())
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[: limit - 3].rstrip()}..."


def _grounding_mode(kind: IntentKind) -> GroundingMode:
    if kind == "note_content":
        return "relevance"
    if kind == "note_status":
        return "claim"
    return "none"


def build_default_intent_classifier() -> HybridIntentClassifier:
    semantic_classifier: LocalSemanticIntentClassifier = build_default_semantic_intent_classifier()
    return HybridIntentClassifier(
        rules=(
            build_tool_rule(),
            build_read_tool_rule(),
            build_status_rule(),
            build_retrieval_rule(),
            build_conversation_rule(),
        ),
        semantic_classifier=semantic_classifier,
    )
