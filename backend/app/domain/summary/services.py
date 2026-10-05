"""Daily/weekly rollup summaries over notes + typed work-memory items.

Boundaries are UTC calendar days; weeks run Sunday-Saturday (see
docs/latency_improvements.md sibling decision log in repo memory for the
discussion that produced these choices). A weekly summary is composed from
the week's daily summaries (narrative + stats), not re-read from raw notes.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from ...infrastructure.db.memory_repository import get_memory_repository
from ...infrastructure.db.period_summary_repository import get_period_summary_repository
from ...infrastructure.llm.gemini_client import generate_period_summary_narrative
from ...infrastructure.llm.llm_config import MIN_NOTES_FOR_DAILY_SUMMARY
from ..ports import MemoryRepository, PeriodSummaryRepository

MAX_HIGHLIGHT_ITEMS = 10
MAX_HIGHLIGHT_TEXT_LENGTH = 200
MAX_NOTE_LINES = 20

DEFAULT_DAILY_TEMPLATE = """You are an assistant that writes a short end-of-day recap for a user's personal work-memory app.

Date: {day}

Notes captured today ({notes_count}):
{notes_text}

Tasks completed today (of {tasks_opened_count} opened):
{tasks_completed_text}

Questions answered today (of {questions_opened_count} opened):
{questions_answered_text}

Risks resolved today (of {risks_opened_count} opened):
{risks_resolved_text}

Decisions made today:
{decisions_text}

Facts recorded today: {facts_count}

Write a concise (3-6 sentence) prose recap of the day's work, highlighting what was accomplished,
resolved, and decided. Do not invent facts beyond what's listed above. If nothing substantive
happened, say so briefly. Write flowing prose, not bullet points.
"""

DEFAULT_WEEKLY_TEMPLATE = """You are an assistant that writes a short weekly recap for a user's personal work-memory app,
composed from that week's daily recaps.

Week: {week_start} to {week_end}

Daily recaps:
{daily_narratives_text}

Aggregate stats for the week:
- Notes captured: {notes_count}
- Tasks completed: {tasks_completed}
- Questions answered: {questions_answered}
- Risks resolved: {risks_resolved}
- Decisions made: {decisions_made}

Write a concise (4-8 sentence) prose recap of the week, synthesizing the daily recaps into an
overall narrative of progress, open threads, and key decisions. Do not invent facts beyond what's
listed above. Write flowing prose, not bullet points.
"""


def _utcnow_date() -> date:
    return datetime.now(timezone.utc).date()


def _day_bounds_iso(day: date) -> tuple[str, str]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _week_bounds(any_day: date) -> tuple[date, date]:
    """Return (week_start, week_end_exclusive) for the Sunday-starting week containing any_day."""
    days_since_sunday = (any_day.weekday() + 1) % 7  # Mon=0..Sun=6 -> Sun=0..Sat=6
    week_start = any_day - timedelta(days=days_since_sunday)
    week_end_exclusive = week_start + timedelta(days=7)
    return week_start, week_end_exclusive


def _truncate(text: str, limit: int = MAX_HIGHLIGHT_TEXT_LENGTH) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _format_bullets(items: list[str]) -> str:
    if not items:
        return "(none)"
    return "\n".join(f"- {_truncate(item)}" for item in items[:MAX_HIGHLIGHT_ITEMS])


def _compute_daily_stats_and_highlights(
    user_id: str, start_iso: str, end_iso: str, repo: MemoryRepository
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    tasks_opened = repo.query_tasks_opened_in_range(user_id, start_iso, end_iso)
    tasks_completed = repo.query_tasks_completed_in_range(user_id, start_iso, end_iso)
    questions_opened = repo.query_questions_opened_in_range(user_id, start_iso, end_iso)
    questions_answered = repo.query_questions_answered_in_range(user_id, start_iso, end_iso)
    risks_opened = repo.query_risks_opened_in_range(user_id, start_iso, end_iso)
    risks_resolved = repo.query_risks_resolved_in_range(user_id, start_iso, end_iso)
    decisions = repo.query_decisions_in_range(user_id, start_iso, end_iso)
    facts = repo.query_facts_in_range(user_id, start_iso, end_iso)

    stats = {
        "tasks_opened": len(tasks_opened),
        "tasks_completed": len(tasks_completed),
        "questions_opened": len(questions_opened),
        "questions_answered": len(questions_answered),
        "risks_opened": len(risks_opened),
        "risks_resolved": len(risks_resolved),
        "decisions_made": len(decisions),
        "facts_recorded": len(facts),
    }
    highlights = {
        "tasks_completed": [t.get("description", "") for t in tasks_completed],
        "questions_answered": [q.get("question", "") for q in questions_answered],
        "risks_resolved": [r.get("risk", "") for r in risks_resolved],
        "decisions": [d.get("decision", "") for d in decisions],
    }
    return stats, highlights


def _build_daily_prompt(
    day: date, notes: list[dict[str, Any]], stats: dict[str, Any], highlights: dict[str, list[str]]
) -> str:
    notes_lines = [
        _truncate(n.get("enriched_summary") or n.get("raw_text") or "") for n in notes[:MAX_NOTE_LINES]
    ]
    return DEFAULT_DAILY_TEMPLATE.format(
        day=day.isoformat(),
        notes_count=stats["notes_count"],
        notes_text=_format_bullets(notes_lines),
        tasks_completed_text=_format_bullets(highlights["tasks_completed"]),
        tasks_opened_count=stats["tasks_opened"],
        questions_answered_text=_format_bullets(highlights["questions_answered"]),
        questions_opened_count=stats["questions_opened"],
        risks_resolved_text=_format_bullets(highlights["risks_resolved"]),
        risks_opened_count=stats["risks_opened"],
        decisions_text=_format_bullets(highlights["decisions"]),
        facts_count=stats["facts_recorded"],
    )


def _merge_stats(stats_list: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for stats in stats_list:
        for key, value in stats.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                merged[key] = merged.get(key, 0) + value
    return merged


def _build_weekly_prompt(week_start: date, week_end_inclusive: date, daily_rows: list[dict[str, Any]]) -> str:
    merged_stats = _merge_stats([row.get("stats", {}) for row in daily_rows])
    daily_narratives_text = "\n\n".join(
        f"{row['period_start']}: {row['narrative']}" for row in daily_rows
    )
    return DEFAULT_WEEKLY_TEMPLATE.format(
        week_start=week_start.isoformat(),
        week_end=week_end_inclusive.isoformat(),
        daily_narratives_text=daily_narratives_text or "(no daily recaps)",
        notes_count=sum(row.get("source_note_count", 0) for row in daily_rows),
        tasks_completed=merged_stats.get("tasks_completed", 0),
        questions_answered=merged_stats.get("questions_answered", 0),
        risks_resolved=merged_stats.get("risks_resolved", 0),
        decisions_made=merged_stats.get("decisions_made", 0),
    )


def get_daily_summary_status(
    user_id: str,
    day: date | None = None,
    repo: MemoryRepository | None = None,
    summary_repo: PeriodSummaryRepository | None = None,
) -> dict[str, Any]:
    """Read-only check: does a daily summary exist, or is one generatable yet?"""
    repo = repo or get_memory_repository()
    summary_repo = summary_repo or get_period_summary_repository()
    day = day or _utcnow_date()

    existing = summary_repo.get_period_summary(user_id, "daily", day.isoformat())
    if existing:
        return {
            "status": "ready",
            "summary": existing,
            "notes_count": existing.get("source_note_count", 0),
            "min_notes_required": MIN_NOTES_FOR_DAILY_SUMMARY,
        }

    start_iso, end_iso = _day_bounds_iso(day)
    notes_count = len(repo.query_notes_for_user_in_range(user_id, start_iso, end_iso))
    status = "not_generated" if notes_count >= MIN_NOTES_FOR_DAILY_SUMMARY else "insufficient_data"
    return {
        "status": status,
        "summary": None,
        "notes_count": notes_count,
        "min_notes_required": MIN_NOTES_FOR_DAILY_SUMMARY,
    }


def generate_daily_summary(
    user_id: str,
    day: date | None = None,
    regenerate: bool = False,
    repo: MemoryRepository | None = None,
    summary_repo: PeriodSummaryRepository | None = None,
) -> dict[str, Any]:
    """Generate (or return the existing) daily summary for ``day`` (defaults to today, UTC)."""
    repo = repo or get_memory_repository()
    summary_repo = summary_repo or get_period_summary_repository()
    day = day or _utcnow_date()

    existing = summary_repo.get_period_summary(user_id, "daily", day.isoformat())
    if existing and not regenerate:
        return {
            "status": "ready",
            "summary": existing,
            "notes_count": existing.get("source_note_count", 0),
            "min_notes_required": MIN_NOTES_FOR_DAILY_SUMMARY,
        }

    start_iso, end_iso = _day_bounds_iso(day)
    notes = repo.query_notes_for_user_in_range(user_id, start_iso, end_iso)
    notes_count = len(notes)
    if notes_count < MIN_NOTES_FOR_DAILY_SUMMARY:
        return {
            "status": "insufficient_data",
            "summary": None,
            "notes_count": notes_count,
            "min_notes_required": MIN_NOTES_FOR_DAILY_SUMMARY,
        }

    stats, highlights = _compute_daily_stats_and_highlights(user_id, start_iso, end_iso, repo)
    stats["notes_count"] = notes_count
    prompt = _build_daily_prompt(day, notes, stats, highlights)
    narrative = generate_period_summary_narrative(prompt)

    row = summary_repo.upsert_period_summary(
        user_id=user_id,
        period_type="daily",
        period_start=day.isoformat(),
        period_end=day.isoformat(),
        narrative=narrative,
        stats=stats,
        source_note_count=notes_count,
    )
    return {
        "status": "ready",
        "summary": row,
        "notes_count": notes_count,
        "min_notes_required": MIN_NOTES_FOR_DAILY_SUMMARY,
    }


def get_weekly_summary_status(
    user_id: str,
    any_day: date | None = None,
    repo: MemoryRepository | None = None,
    summary_repo: PeriodSummaryRepository | None = None,
) -> dict[str, Any]:
    repo = repo or get_memory_repository()
    summary_repo = summary_repo or get_period_summary_repository()
    week_start, week_end_exclusive = _week_bounds(any_day or _utcnow_date())

    existing = summary_repo.get_period_summary(user_id, "weekly", week_start.isoformat())
    if existing:
        return {
            "status": "ready",
            "summary": existing,
            "notes_count": existing.get("source_note_count", 0),
            "min_notes_required": MIN_NOTES_FOR_DAILY_SUMMARY,
        }

    start_iso, _ = _day_bounds_iso(week_start)
    end_iso, _ = _day_bounds_iso(week_end_exclusive)
    notes_count = len(repo.query_notes_for_user_in_range(user_id, start_iso, end_iso))
    status = "not_generated" if notes_count >= MIN_NOTES_FOR_DAILY_SUMMARY else "insufficient_data"
    return {
        "status": status,
        "summary": None,
        "notes_count": notes_count,
        "min_notes_required": MIN_NOTES_FOR_DAILY_SUMMARY,
    }


def generate_weekly_summary(
    user_id: str,
    any_day: date | None = None,
    regenerate: bool = False,
    repo: MemoryRepository | None = None,
    summary_repo: PeriodSummaryRepository | None = None,
) -> dict[str, Any]:
    """Generate (or return the existing) weekly summary for the Sunday-starting week
    containing ``any_day`` (defaults to today, UTC). Composed from that week's daily
    summaries, generating any missing ones (that meet the daily threshold) first.
    """
    repo = repo or get_memory_repository()
    summary_repo = summary_repo or get_period_summary_repository()
    today = _utcnow_date()
    week_start, week_end_exclusive = _week_bounds(any_day or today)

    existing = summary_repo.get_period_summary(user_id, "weekly", week_start.isoformat())
    if existing and not regenerate:
        return {
            "status": "ready",
            "summary": existing,
            "notes_count": existing.get("source_note_count", 0),
            "min_notes_required": MIN_NOTES_FOR_DAILY_SUMMARY,
        }

    daily_rows: list[dict[str, Any]] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        if day > today:
            break
        daily_result = generate_daily_summary(user_id, day, regenerate=False, repo=repo, summary_repo=summary_repo)
        if daily_result["status"] == "ready" and daily_result["summary"] is not None:
            daily_rows.append(daily_result["summary"])

    total_notes = sum(row.get("source_note_count", 0) for row in daily_rows)
    if not daily_rows or total_notes < MIN_NOTES_FOR_DAILY_SUMMARY:
        return {
            "status": "insufficient_data",
            "summary": None,
            "notes_count": total_notes,
            "min_notes_required": MIN_NOTES_FOR_DAILY_SUMMARY,
        }

    week_end_inclusive = week_end_exclusive - timedelta(days=1)
    merged_stats = _merge_stats([row.get("stats", {}) for row in daily_rows])
    merged_stats["notes_count"] = total_notes
    prompt = _build_weekly_prompt(week_start, week_end_inclusive, daily_rows)
    narrative = generate_period_summary_narrative(prompt)

    row = summary_repo.upsert_period_summary(
        user_id=user_id,
        period_type="weekly",
        period_start=week_start.isoformat(),
        period_end=week_end_inclusive.isoformat(),
        narrative=narrative,
        stats=merged_stats,
        source_note_count=total_notes,
    )
    return {
        "status": "ready",
        "summary": row,
        "notes_count": total_notes,
        "min_notes_required": MIN_NOTES_FOR_DAILY_SUMMARY,
    }
