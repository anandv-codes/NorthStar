"""Tests for deterministic recall-candidate scoring."""
from backend.app.domain.recall.candidate_scoring import (
    ELIGIBLE,
    REJECTED,
    ScoringConfig,
    classify,
    is_eligible,
    load_scoring_config,
    normalized_mention_count,
    recency_score,
    related_note_count_score,
    score_candidate,
)


def test_default_weights_sum_to_one():
    config = ScoringConfig()
    total = (
        config.weight_importance
        + config.weight_mention_count
        + config.weight_related_notes
        + config.weight_recency
        + config.weight_user_interest
    )
    assert round(total, 10) == 1.0


def test_perfect_inputs_score_one():
    score = score_candidate(
        importance=1.0,
        mention_count=10,
        related_note_count=3,
        age_days=0,
        user_interest_score=1.0,
    )
    assert score == 1.0


def test_no_signal_scores_zero():
    score = score_candidate(
        importance=0.0,
        mention_count=0,
        related_note_count=0,
        age_days=10_000,
        user_interest_score=0.0,
    )
    assert score < 0.01


def test_normalized_mention_count_is_log_scaled_and_capped():
    assert normalized_mention_count(0, 10) == 0.0
    assert normalized_mention_count(10, 10) == 1.0
    assert normalized_mention_count(50, 10) == 1.0
    assert 0 < normalized_mention_count(3, 10) < 1


def test_related_note_count_reaches_one_at_target():
    assert related_note_count_score(0, 3) == 0.0
    assert related_note_count_score(3, 3) == 1.0
    assert related_note_count_score(10, 3) == 1.0


def test_recency_score_decays():
    assert recency_score(0, 30) == 1.0
    assert round(recency_score(30, 30), 4) == round(0.36787944117, 4)


def test_classify_uses_threshold():
    config = ScoringConfig(eligibility_threshold=0.65)
    assert classify(0.65, config) == ELIGIBLE
    assert classify(0.6499, config) == REJECTED


def test_is_eligible_requires_confidence_floor_and_score():
    config = ScoringConfig(eligibility_threshold=0.65, min_confidence=0.6)
    assert is_eligible(confidence=0.9, score=0.7, config=config) is True
    assert is_eligible(confidence=0.5, score=0.9, config=config) is False
    assert is_eligible(confidence=None, score=0.9, config=config) is True
    assert is_eligible(confidence=0.9, score=0.1, config=config) is False


def test_load_scoring_config_reads_env(monkeypatch):
    monkeypatch.setenv("RECALL_ELIGIBILITY_THRESHOLD", "0.5")
    monkeypatch.setenv("RECALL_MIN_CONFIDENCE", "0.2")
    config = load_scoring_config()
    assert config.eligibility_threshold == 0.5
    assert config.min_confidence == 0.2
