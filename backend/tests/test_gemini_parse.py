"""Tests for Gemini extraction-output validation.

``JsonOutputParser(pydantic_object=...)`` only uses the model to render format
instructions; it does not validate. These tests pin the explicit validation in
``parse_gemini_response`` so malformed model output fails here, not as a
``KeyError`` inside the ingestion worker.
"""
import pytest

pytest.importorskip("langchain_google_genai")

from pydantic import ValidationError

from backend.app.infrastructure.llm.gemini_client import parse_gemini_response


def test_rejects_task_missing_required_description():
    with pytest.raises(ValidationError):
        parse_gemini_response('{"tasks": [{"wrong": "x"}]}')


def test_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        parse_gemini_response('{"tasks": [{"description": "Deploy", "confidence": 2}]}')


def test_valid_payload_returns_normalized_dict():
    parsed = parse_gemini_response(
        '{"summary": "s", "tasks": [{"description": "Deploy", '
        '"importance": 0.7, "due_date": "2026-06-13"}]}'
    )

    assert parsed["summary"] == "s"
    assert parsed["tasks"][0]["description"] == "Deploy"
    assert parsed["tasks"][0]["importance"] == 0.7
    # mode="json" keeps due dates serializable for PostgREST.
    assert parsed["tasks"][0]["due_date"] == "2026-06-13"
    assert parsed["facts"] == []


def test_due_date_wrapped_in_prose_keeps_the_iso_date():
    parsed = parse_gemini_response(
        '{"tasks": [{"description": "Deploy", "due_date": "due 2026-06-13 by EOD"}]}'
    )

    assert parsed["tasks"][0]["due_date"] == "2026-06-13"


def test_unparseable_due_date_becomes_none():
    parsed = parse_gemini_response(
        '{"tasks": [{"description": "Deploy", "due_date": "next Friday"}]}'
    )

    assert parsed["tasks"][0]["due_date"] is None


def test_empty_output_is_rejected():
    with pytest.raises(RuntimeError, match="empty output"):
        parse_gemini_response("   ")
