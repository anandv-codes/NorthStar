from __future__ import annotations

import hashlib
import re
from typing import Any, Sequence

from ..constants import RETRIEVAL_STOP_WORDS

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
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


def fingerprint_notes(notes: Sequence[dict[str, Any]]) -> str:
    digest = hashlib.sha1()

    for note in sorted(notes, key=lambda item: str(item.get("note_id") or "")):
        note_id = str(note.get("note_id") or "")
        updated_at = str(note.get("updated_at") or note.get("created_at") or "")
        text = combine_note_text(note)
        text_digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        payload = "|".join([note_id, updated_at, str(len(text)), text_digest])
        digest.update(payload.encode("utf-8"))

    return digest.hexdigest()
