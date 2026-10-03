from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from ...infrastructure.llm.prompt_logger import append_pipeline_log, elapsed_ms
from .base import BaseIntentClassifier
from .contracts import IntentContext, IntentDecision, RouteKind
from ..chat.routing_contracts import (
    GroundingSnapshot,
    RoutingContext,
    RoutingDecision,
    RoutingOutcome,
    RoutingPlanStep,
)


PlanBuilder = Callable[[IntentDecision], list[RoutingPlanStep]]
RetrievalRunner = Callable[[RoutingContext], dict[str, Any] | None]
GroundingRunner = Callable[[RoutingContext, dict[str, Any] | None], GroundingSnapshot]
ResponseRunner = Callable[
    [RoutingContext, RoutingDecision, Sequence[RoutingPlanStep], dict[str, Any] | None, GroundingSnapshot],
    str,
]


@dataclass(slots=True)
class RoutingDependencies:
    classifier: BaseIntentClassifier
    plan_builder: PlanBuilder
    retrieve_context: RetrievalRunner
    build_grounding: GroundingRunner
    build_response: ResponseRunner


@dataclass(slots=True)
class RoutingOrchestrator:
    dependencies: RoutingDependencies

    def route(self, context: RoutingContext) -> RoutingOutcome:
        request_start = time.perf_counter()
        append_pipeline_log(
            "routing orchestrator",
            [
                "route planning started",
                f"surface: chat",
                f"thread: {context.thread_id or 'new'}",
            ],
        )
        stage_start = time.perf_counter()
        intent = self.dependencies.classifier.classify(
            IntentContext(
                surface="chat",
                message=context.message,
                recent_messages=list(context.recent_messages),
                thread_summary=context.thread_summary,
            )
        )
        plan = self.dependencies.plan_builder(intent)
        context.plan = plan
        append_pipeline_log(
            "routing orchestrator",
            [
                f"plan built with {len(plan)} step(s)",
                f"intent: {intent.kind}",
                f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
            ],
        )

        knowledge_payload = None
        knowledge_error: str | None = None
        if intent.needs_retrieval:
            stage_start = time.perf_counter()
            try:
                knowledge_payload = self.dependencies.retrieve_context(context)
            except RuntimeError as exc:
                knowledge_error = str(exc)
                append_pipeline_log(
                    "routing orchestrator",
                    [
                        f"retrieval failed: {knowledge_error}",
                        f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
                    ],
                )
            else:
                candidate_count = len((knowledge_payload or {}).get("candidates") or [])
                append_pipeline_log(
                    "routing orchestrator",
                    [
                        f"retrieval completed with {candidate_count} candidate(s)",
                        f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
                    ],
                )
        else:
            append_pipeline_log(
                "routing orchestrator",
                [
                    "retrieval skipped",
                ],
            )
        context.knowledge_payload = knowledge_payload

        stage_start = time.perf_counter()
        grounding = self.dependencies.build_grounding(context, knowledge_payload)
        context.grounding = grounding
        append_pipeline_log(
            "routing orchestrator",
            [
                f"grounding status: {grounding.status}",
                f"allow answer: {grounding.allow_answer}",
                f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
            ],
        )

        route = self._resolve_route(intent, grounding)
        decision = RoutingDecision(
            route=route,
            intent_kind=intent.kind,
            confidence=self._route_confidence(intent.confidence, grounding.confidence),
            needs_retrieval=intent.needs_retrieval,
            needs_tools=intent.needs_tools,
            direct_answer=intent.direct_answer,
            allow_answer=grounding.allow_answer,
            reasons=list(intent.reasons),
            source_refs=list(grounding.source_refs),
            fallback_message=grounding.fallback_message,
        )
        append_pipeline_log(
            "routing orchestrator",
            [
                f"route decided as {route}",
                f"confidence: {decision.confidence:.2f}",
            ],
        )

        assistant_message = grounding.fallback_message
        if grounding.allow_answer:
            stage_start = time.perf_counter()
            try:
                assistant_message = self.dependencies.build_response(
                    context,
                    decision,
                    plan,
                    knowledge_payload,
                    grounding,
                )
            except Exception as exc:
                append_pipeline_log(
                    "routing orchestrator",
                    [
                        f"response generation failed: {exc}",
                        f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
                    ],
                )
                raise
            append_pipeline_log(
                "routing orchestrator",
                [
                    "response generation succeeded",
                    f"answer: {shorten_text(assistant_message)}",
                    f"elapsed_ms: {elapsed_ms(stage_start):.1f}",
                ],
            )
        else:
            append_pipeline_log(
                "routing orchestrator",
                [
                    "answer withheld by grounding",
                    f"fallback: {shorten_text(assistant_message or '')}",
                ],
            )

        append_pipeline_log(
            "routing orchestrator",
            [f"total_elapsed_ms: {elapsed_ms(request_start):.1f}"],
        )

        return RoutingOutcome(
            decision=decision,
            context=context,
            assistant_message=assistant_message,
            metadata={
                "intent": {
                    "kind": intent.kind,
                    "confidence": intent.confidence,
                    "needs_retrieval": intent.needs_retrieval,
                    "needs_tools": intent.needs_tools,
                    "direct_answer": intent.direct_answer,
                    "reasons": list(intent.reasons),
                },
                "route": route,
                "plan": [
                    {
                        "name": step.name,
                        "description": step.description,
                        "enabled": step.enabled,
                        "metadata": step.metadata,
                    }
                    for step in plan
                ],
                "grounding": {
                    "status": grounding.status,
                    "confidence": grounding.confidence,
                    "allow_answer": grounding.allow_answer,
                    "top_claim": grounding.top_claim,
                    "summary": grounding.summary,
                    "source_refs": list(grounding.source_refs),
                    "fallback_message": grounding.fallback_message,
                },
                "knowledge_present": knowledge_payload is not None,
                "knowledge_error": knowledge_error,
            },
        )

    def _resolve_route(self, intent: IntentDecision, grounding: GroundingSnapshot) -> RouteKind:
        if not grounding.allow_answer:
            return "abstain"
        if intent.needs_retrieval and intent.needs_tools:
            return "mixed"
        if intent.needs_retrieval:
            return "retrieval"
        if intent.needs_tools:
            return "tool"
        return "direct"

    def _route_confidence(self, intent_confidence: float, grounding_confidence: float) -> float:
        combined = (intent_confidence * 0.4) + (grounding_confidence * 0.6)
        return round(min(max(combined, 0.0), 1.0), 3)


def shorten_text(text: str, limit: int = 96) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."


def build_routing_orchestrator(
    classifier: BaseIntentClassifier,
    plan_builder: PlanBuilder,
    retrieve_context: RetrievalRunner,
    build_grounding: GroundingRunner,
    build_response: ResponseRunner,
) -> RoutingOrchestrator:
    return RoutingOrchestrator(
        dependencies=RoutingDependencies(
            classifier=classifier,
            plan_builder=plan_builder,
            retrieve_context=retrieve_context,
            build_grounding=build_grounding,
            build_response=build_response,
        )
    )
