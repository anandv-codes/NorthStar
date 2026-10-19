"""Anki-style scheduler with learning steps.

Grades (product decision, plan §6.1): Again=1, Hard=3, Good=4, Easy=5.

Card states: ``new`` -> ``learning`` -> ``review``; a failed review card enters
``relearning`` and graduates back to ``review``. Learning steps are measured in
minutes (``next_due`` is a timestamp); review intervals are whole days.

The scheduler is a pure function of (card, grade, now) plus a config, so it can
be unit-tested without a database or clock. ``schedule`` returns only the
columns to persist; the review service records history separately.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta

AGAIN, HARD, GOOD, EASY = 1, 3, 4, 5

NEW = "new"
LEARNING = "learning"
REVIEW = "review"
RELEARNING = "relearning"


@dataclass(frozen=True)
class SchedulerConfig:
    learning_steps: tuple[int, ...] = (1, 10)
    relearning_steps: tuple[int, ...] = (10,)
    graduating_interval: int = 1
    easy_interval: int = 4
    starting_easiness: float = 2.5
    min_easiness: float = 1.3
    easy_bonus: float = 1.3
    hard_multiplier: float = 1.2
    interval_modifier: float = 1.0
    lapse_multiplier: float = 0.0
    max_interval: int = 36500

    # Ease adjustments (SM-2 inspired; applied on review cards)
    ease_bonus: float = 0.1
    ease_penalty_hard: float = 0.14
    ease_penalty_again: float = 0.2


def load_scheduler_config() -> SchedulerConfig:
    def _steps(env: str, default: str) -> tuple[int, ...]:
        raw = os.getenv(env, default)
        steps = tuple(int(part) for part in raw.replace(" ", "").split(",") if part)
        return steps or (1,)

    return SchedulerConfig(
        learning_steps=_steps("RECALL_LEARNING_STEPS", "1,10"),
        relearning_steps=_steps("RECALL_RELEARNING_STEPS", "10"),
        graduating_interval=int(os.getenv("RECALL_GRADUATING_INTERVAL", "1")),
        easy_interval=int(os.getenv("RECALL_EASY_INTERVAL", "4")),
        starting_easiness=float(os.getenv("RECALL_STARTING_EASINESS", "2.5")),
        min_easiness=float(os.getenv("RECALL_MIN_EASINESS", "1.3")),
        easy_bonus=float(os.getenv("RECALL_EASY_BONUS", "1.3")),
        hard_multiplier=float(os.getenv("RECALL_HARD_MULTIPLIER", "1.2")),
        interval_modifier=float(os.getenv("RECALL_INTERVAL_MODIFIER", "1.0")),
        lapse_multiplier=float(os.getenv("RECALL_LAPSE_MULTIPLIER", "0.0")),
        max_interval=int(os.getenv("RECALL_MAX_INTERVAL", "36500")),
    )


def initial_card_state(config: SchedulerConfig | None = None, now: datetime | None = None) -> dict:
    """Scheduling fields for a freshly created card (due immediately)."""
    config = config or load_scheduler_config()
    return {
        "state": NEW,
        "learning_step": 0,
        "interval": 0,
        "easiness": config.starting_easiness,
        "repetitions": 0,
        "lapses": 0,
        "review_count": 0,
        "last_reviewed": None,
        "next_due": now.isoformat() if now is not None else None,
    }


class AnkiScheduler:
    """Concrete ``Scheduler`` port implementation."""

    def __init__(self, config: SchedulerConfig | None = None):
        self.config = config or load_scheduler_config()

    def schedule(self, card: dict, grade: int, now: datetime) -> dict:
        config = self.config
        state = card.get("state") or NEW
        interval = int(card.get("interval") or 0)
        easiness = float(card.get("easiness") or config.starting_easiness)
        repetitions = int(card.get("repetitions") or 0)
        lapses = int(card.get("lapses") or 0)
        review_count = int(card.get("review_count") or 0)
        learning_step = int(card.get("learning_step") or 0)

        previous_interval = interval
        previous_easiness = easiness

        if state in (NEW, LEARNING, RELEARNING):
            steps = (
                config.relearning_steps if state == RELEARNING else config.learning_steps
            )
            state, interval, learning_step, next_due = self._schedule_learning(
                steps, learning_step, interval, grade, state, now
            )
            if state == REVIEW:
                repetitions += 1
        else:  # review
            easiness, interval, state, learning_step, lapses, next_due = self._schedule_review(
                interval, easiness, learning_step, lapses, grade, now
            )
            if state == REVIEW:
                repetitions += 1

        return {
            "state": state,
            "learning_step": learning_step,
            "interval": interval,
            "easiness": round(easiness, 4),
            "repetitions": repetitions,
            "lapses": lapses,
            "review_count": review_count + 1,
            "last_reviewed": now.isoformat(),
            "next_due": next_due.isoformat(),
            "previous_interval": previous_interval,
            "previous_easiness": round(previous_easiness, 4),
        }

    # -- learning / relearning --------------------------------------------

    def _schedule_learning(self, steps, learning_step, interval, grade, state, now):
        config = self.config
        learning_state = state if state in (LEARNING, RELEARNING) else LEARNING
        if grade == AGAIN:
            return learning_state, interval, 0, now + timedelta(minutes=steps[0])
        if grade == HARD:
            step = min(learning_step, len(steps) - 1)
            return learning_state, interval, learning_step, now + timedelta(minutes=steps[step])
        if grade == EASY:
            return REVIEW, config.easy_interval, 0, now + timedelta(days=config.easy_interval)
        # GOOD: advance a step, or graduate
        next_step = learning_step + 1
        if next_step >= len(steps):
            return (
                REVIEW,
                config.graduating_interval,
                0,
                now + timedelta(days=config.graduating_interval),
            )
        return learning_state, interval, next_step, now + timedelta(minutes=steps[next_step])

    # -- review -----------------------------------------------------------

    def _schedule_review(self, interval, easiness, learning_step, lapses, grade, now):
        config = self.config
        if grade == AGAIN:
            easiness = max(config.min_easiness, easiness - config.ease_penalty_again)
            interval = max(1, int(round(interval * config.lapse_multiplier))) if config.lapse_multiplier else 0
            due = now + timedelta(minutes=config.relearning_steps[0])
            return easiness, interval, RELEARNING, 0, lapses + 1, due

        if grade == HARD:
            easiness = max(config.min_easiness, easiness - config.ease_penalty_hard)
            new_interval = max(1, int(round(interval * config.hard_multiplier)))
        else:
            if grade == EASY:
                easiness = easiness + config.ease_bonus
                new_interval = int(
                    round(interval * easiness * config.easy_bonus * config.interval_modifier)
                )
            else:  # GOOD
                new_interval = int(round(interval * easiness * config.interval_modifier))

        new_interval = max(1, min(new_interval, config.max_interval))
        return easiness, new_interval, REVIEW, 0, lapses, now + timedelta(days=new_interval)
