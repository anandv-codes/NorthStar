"""Resolves whether the user's latest chat message is an explicit request to
run one of the registered tools (create/complete a task, etc.), using the
LLM's native tool/function-calling rather than freeform text parsing.

This is only invoked when the cheap keyword-based intent classifier already
flagged ``needs_tools`` — keeps the extra LLM round-trip off the hot path for
ordinary messages.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from ...infrastructure.llm.llm_config import (
    TOOL_CALL_MAX_RETRIES,
    TOOL_CALL_TEMPERATURE,
    TOOL_CALL_TIMEOUT_SECONDS,
)
from .tools import TOOL_REGISTRY, build_tool_context

SYSTEM_PROMPT_TEMPLATE = """You decide whether the user's latest message is an explicit, unambiguous \
request to create or update one work-memory item (a task, question, risk, or concept).

Rules:
- Only call a tool if the request is clear. If it's vague, conversational, or just a question, do not call any tool.
- For "complete/answer/resolve/mark learned" actions you MUST copy the id from the matching list below \
exactly as shown — never invent or guess an id. If no listed item clearly matches what the user means, do not call a tool.
- Call at most one tool.

{tool_context}
"""


@dataclass(slots=True)
class ToolCallProposal:
    tool_name: str
    args: dict[str, Any]
    description: str
    confirmed_message: str


@lru_cache(maxsize=4)
def _get_tool_calling_llm(model_id: str, api_key: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model_id,
        temperature=TOOL_CALL_TEMPERATURE,
        max_retries=TOOL_CALL_MAX_RETRIES,
        timeout=TOOL_CALL_TIMEOUT_SECONDS,
    )


def resolve_tool_call(user_id: str, message: str) -> ToolCallProposal | None:
    """Return a proposed tool call for ``message``, or ``None`` if nothing clearly matched."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be set")

    model_id = os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
    llm = _get_tool_calling_llm(model_id, api_key)
    bound_llm = llm.bind_tools([definition.args_schema for definition in TOOL_REGISTRY.values()])

    tool_context, item_lookup = build_tool_context(user_id)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tool_context=tool_context)

    response = bound_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=message)])
    tool_calls = getattr(response, "tool_calls", None) or []
    if not tool_calls:
        return None

    call = tool_calls[0]
    tool_name = str(call.get("name") or "")
    raw_args = call.get("args") or {}
    definition = TOOL_REGISTRY.get(tool_name)
    if not definition:
        return None

    try:
        validated_args = definition.args_schema(**raw_args)
    except ValidationError:
        return None

    return ToolCallProposal(
        tool_name=tool_name,
        args=validated_args.model_dump(),
        description=definition.describe(validated_args, item_lookup),
        confirmed_message=definition.confirmed_message(validated_args, item_lookup),
    )


def execute_tool_call(user_id: str, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a previously-confirmed tool call. Re-validates args before running."""
    definition = TOOL_REGISTRY.get(tool_name)
    if not definition:
        raise ValueError(f"Unknown tool: {tool_name}")
    validated_args = definition.args_schema(**args)
    return definition.executor(user_id, validated_args)
