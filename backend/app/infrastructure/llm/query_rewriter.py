import json
import os
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from .prompt_logger import append_pipeline_log
from .prompt_loader import load_prompt
from ...schemas.models import QueryRewriteResponse


MIN_QUERY_REWRITE_CONFIDENCE = float(os.getenv("QUERY_REWRITE_MIN_CONFIDENCE", "0.55"))


def build_recent_memory_context(recent_memory: dict[str, list[dict[str, Any]]] | None) -> str:
    if not recent_memory:
        return "No recent memory context available."

    sections: list[str] = []
    section_map = {
        "notes": ("Notes", "enriched_summary", "raw_text"),
        "decisions": ("Decisions", "decision", "rationale"),
        "tasks": ("Tasks", "description", "status"),
        "questions": ("Questions", "question", "status"),
        "risks": ("Risks", "risk", "severity"),
        "concepts": ("Concepts", "concept", "status"),
    }

    for key, (title, primary_field, secondary_field) in section_map.items():
        items = (recent_memory.get(key) or [])[:3]
        if not items:
            continue

        lines: list[str] = []
        for item in items:
            primary_value = str(item.get(primary_field) or "").strip()
            if not primary_value and secondary_field:
                primary_value = str(item.get(secondary_field) or "").strip()
            if not primary_value:
                continue
            lines.append(f"- {primary_value}")

        if lines:
            sections.append(f"{title}:\n" + "\n".join(lines))

    return "\n\n".join(sections) if sections else "No recent memory context available."


def rewrite_query_with_llm(
    user_query: str,
    recent_memory: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        append_pipeline_log(
            "query rewrite",
            [
                "planning rewrite",
                "rewrite aborted: missing GEMINI_API_KEY",
            ],
        )
        raise RuntimeError("GEMINI_API_KEY must be set")

    model_id = os.getenv("QUERY_REWRITE_MODEL_ID", os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash"))
    append_pipeline_log(
        "query rewrite",
        [
            "planning rewrite",
            f"model: {model_id}",
            f"query: {shorten_text(user_query)}",
        ],
    )
    model = ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model_id,
        temperature=0.1,
        max_retries=2,
        timeout=60,
    )

    prompt = generate_rewrite_prompt(user_query=user_query, recent_memory=recent_memory)
    try:
        response = model.invoke([HumanMessage(content=prompt)])
        output_text = extract_text_from_response(response)
        parsed = parse_query_rewrite_response(output_text)
    except Exception as exc:
        append_pipeline_log(
            "query rewrite",
            [
                f"rewrite failed: {exc}",
            ],
        )
        raise

    append_pipeline_log(
        "query rewrite",
        [
            "rewrite succeeded",
            f"rewritten query: {shorten_text(parsed.get('rewritten_query') or '')}",
            f"confidence: {float(parsed.get('confidence') or 0.0):.2f}",
            f"risk flags: {parsed.get('risk_flags') or []}",
        ],
    )
    return parsed


def generate_rewrite_prompt(
    user_query: str,
    recent_memory: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    memory_context = build_recent_memory_context(recent_memory)
        version = os.getenv("WORK_MEMORY_PROMPT_VERSION", "phase3-v1")
        default = """
You rewrite retrieval queries for a note/memory search system.

Original user query:
{user_query}

Recent memory context:
{memory_context}

Return JSON only with this exact structure:
{
    "rewritten_query": "A concise search-friendly query",
    "likely_answer": "A short plausible answer or resolution the user is probably referring to",
    "confidence": 0.0,
    "risk_flags": ["missing_number", "negation_lost", "entity_conflict", "too_broad", "low_context"]
}

Rules:
- Preserve exact numbers, IDs, names, dates, and negations.
- Do not invent facts.
- If the query is already specific, keep the rewrite close to the original.
- Use the recent memory context only as disambiguating context.
- If the query is too vague to rewrite safely, keep rewritten_query close to the original and lower confidence.
"""

        template = load_prompt(version, "01-query_rewrite_prompt.txt", default=default)
        prompt = template.replace("{user_query}", user_query)
        prompt = prompt.replace("{memory_context}", memory_context)
        return prompt.strip()


def parse_query_rewrite_response(output_text: str) -> dict[str, Any]:
    if not output_text or not output_text.strip():
        raise RuntimeError("Query rewrite model returned empty output")

    cleaned = clean_markdown_json(output_text)
    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Query rewrite model output was not valid JSON. Response:\n"
            + cleaned[:1024]
        ) from exc

    if not isinstance(raw, dict):
        raise RuntimeError(f"Query rewrite response must be a JSON object, got {type(raw)}")

    normalized = {
        "rewritten_query": str(raw.get("rewritten_query") or "").strip(),
        "likely_answer": str(raw.get("likely_answer") or "").strip(),
        "confidence": raw.get("confidence", 0.0),
        "risk_flags": raw.get("risk_flags") or [],
    }

    parsed = QueryRewriteResponse.model_validate(normalized)
    return parsed.model_dump(mode="json")


class GeminiQueryRewriter:
    """Concrete ``QueryRewriter`` implementation backed by Gemini."""

    def rewrite(
        self,
        user_query: str,
        recent_memory: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        return rewrite_query_with_llm(user_query=user_query, recent_memory=recent_memory)


_DEFAULT_QUERY_REWRITER: GeminiQueryRewriter | None = None


def get_query_rewriter() -> GeminiQueryRewriter:
    """Return the process-wide default ``QueryRewriter`` implementation."""
    global _DEFAULT_QUERY_REWRITER
    if _DEFAULT_QUERY_REWRITER is None:
        _DEFAULT_QUERY_REWRITER = GeminiQueryRewriter()
    return _DEFAULT_QUERY_REWRITER




def extract_text_from_response(response: Any) -> str:
    if isinstance(response, str):
        return response

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

    raise RuntimeError(f"Unexpected query rewrite response type: {type(response)}")


def clean_markdown_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    if text.startswith("json"):
        text = text[len("json"):].strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[len("```json"):-3].strip()
    return text


def shorten_text(text: str, limit: int = 96) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."
