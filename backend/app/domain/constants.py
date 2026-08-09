from __future__ import annotations

GUARDRAIL_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "what",
    "what's",
    "whats",
    "with",
    "status",
    "tell",
    "me",
    "please",
}

RETRIEVAL_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "this",
    "that",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}

COMPLETION_MARKERS = (
    "completed",
    "done",
    "finished",
    "resolved",
    "closed",
    "fixed",
)

IN_PROGRESS_MARKERS = (
    "in progress",
    "working on",
    "ongoing",
    "in flight",
)

BLOCKED_MARKERS = (
    "blocked",
    "stuck",
    "on hold",
    "waiting on",
)

PENDING_MARKERS = (
    "pending",
    "open",
    "todo",
    "queued",
)

NEGATION_TERMS = {"no", "not", "never", "without", "except", "n't"}

GENERIC_QUERY_TERMS = {
    "status",
    "update",
    "latest",
    "pending",
    "done",
    "complete",
    "completed",
    "result",
    "results",
    "info",
    "information",
    "help",
}

INTENT_RETRIEVAL_HINTS = {
    "find",
    "search",
    "remember",
    "recall",
    "show",
    "what did i say",
    "based on",
    "in my notes",
    "retrieve",
    "memory",
    "task",
    "question",
    "risk",
    "decision",
}

INTENT_TOOL_HINTS = {
    "create",
    "update",
    "delete",
    "mark",
    "set",
    "schedule",
    "calculate",
    "convert",
    "send",
    "email",
    "tool",
}

SHORT_TERM_WINDOW = 8
SUMMARY_TRIGGER_MESSAGES = 12
SUMMARY_MAX_CHARS = 900

NOTE_AUTHORITY = 3.0
SUMMARY_AUTHORITY = 1.8
CHAT_AUTHORITY = 1.2
