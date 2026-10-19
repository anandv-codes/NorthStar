"""Deterministic recall-candidate scoring.

Pure functions so the eligibility formula can be tuned and tested without a
database or LLM. Weights/thresholds come from a ``ScoringConfig`` loaded from
the environment, defaulting to the values in the implementation plan.

    score = 0.30 * importance
          + 0.20 * normalized_mention_count
          + 0.20 * related_note_count_score
          + 0.15 * recency_score
          + 0.15 * user_interest_score
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

# Candidate lifecycle states we persist. ``suggested`` here means "question
# generated, awaiting the user's accept/skip" (see PR7).
ELIGIBLE = "eligible"
SUGGESTED = "suggested"
REJECTED = "rejected"


@dataclass(frozen=True)
class ScoringConfig:
    weight_importance: float = 0.30
    weight_mention_count: float = 0.20
    weight_related_notes: float = 0.20
    weight_recency: float = 0.15
    weight_user_interest: float = 0.15
    mention_count_cap: int = 10
    related_notes_target: int = 3
    recency_half_life_days: float = 30.0
    # 0.45 rather than the plan's original 0.65: on a first note there are no
    # related notes and no interest signal, so even a perfect unit scores only
    # ~0.57. 0.65 would make recall inert for new users (no candidates at all).
    eligibility_threshold: float = 0.45
    min_confidence: float = 0.6
    max_items_per_note: int = 0  # 0 = no cap (user opted out of card caps)


def load_scoring_config() -> ScoringConfig:
    return ScoringConfig(
        weight_importance=float(os.getenv("RECALL_W_IMPORTANCE", "0.30")),
        weight_mention_count=float(os.getenv("RECALL_W_MENTION", "0.20")),
        weight_related_notes=float(os.getenv("RECALL_W_RELATED", "0.20")),
        weight_recency=float(os.getenv("RECALL_W_RECENCY", "0.15")),
        weight_user_interest=float(os.getenv("RECALL_W_INTEREST", "0.15")),
        mention_count_cap=int(os.getenv("RECALL_MENTION_CAP", "10")),
        related_notes_target=int(os.getenv("RECALL_RELATED_TARGET", "3")),
        recency_half_life_days=float(os.getenv("RECALL_RECENCY_HALFLIFE_DAYS", "30")),
        eligibility_threshold=float(os.getenv("RECALL_ELIGIBILITY_THRESHOLD", "0.45")),
        min_confidence=float(os.getenv("RECALL_MIN_CONFIDENCE", "0.6")),
        max_items_per_note=int(os.getenv("RECALL_MAX_ITEMS_PER_NOTE", "0")),
    )


def normalized_mention_count(mention_count: int, cap: int = 10) -> float:
    """log-scaled mention count in [0, 1] (cap maps to 1.0)."""
    if mention_count <= 0:
        return 0.0
    if cap <= 1:
        return 1.0
    return min(1.0, math.log1p(mention_count) / math.log1p(cap))


def related_note_count_score(distinct_notes: int, target: int = 3) -> float:
    if distinct_notes <= 0 or target <= 1:
        return 0.0 if distinct_notes <= 0 else 1.0
    return min(1.0, distinct_notes / target)


def recency_score(age_days: float, half_life_days: float = 30.0) -> float:
    if age_days <= 0:
        return 1.0
    if half_life_days <= 0:
        return 0.0
    return math.exp(-age_days / half_life_days)


def score_candidate(
    *,
    importance: float,
    mention_count: int,
    related_note_count: int,
    age_days: float,
    user_interest_score: float = 0.0,
    config: ScoringConfig | None = None,
) -> float:
    config = config or load_scoring_config()
    score = (
        config.weight_importance * _clamp01(importance)
        + config.weight_mention_count * normalized_mention_count(mention_count, config.mention_count_cap)
        + config.weight_related_notes
        * related_note_count_score(related_note_count, config.related_notes_target)
        + config.weight_recency * recency_score(age_days, config.recency_half_life_days)
        + config.weight_user_interest * _clamp01(user_interest_score)
    )
    return round(_clamp01(score), 6)


def classify(score: float, config: ScoringConfig | None = None) -> str:
    config = config or load_scoring_config()
    return ELIGIBLE if score >= config.eligibility_threshold else REJECTED


def is_eligible(
    *,
    confidence: Any,
    score: float,
    config: ScoringConfig | None = None,
) -> bool:
    """A unit is eligible only if it clears both the confidence floor and score."""
    config = config or load_scoring_config()
    try:
        numeric_confidence = float(confidence) if confidence is not None else 1.0
    except (TypeError, ValueError):
        numeric_confidence = 1.0
    if numeric_confidence < config.min_confidence:
        return False
    return score >= config.eligibility_threshold


def _clamp01(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))
