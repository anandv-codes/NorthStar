"""Tests for prompt rendering and the extraction template.

These guard against the regression where the on-disk extraction prompt used
placeholder names that the code never substituted, so the raw note text was
silently missing from the prompt sent to Gemini.
"""
import pytest

from backend.app.infrastructure.llm.prompt_render import (
    DEFAULT_EXTRACTION_PROMPT_FILENAME,
    DEFAULT_EXTRACTION_PROMPT_VERSION,
    build_extraction_prompt,
    render_prompt_template,
    unresolved_placeholders,
)


def test_render_prompt_template_substitutes_all_placeholders():
    rendered = render_prompt_template(
        "note={note_text} related={related_notes_context}",
        {"note_text": "hello", "related_notes_context": "none"},
    )
    assert rendered == "note=hello related=none"


def test_render_prompt_template_raises_on_unresolved_placeholder():
    with pytest.raises(ValueError, match="note_text"):
        render_prompt_template("note={note_text}", {})


def test_render_prompt_template_leaves_json_braces_intact():
    rendered = render_prompt_template(
        'schema: {"summary": "x"} note={note_text}',
        {"note_text": "hello"},
    )
    assert '"summary": "x"' in rendered
    assert rendered.endswith("note=hello")


def test_render_prompt_template_allows_braces_in_values():
    """User content with braces (code/JSON) must not be treated as placeholders."""
    rendered = render_prompt_template(
        "note={note_text}", {"note_text": "def f(): return {user_id}"}
    )
    assert rendered == "note=def f(): return {user_id}"


def test_unresolved_placeholders_ignores_json_and_doubled_braces():
    text = '{"summary": "x", {{ "legacy": 1 }} {note_text}'
    assert unresolved_placeholders(text) == ["{note_text}"]


def test_build_extraction_prompt_includes_note_and_context():
    prompt = build_extraction_prompt(
        note_text="Fixed the CORS bug",
        related_notes_context="- earlier note",
        structured_items_context="- Supabase (technology)",
    )
    assert "Fixed the CORS bug" in prompt
    assert "- earlier note" in prompt
    assert "- Supabase (technology)" in prompt
    assert unresolved_placeholders(prompt) == []


def test_build_extraction_prompt_uses_stock_template_by_default():
    prompt = build_extraction_prompt("note", "related", "structured")
    assert DEFAULT_EXTRACTION_PROMPT_FILENAME  # document the expected file
    assert "Format your response as JSON" in prompt
    assert "{{" not in prompt and "}}" not in prompt


def test_build_extraction_prompt_falls_back_when_version_missing():
    prompt = build_extraction_prompt(
        note_text="note",
        related_notes_context="related",
        structured_items_context="structured",
        version="version-does-not-exist",
    )
    assert "note" in prompt
    assert unresolved_placeholders(prompt) == []


def test_default_version_is_phase3_v1():
    assert DEFAULT_EXTRACTION_PROMPT_VERSION == "phase3-v1"
