import os
import json
import re
from typing import Any
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ...schemas.models import WorkMemoryExtraction
from .prompt_logger import log_gemini_interaction
from .prompt_loader import load_prompt

def call_gemini_api(note_text: str, related_notes: list[dict[str, Any]] | None = None) -> dict:


    parse_result = parse_note_text(note_text)
    prompt = generate_gemini_prompt(parse_result, related_notes=related_notes or [])
    output_text = invoke_gemini(prompt)
    print(f"Gemini raw output: {output_text[:500]}")
    parsed_response = None
    parse_error = None
    try:
        parsed_response = parse_gemini_response(output_text)
        return parsed_response
    except Exception as exc:
        parse_error = str(exc)
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
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set")

    model_id = os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
    print(f"prompt_text={prompt_text}")
    model = ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model_id,
        temperature=0.2,
        max_retries=3,
        timeout=120,
    )

    response = model.invoke([HumanMessage(content=prompt_text)])
    print(f"Gemini response object: {response}")
    return extract_text_from_response(response)


def extract_text_from_response(response) -> str:
    if isinstance(response, str):
        return response

    if isinstance(response, list) and response:
        return extract_text_from_response(response[0])

    if hasattr(response, "content"):
        content = response.content
        if isinstance(content, str):
            return content
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                text = first.get("text")
                if isinstance(text, str):
                    return text
            if isinstance(first, str):
                return first

    if isinstance(response, dict):
        if "content" in response:
            return extract_text_from_response(response["content"])
        if "text" in response and isinstance(response["text"], str):
            return response["text"]
        if "candidates" in response and response["candidates"]:
            return extract_text_from_response(response["candidates"][0])

    raise RuntimeError(f"Unexpected Gemini response type: {type(response)}")


def parse_gemini_response(output_text: str) -> dict:
    if not output_text or not output_text.strip():
        raise RuntimeError("Gemini returned empty output")

    cleaned = clean_markdown_json(output_text)
    try:
        raw = json.loads(cleaned)
        return normalize_work_memory_output(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Gemini output was not valid JSON. Response:\n"
            + cleaned[:1024]
        ) from exc


def generate_chat_answer(prompt: str) -> str:
    """Generate the final chat answer text for a fully-built prompt."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set")

    model_id = os.getenv("CHAT_MODEL_ID", os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash"))
    model = ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model_id,
        temperature=0.2,
        max_retries=2,
        timeout=90,
    )

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
    """Concrete ``ChatModel`` implementation backed by Gemini."""

    def generate(self, prompt: str) -> str:
        return generate_chat_answer(prompt)


_DEFAULT_CHAT_MODEL: GeminiChatModel | None = None


def get_chat_model() -> GeminiChatModel:
    """Return the process-wide default ``ChatModel`` implementation."""
    global _DEFAULT_CHAT_MODEL
    if _DEFAULT_CHAT_MODEL is None:
        _DEFAULT_CHAT_MODEL = GeminiChatModel()
    return _DEFAULT_CHAT_MODEL

        related_context = generate_related_notes_context(related_notes or [])
        version = os.getenv("WORK_MEMORY_PROMPT_VERSION", "phase3-v1")
        # Try to load the versioned prompt template; fall back to the original inline template
        default = """
    You are an assistant that processes work notes and extracts structured memory.

    Raw notes:
    {normalized_text}

    Related past notes for cross-reference:
    {related_notes_context}

    Action items identified:
    {action_items_json}

    Questions identified:
    {questions_json}

    Please provide the following:
    1. A concise summary of the notes.
    2. Extract typed memory items as tasks, facts, questions, decisions, risks, and entities.
    3. For each extracted item, include confidence when possible.
    4. Include only items grounded in the note or clearly supported by related notes.
    5. If related past notes are relevant, use them only as context and do not invent unsupported facts.

    Format your response as JSON with the following structure:
    {
        "summary": "Concise summary here",
        "tasks": [
            {
                "description": "Action item 1",
                "confidence": 0.9,
                "entities": ["Supabase"]
            }
        ],
        "facts": [
            {
                "content": "A key fact extracted from the notes",
                "confidence": 0.85,
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
                "entities": ["EntityName"]
            }
        ]
    }
    """

        template = load_prompt(version, "00-gemini_extraction_prompt.txt", default=default)
        # Replace only the specific placeholders we intend to populate.
        prompt = template.replace("{normalized_text}", parsed_text.get("normalized_text", ""))
        prompt = prompt.replace("{related_notes_context}", related_context)
        prompt = prompt.replace("{action_items_json}", json.dumps(parsed_text.get("action_items", []), indent=2))
        prompt = prompt.replace("{questions_json}", json.dumps(parsed_text.get("questions", []), indent=2))
        return prompt
    return "\n".join(lines)


def generate_gemini_prompt(
    parsed_text: dict,
    related_notes: list[dict[str, Any]] | None = None,
) -> str:
    related_context = generate_related_notes_context(related_notes or [])
    return f"""
You are an assistant that processes work notes and extracts structured memory.

Raw notes:
{parsed_text['normalized_text']}

Related past notes for cross-reference:
{related_context}

Action items identified:
{json.dumps(parsed_text['action_items'], indent=2)}

Questions identified:
{json.dumps(parsed_text['questions'], indent=2)}

Please provide the following:
1. A concise summary of the notes.
2. Extract typed memory items as tasks, facts, questions, decisions, risks, and entities.
3. For each extracted item, include confidence when possible.
4. Include only items grounded in the note or clearly supported by related notes.
5. If related past notes are relevant, use them only as context and do not invent unsupported facts.

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
    
        {
            "concept": "A learned concept or insight",
            "confidence": 0.7,
            "entities": ["EntityName"]
        }
    ]
}}
"""
