"""Tests for deterministic text chunking."""
import pytest

from backend.app.infrastructure.vector.chunking import chunk_text


def test_blank_text_yields_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_is_a_single_chunk():
    assert chunk_text("A short note.") == ["A short note."]


def test_long_text_is_split_within_bounds():
    text = " ".join(f"This is sentence number {i}." for i in range(200))
    chunks = chunk_text(text, max_chars=200, overlap_chars=40)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 200 + 40


def test_every_sentence_survives_splitting():
    sentences = [f"Sentence {i} carries content." for i in range(60)]
    text = " ".join(sentences)
    chunks = chunk_text(text, max_chars=150, overlap_chars=30)

    joined = " ".join(chunks)
    for sentence in sentences:
        assert sentence in joined


def test_overlap_carries_context_between_chunks():
    text = " ".join(f"Sentence {i}." for i in range(100))
    chunks = chunk_text(text, max_chars=160, overlap_chars=50)
    assert any(chunks[i][:20] in chunks[i - 1] for i in range(1, len(chunks)))


def test_single_oversized_sentence_is_hard_split():
    text = "x" * 500
    chunks = chunk_text(text, max_chars=200, overlap_chars=0)
    assert len(chunks) == 3
    assert "".join(chunks) == text


def test_invalid_parameters_raise():
    with pytest.raises(ValueError):
        chunk_text("text", max_chars=0)
    with pytest.raises(ValueError):
        chunk_text("text", max_chars=100, overlap_chars=100)
