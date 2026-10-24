"""Tests for question-first card generation and validation."""
from backend.app.domain.recall.card_generation import (
    RecallConfig,
    build_answer_prompt,
    build_question_answer_prompt,
    build_question_prompt,
    generate_answer,
    generate_question,
    generate_question_with_answer,
    validate_answer,
    validate_question,
)

CONFIG = RecallConfig(max_attempts=2)

CONTEXT = {
    "candidate_text": "SQS visibility timeout",
    "source_note_text": "SQS visibility timeout controls how long a message stays hidden after retrieval.",
    "related_snippets": ["Our workers set visibility timeout to avoid duplicate processing."],
    "entity_names": ["SQS"],
}

MULTI_NOTE_CONTEXT = {
    "candidate_text": "Retry policy",
    "source_note_text": "Retries use exponential backoff before the message is retried.",
    "related_snippets": [
        "After five attempts the message moves to the dead-letter queue.",
        "The retry queue is drained by the worker fleet.",
    ],
    "entity_names": ["SQS"],
}


class FakeChatModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0) if self.responses else ""


def test_question_prompt_renders_cleanly():
    prompt = build_question_prompt("SQS visibility timeout", "fact", CONTEXT)
    assert "SQS visibility timeout" in prompt
    assert "{candidate_text}" not in prompt
    assert "SQS" in prompt


def test_answer_prompt_renders_cleanly():
    prompt = build_answer_prompt("What does SQS visibility timeout control?", CONTEXT)
    assert "What does SQS visibility timeout control?" in prompt
    assert "SQS visibility timeout" in prompt
    assert "{question}" not in prompt
    assert "{candidate_text}" not in prompt


def test_question_answer_prompt_renders_cleanly():
    prompt = build_question_answer_prompt("SQS visibility timeout", "fact", CONTEXT)
    assert "SQS visibility timeout" in prompt
    assert "SQS" in prompt
    assert "{candidate_text}" not in prompt
    assert "{question}" not in prompt
    assert "{answer}" not in prompt


def test_question_prompt_selects_the_supported_question_form():
    prompt = build_question_prompt("SQS visibility timeout", "fact", CONTEXT)
    assert "Do not force a 'How' question" in prompt
    assert "'What' for definitions" in prompt


def test_answer_prompt_matches_the_question_form():
    prompt = build_answer_prompt("How does the visibility timeout work?", CONTEXT)
    assert "match its form" in prompt
    assert "describe the mechanism, steps, or process" in prompt
    assert "Do not merely restate the knowledge unit" in prompt


def test_question_answer_prompt_matches_the_question_form():
    prompt = build_question_answer_prompt("SQS visibility timeout", "fact", CONTEXT)
    assert "Do not force a 'How' question" in prompt
    assert "match its form" in prompt
    assert "Do not merely restate the knowledge unit" in prompt


def test_prompts_include_all_related_note_snippets():
    answer_prompt = build_answer_prompt("What is the retry policy?", MULTI_NOTE_CONTEXT)
    pair_prompt = build_question_answer_prompt(
        "Retry policy", "fact", MULTI_NOTE_CONTEXT
    )

    for prompt in (answer_prompt, pair_prompt):
        assert "After five attempts the message moves to the dead-letter queue." in prompt
        assert "The retry queue is drained by the worker fleet." in prompt


def test_validate_question_rules():
    assert validate_question("What does SQS visibility timeout control?", [], CONFIG)[0] is True
    assert validate_question("This is not a question", [], CONFIG)[1] == "not_a_question"
    assert validate_question("What does this note say?", [], CONFIG)[1] == "generic_question"
    assert validate_question("x" * 500 + "?", [], CONFIG)[1] == "question_too_long"

    existing = ["What does SQS visibility timeout control?"]
    ok, reason = validate_question(
        "What does SQS visibility timeout control?", existing, CONFIG
    )
    assert ok is False
    assert reason == "duplicate_question"


def test_validate_answer_grounding():
    ok, _ = validate_answer(
        "It controls how long a message stays hidden after retrieval.", CONTEXT["source_note_text"], CONFIG
    )
    assert ok is True

    ok, reason = validate_answer("Bananas are yellow and grow in the tropics.", CONTEXT["source_note_text"], CONFIG)
    assert ok is False
    assert reason == "answer_not_grounded"

    assert validate_answer("", "x", CONFIG)[1] == "empty_answer"


def test_generate_question_parses_json_and_validates():
    model = FakeChatModel(['{"question": "What does SQS visibility timeout control?"}'])
    result = generate_question("SQS visibility timeout", "fact", CONTEXT, model, config=CONFIG)
    assert result["status"] == "generated"
    assert result["question"].endswith("?")


def test_generate_question_retries_then_rejects():
    model = FakeChatModel(
        [
            "This is not a question",  # attempt 1 -> invalid
            '{"question": "not a question either"}',  # attempt 2 -> invalid
        ]
    )
    result = generate_question("unit", "fact", CONTEXT, model, config=CONFIG)
    assert result["status"] == "rejected"
    assert len(model.prompts) == 2


def test_generate_question_retry_succeeds():
    model = FakeChatModel(
        [
            "not a question",
            '{"question": "What does SQS visibility timeout control?"}',
        ]
    )
    result = generate_question("unit", "fact", CONTEXT, model, config=CONFIG)
    assert result["status"] == "generated"


def test_generate_answer_grounding_and_rejection():
    model = FakeChatModel(
        ['{"answer": "It controls how long a message stays hidden after retrieval."}']
    )
    result = generate_answer("What does it control?", CONTEXT, model, config=CONFIG)
    assert result["status"] == "generated"

    model = FakeChatModel(['{"answer": "Totally unrelated answer about bananas."}'] * 2)
    result = generate_answer("What does it control?", CONTEXT, model, config=CONFIG)
    assert result["status"] == "rejected"
    assert result["reason"] == "answer_not_grounded"


def test_generate_answer_uses_related_note_context():
    model = FakeChatModel(
        [
            '{"answer": "It moves the message to the dead-letter queue after five '
            'attempts, and the worker fleet drains the retry queue."}'
        ]
    )
    result = generate_answer(
        "How does the retry policy handle exhausted attempts?",
        MULTI_NOTE_CONTEXT,
        model,
        config=CONFIG,
    )

    assert result["status"] == "generated"
    prompt = model.prompts[0]
    assert "After five attempts the message moves to the dead-letter queue." in prompt
    assert "The retry queue is drained by the worker fleet." in prompt


def test_generate_question_with_answer_returns_both():
    model = FakeChatModel(
        [
            '{"question": "What does SQS visibility timeout control?", '
            '"answer": "It controls how long a message stays hidden after retrieval."}'
        ]
    )
    result = generate_question_with_answer(
        "SQS visibility timeout", "fact", CONTEXT, model, config=CONFIG
    )

    assert result["status"] == "generated"
    assert result["question"].endswith("?")
    assert result["answer"].startswith("It controls")
    assert len(model.prompts) == 1


def test_generate_question_with_answer_keeps_question_when_answer_fails():
    model = FakeChatModel(
        [
            '{"question": "What does SQS visibility timeout control?", '
            '"answer": "Bananas are yellow and grow in the tropics."}',
            '{"question": "What does SQS visibility timeout control?", '
            '"answer": "Bananas are yellow and grow in the tropics."}',
        ]
    )
    result = generate_question_with_answer(
        "SQS visibility timeout", "fact", CONTEXT, model, config=CONFIG
    )

    assert result["status"] == "generated_without_answer"
    assert result["question"].endswith("?")
    assert result["answer"] is None
    assert result["reason"] == "answer_not_grounded"


def test_generate_question_with_answer_rejects_raw_text():
    # A raw string cannot be split into a question and an answer, so it must
    # not be accepted just because the text happens to end with "?".
    model = FakeChatModel(["What does SQS visibility timeout control?"])
    result = generate_question_with_answer(
        "SQS visibility timeout", "fact", CONTEXT, model, config=CONFIG
    )

    assert result["status"] == "rejected"
    assert result["reason"] == "not_a_question"


def test_generate_question_with_answer_rejects_echo():
    model = FakeChatModel(
        [
            '{"question": "What does SQS visibility timeout control?", '
            '"answer": "What does SQS visibility timeout control?"}'
        ]
    )
    result = generate_question_with_answer(
        "SQS visibility timeout", "fact", CONTEXT, model, config=CONFIG
    )

    assert result["status"] == "generated_without_answer"
    assert result["reason"] == "answer_echoes_question"
