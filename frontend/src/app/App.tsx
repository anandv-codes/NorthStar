import { useCallback, useEffect, useState } from "react";
import { NoteStatus, createNote, getNoteStatus } from "../shared/api/httpClient";
import { AppNav, NavRoute } from "../shared/ui/AppNav";
import { useAuthorization } from "../shared/auth/useAuthorization";
import { TodayPage } from "../features/today/TodayPage";
import { ReviewPage } from "../features/review/ReviewPage";
import { NotesPage } from "../features/notes/NotesPage";
import { NoteDetailPage } from "../features/notes/NoteDetailPage";
import { AskPage } from "../features/ask/AskPage";

type Route = "login" | "register" | "today" | "review" | "notes" | "capture" | "ask";

function getRouteFromHash(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "");
  const path = hash.split("/")[0] || "today";
  switch (path) {
    case "login":
      return "login";
    case "register":
      return "register";
    case "review":
      return "review";
    case "notes":
      return "notes";
    case "capture":
    case "add-note":
      return "capture";
    case "ask":
    case "chat":
      return "ask";
    case "today":
    case "dashboard":
    default:
      return "today";
  }
}

function getNoteIdFromHash(): string | null {
  const parts = window.location.hash.replace(/^#\/?/, "").split("/");
  if (parts[0] === "notes" && parts[1]) {
    return decodeURIComponent(parts[1]);
  }
  return null;
}

function getReviewTabFromHash(): "due" | "suggested" {
  const parts = window.location.hash.replace(/^#\/?/, "").split("/");
  return parts[1] === "suggested" ? "suggested" : "due";
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid email or password.");
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
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to register. Check email uniqueness and password policy.",
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

function CapturePage({ onDone }: { onDone: () => Promise<void> }) {
  const [text, setText] = useState("");
  const [noteId, setNoteId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!noteId) {
      return;
    }

    const maxAttempts = 40; // ~1 minute at 1.5s intervals before giving up
    let attempts = 0;

    const interval = window.setInterval(async () => {
      attempts += 1;
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
        } else if (attempts >= maxAttempts) {
          setError(
            "Note is taking longer than expected. Check back on Today later.",
          );
          setSubmitting(false);
          window.clearInterval(interval);
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to poll note status.",
        );
        setSubmitting(false);
        window.clearInterval(interval);
      }
    }, 1500);

    return () => window.clearInterval(interval);
  }, [noteId, onDone]);

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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit note.");
      setStatus(null);
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 16, maxWidth: 900, margin: "0 auto" }}>
      <h1>Capture</h1>
      <textarea
        rows={10}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Write your work note..."
        style={{ width: "100%", boxSizing: "border-box" }}
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
  const [noteId, setNoteId] = useState<string | null>(() => getNoteIdFromHash());
  const [reviewTab, setReviewTab] = useState<"due" | "suggested">(() =>
    getReviewTabFromHash(),
  );

  const syncFromHash = useCallback(() => {
    setRoute(getRouteFromHash());
    setNoteId(getNoteIdFromHash());
    setReviewTab(getReviewTabFromHash());
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      syncFromHash();
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [syncFromHash]);

  const handleLogin = useCallback(
    async (email: string, password: string) => {
      await login(email, password);
      window.location.hash = "#/today";
      setRoute("today");
    },
    [login],
  );

  const handleRegister = useCallback(
    async (email: string, password: string) => {
      await register(email, password);
      window.location.hash = "#/today";
      setRoute("today");
    },
    [register],
  );

  const handleLogout = useCallback(async () => {
    await logout();
    window.location.hash = "#/login";
    setRoute("login");
  }, [logout]);

  const handleCaptureDone = useCallback(async () => {
    window.location.hash = "#/today";
    setRoute("today");
    await bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (
      !isBootstrapping &&
      !isAuthenticated &&
      (route === "today" ||
        route === "review" ||
        route === "notes" ||
        route === "capture" ||
        route === "ask")
    ) {
      window.location.hash = "#/login";
      setRoute("login");
    }
  }, [isAuthenticated, isBootstrapping, route]);

  const protectedRoute =
    route === "today" ||
    route === "review" ||
    route === "notes" ||
    route === "capture" ||
    route === "ask";

  if (isBootstrapping && protectedRoute) {
    return (
      <div style={{ padding: 16, maxWidth: 420, margin: "0 auto" }}>
        Loading session...
      </div>
    );
  }

  if (!isAuthenticated && route === "register") {
    return <RegisterPage onSuccess={handleRegister} />;
  }

  if (!isAuthenticated) {
    return <LoginPage onSuccess={handleLogin} />;
  }

  const activeNav: NavRoute =
    route === "review"
      ? "review"
      : route === "notes"
        ? "notes"
        : route === "ask"
          ? "ask"
          : route === "capture"
            ? "capture"
            : "today";

  let page = null;
  if (route === "ask" && userId) {
    page = <AskPage userId={userId} />;
  } else if (route === "capture" && userId) {
    page = <CapturePage onDone={handleCaptureDone} />;
  } else if (route === "notes" && noteId && userId) {
    page = <NoteDetailPage key={noteId} noteId={noteId} />;
  } else if (route === "notes" && userId) {
    page = <NotesPage />;
  } else if (route === "review" && userId) {
    page = <ReviewPage key={reviewTab} initialTab={reviewTab} />;
  } else if (userId) {
    page = <TodayPage />;
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#f7f5f2",
      }}
    >
      <AppNav active={activeNav} onLogout={() => void handleLogout()} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {page}
      </div>
    </div>
  );
}

export default App;
