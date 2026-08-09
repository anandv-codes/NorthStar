from datetime import datetime
from typing import Any, Dict, Literal, Optional, List
from pydantic import BaseModel, Field

class NoteCreateRequest(BaseModel):
    user_id: str = Field(..., description="User ID for the note")
    text: str = Field(..., min_length=1, description="Raw note text")
    metadata: Optional[dict] = Field(default_factory=dict)

class NoteStatusResponse(BaseModel):
    note_id: str
    user_id: str
    status: str
    created_at: datetime
    raw_text: str
    enriched_summary: Optional[str] = None
    action_items: Optional[List[str]] = None
    questions: Optional[List[str]] = None
    insights: Optional[List[str]] = None
    concepts: Optional[List[str]] = None


TaskStatus = Literal["open", "in_progress", "completed", "archived"]
QuestionStatus = Literal["open", "answered", "archived"]
RiskStatus = Literal["open", "mitigated", "resolved", "archived"]
RiskSeverity = Literal["low", "medium", "high"]
ConceptStatus = Literal["open", "learned", "archived"]
CreatedBy = Literal["llm", "user", "system"]


class ExtractedEntity(BaseModel):
    name: str = Field(..., min_length=1)
    entity_type: Optional[str] = None


class ExtractedTask(BaseModel):
    description: str = Field(..., min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    entities: List[str] = Field(default_factory=list)


class ExtractedFact(BaseModel):
    content: str = Field(..., min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
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


class ExtractedRisk(BaseModel):
    risk: str = Field(..., min_length=1)
    severity: Optional[RiskSeverity] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    entities: List[str] = Field(default_factory=list)
class ExtractedConcept(BaseModel):
    concept:str = Field(..., min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    entities: List[str] = Field(default_factory=list)

class WorkMemoryExtraction(BaseModel):
    summary: str = ""
    tasks: List[ExtractedTask] = Field(default_factory=list)
    facts: List[ExtractedFact] = Field(default_factory=list)
    questions: List[ExtractedQuestion] = Field(default_factory=list)
    decisions: List[ExtractedDecision] = Field(default_factory=list)
    risks: List[ExtractedRisk] = Field(default_factory=list)
    entities: List[ExtractedEntity] = Field(default_factory=list)
    concepts: List[ExtractedConcept] = Field(default_factory=list)


class TaskUpdateRequest(BaseModel):
    status: Optional[TaskStatus] = None
    description: Optional[str] = Field(default=None, min_length=1)


class QuestionUpdateRequest(BaseModel):
    status: QuestionStatus


class RiskUpdateRequest(BaseModel):
    status: RiskStatus

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


class RiskResponse(SourceRef):
    risk_id: str
    user_id: str
    risk: str
    severity: Optional[RiskSeverity] = None
    status: RiskStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None

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
    risks: List[RiskResponse] = Field(default_factory=list)
    concepts: List[ConceptResponse] = Field(default_factory=list)
    entities: List[ExtractedEntity] = Field(default_factory=list)


class RecentMemoryResponse(BaseModel):
    notes: List[RecentNoteResponse] = Field(default_factory=list)
    decisions: List[DecisionResponse] = Field(default_factory=list)
    tasks: List[TaskResponse] = Field(default_factory=list)
    questions: List[QuestionResponse] = Field(default_factory=list)
    risks: List[RiskResponse] = Field(default_factory=list)
    concepts: List[ConceptResponse] = Field(default_factory=list)


class QueryRetrievalRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
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
    candidates: List[QueryRetrievalCandidate] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
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


class ChatMessageResponse(BaseModel):
    thread: ChatThreadResponse
    user_message: ChatMessageRecordResponse
    assistant_message: ChatMessageRecordResponse
    intent: ChatIntentResponse
    routing: Optional[ChatRoutingResponse] = None
    plan: List[ChatPlanActionResponse] = Field(default_factory=list)
    knowledge_error: Optional[str] = None
    grounding: Optional[GroundingResponse] = None


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    is_active: bool = True
