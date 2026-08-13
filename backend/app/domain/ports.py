"""Provider-facing interfaces (ports) used by the domain layer.

The domain layer should depend on these ``Protocol`` definitions instead of
importing concrete infrastructure modules directly. Each protocol mirrors the
call signatures the domain already relies on, so swapping the concrete
Supabase/Chroma/Gemini implementations for a fake (in tests) or an
alternative provider (in production) does not require any domain code
changes beyond passing a different implementation in.

Concrete implementations live under ``backend/app/infrastructure`` and are
wired in via optional constructor/function parameters that default to the
current provider, so existing behavior is unchanged unless a caller supplies
an alternative implementation.
"""
from __future__ import annotations

from typing import Any, Protocol


class UserRepository(Protocol):
    """Persistence for user accounts and refresh tokens."""

    def create_user(self, email: str, password_hash: str) -> dict[str, Any]: ...

    def get_user_by_email(self, email: str) -> dict[str, Any]: ...

    def get_user_by_id(self, user_id: str) -> dict[str, Any]: ...

    def store_refresh_token(
        self,
        user_id: str,
        jti: str,
        token_hash: str,
        expires_at: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]: ...

    def get_refresh_token_by_jti(self, jti: str) -> dict[str, Any]: ...

    def revoke_refresh_token(self, jti: str) -> dict[str, Any]: ...


class MemoryRepository(Protocol):
    """Persistence for extraction runs and typed work-memory items."""

    def create_extraction_run(
        self,
        user_id: str,
        note_id: str,
        model_name: str,
        prompt_version: str,
        status: str = "completed",
        error_message: str | None = None,
    ) -> dict[str, Any]: ...

    def insert_tasks(
        self, user_id: str, source_note_id: str, extraction_run_id: str | None, tasks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...

    def insert_facts(
        self, user_id: str, source_note_id: str, extraction_run_id: str | None, facts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...

    def insert_questions(
        self, user_id: str, source_note_id: str, extraction_run_id: str | None, questions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...

    def insert_decisions(
        self, user_id: str, source_note_id: str, extraction_run_id: str | None, decisions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...

    def insert_risks(
        self, user_id: str, source_note_id: str, extraction_run_id: str | None, risks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...

    def insert_concepts(
        self, user_id: str, source_note_id: str, extraction_run_id: str | None, concepts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...

    def upsert_entities(self, user_id: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]: ...

    def insert_memory_item_entity_links(
        self, user_id: str, source_note_id: str, links: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...

    def query_tasks_for_user(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]: ...

    def query_questions_for_user(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]: ...

    def query_risks_for_user(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]: ...

    def query_concepts_for_user(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]: ...

    def query_recent_memory_for_user(self, user_id: str, limit: int = 10) -> dict[str, list[dict[str, Any]]]: ...

    def update_task_item(self, user_id: str, task_id: str, updates: dict[str, Any]) -> dict[str, Any]: ...

    def update_question_item(self, user_id: str, question_id: str, updates: dict[str, Any]) -> dict[str, Any]: ...

    def update_risk_item(self, user_id: str, risk_id: str, updates: dict[str, Any]) -> dict[str, Any]: ...

    def update_concept_item(self, user_id: str, concept_id: str, updates: dict[str, Any]) -> dict[str, Any]: ...

    def query_latest_extraction_run_for_note(self, user_id: str, note_id: str) -> dict[str, Any]: ...

    def query_tasks_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]: ...

    def query_facts_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]: ...

    def query_questions_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]: ...

    def query_decisions_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]: ...

    def query_risks_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]: ...

    def query_concepts_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]: ...

    def query_entities_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]: ...


class NoteRepository(Protocol):
    """Read access to raw notes, used by the sparse (BM25) retriever."""

    def query_notes_for_user(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]: ...


class ChatRepository(Protocol):
    """Persistence for chat threads and messages."""

    def create_chat_thread(self, user_id: str, title: str | None = None) -> dict[str, Any]: ...

    def get_chat_thread_item(self, user_id: str, thread_id: str) -> dict[str, Any]: ...

    def update_chat_thread_item(self, user_id: str, thread_id: str, updates: dict[str, Any]) -> dict[str, Any]: ...

    def touch_chat_thread_item(self, user_id: str, thread_id: str) -> dict[str, Any]: ...

    def insert_chat_message_item(
        self,
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def query_chat_messages_for_thread(self, user_id: str, thread_id: str, limit: int = 20) -> list[dict[str, Any]]: ...


class EmbeddingProvider(Protocol):
    """Text embedding provider used for semantic retrieval."""

    def embed_query(self, text: str) -> list[float]: ...


class VectorStore(Protocol):
    """Vector similarity search over user-scoped note embeddings."""

    def query_related_notes(
        self,
        user_id: str,
        embedding: list[float],
        k: int = 3,
        exclude_note_id: str | None = None,
    ) -> list[dict[str, Any]]: ...


class QueryRewriter(Protocol):
    """LLM-backed query rewriting for retrieval."""

    def rewrite(
        self,
        user_query: str,
        recent_memory: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]: ...


class ChatModel(Protocol):
    """LLM chat completion used to generate the final assistant answer."""

    def generate(self, prompt: str) -> str: ...


class PipelineLogger(Protocol):
    """Diagnostic logger for LLM/retrieval pipeline stages."""

    def log(self, stage: str, lines: list[str]) -> None: ...
