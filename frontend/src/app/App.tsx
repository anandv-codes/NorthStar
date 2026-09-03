import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChatMessageRecord,
  MemoryQuestion,
  MemoryRisk,
  MemoryTask,
  NoteStatus,
  RecentMemoryResponse,
  createNote,
  fetchQuestions,
  fetchRecentMemory,
  fetchRisks,
  fetchTasks,
  getChatThread,
  getNoteStatus,
  patchQuestionStatus,
  patchRiskStatus,
  patchTaskStatus,
  sendChatMessage,
} from "../shared/api/httpClient";
import { QuestionsSection } from "../features/dashboard/components/QuestionsSection";
import { RecentMemorySection } from "../features/dashboard/components/RecentMemorySection";
import { RisksSection } from "../features/dashboard/components/RisksSection";
import { TasksSection } from "../features/dashboard/components/TasksSection";
import { useAuthorization } from "../shared/auth/useAuthorization";

type Route = "login" | "register" | "dashboard" | "add-note" | "chat";

function getRouteFromHash(): Route {
  const hash = window.location.hash;
  if (hash === "#/login") {
    return "login";
  }
  if (hash === "#/register") {
    return "register";
  }
  if (hash === "#/add-note") {
    return "add-note";
  }
  if (hash === "#/dashboard") {
    return "dashboard";
  }
  return "chat";
}

function getStoredChatThreadId(userId: string) {
  return window.localStorage.getItem(`northstar_chat_thread_${userId}`);
}

function setStoredChatThreadId(userId: string, threadId: string) {
  window.localStorage.setItem(`northstar_chat_thread_${userId}`, threadId);
}

function clearStoredChatThreadId(userId: string) {
  window.localStorage.removeItem(`northstar_chat_thread_${userId}`);
}

interface ChatPageProps {
  userId: string;
  onOpenDashboard: () => void;
}

function ChatPage({ userId, onOpenDashboard }: ChatPageProps) {
  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState<string | null>(() =>
    getStoredChatThreadId(userId),
  );
  const [summary, setSummary] = useState<string | null>(null);
  const [intent, setIntent] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const storedThreadId = getStoredChatThreadId(userId);
    setThreadId(storedThreadId);
    if (!storedThreadId) {
      setMessages([]);
      setSummary(null);
      setIntent(null);
      return;
    }

    let cancelled = false;
    const loadThread = async () => {
      try {
        const thread = await getChatThread(storedThreadId);
        if (cancelled) {
          return;
        }
        setMessages(thread.messages || []);
        setSummary(thread.summary || null);
        setIntent(null);
      } catch {
        if (!cancelled) {
          clearStoredChatThreadId(userId);
          setThreadId(null);
          setMessages([]);
          setSummary(null);
        }
      }
    };

    void loadThread();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  useEffect(() => {
    const container = listRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages, sending]);

  const handleNewChat = useCallback(() => {
    clearStoredChatThreadId(userId);
    setThreadId(null);
    setMessages([]);
    setSummary(null);
    setIntent(null);
    setError(null);
    setInput("");
  }, [userId]);

  const handleSend = useCallback(async () => {
    const content = input.trim();
    if (!content || sending) {
      return;
    }

    setSending(true);
    setError(null);
    setInput("");

    const optimisticUserMessage: ChatMessageRecord = {
      message_id: `local-${Date.now()}`,
      thread_id: threadId || "local",
      user_id: userId,
      role: "user",
      content,
      metadata: {},
      created_at: new Date().toISOString(),
    };

    setMessages((current) => [...current, optimisticUserMessage]);

    try {
      const response = await sendChatMessage({
        message: content,
        thread_id: threadId,
      });

      const nextThreadId = response.thread.thread_id;
      setThreadId(nextThreadId);
      setStoredChatThreadId(userId, nextThreadId);
      setSummary(response.thread.summary || null);
      setIntent(response.intent.kind);
      setMessages(response.thread.messages.length > 0 ? response.thread.messages : [response.user_message, response.assistant_message]);
    } catch {
      setError("Failed to send message.");
      setMessages((current) =>
        current.filter(
          (message) => message.message_id !== optimisticUserMessage.message_id,
        ),
      );
    } finally {
      setSending(false);
    }
  }, [input, sending, threadId, userId]);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#f7f5f2",
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "16px 20px",
          borderBottom: "1px solid #e5e0d8",
          background: "#fff",
        }}
      >
        <div>
          <div style={{ fontWeight: 700 }}>NorthStar Chat</div>
          <div style={{ fontSize: 12, color: "#666" }}>
            {intent ? `Intent: ${intent}` : "Single-pane chat with retrieval"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={onOpenDashboard}>Dashboard</button>
          <button onClick={handleNewChat}>New chat</button>
        </div>
      </header>

      <main
        style={{
          flex: 1,
          display: "flex",
          justifyContent: "center",
          padding: 20,
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: 900,
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          {summary ? (
            <div
              style={{
                padding: 12,
                borderRadius: 12,
                background: "#fff",
                border: "1px solid #e5e0d8",
              }}
            >
              <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>
                Conversation summary
              </div>
              <div style={{ whiteSpace: "pre-wrap" }}>{summary}</div>
            </div>
          ) : null}

          <div
            ref={listRef}
            style={{
              flex: 1,
              minHeight: 420,
              maxHeight: "calc(100vh - 250px)",
              overflowY: "auto",
              padding: 12,
              borderRadius: 16,
              background: "#fff",
              border: "1px solid #e5e0d8",
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            {messages.length === 0 ? (
              <div style={{ color: "#777", padding: 12 }}>
                Ask about your notes, tasks, decisions, or anything you want
                retrieved from memory.
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.message_id}
                  style={{
                    display: "flex",
                    justifyContent:
                      message.role === "user" ? "flex-end" : "flex-start",
                  }}
                >
                  <div
                    style={{
                      maxWidth: "80%",
                      padding: "12px 14px",
                      borderRadius: 16,
                      whiteSpace: "pre-wrap",
                      background: message.role === "user" ? "#111" : "#f0ebe3",
                      color: message.role === "user" ? "#fff" : "#111",
                    }}
                  >
                    {message.content}
                  </div>
                </div>
              ))
            )}
            {sending ? <div style={{ color: "#777" }}>Thinking...</div> : null}
          </div>

          {error ? <div style={{ color: "#b00020" }}>{error}</div> : null}

          <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void handleSend();
                }
              }}
              placeholder="Message NorthStar..."
              rows={3}
              style={{
                flex: 1,
                resize: "none",
                padding: 12,
                borderRadius: 14,
                border: "1px solid #cfc7bc",
                fontFamily: "inherit",
              }}
              disabled={sending}
            />
            <button
              onClick={() => void handleSend()}
              disabled={sending || !input.trim()}
            >
              Send
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

interface AddNotePageProps {
  userId: string;
  onDone: () => Promise<void>;
}

function AddNotePage({ userId, onDone }: AddNotePageProps) {
  const [text, setText] = useState("");
  const [noteId, setNoteId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!noteId) {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const result: NoteStatus = await getNoteStatus(noteId);
        setStatus(result.status);
        if (result.status === "completed") {
          window.clearInterval(interval);
          await onDone();
        } else if (result.status === "failed") {
          setError("Note processing failed.");
          setSubmitting(false);
          window.clearInterval(interval);
        }
      } catch {
        setError("Failed to poll note status.");
        setSubmitting(false);
        window.clearInterval(interval);
      }
    }, 1500);

    return () => window.clearInterval(interval);
  }, [noteId, onDone, userId]);

  const handleSubmit = async () => {
    if (!text.trim()) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setStatus("processing");
    try {
      const result = await createNote({ text: text.trim() });
      setNoteId(result.note_id);
    } catch {
      setError("Failed to submit note.");
      setStatus(null);
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 16, maxWidth: 900, margin: "0 auto" }}>
      <h1>Add Note</h1>
      <p>
        <a href="#/">Back to Dashboard</a>
      </p>
      <textarea
        rows={10}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Write your work note..."
        style={{ width: "100%" }}
        disabled={submitting && status === "processing"}
      />
      <div style={{ marginTop: 12 }}>
        <button
          onClick={() => void handleSubmit()}
          disabled={!text.trim() || (submitting && status === "processing")}
        >
          Submit Note
        </button>
      </div>
      {status && <p>Status: {status}</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}
    </div>
  );
}

interface AuthPageProps {
  onSuccess: (email: string, password: string) => Promise<void>;
}

function LoginPage({ onSuccess }: AuthPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await onSuccess(email.trim(), password);
    } catch {
      setError("Invalid email or password.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 16, maxWidth: 420, margin: "0 auto" }}>
      <h1>Login</h1>
      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        style={{ width: "100%", marginBottom: 8 }}
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        style={{ width: "100%", marginBottom: 12 }}
      />
      <button
        onClick={() => void handleSubmit()}
        disabled={submitting || !email || !password}
      >
        Sign in
      </button>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <p>
        New here? <a href="#/register">Create account</a>
      </p>
    </div>
  );
}

function RegisterPage({ onSuccess }: AuthPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await onSuccess(email.trim(), password);
    } catch {
      setError(
        "Unable to register. Check email uniqueness and password policy.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 16, maxWidth: 420, margin: "0 auto" }}>
      <h1>Register</h1>
      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        style={{ width: "100%", marginBottom: 8 }}
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        style={{ width: "100%", marginBottom: 12 }}
      />
      <button
        onClick={() => void handleSubmit()}
        disabled={submitting || !email || !password}
      >
        Create account
      </button>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <p>
        Already have an account? <a href="#/login">Sign in</a>
      </p>
    </div>
  );
}

function App() {
  const {
    userId,
    isAuthenticated,
    isBootstrapping,
    login,
    register,
    logout,
    bootstrap,
  } = useAuthorization();
  const [route, setRoute] = useState<Route>(() => getRouteFromHash());
  const [tasks, setTasks] = useState<MemoryTask[]>([]);
  const [questions, setQuestions] = useState<MemoryQuestion[]>([]);
  const [risks, setRisks] = useState<MemoryRisk[]>([]);
  const [recentMemory, setRecentMemory] = useState<RecentMemoryResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeQuestionId, setActiveQuestionId] = useState<string | null>(null);
  const [activeRiskId, setActiveRiskId] = useState<string | null>(null);

  const handleLogin = useCallback(
    async (email: string, password: string) => {
      await login(email, password);
      window.location.hash = "#/chat";
      setRoute("chat");
    },
    [login],
  );

  const handleRegister = useCallback(
    async (email: string, password: string) => {
      await register(email, password);
      window.location.hash = "#/chat";
      setRoute("chat");
    },
    [register],
  );

  const handleLogout = useCallback(async () => {
    await logout();
    window.location.hash = "#/login";
    setRoute("login");
  }, [logout]);

  useEffect(() => {
    const onHashChange = () => setRoute(getRouteFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    if (
      !isBootstrapping &&
      !isAuthenticated &&
      (route === "dashboard" || route === "add-note" || route === "chat")
    ) {
      window.location.hash = "#/login";
      setRoute("login");
    }
  }, [isAuthenticated, isBootstrapping, route]);

  const loadDashboard = useCallback(async () => {
    if (!userId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [taskData, questionData, riskData, recentData] = await Promise.all([
        fetchTasks(),
        fetchQuestions(),
        fetchRisks(),
        fetchRecentMemory(10),
      ]);
      setTasks(taskData);
      setQuestions(questionData);
      setRisks(riskData);
      setRecentMemory(recentData);
    } catch {
      setError("Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (!isBootstrapping && route === "dashboard" && userId) {
      void loadDashboard();
    }
  }, [isBootstrapping, loadDashboard, route, userId]);

  const handleAddNoteCompleted = useCallback(async () => {
    window.location.hash = "#/chat";
    setRoute("chat");
    await bootstrap();
    await loadDashboard();
  }, [bootstrap, loadDashboard]);

  const handleTaskDone = async (taskId: string) => {
    if (!userId) {
      return;
    }
    setActiveTaskId(taskId);
    setError(null);
    try {
      await patchTaskStatus(taskId, "completed");
      await loadDashboard();
    } catch {
      setError("Failed to update task status.");
    } finally {
      setActiveTaskId(null);
    }
  };

  const handleToggleQuestion = async (question: MemoryQuestion) => {
    if (!userId) {
      return;
    }
    setActiveQuestionId(question.question_id);
    setError(null);
    const nextStatus = question.status === "open" ? "answered" : "open";
    try {
      await patchQuestionStatus(question.question_id, nextStatus);
      await loadDashboard();
    } catch {
      setError("Failed to update question status.");
    } finally {
      setActiveQuestionId(null);
    }
  };

  const handleToggleRisk = async (risk: MemoryRisk) => {
    if (!userId) {
      return;
    }
    setActiveRiskId(risk.risk_id);
    setError(null);
    const nextStatus = risk.status === "resolved" ? "open" : "resolved";
    try {
      await patchRiskStatus(risk.risk_id, nextStatus);
      await loadDashboard();
    } catch {
      setError("Failed to update risk status.");
    } finally {
      setActiveRiskId(null);
    }
  };

  if (isBootstrapping && (route === "dashboard" || route === "add-note" || route === "chat")) {
    return (
      <div style={{ padding: 16, maxWidth: 420, margin: "0 auto" }}>
        Loading session...
      </div>
    );
  }

  if (!isAuthenticated && route !== "register") {
    return <LoginPage onSuccess={handleLogin} />;
  }

  if (!isAuthenticated && route === "register") {
    return <RegisterPage onSuccess={handleRegister} />;
  }

  if (route === "chat" && userId) {
    return (
      <ChatPage
        userId={userId}
        onOpenDashboard={() => {
          window.location.hash = "#/dashboard";
          setRoute("dashboard");
        }}
      />
    );
  }

  if (route === "add-note" && userId) {
    return <AddNotePage userId={userId} onDone={handleAddNoteCompleted} />;
  }

  return (
    <div style={{ padding: 16, maxWidth: 900, margin: "0 auto" }}>
      <h1>NorthStar Dashboard</h1>
      <p>
        <a href="#/chat">Chat</a>
        {" | "}
        <a href="#/add-note">Add Note</a>
      </p>
      <button onClick={() => void loadDashboard()} disabled={loading}>
        Refresh
      </button>
      <button onClick={() => void handleLogout()} style={{ marginLeft: 8 }}>
        Logout
      </button>
      {loading && <p>Loading...</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}

      <TasksSection
        tasks={tasks}
        onMarkDone={handleTaskDone}
        activeTaskId={activeTaskId}
      />
      <QuestionsSection
        questions={questions}
        onToggleStatus={handleToggleQuestion}
        activeQuestionId={activeQuestionId}
      />
      <RisksSection
        risks={risks}
        onToggleResolved={handleToggleRisk}
        activeRiskId={activeRiskId}
      />
      <RecentMemorySection recentMemory={recentMemory} />
    </div>
  );
}

export default App;
