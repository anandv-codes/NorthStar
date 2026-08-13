from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ...infrastructure.llm.gemini_client import get_chat_model
from ...infrastructure.llm.prompt_logger import append_pipeline_log
from ...infrastructure.llm.prompt_loader import load_prompt
from ..ports import ChatModel
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


def build_chat_routing_orchestrator(
    config: ChatRoutingConfig | None = None, chat_model: ChatModel | None = None
) -> RoutingOrchestrator:
    config = config or ChatRoutingConfig()
    chat_model = chat_model or get_chat_model()
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
            answer = chat_model.generate(prompt)
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
    version = os.getenv("WORK_MEMORY_PROMPT_VERSION", "phase3-v1")
    default = """
You are NorthStar, an assistant for life and work memory.

Follow this workflow:
User Message -> Intent Detection -> Planner -> Retrieval/Tool Calls -> Merge Results -> Conversation Memory -> LLM -> Answer

Intent:
{intent_payload_json}

Plan:
{plan_json}

Conversation summary memory:
{summary_memory}

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
"""

    template = load_prompt(version, "02-chat_prompt.txt", default=default)
    prompt = template.replace("{intent_payload_json}", json.dumps(intent_payload, indent=2))
    prompt = prompt.replace("{plan_json}", json.dumps(plan, indent=2))
    prompt = prompt.replace("{summary_memory}", summary_memory or "No summary memory yet.")
    prompt = prompt.replace("{short_term_context}", short_term_context)
    prompt = prompt.replace("{knowledge_context}", knowledge_context)
    prompt = prompt.replace("{grounding_context}", grounding_context)
    prompt = prompt.replace("{tool_context}", tool_context)
    prompt = prompt.replace("{user_message}", user_message)
    return prompt.strip()


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
