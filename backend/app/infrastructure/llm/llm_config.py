"""LLM configuration constants shared across modules."""
import os

# ============================================================================
# Gemini Model Configuration
# ============================================================================

# Work Memory Extraction (Note Processor)
WORK_MEMORY_EXTRACTION_TEMPERATURE = 0.2
WORK_MEMORY_EXTRACTION_MAX_RETRIES = 3
WORK_MEMORY_EXTRACTION_TIMEOUT_SECONDS = 120

# Chat Answer Generation
CHAT_ANSWER_GENERATION_TEMPERATURE = 0.2
CHAT_ANSWER_GENERATION_MAX_RETRIES = 2
CHAT_ANSWER_GENERATION_TIMEOUT_SECONDS = 90

# Query Rewriting
QUERY_REWRITE_TEMPERATURE = 0.1
QUERY_REWRITE_MAX_RETRIES = 2
QUERY_REWRITE_TIMEOUT_SECONDS = 60
QUERY_REWRITE_MIN_CONFIDENCE = float(os.getenv("QUERY_REWRITE_MIN_CONFIDENCE", "0.55"))

# ============================================================================
# Related Notes Context Configuration
# ============================================================================

# Maximum number of related notes to include in LLM context
MAX_RELATED_NOTES_IN_CONTEXT = 5

# Maximum character length for each related note summary in context
MAX_RELATED_NOTE_SUMMARY_LENGTH = 200

# ============================================================================
# Daily/Weekly Period Summary Configuration
# ============================================================================

PERIOD_SUMMARY_TEMPERATURE = 0.2
PERIOD_SUMMARY_MAX_RETRIES = 2
PERIOD_SUMMARY_TIMEOUT_SECONDS = 90

# A daily summary is only generated once this many notes exist for the day.
MIN_NOTES_FOR_DAILY_SUMMARY = 2

# ============================================================================
# Chat Tool-Calling Configuration
# ============================================================================

# Deterministic tool selection — we want the same message to always resolve
# (or not resolve) to the same tool call.
TOOL_CALL_TEMPERATURE = 0
TOOL_CALL_MAX_RETRIES = 2
TOOL_CALL_TIMEOUT_SECONDS = 30

# How long a proposed tool action waits for the user's yes/no before it's
# treated as stale (a fresh message no longer matches it).
PENDING_ACTION_EXPIRY_MINUTES = 15

# Open items shown to the tool-resolution LLM per type, so it can pick an
# existing item id instead of inventing one.
MAX_OPEN_ITEMS_FOR_TOOL_CONTEXT = 10
MAX_ITEM_TEXT_LENGTH_FOR_TOOL_CONTEXT = 150


