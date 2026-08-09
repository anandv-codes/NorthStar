const BASE_URL = "http://localhost:8000";
const ACCESS_TOKEN_KEY = "northstar_access_token";
const REFRESH_TOKEN_KEY = "northstar_refresh_token";
const USER_ID_KEY = "northstar_user_id";

export interface CreateNotePayload {
  user_id: string;
  text: string;
}

export interface NoteStatus {
  note_id: string;
  user_id: string;
  status: string;
  created_at: string;
  raw_text: string;
  enriched_summary?: string;
  action_items?: string[];
  questions?: string[];
  insights?: string[];
  concepts?: string[];
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
}

export interface RecentMemoryResponse {
  notes: RecentNote[];
  decisions: MemoryDecision[];
  tasks: MemoryTask[];
  questions: MemoryQuestion[];
  risks: MemoryRisk[];
  concepts: MemoryConcept[];
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
  user_id: string;
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
    throw new Error(`Request failed: ${response.status}`);
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
    throw new Error(`Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function registerUser(email: string, password: string) {
  return requestJsonWithoutAuth<AuthTokens>(`${BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function loginUser(email: string, password: string) {
  return requestJsonWithoutAuth<AuthTokens>(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function refreshSession() {
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
  return requestJson<UserProfile>(`${BASE_URL}/auth/me`);
}

export async function createNote(payload: CreateNotePayload) {
  console.debug("[API] Submitting note for user:", payload.user_id);
  const result = requestJson<{ note_id: string; status: string }>(
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

export async function getNoteStatus(user_id: string, note_id: string) {
  console.debug("[API] Polling note status:", note_id);
  return requestJson<NoteStatus>(
    `${BASE_URL}/notes/${note_id}?user_id=${encodeURIComponent(user_id)}`,
  );
}

export async function getNoteMemory(user_id: string, note_id: string) {
  console.debug("[API] Loading note memory:", note_id);
  return requestJson<NoteMemoryResponse>(
    `${BASE_URL}/notes/${note_id}/memory?user_id=${encodeURIComponent(user_id)}`,
  );
}

export async function fetchTasks(userId: string, status?: string) {
  const query = status ? `&status=${encodeURIComponent(status)}` : "";
  return requestJson<MemoryTask[]>(
    `${BASE_URL}/tasks?user_id=${encodeURIComponent(userId)}${query}`,
  );
}

export async function fetchQuestions(userId: string, status?: string) {
  const query = status ? `&status=${encodeURIComponent(status)}` : "";
  return requestJson<MemoryQuestion[]>(
    `${BASE_URL}/questions?user_id=${encodeURIComponent(userId)}${query}`,
  );
}

export async function fetchRisks(userId: string, status?: string) {
  const query = status ? `&status=${encodeURIComponent(status)}` : "";
  return requestJson<MemoryRisk[]>(
    `${BASE_URL}/risks?user_id=${encodeURIComponent(userId)}${query}`,
  );
}

export async function fetchRecentMemory(userId: string, limit = 10) {
  return requestJson<RecentMemoryResponse>(
    `${BASE_URL}/memory/recent?user_id=${encodeURIComponent(userId)}&limit=${limit}`,
  );
}

export async function retrieveQueryContext(
  userId: string,
  query: string,
  limit = 5,
) {
  return requestJson<QueryRetrievalResponse>(`${BASE_URL}/retrieval/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, query, limit }),
  });
}

export async function sendChatMessage(payload: ChatMessageRequest) {
  return requestJson<ChatMessageResponse>(`${BASE_URL}/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getChatThread(userId: string, threadId: string) {
  return requestJson<ChatThread>(
    `${BASE_URL}/chat/threads/${encodeURIComponent(threadId)}?user_id=${encodeURIComponent(userId)}`,
  );
}

export async function patchTaskStatus(
  userId: string,
  taskId: string,
  status: MemoryTask["status"],
) {
  return requestJson<MemoryTask>(
    `${BASE_URL}/tasks/${taskId}?user_id=${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    },
  );
}

export async function patchQuestionStatus(
  userId: string,
  questionId: string,
  status: MemoryQuestion["status"],
) {
  return requestJson<MemoryQuestion>(
    `${BASE_URL}/questions/${questionId}?user_id=${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    },
  );
}

export async function patchRiskStatus(
  userId: string,
  riskId: string,
  status: MemoryRisk["status"],
) {
  return requestJson<MemoryRisk>(
    `${BASE_URL}/risks/${riskId}?user_id=${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    },
  );
}
