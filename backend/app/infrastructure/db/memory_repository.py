"""Supabase-backed implementation of the domain ``MemoryRepository`` port."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from postgrest import APIError

from .supabase_client import supabase

EXTRACTION_RUNS_TABLE = os.getenv("SUPABASE_EXTRACTION_RUNS_TABLE", "extraction_runs")
TASKS_TABLE = os.getenv("SUPABASE_TASKS_TABLE", "tasks")
FACTS_TABLE = os.getenv("SUPABASE_FACTS_TABLE", "facts")
QUESTIONS_TABLE = os.getenv("SUPABASE_QUESTIONS_TABLE", "questions")
DECISIONS_TABLE = os.getenv("SUPABASE_DECISIONS_TABLE", "decisions")
RISKS_TABLE = os.getenv("SUPABASE_RISKS_TABLE", "risks")
CONCEPTS_TABLE = os.getenv("SUPABASE_CONCEPTS_TABLE", "concepts")
ENTITIES_TABLE = os.getenv("SUPABASE_ENTITIES_TABLE", "entities")
MEMORY_ITEM_ENTITIES_TABLE = os.getenv(
    "SUPABASE_MEMORY_ITEM_ENTITIES_TABLE",
    "memory_item_entities",
)
NOTES_TABLE = os.getenv("SUPABASE_NOTES_TABLE", "notes")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _execute_insert(table: str, rows: dict[str, Any] | list[dict[str, Any]]) -> Any:
    try:
        response = supabase.table(table).insert(rows).execute()
    except APIError as exc:
        raise RuntimeError(str(exc)) from exc
    return response.data


def _execute_upsert(
    table: str,
    rows: dict[str, Any] | list[dict[str, Any]],
    on_conflict: str | None = None,
) -> Any:
    try:
        query = supabase.table(table).upsert(rows, on_conflict=on_conflict)
        response = query.execute()
    except APIError as exc:
        raise RuntimeError(str(exc)) from exc
    return response.data


class SupabaseMemoryRepository:
    """Concrete work-memory persistence backed by Supabase."""

    def create_extraction_run(
        self,
        user_id: str,
        note_id: str,
        model_name: str,
        prompt_version: str,
        status: str = "completed",
        error_message: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "extraction_run_id": _new_id(),
            "note_id": note_id,
            "user_id": user_id,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "status": status,
            "error_message": error_message,
            "created_at": _utc_now(),
        }
        inserted = _execute_insert(EXTRACTION_RUNS_TABLE, row)
        return inserted[0] if isinstance(inserted, list) and inserted else row

    def insert_tasks(
        self,
        user_id: str,
        source_note_id: str,
        extraction_run_id: str | None,
        tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = _utc_now()
        rows = [
            {
                "task_id": _new_id(),
                "user_id": user_id,
                "source_note_id": source_note_id,
                "extraction_run_id": extraction_run_id,
                "description": task["description"],
                "status": task.get("status", "open"),
                "created_by": task.get("created_by", "llm"),
                "confidence": task.get("confidence"),
                "created_at": now,
                "updated_at": now,
                "completed_at": task.get("completed_at"),
            }
            for task in tasks
        ]
        return _execute_insert(TASKS_TABLE, rows) if rows else []

    def insert_facts(
        self,
        user_id: str,
        source_note_id: str,
        extraction_run_id: str | None,
        facts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = _utc_now()
        rows = [
            {
                "fact_id": _new_id(),
                "user_id": user_id,
                "source_note_id": source_note_id,
                "extraction_run_id": extraction_run_id,
                "content": fact["content"],
                "created_by": fact.get("created_by", "llm"),
                "confidence": fact.get("confidence"),
                "created_at": now,
            }
            for fact in facts
        ]
        return _execute_insert(FACTS_TABLE, rows) if rows else []

    def insert_questions(
        self,
        user_id: str,
        source_note_id: str,
        extraction_run_id: str | None,
        questions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = _utc_now()
        rows = [
            {
                "question_id": _new_id(),
                "user_id": user_id,
                "source_note_id": source_note_id,
                "extraction_run_id": extraction_run_id,
                "question": question["question"],
                "status": question.get("status", "open"),
                "answer": question.get("answer"),
                "created_by": question.get("created_by", "llm"),
                "confidence": question.get("confidence"),
                "created_at": now,
                "resolved_at": question.get("resolved_at"),
            }
            for question in questions
        ]
        return _execute_insert(QUESTIONS_TABLE, rows) if rows else []

    def insert_decisions(
        self,
        user_id: str,
        source_note_id: str,
        extraction_run_id: str | None,
        decisions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = _utc_now()
        rows = [
            {
                "decision_id": _new_id(),
                "user_id": user_id,
                "source_note_id": source_note_id,
                "extraction_run_id": extraction_run_id,
                "decision": decision["decision"],
                "rationale": decision.get("rationale"),
                "created_by": decision.get("created_by", "llm"),
                "confidence": decision.get("confidence"),
                "created_at": now,
            }
            for decision in decisions
        ]
        return _execute_insert(DECISIONS_TABLE, rows) if rows else []

    def insert_risks(
        self,
        user_id: str,
        source_note_id: str,
        extraction_run_id: str | None,
        risks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = _utc_now()
        rows = [
            {
                "risk_id": _new_id(),
                "user_id": user_id,
                "source_note_id": source_note_id,
                "extraction_run_id": extraction_run_id,
                "risk": risk["risk"],
                "severity": risk.get("severity"),
                "status": risk.get("status", "open"),
                "created_by": risk.get("created_by", "llm"),
                "confidence": risk.get("confidence"),
                "created_at": now,
                "resolved_at": risk.get("resolved_at"),
            }
            for risk in risks
        ]
        return _execute_insert(RISKS_TABLE, rows) if rows else []

    def insert_concepts(
        self,
        user_id: str,
        source_note_id: str,
        extraction_run_id: str | None,
        concepts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = _utc_now()
        rows = [
            {
                "concept_id": _new_id(),
                "user_id": user_id,
                "source_note_id": source_note_id,
                "extraction_run_id": extraction_run_id,
                "concept": concept["concept"],
                "status": concept.get("status", "open"),
                "created_by": concept.get("created_by", "llm"),
                "confidence": concept.get("confidence"),
                "created_at": now,
            }
            for concept in concepts
        ]
        return _execute_insert(CONCEPTS_TABLE, rows) if rows else []

    def upsert_entities(self, user_id: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = _utc_now()
        unique_by_name: dict[str, dict[str, Any]] = {}
        for entity in entities:
            name = str(entity.get("name", "")).strip()
            if not name:
                continue
            unique_by_name[name.lower()] = {
                "entity_id": entity.get("entity_id") or _new_id(),
                "user_id": user_id,
                "name": name,
                "entity_type": entity.get("entity_type"),
                "created_at": now,
            }
        rows = list(unique_by_name.values())
        if not rows:
            return []
        return _execute_upsert(ENTITIES_TABLE, rows, on_conflict="user_id,name")

    def insert_memory_item_entity_links(
        self,
        user_id: str,
        source_note_id: str,
        links: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = _utc_now()
        rows = [
            {
                "user_id": user_id,
                "entity_id": link["entity_id"],
                "item_type": link["item_type"],
                "item_id": link["item_id"],
                "source_note_id": source_note_id,
                "created_at": now,
            }
            for link in links
        ]
        return (
            _execute_upsert(
                MEMORY_ITEM_ENTITIES_TABLE,
                rows,
                on_conflict="user_id,entity_id,item_type,item_id",
            )
            if rows
            else []
        )

    def query_tasks_for_user(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]:
        query = supabase.table(TASKS_TABLE).select("*").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
        try:
            response = query.order("created_at", desc=True).execute()
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def query_questions_for_user(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]:
        query = supabase.table(QUESTIONS_TABLE).select("*").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
        try:
            response = query.order("created_at", desc=True).execute()
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def query_risks_for_user(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]:
        query = supabase.table(RISKS_TABLE).select("*").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
        try:
            response = query.order("created_at", desc=True).execute()
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def query_concepts_for_user(self, user_id: str, status: str | None = None) -> list[dict[str, Any]]:
        query = supabase.table(CONCEPTS_TABLE).select("*").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
        try:
            response = query.order("created_at", desc=True).execute()
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def query_recent_memory_for_user(self, user_id: str, limit: int = 10) -> dict[str, list[dict[str, Any]]]:
        clamped_limit = max(1, min(limit, 50))

        def _query(table: str, order_by: str = "created_at") -> list[dict[str, Any]]:
            try:
                response = (
                    supabase.table(table)
                    .select("*")
                    .eq("user_id", user_id)
                    .order(order_by, desc=True)
                    .limit(clamped_limit)
                    .execute()
                )
            except APIError as exc:
                raise RuntimeError(str(exc)) from exc
            return response.data if isinstance(response.data, list) else []

        notes = _query(NOTES_TABLE)
        decisions = _query(DECISIONS_TABLE)
        tasks = _query(TASKS_TABLE, order_by="updated_at")
        questions = _query(QUESTIONS_TABLE)
        risks = _query(RISKS_TABLE)
        concepts = _query(CONCEPTS_TABLE)
        return {
            "notes": notes,
            "decisions": decisions,
            "tasks": tasks,
            "questions": questions,
            "risks": risks,
            "concepts": concepts,
        }

    def update_task_item(self, user_id: str, task_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        updates = {**updates, "updated_at": _utc_now()}
        if updates.get("status") == "completed" and not updates.get("completed_at"):
            updates["completed_at"] = _utc_now()

        try:
            response = (
                supabase.table(TASKS_TABLE)
                .update(updates)
                .eq("user_id", user_id)
                .eq("task_id", task_id)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc

        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else {}

    def update_question_item(self, user_id: str, question_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        try:
            current_response = (
                supabase.table(QUESTIONS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("question_id", question_id)
                .limit(1)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc

        current_rows = current_response.data if isinstance(current_response.data, list) else []
        if not current_rows:
            return {}

        current_item = current_rows[0]
        next_status = updates.get("status")
        if next_status:
            _validate_transition(
                current_status=str(current_item.get("status", "")),
                next_status=next_status,
                transitions=QUESTION_STATUS_TRANSITIONS,
                item_type="question",
            )
            if next_status == "answered" and not updates.get("resolved_at"):
                updates["resolved_at"] = _utc_now()
            if next_status == "open":
                updates["resolved_at"] = None

        try:
            response = (
                supabase.table(QUESTIONS_TABLE)
                .update(updates)
                .eq("user_id", user_id)
                .eq("question_id", question_id)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc

        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else {}

    def update_risk_item(self, user_id: str, risk_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        try:
            current_response = (
                supabase.table(RISKS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("risk_id", risk_id)
                .limit(1)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc

        current_rows = current_response.data if isinstance(current_response.data, list) else []
        if not current_rows:
            return {}

        current_item = current_rows[0]
        next_status = updates.get("status")
        if next_status:
            _validate_transition(
                current_status=str(current_item.get("status", "")),
                next_status=next_status,
                transitions=RISK_STATUS_TRANSITIONS,
                item_type="risk",
            )
            if next_status in {"mitigated", "resolved"} and not updates.get("resolved_at"):
                updates["resolved_at"] = _utc_now()
            if next_status == "open":
                updates["resolved_at"] = None

        try:
            response = (
                supabase.table(RISKS_TABLE)
                .update(updates)
                .eq("user_id", user_id)
                .eq("risk_id", risk_id)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc

        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else {}

    def update_concept_item(self, user_id: str, concept_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        try:
            current_response = (
                supabase.table(CONCEPTS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("concept_id", concept_id)
                .limit(1)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc

        current_rows = current_response.data if isinstance(current_response.data, list) else []
        if not current_rows:
            return {}

        try:
            response = (
                supabase.table(CONCEPTS_TABLE)
                .update(updates)
                .eq("user_id", user_id)
                .eq("concept_id", concept_id)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc

        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else {}

    def query_latest_extraction_run_for_note(self, user_id: str, note_id: str) -> dict[str, Any]:
        try:
            response = (
                supabase.table(EXTRACTION_RUNS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("note_id", note_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc

        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else {}

    def query_tasks_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table(TASKS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("source_note_id", note_id)
                .order("created_at", desc=False)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def query_facts_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table(FACTS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("source_note_id", note_id)
                .order("created_at", desc=False)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def query_questions_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table(QUESTIONS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("source_note_id", note_id)
                .order("created_at", desc=False)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def query_decisions_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table(DECISIONS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("source_note_id", note_id)
                .order("created_at", desc=False)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def query_risks_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table(RISKS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("source_note_id", note_id)
                .order("created_at", desc=False)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def query_concepts_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table(CONCEPTS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("source_note_id", note_id)
                .order("created_at", desc=False)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc
        return response.data if isinstance(response.data, list) else []

    def query_entities_by_source_note(self, user_id: str, note_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table(MEMORY_ITEM_ENTITIES_TABLE)
                .select("entity_id, item_type, item_id, source_note_id, created_at")
                .eq("user_id", user_id)
                .eq("source_note_id", note_id)
                .order("created_at", desc=False)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc

        rows = response.data if isinstance(response.data, list) else []
        entity_ids = [row.get("entity_id") for row in rows if row.get("entity_id")]
        if not entity_ids:
            return []

        try:
            entity_response = (
                supabase.table(ENTITIES_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .in_("entity_id", entity_ids)
                .execute()
            )
        except APIError as exc:
            raise RuntimeError(str(exc)) from exc

        entity_rows = entity_response.data if isinstance(entity_response.data, list) else []
        entity_by_id = {row.get("entity_id"): row for row in entity_rows if row.get("entity_id")}
        entities = []
        for row in rows:
            entity = entity_by_id.get(row.get("entity_id"))
            if entity:
                entities.append(entity)
        return entities


# Status transitions are enforced here (co-located with the persistence calls
# that read/write status) to keep the read-modify-write check atomic with the
# repository operation it guards.
QUESTION_STATUS_TRANSITIONS: dict[str, set[str]] = {
    # Keep question states reversible for quick reopen from UI.
    "open": {"answered"},
    "answered": {"open"},
    "archived": set(),
}

RISK_STATUS_TRANSITIONS: dict[str, set[str]] = {
    # Risks can be mitigated first, but only open items can be newly mitigated.
    "open": {"mitigated", "resolved"},
    "mitigated": {"open", "resolved"},
    "resolved": {"open"},
    "archived": set(),
}


def _validate_transition(
    current_status: str,
    next_status: str,
    transitions: dict[str, set[str]],
    item_type: str,
) -> None:
    # Treat idempotent writes as valid to avoid noisy client retries failing.
    if current_status == next_status:
        return

    allowed_targets = transitions.get(current_status, set())
    if next_status not in allowed_targets:
        raise ValueError(
            f"Invalid {item_type} status transition: {current_status} -> {next_status}",
        )


_DEFAULT_REPOSITORY: SupabaseMemoryRepository | None = None


def get_memory_repository() -> SupabaseMemoryRepository:
    """Return the process-wide default ``MemoryRepository`` implementation."""
    global _DEFAULT_REPOSITORY
    if _DEFAULT_REPOSITORY is None:
        _DEFAULT_REPOSITORY = SupabaseMemoryRepository()
    return _DEFAULT_REPOSITORY
