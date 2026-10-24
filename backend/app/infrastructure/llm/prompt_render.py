"""Pure prompt rendering helpers.

Kept free of LangChain/Gemini imports so prompt assembly can be unit tested
without constructing model clients. Prompt templates use ``{snake_case}``
placeholders; rendering fails loudly if any placeholder is left unresolved,
which catches template/code drift (a real bug that let the note text silently
drop out of the extraction prompt).
"""
from __future__ import annotations

import os
import re
from typing import Mapping

from .prompt_loader import load_prompt


PLACEHOLDER_PATTERN = re.compile(r"\{[a-z][a-z0-9_]*\}")

DEFAULT_EXTRACTION_PROMPT_FILENAME = "00-gemini_extraction_prompt.txt"
DEFAULT_EXTRACTION_PROMPT_VERSION = "phase3-v1"


DEFAULT_EXTRACTION_TEMPLATE = """You are an assistant that processes work notes and extracts structured memory.

Raw notes:
{note_text}

Related past notes for cross-reference:
{related_notes_context}

Please provide the following:
1. A concise summary of the notes.
2. Extract typed memory items as tasks, facts, questions, decisions, risks, and entities.
3. For each extracted item, include confidence when possible.
4. Include only items grounded in the note or clearly supported by related notes.
5. If related past notes are relevant, use them only as context and do not invent unsupported facts.
6. IMPORTANT: When related context shows a progression (issue -> diagnosis -> resolution), synthesize that history into your summary instead of restating the new note in isolation.
7. IMPORTANT: Surface any open questions from context for awareness, but NEVER mark them as answered unless the current note explicitly resolves them.
8. For tasks, facts, and concepts, add an `importance` score (0-1, how much this matters for future recall) and a `durability` score (0-1, how long-lived/permanent the knowledge is).
9. Add any explicit deadline to a task's `due_date` (YYYY-MM-DD). Only set dates that are stated or directly implied; otherwise omit.
10. Extract `commitments`: things the user committed to doing, with an optional `due_date`. A task may also be a commitment.

Format your response as JSON with the following structure:
{
    "summary": "Concise summary here",
    "tasks": [
        {
            "description": "Action item 1",
            "confidence": 0.9,
            "due_date": "2026-06-13",
            "importance": 0.7,
            "durability": 0.3,
            "entities": ["Supabase"]
        }
    ],
    "commitments": [
        {
            "title": "Finish monthly report",
            "due_date": "2026-06-13",
            "confidence": 0.8,
            "entities": []
        }
    ],
    "facts": [
        {
            "content": "A key fact extracted from the notes",
            "confidence": 0.85,
            "importance": 0.6,
            "durability": 0.9,
            "entities": ["EntityName"]
        }
    ],
    "questions": [
        {
            "question": "Question 1?",
            "confidence": 0.8,
            "entities": []
        }
    ],
    "decisions": [
        {
            "decision": "A decision that was made",
            "rationale": "Why this decision was made",
            "confidence": 0.8,
            "entities": []
        }
    ],
    "risks": [
        {
            "risk": "A potential risk identified",
            "severity": "high",
            "confidence": 0.75,
            "entities": []
        }
    ],
    "entities": [
        {
            "name": "Supabase",
            "entity_type": "technology"
        }
    ],
    "concepts": [
        {
            "concept": "A learned concept or insight",
            "confidence": 0.7,
            "importance": 0.7,
            "durability": 0.8,
            "entities": ["EntityName"]
        }
    ]
}
"""


def render_prompt_template(template: str, values: Mapping[str, str]) -> str:
    """Substitute ``{key}`` placeholders in ``template`` with ``values``.

    Validation happens on the *template*, never on user-supplied content:
    notes often contain braces (code, JSON, f-strings) and must not be mistaken
    for unresolved placeholders.

    Raises ``ValueError`` if the template references a placeholder that was not
    supplied, so template/code drift cannot silently drop content.
    """
    unresolved = [
        placeholder
        for placeholder in unresolved_placeholders(template)
        if placeholder[1:-1] not in values
    ]
    if unresolved:
        raise ValueError(
            "Prompt template contains unresolved placeholders: "
            + ", ".join(sorted(set(unresolved)))
        )

    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def unresolved_placeholders(text: str) -> list[str]:
    """Return all unresolved ``{snake_case}`` placeholders in ``text``."""
    return PLACEHOLDER_PATTERN.findall(text or "")


def load_prompt_template(
    version: str | None,
    filename: str,
    default: str,
) -> str:
    """Load a prompt file, falling back to ``default`` when it is missing."""
    return load_prompt(
        version or DEFAULT_EXTRACTION_PROMPT_VERSION,
        filename,
        default=default,
    )


def build_extraction_prompt(
    note_text: str,
    related_notes_context: str,
    version: str | None = None,
) -> str:
    """Render the note-extraction prompt from the configured template file."""
    resolved_version = version or os.getenv(
        "WORK_MEMORY_PROMPT_VERSION", DEFAULT_EXTRACTION_PROMPT_VERSION
    )
    template = load_prompt_template(
        resolved_version,
        DEFAULT_EXTRACTION_PROMPT_FILENAME,
        DEFAULT_EXTRACTION_TEMPLATE,
    )
    return render_prompt_template(
        template,
        {
            "note_text": note_text,
            "related_notes_context": related_notes_context,
        },
    ).strip()
