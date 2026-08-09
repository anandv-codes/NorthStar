from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from ...infrastructure.llm.prompt_logger import append_pipeline_log
from .base import BaseIntentClassifier, BaseIntentRule
from .contracts import IntentContext, IntentDecision, IntentSignal, RouteKind
from .rules import build_retrieval_rule, build_tool_rule


@dataclass(slots=True)
class RuleBasedIntentClassifier(BaseIntentClassifier):
    rules: Sequence[BaseIntentRule] = field(default_factory=lambda: (build_retrieval_rule(), build_tool_rule()))

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

        signals: list[IntentSignal] = []
        for rule in self.rules:
            signal = rule.score(context)
            if signal:
                signals.append(signal)
        decision = self._merge_signals(signals)

        append_pipeline_log(
            "intent classifier",
            [
                f"intent decided as {decision.kind}",
                f"confidence: {decision.confidence:.2f}",
                f"needs_retrieval: {decision.needs_retrieval}",
                f"needs_tools: {decision.needs_tools}",
            ],
        )
        return decision

    def _merge_signals(self, signals: Sequence[IntentSignal]) -> IntentDecision:
        if not signals:
            return IntentDecision(
                kind="direct",
                confidence=0.6,
                needs_retrieval=False,
                needs_tools=False,
                direct_answer=True,
                reasons=[],
            )

        retrieval = self._combined_signal(signals, "retrieval")
        tool = self._combined_signal(signals, "tool")
        reasons = self._combine_reasons(signals)

        if retrieval and tool:
            return IntentDecision(
                kind="mixed",
                confidence=min(0.78, max(retrieval.confidence, tool.confidence)),
                needs_retrieval=True,
                needs_tools=True,
                direct_answer=True,
                reasons=reasons,
            )

        if retrieval:
            return IntentDecision(
                kind="retrieval",
                confidence=retrieval.confidence,
                needs_retrieval=True,
                needs_tools=False,
                direct_answer=False,
                reasons=reasons,
            )

        if tool:
            return IntentDecision(
                kind="tool",
                confidence=tool.confidence,
                needs_retrieval=False,
                needs_tools=True,
                direct_answer=False,
                reasons=reasons,
            )

        return IntentDecision(
            kind="direct",
            confidence=0.6,
            needs_retrieval=False,
            needs_tools=False,
            direct_answer=True,
            reasons=reasons,
        )

    def _combined_signal(self, signals: Sequence[IntentSignal], kind: RouteKind) -> IntentSignal | None:
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

    def _shorten(self, text: str, limit: int = 96) -> str:
        cleaned = " ".join(str(text or "").split())
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[: limit - 3].rstrip()}..."


def build_default_intent_classifier() -> RuleBasedIntentClassifier:
    return RuleBasedIntentClassifier()
