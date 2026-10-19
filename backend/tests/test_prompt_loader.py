"""Regression tests for the prompt loader's directory resolution.

A path bug previously pointed the loader at ``infrastructure/prompts`` so every
file prompt silently fell back to the in-code default.
"""
from pathlib import Path

import pytest

from backend.app.infrastructure.llm import prompt_loader

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ROOT = REPO_ROOT / "backend" / "app" / "prompts"


def test_prompts_root_points_at_app_prompts():
    assert prompt_loader._prompts_root() == EXPECTED_ROOT
    assert EXPECTED_ROOT.is_dir()


def test_load_prompt_reads_the_file_on_disk():
    content = prompt_loader.load_prompt("phase3-v1", "00-gemini_extraction_prompt.txt")
    assert "{note_text}" in content
    assert "commitments" in content


def test_load_prompt_missing_file_raises_or_defaults():
    with pytest.raises(FileNotFoundError):
        prompt_loader.load_prompt("phase3-v1", "does-not-exist.txt")
    assert prompt_loader.load_prompt("phase3-v1", "does-not-exist.txt", default="fallback") == "fallback"
