"""API contract tests for batch accept.

Covers the two things the batch endpoint promises beyond "it works": one bulk
candidate read (not one per id), and a 207 status when part of the batch failed.
"""
import pytest
from fastapi import Response
from pydantic import ValidationError

from backend.app.api.routes import recall as recall_routes
from backend.app.schemas.models import RecallBulkAcceptRequest
from backend.tests.fakes import InMemoryRecallRepository

USER = "user-1"
ANSWER = "It controls how long a message stays hidden after retrieval."


class _CountingRepo(InMemoryRecallRepository):
    def __init__(self) -> None:
        super().__init__()
        self.bulk_calls = 0
        self.single_candidate_calls = 0
        self._inside_fake_rpc = False

    def get_candidates_by_ids(self, user_id, candidate_ids):
        self.bulk_calls += 1
        return super().get_candidates_by_ids(user_id, candidate_ids)

    def get_candidate(self, user_id, candidate_id):
        if not self._inside_fake_rpc:
            self.single_candidate_calls += 1
        return super().get_candidate(user_id, candidate_id)

    def accept_candidate_atomic(self, *args, **kwargs):
        # The base fake looks candidates up internally; do not count that as a
        # route-level refetch.
        self._inside_fake_rpc = True
        try:
            return super().accept_candidate_atomic(*args, **kwargs)
        finally:
            self._inside_fake_rpc = False

    def update_candidate(self, user_id, candidate_id, updates):
        # The real repository updates by key; the fake's base implementation
        # reads through ``get_candidate``, which would pollute the counter.
        row = self.candidates.get(candidate_id)
        if row is None or row["user_id"] != user_id:
            return {}
        row.update(updates)
        return row


def _candidate(repo, text: str, note_id: str = "note-1", answer: str | None = ANSWER):
    return repo.upsert_candidate(
        USER,
        {
            "item_type": "fact",
            "source_note_id": note_id,
            "text": text,
            "prompt": f"What about {text}?",
            "answer": answer,
            "score": 0.9,
            "status": "suggested",
            "dedupe_key": f"fact:{text}",
            "rationale": {},
        },
    )


class _FakeModel:
    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        return '{"answer": "%s"}' % self.answers.pop(0)


def _call_batch(monkeypatch, repo, candidate_ids, model=None, patch_model=True):
    monkeypatch.setattr(recall_routes, "get_recall_repository", lambda: repo)
    if patch_model:
        monkeypatch.setattr(recall_routes, "get_chat_model", lambda: model)

    context_calls: list[str | None] = []

    def fake_context(user_id, source_note_id):
        context_calls.append(source_note_id)
        return {}

    monkeypatch.setattr(recall_routes, "_context_for_note", fake_context)

    response = Response()
    body = recall_routes.post_accept_candidates(
        RecallBulkAcceptRequest(candidate_ids=candidate_ids),
        response,
        user_id=USER,
    )
    return response, body, context_calls


def test_partial_failure_returns_207(monkeypatch):
    repo = _CountingRepo()
    candidate = _candidate(repo, "sqs")

    response, body, _ = _call_batch(
        monkeypatch, repo, [candidate["candidate_id"], "missing"]
    )

    assert response.status_code == 207
    assert body.accepted == 1
    assert body.failed == 1
    assert {item.status for item in body.results} == {"carded", "failed"}


def test_full_success_returns_200(monkeypatch):
    repo = _CountingRepo()
    first = _candidate(repo, "sqs")
    second = _candidate(repo, "visibility")

    response, body, _ = _call_batch(
        monkeypatch, repo, [first["candidate_id"], second["candidate_id"]]
    )

    assert response.status_code == 200
    assert body.accepted == 2
    assert body.failed == 0


def test_batch_reads_candidates_once_and_context_once_per_note(monkeypatch):
    repo = _CountingRepo()
    first = _candidate(repo, "sqs", answer=None)
    second = _candidate(repo, "visibility", answer=None)
    other_note = _candidate(repo, "retries", note_id="note-2", answer=None)
    model = _FakeModel(["sqs", "visibility", "retries"])

    _, body, context_calls = _call_batch(
        monkeypatch,
        repo,
        [first["candidate_id"], second["candidate_id"], other_note["candidate_id"]],
        model=model,
    )

    assert body.accepted == 3
    assert repo.bulk_calls == 1
    assert repo.single_candidate_calls == 0
    assert context_calls == ["note-1", "note-2"]
    assert model.calls == 3


def test_batch_skips_context_and_model_when_answers_are_cached(monkeypatch):
    repo = _CountingRepo()
    first = _candidate(repo, "sqs")
    second = _candidate(repo, "visibility")

    def unexpected_model(*args, **kwargs):
        raise AssertionError("cached answers should not initialise the model")

    monkeypatch.setattr(recall_routes, "get_chat_model", unexpected_model)
    _, body, context_calls = _call_batch(
        monkeypatch,
        repo,
        [first["candidate_id"], second["candidate_id"]],
        patch_model=False,
    )

    assert body.accepted == 2
    assert context_calls == []


def test_batch_request_is_capped_at_100_ids():
    RecallBulkAcceptRequest(candidate_ids=[f"id-{index}" for index in range(100)])

    with pytest.raises(ValidationError):
        RecallBulkAcceptRequest(candidate_ids=[f"id-{index}" for index in range(101)])
