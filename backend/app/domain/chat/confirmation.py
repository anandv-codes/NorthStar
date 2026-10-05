"""Classifies a reply to a pending tool-action confirmation prompt as a clear
yes, a clear no, or ambiguous (in which case we re-ask rather than guess)."""
from __future__ import annotations

from typing import Literal

from ..constants import CONFIRMATION_AFFIRM_HINTS, CONFIRMATION_DENY_HINTS

ConfirmationDecision = Literal["confirm", "deny", "unclear"]


def _matches(normalized: str, words: set[str], hints: set[str]) -> bool:
    for hint in hints:
        if " " in hint:
            if hint in normalized:
                return True
        elif hint in words:
            return True
    return False


def classify_confirmation(message: str) -> ConfirmationDecision:
    normalized = str(message or "").strip().lower().strip(".!")
    if not normalized:
        return "unclear"

    words = set(normalized.split())
    if _matches(normalized, words, CONFIRMATION_AFFIRM_HINTS):
        return "confirm"
    if _matches(normalized, words, CONFIRMATION_DENY_HINTS):
        return "deny"
    return "unclear"
