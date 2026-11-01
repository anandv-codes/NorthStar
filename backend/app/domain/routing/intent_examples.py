"""Seed utterances for the local semantic intent router.

These examples are training data for the in-repo kNN classifier, not the
evaluation set. Keep the evaluation set separate so threshold tuning does not
overfit to the same phrases.

Labels:
- ``conversation``: small talk and assistant capability questions.
- ``note_content``: questions answered from note content.
- ``note_status``: questions about completion/open/blocked state.
- ``action``: explicit requests to create or change task state.

Both note labels map to the ``note_search`` route. ``note_status`` selects the
claim/conflict grounding path; ``note_content`` selects relevance grounding.
Action routing stays deterministic for safety; the action examples are kept
for future evaluation and tool expansion rather than the semantic kNN index.
"""

from __future__ import annotations

from typing import Final, Literal

SemanticIntentLabel = Literal[
    "conversation",
    "note_content",
    "note_status",
    "action",
]

NOTE_SEARCH_LABELS: Final[frozenset[SemanticIntentLabel]] = frozenset(
    {"note_content", "note_status"}
)

GROUNDING_MODE_BY_LABEL: Final[dict[SemanticIntentLabel, str]] = {
    "conversation": "none",
    "note_content": "relevance",
    "note_status": "claim",
    "action": "none",
}

INTENT_EXAMPLES: Final[dict[SemanticIntentLabel, tuple[str, ...]]] = {
    "conversation": (
        "hi",
        "hello",
        "hey",
        "good morning",
        "good evening",
        "how are you",
        "how's it going",
        "thanks",
        "thank you",
        "that helps",
        "got it",
        "okay",
        "cool",
        "nice",
        "what can you do",
        "who are you",
        "what are you",
        "help me understand what you do",
        "are you there",
        "see you later",
    ),
    "note_content": (
        "what did i say about the deploy",
        "what do my notes say about the launch",
        "summarize my notes",
        "summarize what i logged today",
        "what did i decide about auth",
        "what decisions did i make this week",
        "what did i learn about vector databases",
        "what have i learned about kubernetes",
        "find notes about datafix",
        "search my notes for priya",
        "any notes on the migration",
        "what happened with the lambda issue",
        "recap my week",
        "what was the root cause of the outage",
        "show me my notes from yesterday",
        "what did i write about onboarding",
        "remind me what i captured about pricing",
        "what context do i have on the client call",
        "what's in my notes about the rollout",
        "find the note where i discussed the delay",
        "what did i record about the api design",
        "what do i know about the budget",
        "pull up my notes on hiring",
        "what was discussed in the meeting with onshore",
        "what did i note about the analytics dependency",
    ),
    "note_status": (
        "is datafix 42 done",
        "is the deploy complete",
        "what's the status of datafix 42",
        "did i finish the onboarding task",
        "what tasks are pending",
        "what tasks are still open",
        "what's still open from this week",
        "what is blocked",
        "what's in progress",
        "what did i complete today",
        "which tasks did i close",
        "has the client call been scheduled",
        "is the migration finished",
        "what's waiting on priya",
        "what remains open",
        "did i resolve the auth question",
        "what questions are unanswered",
        "what's the latest status on the rollout",
        "is the analytics work done",
        "what have i completed this week",
        "what's on my plate",
        "what do i still need to do",
    ),
    "action": (
        "create a task to review the pr",
        "add a task to call priya",
        "remind me to follow up with onshore",
        "mark datafix 42 as done",
        "complete the onboarding task",
        "close the auth task",
        "mark the deploy task complete",
        "reopen the analytics task",
        "mark the analytics task as open",
        "set datafix 42 back to open",
        "start working on the migration task",
        "move the hiring task to in progress",
        "mark the client call task in progress",
        "create a task for the budget review",
        "add a to-do to update the runbook",
        "complete task 123",
        "reopen task 456",
        "mark the launch checklist done",
        "close out the pricing task",
        "set the datafix task to open",
    ),
}
