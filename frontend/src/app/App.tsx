import { Navigate, Route, Routes } from "react-router-dom";
import { LandingPage } from "../features/landing/LandingPage";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { AppShell } from "../features/shell/AppShell";
import { ProtectedRoute } from "../features/shell/ProtectedRoute";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { NoteTakerPage } from "../features/notes/NoteTakerPage";
import { ChatPage } from "../features/chat/ChatPage";
import { RecallPage } from "../features/recall/RecallPage";

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
          <Route path="recall" element={<RecallPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
