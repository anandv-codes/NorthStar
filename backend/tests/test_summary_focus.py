"""Summaries expose active goal text as a deterministic final section."""
from datetime import datetime, timezone

from backend.app.domain.commitments.services import update_commitment
from backend.app.domain.summary import services as summary_services
from backend.tests.fakes import InMemoryCommitmentRepository


USER = "user-1"


class _MemoryRepo:
    def __init__(self, notes):
        self.notes = notes

    def query_notes_for_user_in_range(self, user_id, start_iso, end_iso):
        return [
            note
            for note in self.notes
            if start_iso <= str(note.get("created_at")) < end_iso
        ]

    def query_tasks_opened_in_range(self, *args):
        return []

    def query_tasks_completed_in_range(self, *args):
        return []

    def query_questions_opened_in_range(self, *args):
        return []

    def query_questions_answered_in_range(self, *args):
        return []

    def query_decisions_in_range(self, *args):
        return []

    def query_facts_in_range(self, *args):
        return []


class _SummaryRepo:
    def __init__(self):
        self.rows = {}

    def get_period_summary(self, user_id, period_type, period_start):
        return self.rows.get((user_id, period_type, period_start))

    def upsert_period_summary(
        self,
        user_id,
        period_type,
        period_start,
        period_end,
        narrative,
        stats,
        source_note_count,
    ):
        row = {
            "summary_id": f"{period_type}-{period_start}",
            "user_id": user_id,
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "narrative": narrative,
            "stats": stats,
            "source_note_count": source_note_count,
        }
        self.rows[(user_id, period_type, period_start)] = row
        return row


def _commitment_repo():
    repo = InMemoryCommitmentRepository()
    active = repo.create_commitment(USER, "Ship the MVP")
    completed = repo.create_commitment(USER, "Read one book")
    update_commitment(USER, completed["commitment_id"], {"progress": 100}, repo=repo)
    repo.insert_contribution(USER, active["commitment_id"], "note-1", "Finished the API.")
    return repo


def _today_note():
    now = datetime.now(timezone.utc)
    return {
        "note_id": "note-1",
        "created_at": now.isoformat(),
        "enriched_summary": "Built the API.",
        "raw_text": "Built the API.",
    }


def test_daily_summary_stores_and_prompts_active_goal_text_only(monkeypatch):
    prompts = []
    monkeypatch.setattr(
        summary_services,
        "generate_period_summary_narrative",
        lambda prompt: prompts.append(prompt) or "Daily recap.",
    )
    today = summary_services._utcnow_date()
    summary_repo = _SummaryRepo()
    memory_repo = _MemoryRepo([_today_note(), {**_today_note(), "note_id": "note-2"}])

    result = summary_services.generate_daily_summary(
        USER,
        day=today,
        repo=memory_repo,
        summary_repo=summary_repo,
        commitment_repo=_commitment_repo(),
    )

    assert result["status"] == "ready"
    stats = result["summary"]["stats"]
    assert stats["long_term_focus"] == ["Ship the MVP"]
    assert prompts[0].rstrip().splitlines()[-1] == "- Ship the MVP"
    assert "Read one book" not in prompts[0]
    assert "Finished the API." not in prompts[0]
    assert "100" not in prompts[0]


def test_weekly_summary_uses_current_active_goals(monkeypatch):
    prompts = []
    monkeypatch.setattr(
        summary_services,
        "generate_period_summary_narrative",
        lambda prompt: prompts.append(prompt) or "Recap.",
    )
    today = summary_services._utcnow_date()
    summary_repo = _SummaryRepo()
    memory_repo = _MemoryRepo([_today_note(), {**_today_note(), "note_id": "note-2"}])

    result = summary_services.generate_weekly_summary(
        USER,
        any_day=today,
        repo=memory_repo,
        summary_repo=summary_repo,
        commitment_repo=_commitment_repo(),
    )

    assert result["status"] == "ready"
    assert result["summary"]["stats"]["long_term_focus"] == ["Ship the MVP"]
    weekly_prompt = prompts[-1]
    assert weekly_prompt.rstrip().splitlines()[-1] == "- Ship the MVP"
    assert "Read one book" not in weekly_prompt
