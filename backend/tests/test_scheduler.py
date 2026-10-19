"""Tests for the Anki-style scheduler (PR8)."""
from datetime import datetime, timedelta, timezone

from backend.app.domain.recall.scheduling.scheduler import (
    AnkiScheduler,
    SchedulerConfig,
    initial_card_state,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
CONFIG = SchedulerConfig(learning_steps=(1, 10), relearning_steps=(10,))
SCHED = AnkiScheduler(CONFIG)

AGAIN, HARD, GOOD, EASY = 1, 3, 4, 5


def _card(**overrides):
    card = {
        "state": "new",
        "learning_step": 0,
        "interval": 0,
        "easiness": 2.5,
        "repetitions": 0,
        "lapses": 0,
        "review_count": 0,
    }
    card.update(overrides)
    return card


def test_initial_card_state_is_due_now():
    state = initial_card_state(CONFIG, now=NOW)
    assert state["state"] == "new"
    assert state["next_due"] == NOW.isoformat()


def test_new_card_good_advances_step():
    result = SCHED.schedule(_card(), GOOD, NOW)
    assert result["state"] == "learning"
    assert result["learning_step"] == 1
    assert datetime.fromisoformat(result["next_due"]) == NOW + timedelta(minutes=10)


def test_learning_card_good_graduates():
    result = SCHED.schedule(_card(state="learning", learning_step=1), GOOD, NOW)
    assert result["state"] == "review"
    assert result["interval"] == 1
    assert result["repetitions"] == 1
    assert datetime.fromisoformat(result["next_due"]) == NOW + timedelta(days=1)


def test_new_card_easy_graduates_immediately():
    result = SCHED.schedule(_card(), EASY, NOW)
    assert result["state"] == "review"
    assert result["interval"] == 4
    assert result["learning_step"] == 0


def test_new_card_again_stays_on_first_step():
    result = SCHED.schedule(_card(), AGAIN, NOW)
    assert result["state"] == "learning"
    assert result["learning_step"] == 0
    assert datetime.fromisoformat(result["next_due"]) == NOW + timedelta(minutes=1)


def test_new_card_hard_repeats_current_step():
    result = SCHED.schedule(_card(), HARD, NOW)
    assert result["state"] == "learning"
    assert result["learning_step"] == 0
    assert datetime.fromisoformat(result["next_due"]) == NOW + timedelta(minutes=1)


def test_review_card_good_multiplies_by_easiness():
    result = SCHED.schedule(_card(state="review", interval=10, repetitions=3), GOOD, NOW)
    assert result["state"] == "review"
    assert result["interval"] == 25  # round(10 * 2.5)
    assert result["review_count"] == 1


def test_review_card_again_enters_relearning():
    result = SCHED.schedule(_card(state="review", interval=10, repetitions=3), AGAIN, NOW)
    assert result["state"] == "relearning"
    assert result["lapses"] == 1
    assert datetime.fromisoformat(result["next_due"]) == NOW + timedelta(minutes=10)
    assert result["easiness"] < 2.5


def test_review_card_easy_adds_bonus_interval():
    result = SCHED.schedule(_card(state="review", interval=10), EASY, NOW)
    assert result["interval"] == int(round(10 * (2.5 + 0.1) * 1.3))


def test_review_history_fields_exposed():
    result = SCHED.schedule(_card(state="review", interval=10, easiness=2.4), GOOD, NOW)
    assert result["previous_interval"] == 10
    assert result["previous_easiness"] == 2.4
    assert result["last_reviewed"] == NOW.isoformat()
