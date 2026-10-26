"""API contract tests for batch reject and restore."""
import pytest
from fastapi import Response
from pydantic import ValidationError

from backend.app.api.routes import recall as recall_routes
from backend.app.schemas.models import RecallBulkRejectRequest, RecallBulkRestoreRequest
from backend.tests.fakes import InMemoryRecallRepository

USER = "user-1"


def _candidate(repo, text: str):
    return repo.upsert_candidate(
        USER,
        {
            "item_type": "fact",
            "source_note_id": "note-1",
            "text": text,
            "prompt": f"What about {text}?",
            "answer": f"An answer about {text}.",
            "score": 0.9,
            "status": "suggested",
            "dedupe_key": f"fact:{text}",
            "rationale": {},
        },
    )


def _call_batch(monkeypatch, repo, candidate_ids):
    monkeypatch.setattr(recall_routes, "get_recall_repository", lambda: repo)
    response = Response()
    body = recall_routes.post_reject_candidates(
        RecallBulkRejectRequest(candidate_ids=candidate_ids),
        response,
        user_id=USER,
    )
    return response, body


def test_full_success_returns_200(monkeypatch):
    repo = InMemoryRecallRepository()
    first = _candidate(repo, "sqs")
    second = _candidate(repo, "visibility")

    response, body = _call_batch(
        monkeypatch, repo, [first["candidate_id"], second["candidate_id"]]
    )

    assert response.status_code == 200
    assert body.rejected == 2
    assert body.failed == 0
    assert repo.get_candidate(USER, first["candidate_id"])["status"] == "rejected"
    assert repo.get_candidate(USER, second["candidate_id"])["status"] == "rejected"


def test_partial_failure_returns_207(monkeypatch):
    repo = InMemoryRecallRepository()
    candidate = _candidate(repo, "sqs")

    response, body = _call_batch(
        monkeypatch, repo, [candidate["candidate_id"], "missing"]
    )

    assert response.status_code == 207
    assert body.rejected == 1
    assert body.failed == 1
    assert {item.status for item in body.results} == {"rejected", "failed"}


def _call_restore_batch(monkeypatch, repo, candidate_ids):
    monkeypatch.setattr(recall_routes, "get_recall_repository", lambda: repo)
    response = Response()
    body = recall_routes.post_restore_candidates(
        RecallBulkRestoreRequest(candidate_ids=candidate_ids),
        response,
        user_id=USER,
    )
    return response, body


def test_restore_batch_undoes_rejections(monkeypatch):
    repo = InMemoryRecallRepository()
    first = _candidate(repo, "sqs")
    second = _candidate(repo, "visibility")
    _call_batch(monkeypatch, repo, [first["candidate_id"], second["candidate_id"]])

    response, body = _call_restore_batch(
        monkeypatch, repo, [first["candidate_id"], second["candidate_id"]]
    )

    assert response.status_code == 200
    assert body.restored == 2
    assert body.failed == 0
    assert repo.get_candidate(USER, first["candidate_id"])["status"] == "suggested"
    assert repo.get_candidate(USER, second["candidate_id"])["status"] == "suggested"


def test_restore_batch_partial_failure_returns_207(monkeypatch):
    repo = InMemoryRecallRepository()
    candidate = _candidate(repo, "sqs")
    _call_batch(monkeypatch, repo, [candidate["candidate_id"]])

    response, body = _call_restore_batch(
        monkeypatch, repo, [candidate["candidate_id"], "missing"]
    )

    assert response.status_code == 207
    assert body.restored == 1
    assert body.failed == 1
    assert {item.status for item in body.results} == {"suggested", "failed"}


def test_batch_request_is_capped_at_200_ids():
    RecallBulkRejectRequest(candidate_ids=[f"id-{index}" for index in range(200)])
    RecallBulkRestoreRequest(candidate_ids=[f"id-{index}" for index in range(200)])

    with pytest.raises(ValidationError):
        RecallBulkRejectRequest(candidate_ids=[f"id-{index}" for index in range(201)])
    with pytest.raises(ValidationError):
        RecallBulkRestoreRequest(candidate_ids=[f"id-{index}" for index in range(201)])
