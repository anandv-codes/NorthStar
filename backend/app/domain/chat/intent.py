from __future__ import annotations

from typing import Sequence

from ..routing.classifier import build_default_intent_classifier
from ..routing.contracts import IntentContext, IntentDecision

ChatIntent = IntentDecision


def classify_chat_intent(
    message: str,
    recent_messages: Sequence[dict[str, str]] | None = None,
) -> ChatIntent:
    classifier = build_default_intent_classifier()
    context = IntentContext(
        surface="chat",
        message=message,
        recent_messages=list(recent_messages or []),
    )
    return classifier.classify(context)
