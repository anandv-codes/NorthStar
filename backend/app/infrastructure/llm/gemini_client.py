"""Gemini API client for work memory extraction."""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

from functools import lru_cache

# Fallback when GEMINI_MODEL_ID is unset. Keep this in sync with the value in
# backend/.env. ``gemini-2.5-flash`` is not available to new API keys (404
# NOT_FOUND), ``gemini-2.5-flash-lite`` is capped at 20 requests/day on the free
# tier, and ``gemini-3.1-flash-lite`` returns 503 under load; 3.5-flash-lite is
# the youngest lite model that answered reliably in testing (~1-2s/call).
DEFAULT_GEMINI_MODEL_ID = "gemini-3.5-flash-lite"

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser

from ...schemas.models import WorkMemoryExtraction
from .prompt_logger import log_gemini_interaction
from .prompt_render import build_extraction_prompt
from .llm_response_utils import extract_text_from_response
from .llm_config import (
    WORK_MEMORY_EXTRACTION_TEMPERATURE,
    WORK_MEMORY_EXTRACTION_MAX_RETRIES,
    WORK_MEMORY_EXTRACTION_TIMEOUT_SECONDS,
    CHAT_ANSWER_GENERATION_TEMPERATURE,
    CHAT_ANSWER_GENERATION_MAX_RETRIES,
    CHAT_ANSWER_GENERATION_TIMEOUT_SECONDS,
    MAX_RELATED_NOTES_IN_CONTEXT,
    MAX_RELATED_NOTE_SUMMARY_LENGTH,
    PERIOD_SUMMARY_TEMPERATURE,
    PERIOD_SUMMARY_MAX_RETRIES,
    PERIOD_SUMMARY_TIMEOUT_SECONDS,
)


def call_gemini_api(
    note_text: str,
    related_notes: list[dict[str, Any]] | None = None,
    commitments: list[dict[str, Any]] | None = None,
) -> dict:
    """Extract structured memory from note text using Gemini."""
    prompt = generate_gemini_prompt(
        note_text,
        related_notes=related_notes or [],
        commitments=commitments or [],
    )
    output_text = invoke_gemini(prompt)

    parsed_response = None
    parse_error = None
    try:
        parsed_response = parse_gemini_response(output_text)
        logger.info(
            "Gemini extraction parsed: tasks=%d facts=%d questions=%d decisions=%d risks=%d concepts=%d contributions=%d",
            len(parsed_response.get("tasks", [])),
            len(parsed_response.get("facts", [])),
            len(parsed_response.get("questions", [])),
            len(parsed_response.get("decisions", [])),
            len(parsed_response.get("risks", [])),
            len(parsed_response.get("concepts", [])),
            len(parsed_response.get("commitment_contributions", [])),
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


@lru_cache(maxsize=4)
def _get_extraction_llm(model_id: str, api_key: str) -> ChatGoogleGenerativeAI:
    """Process-wide singleton per model id for note extraction.

    Building ``ChatGoogleGenerativeAI`` costs several hundred ms; without this
    cache every note paid that cost again inside the request.
    """
    return ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model_id,
        temperature=WORK_MEMORY_EXTRACTION_TEMPERATURE,
        max_retries=WORK_MEMORY_EXTRACTION_MAX_RETRIES,
        timeout=WORK_MEMORY_EXTRACTION_TIMEOUT_SECONDS,
    )


def invoke_gemini(prompt_text: str) -> str:
    """Call Gemini API with the given prompt."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set")

    model_id = os.getenv("GEMINI_MODEL_ID", DEFAULT_GEMINI_MODEL_ID)
    model = _get_extraction_llm(model_id, api_key)

    logger.info(f"Calling Gemini ({model_id}), prompt_chars={len(prompt_text)}")
    response = model.invoke([HumanMessage(content=prompt_text)])
    return extract_text_from_response(response)


def parse_gemini_response(output_text: str) -> dict:
    """Parse and validate Gemini JSON output as ``WorkMemoryExtraction``.

    ``JsonOutputParser`` only parses; it does not enforce the Pydantic schema.
    Validation here turns a malformed extraction into a clear failure instead
    of a ``KeyError`` deeper in the worker.
    """
    if not output_text or not output_text.strip():
        raise RuntimeError("Gemini returned empty output")

    parser = JsonOutputParser(pydantic_object=WorkMemoryExtraction)
    parsed = parser.invoke(output_text)
    return WorkMemoryExtraction.model_validate(parsed).model_dump(mode="json")


def generate_gemini_prompt(
    note_text: str,
    related_notes: list[dict[str, Any]] | None = None,
    commitments: list[dict[str, Any]] | None = None,
) -> str:
    """Generate the extraction prompt with note text, related notes, and goals."""
    related_context = generate_related_notes_context(related_notes or [])

    return build_extraction_prompt(
        note_text=note_text,
        related_notes_context=related_context,
        commitments=commitments or [],
        version=os.getenv("WORK_MEMORY_PROMPT_VERSION"),
    )


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

    model_id = os.getenv("CHAT_MODEL_ID", os.getenv("GEMINI_MODEL_ID", DEFAULT_GEMINI_MODEL_ID))
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

    model_id = os.getenv("GEMINI_MODEL_ID", DEFAULT_GEMINI_MODEL_ID)
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


def warm_up_llm_clients() -> None:
    """Construct the cached Gemini clients ahead of the first request.

    Called from the FastAPI lifespan. Client construction is a fixed cost
    (imports + TLS setup) that otherwise lands on the first note/chat request.
    No API call is made here, so it costs no quota.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set")

    extraction_model_id = os.getenv("GEMINI_MODEL_ID", DEFAULT_GEMINI_MODEL_ID)
    chat_model_id = os.getenv("CHAT_MODEL_ID", extraction_model_id)
    _get_extraction_llm(extraction_model_id, api_key)
    _get_chat_llm(chat_model_id, api_key)
    _get_period_summary_llm(extraction_model_id, api_key)
