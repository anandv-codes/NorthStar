from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from ..constants import (
    BLOCKED_MARKERS,
    CHAT_AUTHORITY,
    COMPLETION_MARKERS,
    GUARDRAIL_STOP_WORDS,
    IN_PROGRESS_MARKERS,
    NOTE_AUTHORITY,
    PENDING_MARKERS,
    SUMMARY_AUTHORITY,
)


@dataclass(slots=True)
class GroundingEvidence:
    source_type: str
    source_id: str
    source_ref: str
    excerpt: str
    claim: str | None
    authority: float
    recency: float
    retrieval_score: float
    overlap: float
    weight: float


@dataclass(slots=True)
class GroundingDecision:
    status: str
    confidence: float
    allow_answer: bool
    top_claim: str | None
    summary: str
    source_refs: list[str] = field(default_factory=list)
    evidence: list[GroundingEvidence] = field(default_factory=list)
    fallback_message: str | None = None


def assess_grounding(
    user_message: str,
    recent_messages: Sequence[dict[str, Any]] | None,
    knowledge_payload: dict[str, Any] | None,
    summary_memory: str | None = None,
) -> GroundingDecision:
    query_tokens = _query_tokens(user_message)
    evidence = _collect_evidence(
        user_message=user_message,
        query_tokens=query_tokens,
        recent_messages=recent_messages or [],
        knowledge_payload=knowledge_payload,
        summary_memory=summary_memory,
    )

    if not evidence:
        return GroundingDecision(
            status="no_context",
            confidence=0.0,
            allow_answer=False,
            top_claim=None,
            summary="No grounding evidence found in notes, summary, or recent messages.",
            fallback_message=_build_no_context_message(user_message),
        )

    claim_scores: dict[str, float] = {}
    claim_supporters: dict[str, list[GroundingEvidence]] = {}
    for item in evidence:
        if not item.claim:
            continue
        claim_scores[item.claim] = claim_scores.get(item.claim, 0.0) + item.weight
        claim_supporters.setdefault(item.claim, []).append(item)

    if not claim_scores:
        return GroundingDecision(
            status="no_context",
            confidence=0.0,
            allow_answer=False,
            top_claim=None,
            summary="Evidence was found, but none of it contained a clear status claim.",
            source_refs=_source_refs(evidence),
            evidence=evidence,
            fallback_message=_build_no_context_message(user_message),
        )

    ranked_claims = sorted(claim_scores.items(), key=lambda item: item[1], reverse=True)
    top_claim, top_score = ranked_claims[0]
    runner_up_score = ranked_claims[1][1] if len(ranked_claims) > 1 else 0.0
    top_supporters = claim_supporters.get(top_claim, [])
    dissenters = [
        item
        for claim, items in claim_supporters.items()
        if claim != top_claim
        for item in items
        if item.weight >= 0.9
    ]

    confidence = _normalize_confidence(top_score, runner_up_score, len(top_supporters))
    source_refs = _source_refs(top_supporters)
    if not source_refs:
        source_refs = _source_refs(evidence)

    if top_score < 1.4 or not top_supporters:
        return GroundingDecision(
            status="weak",
            confidence=confidence,
            allow_answer=False,
            top_claim=top_claim,
            summary="Evidence is too weak to answer confidently.",
            source_refs=source_refs,
            evidence=evidence,
            fallback_message=_build_weak_message(user_message, source_refs),
        )

    if dissenters and runner_up_score >= top_score * 0.7:
        return GroundingDecision(
            status="conflict",
            confidence=confidence,
            allow_answer=False,
            top_claim=top_claim,
            summary="Retrieved evidence disagrees across sources.",
            source_refs=sorted(set(source_refs + _source_refs(dissenters))),
            evidence=evidence,
            fallback_message=_build_conflict_message(user_message, top_claim, top_supporters, dissenters),
        )

    if top_score < 2.2 and len(top_supporters) < 2:
        return GroundingDecision(
            status="weak",
            confidence=confidence,
            allow_answer=False,
            top_claim=top_claim,
            summary="Only one weak source supports this answer.",
            source_refs=source_refs,
            evidence=evidence,
            fallback_message=_build_weak_message(user_message, source_refs),
        )

    return GroundingDecision(
        status="strong",
        confidence=confidence,
        allow_answer=True,
        top_claim=top_claim,
        summary=f"Sources agree on '{top_claim}'.",
        source_refs=source_refs,
        evidence=evidence,
    )


def format_grounding_context(decision: GroundingDecision) -> str:
    lines = [
        f"Grounding status: {decision.status}",
        f"Grounding confidence: {decision.confidence:.2f}",
        f"Top claim: {decision.top_claim or 'unknown'}",
        f"Evidence summary: {decision.summary}",
    ]
    if decision.source_refs:
        lines.append(f"Source references: {', '.join(decision.source_refs)}")
    return "\n".join(lines)


def _collect_evidence(
    user_message: str,
    query_tokens: set[str],
    recent_messages: Sequence[dict[str, Any]],
    knowledge_payload: dict[str, Any] | None,
    summary_memory: str | None,
) -> list[GroundingEvidence]:
    evidence: list[GroundingEvidence] = []

    if summary_memory and str(summary_memory).strip():
        text = str(summary_memory).strip()
        evidence.append(
            _build_evidence(
                source_type="summary",
                source_id="thread-summary",
                source_ref="summary:thread",
                text=text,
                query_tokens=query_tokens,
                authority=SUMMARY_AUTHORITY,
                recency=0.7,
                retrieval_score=0.7,
            )
        )

    recent_slice = list(recent_messages)[-8:]
    total_recent = len(recent_slice) or 1
    for index, message in enumerate(recent_slice):
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        role = str(message.get("role") or "chat").strip().lower() or "chat"
        message_id = str(message.get("message_id") or f"recent-{index}")
        recency = 0.9 + (index / max(total_recent - 1, 1)) * 0.1 if total_recent > 1 else 1.0
        evidence.append(
            _build_evidence(
                source_type=f"chat:{role}",
                source_id=message_id,
                source_ref=f"chat:{message_id}",
                text=content,
                query_tokens=query_tokens,
                authority=CHAT_AUTHORITY,
                recency=recency,
                retrieval_score=0.75,
            )
        )

    candidates = list((knowledge_payload or {}).get("candidates") or [])
    if candidates:
        raw_scores = [float(candidate.get("score") or candidate.get("rrf_score") or 0.0) for candidate in candidates]
        max_score = max(raw_scores) if raw_scores else 0.0
        for candidate in candidates[:5]:
            note_id = str(candidate.get("note_id") or "").strip()
            if not note_id:
                continue
            text = str(candidate.get("summary") or candidate.get("text") or "").strip()
            if not text:
                continue
            score = float(candidate.get("score") or candidate.get("rrf_score") or 0.0)
            retrieval_score = 1.0
            if max_score > 0:
                retrieval_score = 0.7 + (score / max_score) * 0.3
            evidence.append(
                _build_evidence(
                    source_type="note",
                    source_id=note_id,
                    source_ref=f"note:{note_id}",
                    text=text,
                    query_tokens=query_tokens,
                    authority=NOTE_AUTHORITY,
                    recency=1.0,
                    retrieval_score=retrieval_score,
                )
            )

    return evidence


def _build_evidence(
    source_type: str,
    source_id: str,
    source_ref: str,
    text: str,
    query_tokens: set[str],
    authority: float,
    recency: float,
    retrieval_score: float,
) -> GroundingEvidence:
    claim = _detect_claim(text)
    overlap = _token_overlap(text, query_tokens)
    weight = authority * recency * retrieval_score * (0.7 + (0.3 * overlap))
    return GroundingEvidence(
        source_type=source_type,
        source_id=source_id,
        source_ref=source_ref,
        excerpt=_truncate(text),
        claim=claim,
        authority=round(authority, 3),
        recency=round(recency, 3),
        retrieval_score=round(retrieval_score, 3),
        overlap=round(overlap, 3),
        weight=round(weight, 3),
    )


def _detect_claim(text: str) -> str | None:
    lowered = str(text or "").lower()

    if re.search(r"\b(not|never|without)\s+(?:\w+\s+){0,2}?(completed|done|finished|resolved|closed|fixed)\b", lowered):
        return "not_completed"

    if any(marker in lowered for marker in COMPLETION_MARKERS):
        return "completed"
    if any(marker in lowered for marker in IN_PROGRESS_MARKERS):
        return "in_progress"
    if any(marker in lowered for marker in BLOCKED_MARKERS):
        return "blocked"
    if any(marker in lowered for marker in PENDING_MARKERS):
        return "pending"
    return None


def _query_tokens(message: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(message or "").lower())
        if token and token not in GUARDRAIL_STOP_WORDS
    }


def _token_overlap(text: str, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    source_tokens = _query_tokens(text)
    if not source_tokens:
        return 0.0
    intersection = len(source_tokens.intersection(query_tokens))
    return intersection / max(len(query_tokens), 1)


def _normalize_confidence(top_score: float, runner_up_score: float, supporter_count: int) -> float:
    evidence_strength = min(top_score / 5.0, 1.0)
    separation = top_score - runner_up_score
    separation_strength = min(max(separation, 0.0) / 2.0, 1.0)
    supporter_strength = min(supporter_count / 3.0, 1.0)
    confidence = (evidence_strength * 0.45) + (separation_strength * 0.35) + (supporter_strength * 0.2)
    return round(min(max(confidence, 0.0), 1.0), 3)


def _source_refs(evidence: Sequence[GroundingEvidence]) -> list[str]:
    refs = [item.source_ref for item in evidence if item.source_ref]
    return list(dict.fromkeys(refs))


def _build_no_context_message(user_message: str) -> str:
    label = _short_label(user_message)
    return (
        f"I couldn't find enough grounded context for '{label}' in recent chat or notes. "
        "Please share the relevant note, task, or thread, and I’ll check again."
    )


def _build_weak_message(user_message: str, source_refs: Sequence[str]) -> str:
    label = _short_label(user_message)
    refs = _render_refs(source_refs)
    suffix = f" Sources: {refs}." if refs else ""
    return (
        f"I found only weak evidence for '{label}', so I’m not confident enough to answer directly."
        f"{suffix}"
    )


def _build_conflict_message(
    user_message: str,
    top_claim: str | None,
    top_supporters: Sequence[GroundingEvidence],
    dissenters: Sequence[GroundingEvidence],
) -> str:
    label = _short_label(user_message)
    top_refs = _render_refs(_source_refs(top_supporters))
    dissent_refs = _render_refs(_source_refs(dissenters))
    claim_text = top_claim or "different answers"
    return (
        f"I found conflicting evidence for '{label}'. "
        f"One set of sources points to {claim_text}, but other sources disagree. "
        f"Top sources: {top_refs or 'n/a'}; conflicting sources: {dissent_refs or 'n/a'}."
    )


def _render_refs(source_refs: Sequence[str]) -> str:
    unique_refs = [ref for ref in dict.fromkeys(source_refs) if ref]
    return ", ".join(unique_refs)


def _short_label(user_message: str, max_length: int = 72) -> str:
    label = " ".join(str(user_message or "").strip().split())
    if len(label) <= max_length:
        return label
    return f"{label[: max_length - 3].rstrip()}..."


def _truncate(text: str, max_length: int = 220) -> str:
    cleaned = " ".join(str(text or "").strip().split())
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."
