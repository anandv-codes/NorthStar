"""Gemini API client for work memory extraction."""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

from functools import lru_cache

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser

from ...schemas.models import WorkMemoryExtraction
from .prompt_logger import log_gemini_interaction
from .prompt_loader import load_prompt
from .llm_response_utils import extract_text_from_response
from .llm_config import (
    WORK_MEMORY_EXTRACTION_TEMPERATURE,
    WORK_MEMORY_EXTRACTION_MAX_RETRIES,
    WORK_MEMORY_EXTRACTION_TIMEOUT_SECONDS,
    CHAT_ANSWER_GENERATION_TEMPERATURE,
    CHAT_ANSWER_GENERATION_MAX_RETRIES,
    CHAT_ANSWER_GENERATION_TIMEOUT_SECONDS,
    STRUCTURED_ITEMS_LIMIT,
    OPEN_STATUSES,
    MAX_ITEM_DESCRIPTION_LENGTH,
    MAX_MATCHED_ENTITIES_TO_DISPLAY,
    MAX_RELATED_NOTES_IN_CONTEXT,
    MAX_RELATED_NOTE_SUMMARY_LENGTH,
    PERIOD_SUMMARY_TEMPERATURE,
    PERIOD_SUMMARY_MAX_RETRIES,
    PERIOD_SUMMARY_TIMEOUT_SECONDS,
)


def filter_open_items(memory_items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Filter memory items to only open ones, grouped by type, with limits and truncation.
    
    Returns dict mapping item type -> list of filtered items (limited to top N, descriptions truncated).
    """
    grouped = {}
    
    for item in memory_items:
        item_type = item.get("type")
        if not item_type:
            continue
        
        # Check if item is open (if status filter is defined)
        open_statuses = OPEN_STATUSES.get(item_type)
        if open_statuses is not None:
            status = item.get("status", "").lower()
            if status not in open_statuses:
                continue
        
        if item_type not in grouped:
            grouped[item_type] = []
        
        # Truncate description
        description = item.get("description") or item.get("content") or item.get("question") or item.get("decision") or ""
        if len(description) > MAX_ITEM_DESCRIPTION_LENGTH:
            description = description[:MAX_ITEM_DESCRIPTION_LENGTH].rstrip() + "…"
        
        truncated_item = {**item, "description": description}
        grouped[item_type].append(truncated_item)
    
    # Limit each group to top N
    result = {}
    for item_type, items in grouped.items():
        limit = STRUCTURED_ITEMS_LIMIT.get(item_type, 3)
        result[item_type] = items[:limit]
    
    return result


def generate_structured_items_context(
    matched_entity_names: list[str] | None = None,
    memory_items: list[dict[str, Any]] | None = None,
) -> str:
    """Format filtered memory items as text block for LLM context.
    
    Only includes open items, limited by STRUCTURED_ITEMS_LIMIT, with descriptions truncated.
    """
    if not memory_items:
        return ""
    
    filtered = filter_open_items(memory_items)
    if not filtered:
        return ""
    
    lines = []
    
    # Add matched entity names as anchors
    if matched_entity_names:
        lines.append("Linked Entities:")
        for entity_name in matched_entity_names[:MAX_MATCHED_ENTITIES_TO_DISPLAY]:
            lines.append(f"  • {entity_name}")
        lines.append("")
    
    # Add grouped items
    type_labels = {
        "tasks": "Open Tasks",
        "questions": "Open Questions",
        "risks": "Open Risks",
        "concepts": "Concepts",
        "decisions": "Recent Decisions",
        "facts": "Key Facts",
    }
    
    for item_type in ["tasks", "questions", "risks", "concepts", "decisions", "facts"]:
        items = filtered.get(item_type, [])
        if not items:
            continue
        
        label = type_labels.get(item_type, item_type.title())
        lines.append(f"{label}:")
        for item in items:
            desc = item.get("description") or ""
            if desc:
                lines.append(f"  • {desc}")
        lines.append("")
    
    return "\n".join(lines).strip()


def call_gemini_api(
    note_text: str,
    related_notes: list[dict[str, Any]] | None = None,
    matched_entity_names: list[str] | None = None,
    memory_items: list[dict[str, Any]] | None = None,
) -> dict:
    """Extract structured memory from note text using Gemini."""
    prompt = generate_gemini_prompt(
        note_text,
        related_notes=related_notes or [],
        matched_entity_names=matched_entity_names,
        memory_items=memory_items,
    )
    output_text = invoke_gemini(prompt)

    parsed_response = None
    parse_error = None
    try:
        parsed_response = parse_gemini_response(output_text)
        logger.info(
            "Gemini extraction parsed: tasks=%d facts=%d questions=%d decisions=%d risks=%d concepts=%d",
            len(parsed_response.get("tasks", [])),
            len(parsed_response.get("facts", [])),
            len(parsed_response.get("questions", [])),
            len(parsed_response.get("decisions", [])),
            len(parsed_response.get("risks", [])),
            len(parsed_response.get("concepts", [])),
        )
        return parsed_response
    except Exception as exc:
        parse_error = str(exc)
        logger.error(f"Gemini response parsing failed: {exc} (see gemini_prompt_response.txt for full output)")
        raise
    finally:
        # Persist the interaction even if parsing fails so debugging always has artifacts.
        log_gemini_interaction(
            note_text=note_text,
            related_notes=related_notes,
            prompt=prompt,
            response=output_text,
            parsed_result=parsed_response,
            parse_error=parse_error,
        )


def invoke_gemini(prompt_text: str) -> str:
    """Call Gemini API with the given prompt."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set")

    model_id = os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
    model = ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model_id,
        temperature=WORK_MEMORY_EXTRACTION_TEMPERATURE,
        max_retries=WORK_MEMORY_EXTRACTION_MAX_RETRIES,
        timeout=WORK_MEMORY_EXTRACTION_TIMEOUT_SECONDS,
    )

    logger.info(f"Calling Gemini ({model_id}), prompt_chars={len(prompt_text)}")
    response = model.invoke([HumanMessage(content=prompt_text)])
    return extract_text_from_response(response)


def parse_gemini_response(output_text: str) -> dict:
    """Parse Gemini JSON output into structured WorkMemoryExtraction."""
    if not output_text or not output_text.strip():
        raise RuntimeError("Gemini returned empty output")

    parser = JsonOutputParser(pydantic_object=WorkMemoryExtraction)
    parsed = parser.invoke(output_text)
    return parsed


def generate_gemini_prompt(
    note_text: str,
    related_notes: list[dict[str, Any]] | None = None,
    matched_entity_names: list[str] | None = None,
    memory_items: list[dict[str, Any]] | None = None,
) -> str:
    """Generate the extraction prompt with note text, related context, and structured items."""
    related_context = generate_related_notes_context(related_notes or [])
    structured_items_context = generate_structured_items_context(matched_entity_names, memory_items)
    
    version = os.getenv("WORK_MEMORY_PROMPT_VERSION", "phase3-v1")
    
    default_template = """You are an assistant that processes work notes and extracts structured memory.

Raw notes:
{note_text}

Related past notes for cross-reference:
{related_notes_context}

Related context (linked entities and open items):
{structured_items_context}

Please provide the following:
1. A concise summary of the notes.
2. Extract typed memory items as tasks, facts, questions, decisions, risks, and entities.
3. For each extracted item, include confidence when possible.
4. Include only items grounded in the note or clearly supported by related notes.
5. If related past notes are relevant, use them only as context and do not invent unsupported facts.
6. IMPORTANT: When related context shows a progression (issue → diagnosis → resolution), synthesize that history into your summary instead of restating the new note in isolation.
7. IMPORTANT: Surface any open questions from context for awareness, but NEVER mark them as answered unless the current note explicitly resolves them.

Format your response as JSON with the following structure:
{{
    "summary": "Concise summary here",
    "tasks": [
        {{
            "description": "Action item 1",
            "confidence": 0.9,
            "entities": ["Supabase"]
        }}
    ],
    "facts": [
        {{
            "content": "A key fact extracted from the notes",
            "confidence": 0.85,
            "entities": ["EntityName"]
        }}
    ],
    "questions": [
        {{
            "question": "Question 1?",
            "confidence": 0.8,
            "entities": []
        }}
    ],
    "decisions": [
        {{
            "decision": "A decision that was made",
            "rationale": "Why this decision was made",
            "confidence": 0.8,
            "entities": []
        }}
    ],
    "risks": [
        {{
            "risk": "A potential risk identified",
            "severity": "high",
            "confidence": 0.75,
            "entities": []
        }}
    ],
    "entities": [
        {{
            "name": "Supabase",
            "entity_type": "technology"
        }}
    ],
    "concepts": [
        {{
            "concept": "A learned concept or insight",
            "confidence": 0.7,
            "entities": ["EntityName"]
        }}
    ]
}}
"""
    
    template = load_prompt(version, "00-gemini_extraction_prompt.txt", default=default_template)
    prompt = template.replace("{note_text}", note_text)
    prompt = prompt.replace("{related_notes_context}", related_context)
    prompt = prompt.replace("{structured_items_context}", structured_items_context)
    return prompt.strip()


def generate_related_notes_context(related_notes: list[dict[str, Any]]) -> str:
    """Format related notes for inclusion in the extraction prompt."""
    if not related_notes:
        return "No related past notes."
    
    lines = []
    for note in related_notes[:MAX_RELATED_NOTES_IN_CONTEXT]:
        summary = note.get("enriched_summary") or note.get("raw_text", "")
        if summary:
            lines.append(f"- {summary[:MAX_RELATED_NOTE_SUMMARY_LENGTH]}")
    
    return "\n".join(lines) if lines else "No related past notes."


@lru_cache(maxsize=4)
def _get_chat_llm(model_id: str, api_key: str) -> ChatGoogleGenerativeAI:
    """Process-wide singleton per model id — client construction has fixed
    overhead that shouldn't be paid on every chat request. Note: a cached
    client keeps using the api_key it was built with if GEMINI_API_KEY is
    rotated at runtime; restart the process after rotating keys.
    """
    return ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model_id,
        temperature=CHAT_ANSWER_GENERATION_TEMPERATURE,
        max_retries=CHAT_ANSWER_GENERATION_MAX_RETRIES,
        timeout=CHAT_ANSWER_GENERATION_TIMEOUT_SECONDS,
    )


def generate_chat_answer(prompt: str) -> str:
    """Generate the final chat answer text for a fully-built prompt."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set")

    model_id = os.getenv("CHAT_MODEL_ID", os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash"))
    model = _get_chat_llm(model_id, api_key)

    response = model.invoke([HumanMessage(content=prompt)])
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, str):
            return first.strip()
        if isinstance(first, dict) and isinstance(first.get("text"), str):
            return first["text"].strip()
    return str(content).strip()


class GeminiChatModel:
    """Concrete ChatModel implementation backed by Gemini."""

    def generate(self, prompt: str) -> str:
        return generate_chat_answer(prompt)


@lru_cache(maxsize=4)
def _get_period_summary_llm(model_id: str, api_key: str) -> ChatGoogleGenerativeAI:
    """Process-wide singleton per model id, mirroring ``_get_chat_llm``."""
    return ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model_id,
        temperature=PERIOD_SUMMARY_TEMPERATURE,
        max_retries=PERIOD_SUMMARY_MAX_RETRIES,
        timeout=PERIOD_SUMMARY_TIMEOUT_SECONDS,
    )


def generate_period_summary_narrative(prompt: str) -> str:
    """Generate a daily/weekly rollup narrative for a fully-built prompt."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set")

    model_id = os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
    model = _get_period_summary_llm(model_id, api_key)

    response = model.invoke([HumanMessage(content=prompt)])
    return extract_text_from_response(response).strip()


_DEFAULT_CHAT_MODEL: GeminiChatModel | None = None


def get_chat_model() -> GeminiChatModel:
    """Return the process-wide default ChatModel implementation."""
    global _DEFAULT_CHAT_MODEL
    if _DEFAULT_CHAT_MODEL is None:
        _DEFAULT_CHAT_MODEL = GeminiChatModel()
    return _DEFAULT_CHAT_MODEL
