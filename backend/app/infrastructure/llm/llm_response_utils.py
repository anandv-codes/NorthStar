"""Shared LLM response parsing utilities."""
from typing import Any


def extract_text_from_response(response: Any) -> str:
    """Extract text content from Gemini or other LLM response objects.
    
    Handles nested lists, dicts, and objects with .content attributes.
    """
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

    raise RuntimeError(f"Unexpected LLM response type: {type(response)}")
