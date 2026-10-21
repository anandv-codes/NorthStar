// Vite inlines this at build time; set VITE_API_BASE_URL in the deployment
// environment (see frontend/.env.example) so the bundle talks to the real API.
const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/+$/, "");
const ACCESS_TOKEN_KEY = "northstar_access_token";
const REFRESH_TOKEN_KEY = "northstar_refresh_token";
const USER_ID_KEY = "northstar_user_id";

// Local-only escape hatch for visual QA without a running backend (see frontend/src/mock/).
// The specifier is kept out of a string literal so neither tsc nor the bundler
// resolve it at build time when the (gitignored) mock folder doesn't exist.
const MOCK_MODE = import.meta.env.VITE_MOCK_MODE === "true";
const mockModuleSpecifier = ["..", "..", "mock", "mockApi"].join("/");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let mockApiPromise: Promise<any> | null = null;
function loadMockApi() {
  if (!mockApiPromise) {
    mockApiPromise = import(/* @vite-ignore */ mockModuleSpecifier).catch(() => {
      mockApiPromise = null;
      throw new Error(
        "VITE_MOCK_MODE is enabled but frontend/src/mock/mockApi.ts is missing. Create it or unset VITE_MOCK_MODE.",
      );
    });
  }
  return mockApiPromise;
}

export interface CreateNotePayload {
  text: string;
  recall_enabled?: boolean;
}

export interface NoteStatus {
  note_id: string;
  user_id: string;
  status: string;
  created_at: string;
  raw_text: string;
  enriched_summary?: string;
  context_note_ids?: string[];
  action_items?: string[];
  questions?: string[];
  insights?: string[];
  concepts?: string[];
  recall_enabled?: boolean;
  recall_status?: string;
}

export interface ExtractionRun {
  extraction_run_id: string;
  note_id: string;
  user_id: string;
  model_name: string;
  prompt_version: string;
  status: string;
  error_message?: string | null;
  created_at: string;
}

export interface MemoryEntity {
  entity_id: string;
  user_id: string;
  name: string;
  entity_type?: string | null;
  created_at: string;
}

export interface MemoryTask {
  task_id: string;
  user_id: string;
  source_note_id: string;
  extraction_run_id?: string | null;
  description: string;
  status: string;
  created_by: string;
  confidence?: number | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface MemoryFact {
  fact_id: string;
  user_id: string;
  source_note_id: string;
  extraction_run_id?: string | null;
  content: string;
  created_by: string;
  confidence?: number | null;
  created_at: string;
}

export interface MemoryQuestion {
  question_id: string;
  user_id: string;
  source_note_id: string;
  extraction_run_id?: string | null;
  question: string;
  status: string;
  answer?: string | null;
  created_by: string;
  confidence?: number | null;
  created_at: string;
  resolved_at?: string | null;
}

export interface MemoryDecision {
  decision_id: string;
  user_id: string;
  source_note_id: string;
  extraction_run_id?: string | null;
  decision: string;
  rationale?: string | null;
  created_by: string;
  confidence?: number | null;
  created_at: string;
}

export interface MemoryRisk {
  risk_id: string;
  user_id: string;
  source_note_id: string;
  extraction_run_id?: string | null;
  risk: string;
  severity?: string | null;
  status: string;
  created_by: string;
  confidence?: number | null;
  created_at: string;
  resolved_at?: string | null;
}

export interface NoteMemoryResponse {
  note: NoteStatus;
  extraction_run?: ExtractionRun | null;
  tasks: MemoryTask[];
  facts: MemoryFact[];
  questions: MemoryQuestion[];
  decisions: MemoryDecision[];
  risks: MemoryRisk[];
  entities: MemoryEntity[];
}

export interface MemoryConcept {
  concept_id: string;
  user_id: string;
  source_note_id: string;
  extraction_run_id?: string | null;
  concept: string;
  status: string;
  created_by: string;
  confidence?: number | null;
  created_at: string;
}

export interface RecentNote {
  note_id: string;
  user_id: string;
  status: string;
  created_at: string;
  raw_text: string;
  enriched_summary?: string | null;
  context_note_ids?: string[];
  recall_enabled?: boolean;
  recall_status?: string;
}

export interface RecentMemoryResponse {
  notes: RecentNote[];
  decisions: MemoryDecision[];
  tasks: MemoryTask[];
  questions: MemoryQuestion[];
  risks: MemoryRisk[];
  concepts: MemoryConcept[];
}

export interface NoteActivityDay {
  /** ISO date, YYYY-MM-DD */
  date: string;
  count: number;
}

export type PeriodType = "daily" | "weekly";

export interface PeriodSummary {
  summary_id: string;
  user_id: string;
  period_type: PeriodType;
  period_start: string;
  period_end: string;
  narrative: string;
  stats: Record<string, number>;
  source_note_count: number;
  generated_at: string;
}

export interface PeriodSummaryStatus {
  status: "ready" | "insufficient_data" | "not_generated";
  summary?: PeriodSummary | null;
  notes_count: number;
  min_notes_required: number;
}

export type RecallGrade = 1 | 3 | 4 | 5;

export type RecallDeckColor = "neutral" | "amber" | "emerald" | "sky" | "violet" | "rose";

export interface RecallDeck {
  deck_id: string;
  user_id: string;
  name: string;
  description?: string | null;
  color: RecallDeckColor;
  is_default: boolean;
  sort_order: number;
  archived_at?: string | null;
  created_at: string;
  updated_at: string;
  total_cards: number;
  due_cards: number;
  new_cards: number;
  suspended_cards: number;
}

export interface RecallDeckList {
  decks: RecallDeck[];
  total: number;
}

export interface RecallDeckPayload {
  name: string;
  description?: string | null;
  color?: RecallDeckColor;
}

export interface RecallSuggestion {
  candidate_id: string;
  question: string;
  answer?: string | null;
  item_type: string;
  source_note_id?: string | null;
  deck_id?: string | null;
  score?: number | null;
  importance?: number | null;
  durability?: number | null;
  created_at?: string | null;
}

export interface RecallSuggestionList {
  suggestions: RecallSuggestion[];
  total: number;
}

export interface RecallSuggestionUpdate {
  question?: string;
  answer?: string;
  deck_id?: string | null;
}

export interface RecallBulkAcceptItem {
  candidate_id: string;
  status: string;
  card?: RecallCard | null;
  error?: string | null;
}

export interface RecallBulkAcceptResponse {
  accepted: number;
  failed: number;
  results: RecallBulkAcceptItem[];
}

export interface RecallCard {
  card_id: string;
  user_id: string;
  candidate_id?: string | null;
  deck_id?: string | null;
  question: string;
  answer: string;
  source_note_ids: string[];
  entity_ids: string[];
  status: string;
  state: string;
  learning_step: number;
  interval: number;
  easiness: number;
  repetitions: number;
  lapses: number;
  review_count: number;
  last_reviewed?: string | null;
  next_due?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DueCardsResponse {
  cards: RecallCard[];
  total_due: number;
}

export interface RecallCardList {
  cards: RecallCard[];
  total: number;
}

export interface RecallDecisionResponse {
  status: string;
  candidate_id: string;
  card?: RecallCard | null;
}

export interface ReviewHistory {
  review_id: string;
  card_id: string;
  grade: number;
  reviewed_at: string;
  previous_interval?: number | null;
  new_interval?: number | null;
  previous_easiness?: number | null;
  new_easiness?: number | null;
  elapsed_ms?: number | null;
}

export interface RecallReviewResult {
  card: RecallCard;
  history?: ReviewHistory | null;
}

export interface NoteRecallToggleResponse {
  note_id: string;
  enabled: boolean;
  recall_status: string;
  questions_generated: number;
  suggestions_total: number;
}

export interface QueryRetrievalCandidate {
  note_id: string;
  text: string;
  summary?: string | null;
  sparse_distance?: number | null;
  sparse_rank?: number | null;
  original_distance?: number | null;
  original_rank?: number | null;
  rewritten_distance?: number | null;
  rewritten_rank?: number | null;
  rrf_score?: number | null;
  rerank_score?: number | null;
  score: number;
}

export interface QueryRetrievalResponse {
  original_query: string;
  rewritten_query?: string | null;
  likely_answer?: string | null;
  rewrite_confidence?: number | null;
  rewrite_used: boolean;
  fallback_reason?: string | null;
  rerank_used: boolean;
  rerank_strategy?: string | null;
  candidates: QueryRetrievalCandidate[];
}

export interface ChatMessageRequest {
  message: string;
  thread_id?: string | null;
}

export interface ChatPlanAction {
  name: string;
  description: string;
  enabled: boolean;
  metadata: Record<string, string>;
}

export interface ChatIntent {
  kind: string;
  confidence: number;
  needs_retrieval: boolean;
  needs_tools: boolean;
  direct_answer: boolean;
  reasons: string[];
}

export interface ChatRouting {
  route: "direct" | "retrieval" | "tool" | "mixed" | "abstain";
  confidence: number;
  allow_answer: boolean;
  reasons: string[];
  source_refs: string[];
  fallback_message?: string | null;
}

export interface GroundingEvidence {
  source_type: string;
  source_id: string;
  source_ref: string;
  excerpt: string;
  claim?: string | null;
  authority: number;
  recency: number;
  retrieval_score: number;
  overlap: number;
  weight: number;
}

export interface GroundingResponse {
  status: "strong" | "weak" | "conflict" | "no_context";
  confidence: number;
  allow_answer: boolean;
  top_claim?: string | null;
  summary: string;
  source_refs: string[];
  evidence: GroundingEvidence[];
  fallback_message?: string | null;
}

export interface ChatMessageRecord {
  message_id: string;
  thread_id: string;
  user_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  intent?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ChatThread {
  thread_id: string;
  user_id: string;
  title?: string | null;
  summary?: string | null;
  summary_updated_at?: string | null;
  created_at: string;
  updated_at: string;
  messages: ChatMessageRecord[];
}

export interface ChatMessageResponse {
  thread: ChatThread;
  user_message: ChatMessageRecord;
  assistant_message: ChatMessageRecord;
  intent: ChatIntent;
  routing?: ChatRouting | null;
  plan: ChatPlanAction[];
  knowledge_error?: string | null;
  grounding?: GroundingResponse | null;
  pending_action?: { pending_action_id: string; tool_name: string; description: string } | null;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: string;
  email: string;
}

export interface UserProfile {
  user_id: string;
  email: string;
  is_active: boolean;
}

export function getStoredAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getStoredUserId() {
  return localStorage.getItem(USER_ID_KEY);
}

export function setAuthTokens(tokens: AuthTokens) {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  localStorage.setItem(USER_ID_KEY, tokens.user_id);
}

export function clearAuthTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_ID_KEY);
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      return body.detail;
    }
  } catch {
    // Response body wasn't JSON; fall through to the generic message.
  }
  return `Request failed: ${response.status}`;
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  const accessToken = getStoredAccessToken();
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  let response = await fetch(url, { ...init, headers });

  if (response.status === 401 && getStoredRefreshToken()) {
    try {
      const refreshed = await refreshSession();
      setAuthTokens(refreshed);
      headers.set("Authorization", `Bearer ${refreshed.access_token}`);
      response = await fetch(url, { ...init, headers });
    } catch {
      clearAuthTokens();
      throw new Error("Session expired");
    }
  }

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function requestJsonWithoutAuth<T>(
  url: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function registerUser(email: string, password: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).registerUser(email, password) as Promise<AuthTokens>;
  }
  return requestJsonWithoutAuth<AuthTokens>(`${BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function loginUser(email: string, password: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).loginUser(email, password) as Promise<AuthTokens>;
  }
  return requestJsonWithoutAuth<AuthTokens>(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function refreshSession() {
  if (MOCK_MODE) {
    return (await loadMockApi()).refreshSession() as Promise<AuthTokens>;
  }
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }
  return requestJsonWithoutAuth<AuthTokens>(`${BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function logoutUser() {
  if (MOCK_MODE) {
    return (await loadMockApi()).logoutUser() as Promise<void>;
  }
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    return;
  }
  await requestJsonWithoutAuth<void>(`${BASE_URL}/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function fetchCurrentUser() {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchCurrentUser() as Promise<UserProfile>;
  }
  return requestJson<UserProfile>(`${BASE_URL}/auth/me`);
}

export async function createNote(payload: CreateNotePayload) {
  if (MOCK_MODE) {
    return (await loadMockApi()).createNote(payload) as Promise<{ note_id: string; status: string }>;
  }
  console.debug("[API] Submitting note:", payload.text);
  const result = await requestJson<{ note_id: string; status: string }>(
    `${BASE_URL}/notes`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  console.debug("[API] Note created:", result);
  return result;
}

export async function getNoteStatus(note_id: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).getNoteStatus(note_id) as Promise<NoteStatus>;
  }
  console.debug("[API] Polling note status:", note_id);
  return requestJson<NoteStatus>(`${BASE_URL}/notes/${note_id}`);
}

export async function getNoteMemory(note_id: string) {
  console.debug("[API] Loading note memory:", note_id);
  return requestJson<NoteMemoryResponse>(
    `${BASE_URL}/notes/${note_id}/memory`,
  );
}

export async function fetchTasks(status?: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchTasks(status) as Promise<MemoryTask[]>;
  }
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return requestJson<MemoryTask[]>(`${BASE_URL}/tasks${query}`);
}

export async function fetchQuestions(status?: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchQuestions(status) as Promise<MemoryQuestion[]>;
  }
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return requestJson<MemoryQuestion[]>(`${BASE_URL}/questions${query}`);
}

export async function fetchRisks(status?: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchRisks(status) as Promise<MemoryRisk[]>;
  }
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return requestJson<MemoryRisk[]>(`${BASE_URL}/risks${query}`);
}

export async function fetchConcepts(status?: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchConcepts(status) as Promise<MemoryConcept[]>;
  }
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return requestJson<MemoryConcept[]>(`${BASE_URL}/concepts${query}`);
}

export async function fetchRecentMemory(limit = 10) {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchRecentMemory(limit) as Promise<RecentMemoryResponse>;
  }
  return requestJson<RecentMemoryResponse>(
    `${BASE_URL}/memory/recent?limit=${limit}`,
  );
}

// There is no dedicated backend aggregate endpoint for this yet, so the real-mode
// path derives current-month counts client-side from the most recent notes
// (capped at 50 by the API) — best-effort until a proper endpoint exists.
export async function fetchNoteActivity(): Promise<NoteActivityDay[]> {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchNoteActivity() as Promise<NoteActivityDay[]>;
  }
  const recent = await fetchRecentMemory(50);
  const now = new Date();
  const counts = new Map<string, number>();
  for (const note of recent.notes) {
    const created = new Date(note.created_at);
    if (created.getFullYear() === now.getFullYear() && created.getMonth() === now.getMonth()) {
      const key = created.toISOString().slice(0, 10);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries()).map(([date, count]) => ({ date, count }));
}

export async function fetchDailySummary(date?: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchDailySummary(date) as Promise<PeriodSummaryStatus>;
  }
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  return requestJson<PeriodSummaryStatus>(`${BASE_URL}/summaries/daily${query}`);
}

export async function generateDailySummary(regenerate = false, date?: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).generateDailySummary(regenerate, date) as Promise<PeriodSummaryStatus>;
  }
  return requestJson<PeriodSummaryStatus>(`${BASE_URL}/summaries/daily/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ period_start: date ?? null, regenerate }),
  });
}

export async function fetchWeeklySummary(date?: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchWeeklySummary(date) as Promise<PeriodSummaryStatus>;
  }
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  return requestJson<PeriodSummaryStatus>(`${BASE_URL}/summaries/weekly${query}`);
}

export async function generateWeeklySummary(regenerate = false, date?: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).generateWeeklySummary(regenerate, date) as Promise<PeriodSummaryStatus>;
  }
  return requestJson<PeriodSummaryStatus>(`${BASE_URL}/summaries/weekly/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ period_start: date ?? null, regenerate }),
  });
}

export async function retrieveQueryContext(query: string, limit = 5) {
  return requestJson<QueryRetrievalResponse>(`${BASE_URL}/retrieval/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });
}

export async function sendChatMessage(payload: ChatMessageRequest) {
  if (MOCK_MODE) {
    return (await loadMockApi()).sendChatMessage(payload) as Promise<ChatMessageResponse>;
  }
  return requestJson<ChatMessageResponse>(`${BASE_URL}/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getChatThread(threadId: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).getChatThread(threadId) as Promise<ChatThread>;
  }
  return requestJson<ChatThread>(
    `${BASE_URL}/chat/threads/${encodeURIComponent(threadId)}`,
  );
}

export async function patchTaskStatus(
  taskId: string,
  status: MemoryTask["status"],
) {
  if (MOCK_MODE) {
    return (await loadMockApi()).patchTaskStatus(taskId, status) as Promise<MemoryTask>;
  }
  return requestJson<MemoryTask>(`${BASE_URL}/tasks/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export async function patchQuestionStatus(
  questionId: string,
  status: MemoryQuestion["status"],
) {
  if (MOCK_MODE) {
    return (await loadMockApi()).patchQuestionStatus(questionId, status) as Promise<MemoryQuestion>;
  }
  return requestJson<MemoryQuestion>(`${BASE_URL}/questions/${questionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export async function patchRiskStatus(
  riskId: string,
  status: MemoryRisk["status"],
) {
  if (MOCK_MODE) {
    return (await loadMockApi()).patchRiskStatus(riskId, status) as Promise<MemoryRisk>;
  }
  return requestJson<MemoryRisk>(`${BASE_URL}/risks/${riskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export async function patchConceptStatus(
  conceptId: string,
  status: MemoryConcept["status"],
) {
  return requestJson<MemoryConcept>(`${BASE_URL}/concepts/${conceptId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export async function fetchDueCards(limit = 50, deckId?: string | null) {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchDueCards(limit, deckId) as Promise<DueCardsResponse>;
  }
  const params = new URLSearchParams({ limit: String(limit) });
  if (deckId) params.set("deck_id", deckId);
  return requestJson<DueCardsResponse>(`${BASE_URL}/recall/due?${params}`);
}

export async function fetchSuggestions(limit = 50, sourceNoteId?: string | null) {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchSuggestions(limit, sourceNoteId) as Promise<RecallSuggestionList>;
  }
  const params = new URLSearchParams({ status: "suggested", limit: String(limit) });
  if (sourceNoteId) params.set("source_note_id", sourceNoteId);
  return requestJson<RecallSuggestionList>(`${BASE_URL}/recall/candidates?${params}`);
}

export async function fetchRecallDecks(includeArchived = false) {
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchRecallDecks(includeArchived) as Promise<RecallDeckList>;
  }
  const params = new URLSearchParams();
  if (includeArchived) params.set("include_archived", "true");
  const query = params.toString();
  return requestJson<RecallDeckList>(`${BASE_URL}/recall/decks${query ? `?${query}` : ""}`);
}

export async function createRecallDeck(payload: RecallDeckPayload) {
  if (MOCK_MODE) {
    return (await loadMockApi()).createRecallDeck(payload) as Promise<RecallDeck>;
  }
  return requestJson<RecallDeck>(`${BASE_URL}/recall/decks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateRecallDeck(deckId: string, payload: Partial<RecallDeckPayload>) {
  if (MOCK_MODE) {
    return (await loadMockApi()).updateRecallDeck(deckId, payload) as Promise<RecallDeck>;
  }
  return requestJson<RecallDeck>(`${BASE_URL}/recall/decks/${encodeURIComponent(deckId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function archiveRecallDeck(deckId: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).archiveRecallDeck(deckId) as Promise<RecallDeck>;
  }
  return requestJson<RecallDeck>(`${BASE_URL}/recall/decks/${encodeURIComponent(deckId)}`, {
    method: "DELETE",
  });
}

export async function restoreRecallDeck(deckId: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).restoreRecallDeck(deckId) as Promise<RecallDeck>;
  }
  return requestJson<RecallDeck>(
    `${BASE_URL}/recall/decks/${encodeURIComponent(deckId)}/restore`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) },
  );
}

export async function fetchRecallCards(options: {
  deckId?: string | null;
  includeNotDue?: boolean;
  status?: string;
  limit?: number;
} = {}) {
  const { deckId, includeNotDue = false, status = "active", limit = 200 } = options;
  if (MOCK_MODE) {
    return (await loadMockApi()).fetchRecallCards(options) as Promise<RecallCardList>;
  }
  const params = new URLSearchParams({ status, limit: String(limit) });
  if (deckId) params.set("deck_id", deckId);
  if (includeNotDue) params.set("include_not_due", "true");
  return requestJson<RecallCardList>(`${BASE_URL}/recall/cards?${params}`);
}

export async function moveRecallCard(cardId: string, deckId: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).moveRecallCard(cardId, deckId) as Promise<RecallCard>;
  }
  return requestJson<RecallCard>(`${BASE_URL}/recall/cards/${encodeURIComponent(cardId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ deck_id: deckId }),
  });
}

export async function assignCandidateDecks(candidateIds: string[], deckId: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).assignCandidateDecks(candidateIds, deckId) as Promise<RecallSuggestionList>;
  }
  return requestJson<RecallSuggestionList>(`${BASE_URL}/recall/candidates/assign-deck`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_ids: candidateIds, deck_id: deckId }),
  });
}

export async function updateSuggestion(candidateId: string, payload: RecallSuggestionUpdate) {
  if (MOCK_MODE) {
    return (await loadMockApi()).updateSuggestion(candidateId, payload) as Promise<RecallSuggestion>;
  }
  return requestJson<RecallSuggestion>(
    `${BASE_URL}/recall/candidates/${encodeURIComponent(candidateId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export async function acceptSuggestions(candidateIds: string[], deckId?: string | null) {
  if (MOCK_MODE) {
    return (await loadMockApi()).acceptSuggestions(candidateIds, deckId) as Promise<RecallBulkAcceptResponse>;
  }
  return requestJson<RecallBulkAcceptResponse>(`${BASE_URL}/recall/candidates/accept-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_ids: candidateIds, deck_id: deckId ?? null }),
  });
}

export async function acceptSuggestion(candidateId: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).acceptSuggestion(candidateId) as Promise<RecallDecisionResponse>;
  }
  return requestJson<RecallDecisionResponse>(
    `${BASE_URL}/recall/candidates/${encodeURIComponent(candidateId)}/accept`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
}

/**
 * Generate (or fetch) a suggestion's answer on demand.
 *
 * Answers are no longer generated while the note is processed: the first
 * "Show answer" (or accepting the suggestion) triggers generation.
 */
export async function revealSuggestionAnswer(candidateId: string) {
  if (MOCK_MODE) {
    const api = await loadMockApi();
    if (typeof api.revealSuggestionAnswer === "function") {
      return api.revealSuggestionAnswer(candidateId) as Promise<RecallSuggestion>;
    }
    return null;
  }
  return requestJson<RecallSuggestion>(
    `${BASE_URL}/recall/candidates/${encodeURIComponent(candidateId)}/answer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
}

export async function rejectSuggestion(candidateId: string, feedback?: string) {
  if (MOCK_MODE) {
    return (await loadMockApi()).rejectSuggestion(candidateId, feedback) as Promise<RecallDecisionResponse>;
  }
  return requestJson<RecallDecisionResponse>(
    `${BASE_URL}/recall/candidates/${encodeURIComponent(candidateId)}/reject`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedback: feedback ?? null }),
    },
  );
}

export async function reviewCard(
  cardId: string,
  grade: RecallGrade,
  elapsedMs?: number,
) {
  if (MOCK_MODE) {
    return (await loadMockApi()).reviewCard(cardId, grade, elapsedMs) as Promise<RecallReviewResult>;
  }
  return requestJson<RecallReviewResult>(
    `${BASE_URL}/recall/cards/${encodeURIComponent(cardId)}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grade, elapsed_ms: elapsedMs ?? null }),
    },
  );
}

export async function setNoteRecall(noteId: string, enabled: boolean) {
  if (MOCK_MODE) {
    return (await loadMockApi()).setNoteRecall(noteId, enabled) as Promise<NoteRecallToggleResponse>;
  }
  return requestJson<NoteRecallToggleResponse>(
    `${BASE_URL}/notes/${encodeURIComponent(noteId)}/recall`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    },
  );
}
