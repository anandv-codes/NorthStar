"""Intent routing and notes-only grounding tests."""
from __future__ import annotations

from typing import Sequence

from backend.app.domain.chat.guardrails import assess_grounding
from backend.app.domain.chat.planner import build_chat_plan
from backend.app.domain.chat.routing_contracts import (
    GroundingSnapshot,
    RoutingContext,
    RoutingOutcome,
)
from backend.app.domain.routing.base import BaseIntentClassifier
from backend.app.domain.routing.classifier import HybridIntentClassifier
from backend.app.domain.routing.contracts import IntentContext, IntentDecision
from backend.app.domain.routing.embedding_intent import (
    LocalSemanticIntentClassifier,
    SemanticIntentMatch,
)
from backend.app.domain.routing.intent_examples import INTENT_EXAMPLES
from backend.app.domain.routing.orchestrator import build_routing_orchestrator
from backend.app.domain.routing.rules import (
    build_conversation_rule,
    build_read_tool_rule,
    build_retrieval_rule,
    build_status_rule,
    build_tool_rule,
)


class FakeSemanticClassifier:
    def __init__(self, match: SemanticIntentMatch | None = None) -> None:
        self.match = match
        self.messages: list[str] = []

    def classify(self, message: str) -> SemanticIntentMatch | None:
        self.messages.append(message)
        return self.match


class StaticClassifier(BaseIntentClassifier):
    def __init__(self, decision: IntentDecision) -> None:
        self.decision = decision

    def classify(self, context: IntentContext) -> IntentDecision:
        return self.decision


def _classifier(semantic: FakeSemanticClassifier | None = None) -> HybridIntentClassifier:
    return HybridIntentClassifier(
        rules=(
            build_tool_rule(),
            build_read_tool_rule(),
            build_status_rule(),
            build_retrieval_rule(),
            build_conversation_rule(),
        ),
        semantic_classifier=semantic,
    )


def _classify(message: str, semantic: FakeSemanticClassifier | None = None) -> IntentDecision:
    return _classifier(semantic).classify(IntentContext(surface="chat", message=message))


def test_seed_examples_are_unique_and_cover_labels() -> None:
    assert set(INTENT_EXAMPLES) == {"conversation", "note_content", "note_status", "action"}
    seen: set[str] = set()
    for examples in INTENT_EXAMPLES.values():
        assert examples
        for example in examples:
            assert example not in seen
            seen.add(example)


def test_exact_greeting_routes_to_conversation_without_grounding() -> None:
    decision = _classify("hi")

    assert decision.kind == "conversation"
    assert decision.needs_retrieval is False
    assert decision.grounding_mode == "none"


def test_status_question_uses_claim_grounding() -> None:
    decision = _classify("what tasks are pending")

    assert decision.kind == "note_status"
    assert decision.needs_retrieval is True
    assert decision.grounding_mode == "claim"


def test_finish_question_uses_claim_grounding() -> None:
    decision = _classify("did I finish the onboarding task")

    assert decision.kind == "note_status"
    assert decision.grounding_mode == "claim"


def test_content_question_uses_relevance_grounding() -> None:
    decision = _classify("what did I decide about auth")

    assert decision.kind == "note_content"
    assert decision.needs_retrieval is True
    assert decision.grounding_mode == "relevance"


def test_summary_request_prefers_content_even_with_status_words() -> None:
    decision = _classify("summarize my completed tasks")

    assert decision.kind == "note_content"
    assert decision.grounding_mode == "relevance"


def test_action_request_routes_to_tool() -> None:
    decision = _classify("mark datafix 42 as done")

    assert decision.kind == "action"
    assert decision.needs_tools is True
    assert decision.grounding_mode == "none"


def test_action_phrase_inside_a_status_question_is_not_a_write() -> None:
    decision = _classify("did I close the auth item")

    assert decision.kind == "note_status"
    assert decision.needs_tools is False


def test_start_task_request_routes_to_tool() -> None:
    decision = _classify("start the hiring task")

    assert decision.kind == "action"
    assert decision.needs_tools is True


def test_open_loops_request_routes_to_read_tool() -> None:
    decision = _classify("what am I forgetting")

    assert decision.kind == "tool_read"
    assert decision.tool_name == "get_open_loops"
    assert decision.needs_tools is True
    assert decision.needs_retrieval is False
    assert decision.grounding_mode == "none"


def test_due_cards_request_routes_to_read_tool() -> None:
    decision = _classify("what should I review today?")

    assert decision.kind == "tool_read"
    assert decision.tool_name == "get_due_cards"
    assert decision.needs_tools is True


def test_status_question_about_due_cards_is_not_a_read_tool() -> None:
    decision = _classify("did I finish my due cards")

    assert decision.kind == "note_status"
    assert decision.tool_name is None


def test_unrelated_message_is_ambiguous() -> None:
    decision = _classify("calculate 2+2")

    assert decision.kind == "ambiguous"
    assert decision.needs_retrieval is False
    assert decision.grounding_mode == "none"


def test_semantic_match_routes_paraphrase_without_rule_hit() -> None:
    semantic = FakeSemanticClassifier(
        SemanticIntentMatch(
            label="note_content",
            confidence=0.71,
            margin=0.12,
            scores={"note_content": 0.71, "note_status": 0.59, "conversation": 0.2},
        )
    )

    decision = _classify("any news on the rollout", semantic)

    assert decision.kind == "note_content"
    assert decision.grounding_mode == "relevance"
    assert semantic.messages == ["any news on the rollout"]


def test_semantic_conversation_does_not_override_note_rule() -> None:
    semantic = FakeSemanticClassifier(
        SemanticIntentMatch(
            label="conversation",
            confidence=0.8,
            margin=0.2,
            scores={"conversation": 0.8, "note_content": 0.6, "note_status": 0.5},
        )
    )

    decision = _classify("what did I decide about auth", semantic)

    assert decision.kind == "note_content"


def test_local_semantic_knn_separates_labels_with_injected_embedder() -> None:
    def embed(texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            lowered = text.lower()
            if "hello" in lowered or "hi" in lowered:
                vectors.append([1.0, 0.0, 0.0])
            elif "done" in lowered or "status" in lowered:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors

    classifier = LocalSemanticIntentClassifier(
        examples={
            "conversation": ("hello",),
            "note_content": ("what did i write",),
            "note_status": ("is it done",),
        },
        embedder=embed,
        threshold=0.5,
        margin=0.1,
    )

    assert classifier.classify("hi").label == "conversation"  # type: ignore[union-attr]
    assert classifier.classify("status update").label == "note_status"  # type: ignore[union-attr]
    assert classifier.classify("what did i write").label == "note_content"  # type: ignore[union-attr]


def test_conversation_route_skips_retrieval_and_grounding() -> None:
    retrieval_calls: list[str] = []
    grounding_calls: list[str] = []
    responses: list[str] = []

    def retrieve(context: RoutingContext) -> dict[str, object] | None:
        retrieval_calls.append(context.message)
        return {"candidates": []}

    def grounding(context: RoutingContext, payload: dict[str, object] | None) -> GroundingSnapshot:
        grounding_calls.append(context.grounding_mode)
        return GroundingSnapshot(status="strong", confidence=1.0, allow_answer=True)

    def response(
        context: RoutingContext,
        decision: object,
        plan: object,
        payload: object,
        snapshot: object,
    ) -> str:
        responses.append(context.message)
        return "Hello."

    orchestrator = build_routing_orchestrator(
        classifier=StaticClassifier(
            IntentDecision(
                kind="conversation",
                confidence=0.95,
                needs_retrieval=False,
                needs_tools=False,
                direct_answer=True,
                grounding_mode="none",
            )
        ),
        plan_builder=build_chat_plan,
        retrieve_context=retrieve,
        build_grounding=grounding,
        build_response=response,
    )

    outcome: RoutingOutcome = orchestrator.route(
        RoutingContext(user_id="u1", thread_id="t1", message="hi")
    )

    assert outcome.decision.route == "conversation"
    assert outcome.decision.grounding_mode == "none"
    assert outcome.decision.allow_answer is True
    assert outcome.metadata["grounding"]["status"] == "not_required"
    assert retrieval_calls == []
    assert grounding_calls == []
    assert responses == ["hi"]


def test_read_tool_route_executes_inline_without_retrieval() -> None:
    retrieval_calls: list[str] = []
    tool_calls: list[str] = []
    tool_context_seen: list[str] = []

    def retrieve(context: RoutingContext) -> dict[str, object] | None:
        retrieval_calls.append(context.message)
        return {"candidates": []}

    def grounding(context: RoutingContext, payload: dict[str, object] | None) -> GroundingSnapshot:
        raise AssertionError("read tools should not run grounding")

    def read_tool(context: RoutingContext, tool_name: str) -> str:
        tool_calls.append(tool_name)
        return "Open loops: 1 open task."

    def response(
        context: RoutingContext,
        decision: object,
        plan: object,
        payload: object,
        snapshot: object,
    ) -> str:
        tool_context_seen.append(context.tool_context)
        return "You have one open task."

    orchestrator = build_routing_orchestrator(
        classifier=StaticClassifier(
            IntentDecision(
                kind="tool_read",
                confidence=0.9,
                needs_retrieval=False,
                needs_tools=True,
                direct_answer=False,
                grounding_mode="none",
                tool_name="get_open_loops",
            )
        ),
        plan_builder=build_chat_plan,
        retrieve_context=retrieve,
        build_grounding=grounding,
        build_response=response,
        run_read_tool=read_tool,
    )

    outcome = orchestrator.route(
        RoutingContext(user_id="u1", thread_id="t1", message="what am I forgetting")
    )

    assert outcome.decision.route == "tool"
    assert outcome.decision.tool_name == "get_open_loops"
    assert tool_calls == ["get_open_loops"]
    assert retrieval_calls == []
    assert tool_context_seen == ["Open loops: 1 open task."]
    assert outcome.metadata["intent"]["tool_name"] == "get_open_loops"


def test_read_tool_failure_degrades_without_breaking_response() -> None:
    def read_tool(context: RoutingContext, tool_name: str) -> str:
        raise RuntimeError("recall unavailable")

    def response(
        context: RoutingContext,
        decision: object,
        plan: object,
        payload: object,
        snapshot: object,
    ) -> str:
        assert "couldn't load" in context.tool_context
        return "I couldn't load your review queue."

    orchestrator = build_routing_orchestrator(
        classifier=StaticClassifier(
            IntentDecision(
                kind="tool_read",
                confidence=0.9,
                needs_retrieval=False,
                needs_tools=True,
                direct_answer=False,
                grounding_mode="none",
                tool_name="get_due_cards",
            )
        ),
        plan_builder=build_chat_plan,
        retrieve_context=lambda context: None,
        build_grounding=lambda context, payload: GroundingSnapshot(
            status="not_required", confidence=1.0, allow_answer=True
        ),
        build_response=response,
        run_read_tool=read_tool,
    )

    outcome = orchestrator.route(
        RoutingContext(user_id="u1", thread_id="t1", message="what is due")
    )

    assert outcome.decision.route == "tool"
    assert outcome.assistant_message == "I couldn't load your review queue."


def test_note_route_runs_retrieval_and_selected_grounding_mode() -> None:
    retrieval_calls: list[str] = []
    grounding_calls: list[str] = []

    def retrieve(context: RoutingContext) -> dict[str, object] | None:
        retrieval_calls.append(context.message)
        return {"candidates": [{"note_id": "n1", "summary": "Auth uses JWT.", "score": 1.0}]}

    def grounding(context: RoutingContext, payload: dict[str, object] | None) -> GroundingSnapshot:
        grounding_calls.append(context.grounding_mode)
        return GroundingSnapshot(
            status="strong",
            confidence=0.9,
            allow_answer=True,
            source_refs=["note:n1"],
        )

    def response(
        context: RoutingContext,
        decision: object,
        plan: object,
        payload: object,
        snapshot: object,
    ) -> str:
        return "Auth uses JWT [n1]."

    orchestrator = build_routing_orchestrator(
        classifier=StaticClassifier(
            IntentDecision(
                kind="note_status",
                confidence=0.8,
                needs_retrieval=True,
                needs_tools=False,
                direct_answer=False,
                grounding_mode="claim",
            )
        ),
        plan_builder=build_chat_plan,
        retrieve_context=retrieve,
        build_grounding=grounding,
        build_response=response,
    )

    outcome = orchestrator.route(
        RoutingContext(user_id="u1", thread_id="t1", message="is auth done")
    )

    assert outcome.decision.route == "note_search"
    assert outcome.decision.source_refs == ["note:n1"]
    assert retrieval_calls == ["is auth done"]
    assert grounding_calls == ["claim"]


def test_relevance_grounding_allows_note_evidence_without_claim() -> None:
    decision = assess_grounding(
        user_message="what did I say about the deploy",
        recent_messages=[],
        knowledge_payload={
            "candidates": [
                {
                    "note_id": "n1",
                    "summary": "The deploy depends on the analytics migration.",
                    "score": 1.0,
                }
            ]
        },
        mode="relevance",
    )

    assert decision.status == "strong"
    assert decision.allow_answer is True
    assert decision.source_refs == ["note:n1"]


def test_relevance_grounding_rejects_summary_only_context() -> None:
    decision = assess_grounding(
        user_message="what did I say about the deploy",
        recent_messages=[],
        knowledge_payload=None,
        summary_memory="We discussed the deploy earlier.",
        mode="relevance",
    )

    assert decision.status == "no_context"
    assert decision.allow_answer is False


def test_none_grounding_is_not_required() -> None:
    decision = assess_grounding(
        user_message="hi",
        recent_messages=[],
        knowledge_payload=None,
        mode="none",
    )

    assert decision.status == "not_required"
    assert decision.allow_answer is True
