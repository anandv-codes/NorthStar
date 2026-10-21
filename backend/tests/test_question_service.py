"""Tests for persisting generated questions onto candidates (PR7)."""
import pytest

from backend.app.domain.recall.card_generation import RecallConfig
from backend.app.domain.recall.question_service import (
    build_context,
    generate_answer_for_candidate,
    generate_questions,
    generate_questions_for_note,
)
from backend.tests.fakes import InMemoryRecallRepository

CONFIG = RecallConfig(max_attempts=1)
ANSWER = '{"answer": "It controls how long a message stays hidden after retrieval."}'

CONTEXT = build_context(
    "SQS visibility timeout controls how long a message stays hidden after retrieval.",
    ["Workers tune visibility timeout to avoid duplicates."],
    ["SQS"],
)


class FakeChatModel:
    def __init__(self, responses):
        self.responses = list(responses)

    def generate(self, prompt):
        return self.responses.pop(0) if self.responses else ""


def _candidate(repo, text="SQS visibility timeout"):
    row = repo.upsert_candidate(
        "user-1",
        {
            "item_type": "fact",
            "source_note_id": "note-1",
            "text": text,
            "score": 0.9,
            "status": "eligible",
            "dedupe_key": f"fact:{text}",
            "rationale": {},
        },
    )
    return row


def test_generate_questions_marks_suggested():
    repo = InMemoryRecallRepository()
    candidate = _candidate(repo)
    model = FakeChatModel(['{"question": "What does SQS visibility timeout control?"}'])

    results = generate_questions([candidate], CONTEXT, model=model, repo=repo, config=CONFIG)

    assert results[0]["status"] == "suggested"
    stored = repo.get_candidate("user-1", candidate["candidate_id"])
    assert stored["status"] == "suggested"
    assert stored["prompt"].endswith("?")
    # Answers are generated on demand, not during note processing.
    assert stored["answer"] is None
    assert results[0]["answer"] is None
    assert model.responses == []


def test_generate_questions_rejects_and_records_reason():
    repo = InMemoryRecallRepository()
    candidate = _candidate(repo)
    model = FakeChatModel(["this is not a question"])

    results = generate_questions([candidate], CONTEXT, model=model, repo=repo, config=CONFIG)

    assert results[0]["status"] == "rejected"
    stored = repo.get_candidate("user-1", candidate["candidate_id"])
    assert stored["status"] == "rejected"
    assert stored["rationale"]["question_reason"] == "not_a_question"


def test_generate_questions_for_note_only_eligible_of_that_note():
    repo = InMemoryRecallRepository()
    eligible = _candidate(repo, text="SQS visibility timeout")
    # A candidate from another note must not be touched.
    other = _candidate(repo, text="unrelated unit")
    other["source_note_id"] = "note-2"
    # An already-suggested candidate must be skipped.
    suggested = _candidate(repo, text="already asked")
    suggested["status"] = "suggested"

    model = FakeChatModel(['{"question": "What does SQS visibility timeout control?"}'])
    results = generate_questions_for_note(
        "user-1", "note-1", CONTEXT, model=model, repo=repo, config=CONFIG
    )

    assert len(results) == 1
    assert results[0]["candidate_id"] == eligible["candidate_id"]
    assert results[0]["status"] == "suggested"
    assert repo.get_candidate("user-1", eligible["candidate_id"])["answer"] is None
    assert repo.get_candidate("user-1", other["candidate_id"])["status"] == "eligible"
    assert repo.get_candidate("user-1", suggested["candidate_id"])["status"] == "suggested"


def test_generate_questions_dedupes_with_existing():
    repo = InMemoryRecallRepository()
    candidate = _candidate(repo)
    model = FakeChatModel(['{"question": "What does SQS visibility timeout control?"}'])

    results = generate_questions(
        [candidate],
        CONTEXT,
        model=model,
        repo=repo,
        existing_questions=["What does SQS visibility timeout control?"],
        config=CONFIG,
    )

    assert results[0]["status"] == "rejected"
    assert results[0]["reason"] == "duplicate_question"


def test_answer_generation_is_deferred_until_requested():
    repo = InMemoryRecallRepository()
    candidate = _candidate(repo)
    model = FakeChatModel(['{"question": "What does SQS visibility timeout control?"}'])

    generate_questions([candidate], CONTEXT, model=model, repo=repo, config=CONFIG)
    assert model.responses == []  # no second (answer) call

    model.responses.append(ANSWER)
    updated = generate_answer_for_candidate(
        "user-1",
        candidate["candidate_id"],
        model=model,
        repo=repo,
        context=CONTEXT,
        config=CONFIG,
    )

    assert updated["answer"].startswith("It controls")
    stored = repo.get_candidate("user-1", candidate["candidate_id"])
    assert stored["answer"].startswith("It controls")
    assert stored["status"] == "suggested"


def test_answer_generation_is_idempotent_once_stored():
    repo = InMemoryRecallRepository()
    candidate = _candidate(repo)
    candidate["prompt"] = "What does SQS visibility timeout control?"
    candidate["answer"] = "It controls how long a message stays hidden after retrieval."
    model = FakeChatModel([])

    updated = generate_answer_for_candidate(
        "user-1", candidate["candidate_id"], model=model, repo=repo, context=CONTEXT, config=CONFIG
    )

    assert updated["answer"].startswith("It controls")
    assert model.responses == []


def test_answer_generation_rejects_ungrounded_answer():
    repo = InMemoryRecallRepository()
    candidate = _candidate(repo)
    candidate["prompt"] = "What does SQS visibility timeout control?"
    model = FakeChatModel(['{"answer": "Bananas are yellow and grow in the tropics."}'])

    with pytest.raises(ValueError, match="answer_generation_failed:answer_not_grounded"):
        generate_answer_for_candidate(
            "user-1",
            candidate["candidate_id"],
            model=model,
            repo=repo,
            context=CONTEXT,
            config=CONFIG,
        )

    assert repo.get_candidate("user-1", candidate["candidate_id"]).get("answer") is None


def test_rejected_question_does_not_call_answer_model():
    repo = InMemoryRecallRepository()
    candidate = _candidate(repo)
    model = FakeChatModel(["this is not a question"])

    generate_questions([candidate], CONTEXT, model=model, repo=repo, config=CONFIG)

    assert model.responses == []
