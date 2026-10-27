import re
from datetime import date, datetime
from typing import Any, Dict, Literal, Optional, List
from pydantic import BaseModel, Field, field_validator

_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _extract_iso_date(value: Any) -> Any:
    """Keep only the ISO date from model output such as 'due 2026-06-13 by EOD'.

    The extraction prompt asks for YYYY-MM-DD but the model occasionally wraps
    it in prose. Unparseable values become None, matching
    ``extraction_v2.normalize_due_date``.
    """
    if isinstance(value, str):
        match = _ISO_DATE_RE.search(value)
        return match.group(0) if match else None
    return value

class NoteCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw note text")
    metadata: Optional[dict] = Field(default_factory=dict)
    recall_enabled: bool = Field(
        default=False,
        description="Generate recall questions for this note when it is processed",
    )

NoteStatus = Literal["processing", "enriched", "indexed", "failed"]

class NoteStatusResponse(BaseModel):
    note_id: str
    user_id: str
    status: NoteStatus
    created_at: datetime
    raw_text: str
    enriched_summary: Optional[str] = None
    context_note_ids: List[str] = Field(default_factory=list, description="Note IDs used to enrich this summary")
    action_items: Optional[List[str]] = None
    questions: Optional[List[str]] = None
    insights: Optional[List[str]] = None
    concepts: Optional[List[str]] = None
    recall_enabled: bool = False
    recall_status: str = "off"
    indexed_at: Optional[datetime] = Field(
        default=None,
        description="When vector indexing finished; set only for status=indexed",
    )
    index_error: Optional[str] = Field(
        default=None,
        description="Why vector indexing failed; set only for status=failed",
    )

class NoteListResponse(BaseModel):
    notes: List[NoteStatusResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


TaskStatus = Literal["open", "in_progress", "completed", "archived"]
QuestionStatus = Literal["open", "answered", "archived"]
ConceptStatus = Literal["open", "learned", "archived"]
CreatedBy = Literal["llm", "user", "system"]


class ExtractedEntity(BaseModel):
    name: str = Field(..., min_length=1)
    entity_type: Optional[str] = None


class ExtractedTask(BaseModel):
    description: str = Field(..., min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    due_date: Optional[date] = None
    importance: Optional[float] = Field(default=None, ge=0, le=1)
    durability: Optional[float] = Field(default=None, ge=0, le=1)
    entities: List[str] = Field(default_factory=list)

    @field_validator("due_date", mode="before")
    @classmethod
    def _clean_due_date(cls, value: Any) -> Any:
        return _extract_iso_date(value)


class ExtractedFact(BaseModel):
    content: str = Field(..., min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    importance: Optional[float] = Field(default=None, ge=0, le=1)
    durability: Optional[float] = Field(default=None, ge=0, le=1)
    entities: List[str] = Field(default_factory=list)


class ExtractedQuestion(BaseModel):
    question: str = Field(..., min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    entities: List[str] = Field(default_factory=list)


class ExtractedDecision(BaseModel):
    decision: str = Field(..., min_length=1)
    rationale: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    entities: List[str] = Field(default_factory=list)


class ExtractedConcept(BaseModel):
    concept:str = Field(..., min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    importance: Optional[float] = Field(default=None, ge=0, le=1)
    durability: Optional[float] = Field(default=None, ge=0, le=1)
    entities: List[str] = Field(default_factory=list)


class ExtractedCommitmentContribution(BaseModel):
    """One line describing explicit progress toward a user-authored goal."""

    commitment_id: str = Field(..., min_length=1)
    comment: str = Field(..., min_length=1, max_length=240)


class WorkMemoryExtraction(BaseModel):
    summary: str = ""
    tasks: List[ExtractedTask] = Field(default_factory=list)
    facts: List[ExtractedFact] = Field(default_factory=list)
    questions: List[ExtractedQuestion] = Field(default_factory=list)
    decisions: List[ExtractedDecision] = Field(default_factory=list)
    entities: List[ExtractedEntity] = Field(default_factory=list)
    concepts: List[ExtractedConcept] = Field(default_factory=list)
    commitment_contributions: List[ExtractedCommitmentContribution] = Field(
        default_factory=list
    )


class TaskUpdateRequest(BaseModel):
    status: Optional[TaskStatus] = None
    description: Optional[str] = Field(default=None, min_length=1)


class QuestionUpdateRequest(BaseModel):
    status: QuestionStatus


class ConceptUpdateRequest(BaseModel):
    status: ConceptStatus

class SourceRef(BaseModel):
    source_note_id: str
    extraction_run_id: Optional[str] = None
    created_by: CreatedBy = "llm"
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class TaskResponse(SourceRef):
    task_id: str
    user_id: str
    description: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class QuestionResponse(SourceRef):
    question_id: str
    user_id: str
    question: str
    status: QuestionStatus
    answer: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class FactResponse(SourceRef):
    fact_id: str
    user_id: str
    content: str
    created_at: datetime


class DecisionResponse(SourceRef):
    decision_id: str
    user_id: str
    decision: str
    rationale: Optional[str] = None
    created_at: datetime


class RecentNoteResponse(BaseModel):
    note_id: str
    user_id: str
    status: str
    created_at: datetime
    raw_text: str
    enriched_summary: Optional[str] = None
    context_note_ids: List[str] = Field(default_factory=list, description="Note IDs used to enrich this summary")


class ConceptResponse(SourceRef):
    concept_id: str
    user_id: str
    concept: Optional[str] = None
    status: ConceptStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None

class ExtractionRunResponse(BaseModel):
    extraction_run_id: str
    note_id: str
    user_id: str
    model_name: str
    prompt_version: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime


class NoteMemoryResponse(BaseModel):
    note: NoteStatusResponse
    extraction_run: Optional[ExtractionRunResponse] = None
    tasks: List[TaskResponse] = Field(default_factory=list)
    facts: List[FactResponse] = Field(default_factory=list)
    questions: List[QuestionResponse] = Field(default_factory=list)
    decisions: List[DecisionResponse] = Field(default_factory=list)
    concepts: List[ConceptResponse] = Field(default_factory=list)
    entities: List[ExtractedEntity] = Field(default_factory=list)


class RecentMemoryResponse(BaseModel):
    notes: List[RecentNoteResponse] = Field(default_factory=list)
    decisions: List[DecisionResponse] = Field(default_factory=list)
    tasks: List[TaskResponse] = Field(default_factory=list)
    questions: List[QuestionResponse] = Field(default_factory=list)
    concepts: List[ConceptResponse] = Field(default_factory=list)


PeriodType = Literal["daily", "weekly"]
PeriodSummaryStatus = Literal["ready", "insufficient_data", "not_generated"]


class PeriodSummaryResponse(BaseModel):
    summary_id: str
    user_id: str
    period_type: PeriodType
    period_start: date
    period_end: date
    narrative: str
    stats: Dict[str, Any] = Field(default_factory=dict)
    source_note_count: int
    generated_at: datetime


class PeriodSummaryStatusResponse(BaseModel):
    status: PeriodSummaryStatus
    summary: Optional[PeriodSummaryResponse] = None
    notes_count: int = 0
    min_notes_required: int = 2


class GenerateSummaryRequest(BaseModel):
    period_start: Optional[date] = Field(
        default=None, description="Day (daily) or any day within the week (weekly). Defaults to today/this week."
    )
    regenerate: bool = False


class QueryRetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class QueryRetrievalCandidate(BaseModel):
    note_id: str
    text: str
    summary: Optional[str] = None
    sparse_distance: Optional[float] = None
    sparse_rank: Optional[int] = None
    original_distance: Optional[float] = None
    original_rank: Optional[int] = None
    rewritten_distance: Optional[float] = None
    rewritten_rank: Optional[int] = None
    exact_distance: Optional[float] = None
    exact_rank: Optional[int] = None
    rrf_score: Optional[float] = None
    rerank_score: Optional[float] = None
    score: float


class QueryRewriteResponse(BaseModel):
    rewritten_query: str
    likely_answer: str
    confidence: float = Field(..., ge=0, le=1)
    risk_flags: List[str] = Field(default_factory=list)


class QueryRetrievalResponse(BaseModel):
    original_query: str
    rewritten_query: Optional[str] = None
    likely_answer: Optional[str] = None
    rewrite_confidence: Optional[float] = None
    rewrite_used: bool = False
    fallback_reason: Optional[str] = None
    rerank_used: bool = False
    rerank_strategy: Optional[str] = None
    explicit_identifiers: List[str] = Field(default_factory=list)
    candidates: List[QueryRetrievalCandidate] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: Optional[str] = None


class ChatPlanActionResponse(BaseModel):
    name: str
    description: str
    enabled: bool = True
    metadata: Dict[str, str] = Field(default_factory=dict)


class ChatIntentResponse(BaseModel):
    kind: str
    confidence: float
    needs_retrieval: bool = False
    needs_tools: bool = False
    direct_answer: bool = True
    reasons: List[str] = Field(default_factory=list)


ChatRouteKind = Literal["direct", "retrieval", "tool", "mixed", "abstain"]


class ChatRoutingResponse(BaseModel):
    route: ChatRouteKind
    confidence: float
    allow_answer: bool
    reasons: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)
    fallback_message: Optional[str] = None


GroundingStatus = Literal["strong", "weak", "conflict", "no_context"]


class GroundingEvidenceResponse(BaseModel):
    source_type: str
    source_id: str
    source_ref: str
    excerpt: str
    claim: Optional[str] = None
    authority: float
    recency: float
    retrieval_score: float
    overlap: float
    weight: float


class GroundingResponse(BaseModel):
    status: GroundingStatus
    confidence: float
    allow_answer: bool
    top_claim: Optional[str] = None
    summary: str
    source_refs: List[str] = Field(default_factory=list)
    evidence: List[GroundingEvidenceResponse] = Field(default_factory=list)
    fallback_message: Optional[str] = None


class ChatMessageRecordResponse(BaseModel):
    message_id: str
    thread_id: str
    user_id: str
    role: str
    content: str
    intent: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ChatThreadResponse(BaseModel):
    thread_id: str
    user_id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    summary_updated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageRecordResponse] = Field(default_factory=list)


class PendingToolActionResponse(BaseModel):
    pending_action_id: str
    tool_name: str
    description: str


class ChatMessageResponse(BaseModel):
    thread: ChatThreadResponse
    user_message: ChatMessageRecordResponse
    assistant_message: ChatMessageRecordResponse
    intent: ChatIntentResponse
    routing: Optional[ChatRoutingResponse] = None
    plan: List[ChatPlanActionResponse] = Field(default_factory=list)
    knowledge_error: Optional[str] = None
    grounding: Optional[GroundingResponse] = None
    pending_action: Optional[PendingToolActionResponse] = None


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    is_active: bool = True


# ---------------------------------------------------------------------------
# User-authored long-term commitments (Phase 5)
# ---------------------------------------------------------------------------

UserCommitmentStatus = Literal["active", "completed"]


class UserCommitmentCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)


class UserCommitmentUpdateRequest(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=200)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    status: Optional[Literal["completed"]] = None


class CommitmentContributionUpdateRequest(BaseModel):
    comment: str = Field(..., min_length=1, max_length=240)


class CommitmentContributionResponse(BaseModel):
    contribution_id: str
    commitment_id: str
    note_id: str
    comment: str
    created_at: datetime
    updated_at: datetime
    edited_at: Optional[datetime] = None
    source_note_created_at: Optional[datetime] = None
    source_note_excerpt: Optional[str] = None


class UserCommitmentResponse(BaseModel):
    commitment_id: str
    user_id: str
    text: str
    progress: int = Field(..., ge=0, le=100)
    status: UserCommitmentStatus
    contribution_count: int = 0
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class UserCommitmentListResponse(BaseModel):
    commitments: List[UserCommitmentResponse] = Field(default_factory=list)
    active_count: int = 0
    max_active: int = 3


# ---------------------------------------------------------------------------
# Recall loop (Phase 4): candidates, cards, reviews, commitments, note links
# ---------------------------------------------------------------------------

RecallCandidateStatus = Literal[
    "new", "candidate", "suggested", "approved", "rejected", "carded"
]
RecallCardStatus = Literal["active", "suspended"]
RecallCardState = Literal["new", "learning", "review", "relearning"]
RecallDeckColor = Literal["neutral", "amber", "emerald", "sky", "violet", "rose"]
CommitmentStatus = Literal["pending", "confirmed", "dismissed", "scheduled"]
ReviewGrade = Literal[1, 3, 4, 5]


class RecallDeckCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    description: Optional[str] = Field(default=None, max_length=240)
    color: RecallDeckColor = "neutral"


class RecallDeckUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    description: Optional[str] = Field(default=None, max_length=240)
    color: Optional[RecallDeckColor] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class RecallDeckResponse(BaseModel):
    deck_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    color: RecallDeckColor = "neutral"
    is_default: bool = False
    sort_order: int = 0
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    total_cards: int = 0
    due_cards: int = 0
    new_cards: int = 0
    suspended_cards: int = 0


class RecallDeckListResponse(BaseModel):
    decks: List[RecallDeckResponse] = Field(default_factory=list)
    total: int = 0


class RecallBulkDeckAssignRequest(BaseModel):
    candidate_ids: List[str] = Field(..., min_length=1, max_length=200)
    deck_id: str = Field(..., min_length=1)


class RecallCardUpdateRequest(BaseModel):
    deck_id: Optional[str] = Field(default=None, min_length=1)
    status: Optional[RecallCardStatus] = None


class RecallCardBulkUpdateRequest(BaseModel):
    card_ids: List[str] = Field(..., min_length=1, max_length=200)
    deck_id: Optional[str] = Field(default=None, min_length=1)
    status: Optional[RecallCardStatus] = None


class NoteEntityLink(BaseModel):
    note_id: str
    entity_id: str
    user_id: Optional[str] = None
    snippet: Optional[str] = None
    created_at: Optional[datetime] = None


class RecallCandidateCreate(BaseModel):
    user_id: str
    item_type: str
    item_id: Optional[str] = None
    source_note_id: Optional[str] = None
    prompt: Optional[str] = None
    answer: Optional[str] = None
    importance: Optional[float] = Field(default=None, ge=0, le=1)
    durability: Optional[float] = Field(default=None, ge=0, le=1)
    mention_count: int = Field(default=1, ge=1)
    related_note_count: int = Field(default=1, ge=1)
    recency_score: Optional[float] = Field(default=None, ge=0, le=1)
    user_interest_score: Optional[float] = Field(default=None, ge=0, le=1)
    score: Optional[float] = Field(default=None, ge=0, le=1)
    status: RecallCandidateStatus = "new"
    dedupe_key: Optional[str] = None
    rationale: Dict[str, Any] = Field(default_factory=dict)


class RecallCandidateResponse(RecallCandidateCreate):
    candidate_id: str
    created_at: datetime
    updated_at: datetime
    decided_at: Optional[datetime] = None


class RecallCardCreate(BaseModel):
    user_id: str
    candidate_id: Optional[str] = None
    deck_id: Optional[str] = None
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    source_note_ids: List[str] = Field(default_factory=list)
    entity_ids: List[str] = Field(default_factory=list)
    status: RecallCardStatus = "active"
    state: RecallCardState = "new"
    learning_step: int = Field(default=0, ge=0)
    interval: int = Field(default=0, ge=0)
    easiness: float = Field(default=2.5, ge=1.3)
    repetitions: int = Field(default=0, ge=0)
    lapses: int = Field(default=0, ge=0)
    review_count: int = Field(default=0, ge=0)
    last_reviewed: Optional[datetime] = None
    next_due: Optional[datetime] = None


class RecallCardResponse(RecallCardCreate):
    card_id: str
    created_at: datetime
    updated_at: datetime


class ReviewHistoryCreate(BaseModel):
    user_id: str
    card_id: str
    grade: ReviewGrade
    reviewed_at: Optional[datetime] = None
    previous_interval: Optional[int] = None
    new_interval: Optional[int] = None
    previous_easiness: Optional[float] = None
    new_easiness: Optional[float] = None
    elapsed_ms: Optional[int] = None


class ReviewHistoryResponse(ReviewHistoryCreate):
    review_id: str
    reviewed_at: datetime


class CommitmentCreate(BaseModel):
    user_id: str
    source_note_id: str
    task_id: Optional[str] = None
    title: str = Field(..., min_length=1)
    due_date: Optional[date] = None
    status: CommitmentStatus = "pending"
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    calendar_provider: Optional[str] = None
    calendar_event_id: Optional[str] = None


class CommitmentResponse(CommitmentCreate):
    commitment_id: str
    created_at: datetime
    updated_at: datetime
    confirmed_at: Optional[datetime] = None


class RecallReviewRequest(BaseModel):
    card_id: str
    grade: ReviewGrade


class DueCardsResponse(BaseModel):
    cards: List[RecallCardResponse] = Field(default_factory=list)
    total_due: int = 0


class RecallCardListResponse(BaseModel):
    cards: List[RecallCardResponse] = Field(default_factory=list)
    total: int = 0


class RecallSuggestionResponse(BaseModel):
    """A candidate shown to the user with its generated question/answer pair."""

    candidate_id: str
    question: str
    answer: Optional[str] = None
    item_type: str
    source_note_id: Optional[str] = None
    deck_id: Optional[str] = None
    score: Optional[float] = None
    importance: Optional[float] = None
    durability: Optional[float] = None
    created_at: Optional[datetime] = None


class RecallSuggestionListResponse(BaseModel):
    suggestions: List[RecallSuggestionResponse] = Field(default_factory=list)
    total: int = 0


class RecallSuggestionUpdateRequest(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    deck_id: Optional[str] = None


class RecallBulkAcceptRequest(BaseModel):
    candidate_ids: List[str] = Field(..., min_length=1, max_length=100)
    deck_id: Optional[str] = None


class RecallBulkAcceptItem(BaseModel):
    candidate_id: str
    status: str
    card: Optional[RecallCardResponse] = None
    error: Optional[str] = None


class RecallBulkAcceptResponse(BaseModel):
    accepted: int = 0
    failed: int = 0
    results: List[RecallBulkAcceptItem] = Field(default_factory=list)


class RecallBulkRejectRequest(BaseModel):
    candidate_ids: List[str] = Field(..., min_length=1, max_length=200)


class RecallBulkRejectItem(BaseModel):
    candidate_id: str
    status: str
    error: Optional[str] = None


class RecallBulkRejectResponse(BaseModel):
    rejected: int = 0
    failed: int = 0
    results: List[RecallBulkRejectItem] = Field(default_factory=list)


class RecallBulkRestoreRequest(BaseModel):
    candidate_ids: List[str] = Field(..., min_length=1, max_length=200)


class RecallBulkRestoreItem(BaseModel):
    candidate_id: str
    status: str
    error: Optional[str] = None


class RecallBulkRestoreResponse(BaseModel):
    restored: int = 0
    failed: int = 0
    results: List[RecallBulkRestoreItem] = Field(default_factory=list)


class NoteRecallToggleRequest(BaseModel):
    enabled: bool


class NoteRecallToggleResponse(BaseModel):
    note_id: str
    enabled: bool
    recall_status: str = "off"
    questions_generated: int = 0
    suggestions_total: int = 0


class RecallDecisionRequest(BaseModel):
    feedback: Optional[str] = None


class RecallDecisionResponse(BaseModel):
    status: str
    candidate_id: str
    card: Optional[RecallCardResponse] = None


class RecallReviewResult(BaseModel):
    card: RecallCardResponse
    history: Optional[ReviewHistoryResponse] = None


class RecallGradeRequest(BaseModel):
    grade: ReviewGrade
    elapsed_ms: Optional[int] = Field(default=None, ge=0)
