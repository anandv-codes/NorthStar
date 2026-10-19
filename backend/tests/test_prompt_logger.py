"""Tests for prompt-log gating.

Raw prompt logs contain full note text, so file logging must stay off unless
``PROMPT_LOG_ENABLED`` is explicitly set.
"""
import pytest

from backend.app.infrastructure.llm import prompt_logger as pl


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("", False),
    ],
)
def test_is_prompt_logging_enabled(monkeypatch, value, expected):
    monkeypatch.setenv("PROMPT_LOG_ENABLED", value)
    assert pl.is_prompt_logging_enabled() is expected


def test_is_prompt_logging_enabled_defaults_off(monkeypatch):
    monkeypatch.delenv("PROMPT_LOG_ENABLED", raising=False)
    assert pl.is_prompt_logging_enabled() is False


def test_writers_noop_when_disabled(monkeypatch, tmp_path):
    monkeypatch.delenv("PROMPT_LOG_ENABLED", raising=False)
    monkeypatch.setenv("PROMPT_LOG_DIR", str(tmp_path))

    pl.log_gemini_interaction("raw note", None, "prompt", "response")
    pl.append_pipeline_log("stage", ["line"])
    pl.append_deterministic_resolution_log("note-1", "user-1", {})

    assert list(tmp_path.iterdir()) == []
