from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from ...infrastructure.llm.prompt_logger import append_pipeline_log
from ..query_retrieval.services import retrieve_query_context
from ..routing.classifier import build_default_intent_classifier
from ..routing.contracts import GroundingSnapshot, RoutingContext, RoutingDecision, RoutingOutcome, RoutingPlanStep
from ..routing.orchestrator import RoutingOrchestrator, build_routing_orchestrator
from .guardrails import GroundingDecision, assess_grounding, format_grounding_context
from .memory import build_short_term_context
from .planner import build_chat_plan


@dataclass(slots=True)
class ChatRoutingConfig:
    retrieval_limit: int = 5


def build_chat_routing_orchestrator(config: ChatRoutingConfig | None = None) -> RoutingOrchestrator:
    config = config or ChatRoutingConfig()
    classifier = build_default_intent_classifier()

    def _retrieve_context(context: RoutingContext) -> dict[str, Any] | None:
        append_pipeline_log(
            "chat orchestrator",
            [
                "retrieval stage starting",
                f"thread: {context.thread_id or 'new'}",
                f"message: {shorten_text(context.message)}",
            ],
        )
        return retrieve_query_context(
            user_id=context.user_id,
            query=context.message,
            limit=config.retrieval_limit,
        )

    def _build_grounding(context: RoutingContext, knowledge_payload: dict[str, Any] | None) -> GroundingSnapshot:
        decision = assess_grounding(
            user_message=context.message,
            recent_messages=context.recent_messages,
            knowledge_payload=knowledge_payload,
            summary_memory=context.thread_summary or None,
        )
        return _snapshot_from_decision(decision)

    def _build_response(
        context: RoutingContext,
        decision: RoutingDecision,
        plan: list[RoutingPlanStep],
        knowledge_payload: dict[str, Any] | None,
        grounding: GroundingSnapshot,
    ) -> str:
        append_pipeline_log(
            "chat orchestrator",
            [
                "response generation starting",
                f"route: {decision.route}",
                f"grounding: {grounding.status}",
            ],
        )
        prompt = _build_chat_prompt(
            user_message=context.message,
            intent_payload=decision_to_payload(decision),
            plan=[_step_to_payload(step) for step in plan],
            summary_memory=context.thread_summary,
            short_term_context=build_short_term_context(context.recent_messages),
            knowledge_context=_format_knowledge_context(knowledge_payload),
            grounding_context=format_grounding_context(_decision_for_prompt(grounding)),
            tool_context="No tool results.",
        )
        try:
            answer = _generate_chat_answer(prompt)
        except Exception as exc:
            append_pipeline_log(
                "chat orchestrator",
                [
                    f"response generation failed: {exc}",
                ],
            )
            raise

        append_pipeline_log(
            "chat orchestrator",
            [
                "response generation succeeded",
                f"answer: {shorten_text(answer)}",
            ],
        )
        return answer

    return build_routing_orchestrator(
        classifier=classifier,
        plan_builder=build_chat_plan,
        retrieve_context=_retrieve_context,
        build_grounding=_build_grounding,
        build_response=_build_response,
    )


def decision_to_payload(decision: RoutingDecision) -> dict[str, Any]:
    return {
        "kind": decision.intent_kind,
        "confidence": decision.confidence,
        "needs_retrieval": decision.needs_retrieval,
        "needs_tools": decision.needs_tools,
        "direct_answer": decision.direct_answer,
        "reasons": list(decision.reasons),
    }


def _step_to_payload(step: RoutingPlanStep) -> dict[str, Any]:
    return {
        "name": step.name,
        "description": step.description,
        "enabled": step.enabled,
        "metadata": step.metadata,
    }


def _format_knowledge_context(candidate_payload: dict[str, Any] | None) -> str:
    if not candidate_payload:
        return "No knowledge memory retrieved."

    candidates = candidate_payload.get("candidates") or []
    if not candidates:
        return "No knowledge memory retrieved."

    lines: list[str] = []
    for candidate in candidates[:5]:
        note_id = str(candidate.get("note_id") or "").strip()
        summary = str(candidate.get("summary") or "").strip()
        text = str(candidate.get("text") or "").strip()
        excerpt = summary or text
        if not excerpt:
            continue
        lines.append(f"- [{note_id}] {excerpt[:240]}")

    return "\n".join(lines) if lines else "No knowledge memory retrieved."


def _build_chat_prompt(
    user_message: str,
    intent_payload: dict[str, Any],
    plan: list[dict[str, Any]],
    summary_memory: str | None,
    short_term_context: str,
    knowledge_context: str,
    grounding_context: str,
    tool_context: str,
) -> str:
    return f"""
You are NorthStar, an assistant for life and work memory.

Follow this workflow:
User Message -> Intent Detection -> Planner -> Retrieval/Tool Calls -> Merge Results -> Conversation Memory -> LLM -> Answer

Intent:
{json.dumps(intent_payload, indent=2)}

Plan:
{json.dumps(plan, indent=2)}

Conversation summary memory:
{summary_memory or "No summary memory yet."}

Short-term conversation memory:
{short_term_context}

Knowledge memory:
{knowledge_context}

Grounding guardrail:
{grounding_context}

Tool results:
{tool_context}

User message:
{user_message}

Answer rules:
- Be concise and helpful.
- Use knowledge memory when relevant.
- If the answer depends on unavailable tools, say so clearly.
- If you are unsure, ask one focused follow-up question.
""".strip()


def _generate_chat_answer(prompt: str) -> str:
    from langchain_core.messages import HumanMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

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


def _snapshot_from_decision(decision: GroundingDecision) -> GroundingSnapshot:
    return GroundingSnapshot(
        status=decision.status,
        confidence=decision.confidence,
        allow_answer=decision.allow_answer,
        top_claim=decision.top_claim,
        summary=decision.summary,
        source_refs=list(decision.source_refs),
        fallback_message=decision.fallback_message,
    )


def _decision_for_prompt(grounding: GroundingSnapshot) -> GroundingDecision:
    return GroundingDecision(
        status=grounding.status,
        confidence=grounding.confidence,
        allow_answer=grounding.allow_answer,
        top_claim=grounding.top_claim,
        summary=grounding.summary,
        source_refs=list(grounding.source_refs),
        fallback_message=grounding.fallback_message,
    )


def shorten_text(text: str, limit: int = 96) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."
