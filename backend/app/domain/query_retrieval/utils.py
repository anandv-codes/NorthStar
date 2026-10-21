from __future__ import annotations

import hashlib
import re
from typing import Any, Sequence

from ..constants import RETRIEVAL_STOP_WORDS

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
# Explicit identifiers look like ITEM-4101, CVE-2026-1234, or item4101. The
# lookahead requires a digit so ordinary hyphenated words ("read-model") do
# not become exact-match anchors.
IDENTIFIER_PATTERN = re.compile(
    r"\b(?=[a-z0-9_-]*\d)[a-z][a-z0-9]*(?:[-_][a-z0-9]+)+\b|\b[a-z]+\d+\b",
    re.IGNORECASE,
)
NOTE_TEXT_FIELDS = ("raw_text", "enriched_summary", "text", "summary", "title", "content")


def tokenize(text: str) -> list[str]:
    normalized_text = str(text or "").lower()
    tokens = TOKEN_PATTERN.findall(normalized_text)
    return [token for token in tokens if token not in RETRIEVAL_STOP_WORDS]


def combine_note_text(note: dict[str, Any]) -> str:
    parts: list[str] = []
    seen: set[str] = set()

    for field in NOTE_TEXT_FIELDS:
        value = note.get(field)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                parts.append(cleaned)

    return " ".join(parts)


def extract_identifiers(text: str) -> list[str]:
    """Return unique, normalized explicit identifiers found in ``text``."""
    identifiers: list[str] = []
    seen: set[str] = set()
    for match in IDENTIFIER_PATTERN.findall(str(text or "")):
        normalized = match.lower()
        if normalized not in seen:
            seen.add(normalized)
            identifiers.append(normalized)
    return identifiers


def contains_identifier(text: str, identifier: str) -> bool:
    """True when ``identifier`` appears as a standalone token in ``text``."""
    normalized_identifier = str(identifier or "").strip().lower()
    if not normalized_identifier:
        return False
    pattern = re.compile(
        rf"(?<![a-z0-9]){re.escape(normalized_identifier)}(?![a-z0-9])",
        re.IGNORECASE,
    )
    return bool(pattern.search(str(text or "")))


def fingerprint_notes(notes: Sequence[dict[str, Any]]) -> str:
    # Assumes updated_at/created_at changes whenever note content changes, so this only hashes
    # id + timestamp per note instead of hashing every note's full text on every cache check.
    digest = hashlib.sha1()

    for note in sorted(notes, key=lambda item: str(item.get("note_id") or "")):
        note_id = str(note.get("note_id") or "")
        updated_at = str(note.get("updated_at") or note.get("created_at") or "")
        digest.update(f"{note_id}|{updated_at}".encode("utf-8"))

    return digest.hexdigest()
