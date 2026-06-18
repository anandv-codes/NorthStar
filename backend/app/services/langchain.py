import os
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Any
from langchain_core.messages import HumanMessage

def call_gemini_api(note_text: str, related_notes: list[dict[str, Any]] | None = None) -> dict:
    parse_result = parse_note_text(note_text)
    prompt = generate_gemini_prompt(parse_result, related_notes=related_notes or [])
    output_text = invoke_gemini(prompt)
    print(f"Gemini raw output: {output_text[:500]}")
    return parse_gemini_response(output_text)

def invoke_gemini(prompt_text: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set")

    model_id = os.getenv("GEMINI_MODEL_ID", "gemini-3.5-flash")

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
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Gemini output was not valid JSON. Response:\n"
            + cleaned[:1024]
        ) from exc


def clean_markdown_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    if text.startswith("json"):
        text = text[len("json"):].strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[len("```json"): -3].strip()
    return text

def parse_note_text(raw_text: str) -> dict:
    text = str(raw_text)
    action_items = []
    questions = []
    stripped_lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized_text = "\n".join(stripped_lines)

    for line in stripped_lines:
        lower = line.lower()
        if re.search(r"\b(todo|action item|follow up|next step | reminder | remind)\b", lower):
            action_items.append(line)
        if line.strip().endswith("?"):
            questions.append(line)

    return {
        "normalized_text": normalized_text,
        "action_items": action_items,
        "questions": questions,
    }

def generate_related_notes_context(related_notes: list[dict[str, Any]]) -> str:
    if not related_notes:
        return "No related past notes were retrieved."

    lines = []
    for index, note in enumerate(related_notes, start=1):
        lines.append(
            "\n".join(
                [
                    f"{index}. note_id: {note.get('note_id', 'unknown')}",
                    f"   text: {note.get('text', '')}",
                    f"   summary: {note.get('summary', '')}",
                ]
            )
        )
    return "\n".join(lines)


def generate_gemini_prompt(
    parsed_text: dict,
    related_notes: list[dict[str, Any]] | None = None,
) -> str:
    related_context = generate_related_notes_context(related_notes or [])
    return f"""
You are an assistant that processes daily journal notes and extracts key information.

Raw notes:
{parsed_text['normalized_text']}

Related past notes for cross-reference:
{related_context}

Action items identified:
{json.dumps(parsed_text['action_items'], indent=2)}

Questions identified:
{json.dumps(parsed_text['questions'], indent=2)}

Please provide the following:
1. A concise summary of the notes (max 250 characters).
2. Expand on the list of action items mentioned in the notes (the provided action items are not foolproof).
3. Answer the questions that arise from the notes.
4. Any insights or observations (max 2) that can be drawn from the notes.
5. If related past notes are relevant, mention the connection briefly in the insights.

Format your response as JSON with the following structure:
{{
    "summary": "Concise summary here",
    "action_items": ["Action item 1", "Action item 2"],
    "questions": ["Question 1?", "Question 2?"],
    "insights": ["Insight 1", "Insight 2"]
}}
"""
