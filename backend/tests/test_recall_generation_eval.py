"""Tests for the deterministic recall generation evaluation harness."""
from evals.scripts.run_recall_generation_eval import evaluate


def _case(response, expected_points, related_snippets=None):
    return {
        "id": "case-1",
        "candidate_text": "Retry backoff policy",
        "item_type": "fact",
        "context": {
            "source_note_text": "Retries use exponential backoff.",
            "related_snippets": related_snippets or [],
            "related_note_ids": ["note-2", "note-3"] if related_snippets else [],
            "entity_names": [],
        },
        "response": response,
        "expected": {
            "question_form": "how",
            "answer_points": expected_points,
        },
    }


def test_eval_flags_a_how_question_answered_like_a_definition():
    report = evaluate(
        [
            _case(
                '{"question": "How does the retry policy work?", '
                '"answer": "Exponential backoff is a delay strategy."}',
                ["doubles the delay after each attempt"],
            )
        ]
    )

    result = report["cases"][0]
    assert result["checks"]["question_form"] is True
    assert result["checks"]["answer_points"] is False
    assert result["passed"] is False


def test_eval_accepts_a_multi_note_answer_with_both_related_snippets():
    report = evaluate(
        [
            _case(
                '{"question": "How does the retry policy handle exhausted attempts?", '
                '"answer": "It retries with exponential backoff, then moves the message '
                'to the dead-letter queue after five attempts."}',
                ["exponential backoff", "dead-letter queue after five attempts"],
                related_snippets=[
                    "After five attempts the message moves to the dead-letter queue.",
                    "The worker fleet drains the retry queue.",
                ],
            )
        ]
    )

    result = report["cases"][0]
    assert result["checks"]["answer_points"] is True
    assert result["checks"]["prompt_context"] is True
    assert result["checks"]["multi_note"] is True
    assert result["passed"] is True
