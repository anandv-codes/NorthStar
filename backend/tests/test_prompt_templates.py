"""Static validation of on-disk prompt templates.

Each template is rendered by ``str.replace`` at runtime, not ``str.format``,
so any placeholder the code does not substitute is sent to the model verbatim.
These tests pin the supported placeholder set per template and reject
format-style doubled braces that ``replace`` would emit literally.
"""
from pathlib import Path

import pytest

from backend.app.infrastructure.llm.prompt_render import unresolved_placeholders

PROMPTS_ROOT = Path(__file__).resolve().parents[1] / "app" / "prompts"

EXPECTED_PLACEHOLDERS = {
    "00-gemini_extraction_prompt.txt": {
        "note_text",
        "related_notes_context",
        "commitments_context",
    },
    "01-query_rewrite_prompt.txt": {"user_query", "memory_context"},
    "02-chat_prompt.txt": {
        "intent_payload_json",
        "plan_json",
        "summary_memory",
        "short_term_context",
        "knowledge_context",
        "grounding_context",
        "tool_context",
        "user_message",
    },
    "03-recall-question_prompt.txt": {
        "item_type",
        "candidate_text",
        "source_note_text",
        "related_snippets",
        "entity_names",
    },
    "04-recall-answer_prompt.txt": {
        "question",
        "candidate_text",
        "source_note_text",
        "related_snippets",
        "entity_names",
    },
    "05-recall-question-answer_prompt.txt": {
        "item_type",
        "candidate_text",
        "source_note_text",
        "related_snippets",
        "entity_names",
    },
}

PROMPT_FILES = sorted(PROMPTS_ROOT.glob("**/*.txt"))


def test_expected_prompt_files_exist():
    discovered = {path.name for path in PROMPT_FILES}
    assert set(EXPECTED_PLACEHOLDERS).issubset(discovered)


@pytest.mark.parametrize("template_path", PROMPT_FILES, ids=lambda p: p.name)
def test_prompt_placeholders_are_known(template_path: Path):
    text = template_path.read_text(encoding="utf-8")
    found = {name.strip("{}") for name in unresolved_placeholders(text)}
    expected = EXPECTED_PLACEHOLDERS[template_path.name]

    assert found == expected, (
        f"{template_path.name} placeholders changed. "
        f"found={sorted(found)} expected={sorted(expected)}. "
        "Update the rendering code and this expectation together."
    )


@pytest.mark.parametrize("template_path", PROMPT_FILES, ids=lambda p: p.name)
def test_prompt_templates_do_not_use_format_style_braces(template_path: Path):
    text = template_path.read_text(encoding="utf-8")
    assert "{{" not in text, (
        f"{template_path.name} contains '{{{{' which is emitted literally by "
        "str.replace. Use single braces for example JSON."
    )
