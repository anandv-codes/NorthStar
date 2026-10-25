"""Domain rules for long-term commitments.

Commitments are deliberately small and user-authored. Notes may add one
provenance-linked contribution per commitment, but they never change progress
or complete a goal. The three-active-goal limit is enforced here so every entry
point (onboarding, settings, API) follows the same rule.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ..ports import CommitmentRepository

MAX_ACTIVE_COMMITMENTS = 3
MAX_COMMITMENT_TEXT_LENGTH = 200
MAX_CONTRIBUTION_LENGTH = 240

COMMITMENT_STATUSES = {"active", "completed"}


class CommitmentError(ValueError):
    """Base class for user-facing commitment validation errors."""


class CommitmentLimitError(CommitmentError):
    """Raised when the user already has the maximum number of active goals."""


class CommitmentNotFoundError(CommitmentError):
    """Raised when a goal or contribution does not belong to the user."""


class CommitmentStateError(CommitmentError):
    """Raised when an update would mutate a completed goal."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_repo(repo: CommitmentRepository | None) -> CommitmentRepository:
    if repo is not None:
        return repo
    from ...infrastructure.db.commitment_repository import get_commitment_repository

    return get_commitment_repository()


def normalize_commitment_text(value: Any) -> str:
    """Collapse whitespace and enforce the single-line goal text limit."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        raise CommitmentError("Commitment text cannot be empty.")
    if len(text) > MAX_COMMITMENT_TEXT_LENGTH:
        raise CommitmentError(
            f"Commitment text must be {MAX_COMMITMENT_TEXT_LENGTH} characters or fewer."
        )
    return text


def normalize_contribution_comment(value: Any) -> str:
    """Normalize a model-written contribution to one short, readable line."""
    comment = re.sub(r"\s+", " ", str(value or "")).strip()
    if not comment:
        return ""
    if len(comment) > MAX_CONTRIBUTION_LENGTH:
        comment = comment[: MAX_CONTRIBUTION_LENGTH - 1].rstrip() + "…"
    return comment


def _with_contribution_count(
    row: dict[str, Any], counts: dict[str, int]
) -> dict[str, Any]:
    commitment_id = str(row.get("commitment_id") or "")
    return {**row, "contribution_count": counts.get(commitment_id, 0)}


def _attach_counts(
    rows: list[dict[str, Any]], user_id: str, repo: CommitmentRepository
) -> list[dict[str, Any]]:
    ids = [str(row.get("commitment_id")) for row in rows if row.get("commitment_id")]
    counts = repo.count_contributions_by_commitment(user_id, ids) if ids else {}
    return [_with_contribution_count(row, counts) for row in rows]


def _sort_commitments(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Active first, then newest; completed goals remain available as history."""
    newest_first = sorted(
        rows, key=lambda row: str(row.get("created_at") or ""), reverse=True
    )
    return sorted(newest_first, key=lambda row: 0 if row.get("status") == "active" else 1)


def list_commitments(
    user_id: str,
    status: str | None = None,
    repo: CommitmentRepository | None = None,
) -> list[dict[str, Any]]:
    repo = _get_repo(repo)
    if status and status not in COMMITMENT_STATUSES:
        raise CommitmentError(f"Invalid commitment status: {status}")
    rows = repo.query_commitments(user_id, status=status)
    rows = _sort_commitments(rows)
    return _attach_counts(rows, user_id, repo)


def get_commitment(
    user_id: str,
    commitment_id: str,
    repo: CommitmentRepository | None = None,
) -> dict[str, Any] | None:
    repo = _get_repo(repo)
    row = repo.get_commitment(user_id, commitment_id)
    if row is None:
        return None
    return _with_contribution_count(
        row, repo.count_contributions_by_commitment(user_id, [commitment_id])
    )


def create_commitment(
    user_id: str,
    text: str,
    repo: CommitmentRepository | None = None,
) -> dict[str, Any]:
    repo = _get_repo(repo)
    normalized = normalize_commitment_text(text)
    active = repo.query_commitments(user_id, status="active")
    if len(active) >= MAX_ACTIVE_COMMITMENTS:
        raise CommitmentLimitError(
            f"You can have up to {MAX_ACTIVE_COMMITMENTS} active long-term goals. "
            "Complete or delete one before adding another."
        )
    row = repo.create_commitment(user_id, normalized)
    return _with_contribution_count(row, {})


def update_commitment(
    user_id: str,
    commitment_id: str,
    updates: dict[str, Any],
    repo: CommitmentRepository | None = None,
) -> dict[str, Any]:
    repo = _get_repo(repo)
    current = repo.get_commitment(user_id, commitment_id)
    if current is None:
        return {}
    requested_status = updates.get("status")
    if current.get("status") == "completed":
        if requested_status is not None and requested_status != "completed":
            raise CommitmentError("Completed goals cannot be reopened.")
        raise CommitmentStateError("Completed long-term goals are read-only.")

    payload: dict[str, Any] = {}
    if "text" in updates and updates["text"] is not None:
        payload["text"] = normalize_commitment_text(updates["text"])

    if "progress" in updates and updates["progress"] is not None:
        try:
            progress = int(updates["progress"])
        except (TypeError, ValueError) as exc:
            raise CommitmentError("Progress must be a whole number from 0 to 100.") from exc
        if progress < 0 or progress > 100:
            raise CommitmentError("Progress must be between 0 and 100.")
        payload["progress"] = progress
        if progress >= 100:
            payload["status"] = "completed"
            payload["completed_at"] = _utcnow()

    if requested_status is not None:
        if requested_status != "completed":
            raise CommitmentError("Completed goals cannot be reopened.")
        payload["status"] = "completed"
        payload["progress"] = 100
        payload["completed_at"] = payload.get("completed_at") or _utcnow()

    if not payload:
        raise CommitmentError("At least one editable field is required.")

    updated = repo.update_commitment(user_id, commitment_id, payload)
    if not updated:
        return {}
    return _with_contribution_count(
        updated, repo.count_contributions_by_commitment(user_id, [commitment_id])
    )


def delete_commitment(
    user_id: str,
    commitment_id: str,
    repo: CommitmentRepository | None = None,
) -> bool:
    repo = _get_repo(repo)
    return repo.delete_commitment(user_id, commitment_id)


def list_contributions(
    user_id: str,
    commitment_id: str,
    repo: CommitmentRepository | None = None,
) -> list[dict[str, Any]]:
    repo = _get_repo(repo)
    if repo.get_commitment(user_id, commitment_id) is None:
        raise CommitmentNotFoundError("Commitment not found.")
    return repo.query_contributions(user_id, commitment_id)


def update_contribution(
    user_id: str,
    contribution_id: str,
    comment: str,
    repo: CommitmentRepository | None = None,
) -> dict[str, Any]:
    repo = _get_repo(repo)
    normalized = normalize_contribution_comment(comment)
    if not normalized:
        raise CommitmentError("Contribution text cannot be empty.")
    contribution = repo.get_contribution(user_id, contribution_id)
    if contribution is None:
        raise CommitmentNotFoundError("Contribution not found.")
    commitment = repo.get_commitment(user_id, str(contribution.get("commitment_id")))
    if commitment is None:
        raise CommitmentNotFoundError("Commitment not found.")
    if commitment.get("status") == "completed":
        raise CommitmentStateError("Contributions on completed goals are read-only.")
    return repo.update_contribution(user_id, contribution_id, normalized)


def delete_contribution(
    user_id: str,
    contribution_id: str,
    repo: CommitmentRepository | None = None,
) -> bool:
    repo = _get_repo(repo)
    contribution = repo.get_contribution(user_id, contribution_id)
    if contribution is None:
        raise CommitmentNotFoundError("Contribution not found.")
    commitment = repo.get_commitment(user_id, str(contribution.get("commitment_id")))
    if commitment is None:
        raise CommitmentNotFoundError("Commitment not found.")
    if commitment.get("status") == "completed":
        raise CommitmentStateError("Contributions on completed goals are read-only.")
    return repo.delete_contribution(user_id, contribution_id)


def persist_note_contributions(
    user_id: str,
    note_id: str,
    extraction: dict[str, Any],
    repo: CommitmentRepository | None = None,
) -> list[dict[str, Any]]:
    """Persist at most one model contribution per active goal for this note.

    The extraction prompt receives only user-authored commitment text and ids.
    Anything returned for an inactive/unknown id is ignored. Repository-level
    de-duplication by ``(commitment_id, note_id)`` preserves user edits when a
    note is processed again.
    """
    repo = _get_repo(repo)
    active = repo.query_commitments(user_id, status="active")
    active_ids = {str(row.get("commitment_id")) for row in active if row.get("commitment_id")}
    if not active_ids:
        return []

    inserted: list[dict[str, Any]] = []
    for item in extraction.get("commitment_contributions", []) or []:
        commitment_id = str(item.get("commitment_id") or "").strip()
        comment = normalize_contribution_comment(item.get("comment"))
        if not commitment_id or commitment_id not in active_ids or not comment:
            continue
        row = repo.insert_contribution(
            user_id=user_id,
            commitment_id=commitment_id,
            note_id=note_id,
            comment=comment,
        )
        if row:
            inserted.append(row)
    return inserted
