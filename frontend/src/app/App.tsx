import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { LandingPage } from "../features/landing/LandingPage";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { AppShell } from "../features/shell/AppShell";
import { ProtectedRoute } from "../features/shell/ProtectedRoute";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { NoteTakerPage } from "../features/notes/NoteTakerPage";
import { ChatPage } from "../features/chat/ChatPage";
import { RecallPage } from "../features/recall/RecallPage";
import { RecallVerifyPage } from "../features/recall/RecallVerifyPage";
import { StudyPage } from "../features/recall/StudyPage";
const LibraryLayout = lazy(() =>
  import("../features/library/LibraryLayout").then((module) => ({ default: module.LibraryLayout })),
);
const NotesLibraryPage = lazy(() =>
  import("../features/library/NotesLibraryPage").then((module) => ({ default: module.NotesLibraryPage })),
);
const RecallLibraryPage = lazy(() =>
  import("../features/library/RecallLibraryPage").then((module) => ({ default: module.RecallLibraryPage })),
);

function LazyRoute({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[320px] items-center justify-center">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-950" />
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

function DeckLibraryRedirect() {
  const { deckId = "" } = useParams();
  return <Navigate to={`/app/library/recall/${deckId}`} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="notes" element={<NoteTakerPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route
            path="library"
            element={
              <LazyRoute>
                <LibraryLayout />
              </LazyRoute>
            }
          >
            <Route index element={<Navigate to="notes" replace />} />
            <Route
              path="notes"
              element={
                <LazyRoute>
                  <NotesLibraryPage />
                </LazyRoute>
              }
            />
            <Route
              path="notes/:noteId"
              element={
                <LazyRoute>
                  <NotesLibraryPage />
                </LazyRoute>
              }
            />
            <Route
              path="recall"
              element={
                <LazyRoute>
                  <RecallLibraryPage />
                </LazyRoute>
              }
            />
            <Route
              path="recall/:deckId"
              element={
                <LazyRoute>
                  <RecallLibraryPage />
                </LazyRoute>
              }
            />
          </Route>
          <Route path="recall" element={<RecallPage />} />
          <Route path="recall/verify" element={<RecallVerifyPage />} />
          <Route path="recall/decks/:deckId" element={<DeckLibraryRedirect />} />
          <Route path="recall/study/:deckId" element={<StudyPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
