"""Domain rules for user-authored commitments and note contributions."""
import pytest

from backend.app.domain.commitments.services import (
    CommitmentError,
    CommitmentLimitError,
    CommitmentNotFoundError,
    CommitmentStateError,
    MAX_ACTIVE_COMMITMENTS,
    create_commitment,
    delete_commitment,
    list_commitments,
    list_contributions,
    persist_note_contributions,
    update_commitment,
    update_contribution,
    delete_contribution,
)
from backend.tests.fakes import InMemoryCommitmentRepository

USER = "user-1"
OTHER = "user-2"


@pytest.fixture
def repo():
    return InMemoryCommitmentRepository()


def test_create_normalizes_text_and_starts_at_zero(repo):
    row = create_commitment(USER, "  Ship   the  MVP  ", repo=repo)

    assert row["text"] == "Ship the MVP"
    assert row["progress"] == 0
    assert row["status"] == "active"
    assert row["contribution_count"] == 0


def test_empty_text_is_rejected(repo):
    with pytest.raises(CommitmentError, match="cannot be empty"):
        create_commitment(USER, "   ", repo=repo)


def test_active_limit_is_three(repo):
    for index in range(MAX_ACTIVE_COMMITMENTS):
        create_commitment(USER, f"Goal {index}", repo=repo)

    with pytest.raises(CommitmentLimitError, match="up to 3"):
        create_commitment(USER, "Goal 4", repo=repo)


def test_completing_a_goal_frees_an_active_slot(repo):
    first = create_commitment(USER, "Goal 1", repo=repo)
    create_commitment(USER, "Goal 2", repo=repo)
    create_commitment(USER, "Goal 3", repo=repo)
    update_commitment(USER, first["commitment_id"], {"progress": 100}, repo=repo)

    fourth = create_commitment(USER, "Goal 4", repo=repo)
    assert fourth["status"] == "active"


def test_progress_100_completes_and_stamps_completed_at(repo):
    row = create_commitment(USER, "Finish report", repo=repo)
    updated = update_commitment(
        USER, row["commitment_id"], {"progress": 100}, repo=repo
    )

    assert updated["status"] == "completed"
    assert updated["progress"] == 100
    assert updated["completed_at"]


def test_completed_goals_are_read_only(repo):
    row = create_commitment(USER, "Finish report", repo=repo)
    update_commitment(USER, row["commitment_id"], {"progress": 75}, repo=repo)
    update_commitment(USER, row["commitment_id"], {"status": "completed"}, repo=repo)

    with pytest.raises(CommitmentStateError, match="read-only"):
        update_commitment(
            USER, row["commitment_id"], {"progress": 20}, repo=repo
        )


def test_completed_goals_cannot_be_reopened(repo):
    row = create_commitment(USER, "Finish report", repo=repo)
    update_commitment(USER, row["commitment_id"], {"progress": 100}, repo=repo)

    with pytest.raises(CommitmentError, match="cannot be reopened"):
        update_commitment(
            USER, row["commitment_id"], {"status": "active"}, repo=repo
        )


def test_owner_scoping(repo):
    row = create_commitment(USER, "Finish report", repo=repo)
    assert update_commitment(OTHER, row["commitment_id"], {"progress": 20}, repo=repo) == {}
    assert list_commitments(OTHER, repo=repo) == []


def test_list_places_active_before_completed(repo):
    completed = create_commitment(USER, "Done goal", repo=repo)
    active = create_commitment(USER, "Active goal", repo=repo)
    update_commitment(USER, completed["commitment_id"], {"progress": 100}, repo=repo)

    rows = list_commitments(USER, repo=repo)
    assert [row["commitment_id"] for row in rows] == [
        active["commitment_id"],
        completed["commitment_id"],
    ]


def test_delete_removes_goal_and_contributions(repo):
    row = create_commitment(USER, "Finish report", repo=repo)
    persist_note_contributions(
        USER,
        "note-1",
        {
            "commitment_contributions": [
                {"commitment_id": row["commitment_id"], "comment": "Drafted the intro."}
            ]
        },
        repo=repo,
    )
    assert len(list_contributions(USER, row["commitment_id"], repo=repo)) == 1

    assert delete_commitment(USER, row["commitment_id"], repo=repo) is True
    assert list_commitments(USER, repo=repo) == []
    assert repo.contributions == {}


def test_note_contributions_ignore_unknown_ids_and_duplicates(repo):
    row = create_commitment(USER, "Finish report", repo=repo)
    extraction = {
        "commitment_contributions": [
            {"commitment_id": row["commitment_id"], "comment": "Drafted the intro."},
            {"commitment_id": row["commitment_id"], "comment": "Drafted the intro again."},
            {"commitment_id": "not-mine", "comment": "Nope."},
            {"commitment_id": row["commitment_id"], "comment": "   "},
        ]
    }

    first = persist_note_contributions(USER, "note-1", extraction, repo=repo)
    second = persist_note_contributions(USER, "note-1", extraction, repo=repo)

    assert len(first) == 1
    assert second == []
    assert first[0]["comment"] == "Drafted the intro."
    # Evidence never moves the slider; only the user does.
    assert repo.get_commitment(USER, row["commitment_id"])["progress"] == 0


def test_reprocessing_a_note_preserves_a_user_edit(repo):
    row = create_commitment(USER, "Finish report", repo=repo)
    inserted = persist_note_contributions(
        USER,
        "note-1",
        {
            "commitment_contributions": [
                {"commitment_id": row["commitment_id"], "comment": "Drafted the intro."}
            ]
        },
        repo=repo,
    )[0]
    update_contribution(USER, inserted["contribution_id"], "Drafted the intro and methods.", repo=repo)

    persist_note_contributions(
        USER,
        "note-1",
        {
            "commitment_contributions": [
                {"commitment_id": row["commitment_id"], "comment": "A different generated line."}
            ]
        },
        repo=repo,
    )

    rows = list_contributions(USER, row["commitment_id"], repo=repo)
    assert len(rows) == 1
    assert rows[0]["comment"] == "Drafted the intro and methods."
    assert rows[0]["edited_at"]


def test_completed_goal_contributions_are_read_only(repo):
    row = create_commitment(USER, "Finish report", repo=repo)
    inserted = persist_note_contributions(
        USER,
        "note-1",
        {
            "commitment_contributions": [
                {"commitment_id": row["commitment_id"], "comment": "Drafted the intro."}
            ]
        },
        repo=repo,
    )[0]
    update_commitment(USER, row["commitment_id"], {"progress": 100}, repo=repo)

    with pytest.raises(CommitmentStateError, match="read-only"):
        update_contribution(USER, inserted["contribution_id"], "Changed.", repo=repo)
    with pytest.raises(CommitmentStateError, match="read-only"):
        delete_contribution(USER, inserted["contribution_id"], repo=repo)


def test_contribution_owner_scoping(repo):
    row = create_commitment(USER, "Finish report", repo=repo)
    inserted = persist_note_contributions(
        USER,
        "note-1",
        {
            "commitment_contributions": [
                {"commitment_id": row["commitment_id"], "comment": "Drafted the intro."}
            ]
        },
        repo=repo,
    )[0]

    with pytest.raises(CommitmentNotFoundError):
        update_contribution(OTHER, inserted["contribution_id"], "Changed.", repo=repo)
