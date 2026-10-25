import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Plus } from "@phosphor-icons/react";
import {
  MemoryConcept,
  MemoryQuestion,
  MemoryRisk,
  MemoryTask,
  PeriodSummaryStatus,
  RecentNote,
  fetchConcepts,
  fetchDailySummary,
  fetchQuestions,
  fetchRecentMemory,
  fetchRisks,
  fetchTasks,
  fetchWeeklySummary,
  generateDailySummary,
  generateWeeklySummary,
  patchQuestionStatus,
  patchRiskStatus,
  patchTaskStatus,
} from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { Modal } from "../../shared/ui/Modal";
import { TodaySummaryCard } from "./components/TodaySummaryCard";
import { ConceptCloud } from "./components/ConceptCloud";
import { RecentMemoryFeed } from "./components/RecentMemoryFeed";
import { ActivityHeatmap } from "./components/ActivityHeatmap";
import { RecallSpotlight } from "./components/RecallSpotlight";
import { WhatToDoPanel } from "./components/WhatToDoPanel";
import { QuickAddNote } from "./components/QuickAddNote";
import { CommitmentsPanel } from "../commitments/CommitmentsPanel";

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-card">
      <h2 className="text-sm font-semibold text-neutral-950">{title}</h2>
      <div className="mt-2">{children}</div>
    </section>
  );
}

export function DashboardPage() {
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [heatmapKey, setHeatmapKey] = useState(0);
  const [dailySummary, setDailySummary] = useState<PeriodSummaryStatus | null>(null);
  const [weeklySummary, setWeeklySummary] = useState<PeriodSummaryStatus | null>(null);
  const [tasks, setTasks] = useState<MemoryTask[]>([]);
  const [questions, setQuestions] = useState<MemoryQuestion[]>([]);
  const [risks, setRisks] = useState<MemoryRisk[]>([]);
  const [concepts, setConcepts] = useState<MemoryConcept[]>([]);
  const [recentNotes, setRecentNotes] = useState<RecentNote[]>([]);
  const [generatingDaily, setGeneratingDaily] = useState(false);
  const [generatingWeekly, setGeneratingWeekly] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [daily, weekly, taskList, questionList, riskList, conceptList, recent] = await Promise.all([
        fetchDailySummary(),
        fetchWeeklySummary(),
        fetchTasks(),
        fetchQuestions(),
        fetchRisks(),
        fetchConcepts(),
        fetchRecentMemory(8),
      ]);
      setDailySummary(daily);
      setWeeklySummary(weekly);
      setTasks(taskList);
      setQuestions(questionList);
      setRisks(riskList);
      setConcepts(conceptList);
      setRecentNotes(recent.notes);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load dashboard data.");
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const handleGenerateDaily = async () => {
    setGeneratingDaily(true);
    try {
      setDailySummary(await generateDailySummary(Boolean(dailySummary?.summary)));
    } finally {
      setGeneratingDaily(false);
    }
  };

  const handleGenerateWeekly = async () => {
    setGeneratingWeekly(true);
    try {
      setWeeklySummary(await generateWeeklySummary(Boolean(weeklySummary?.summary)));
    } finally {
      setGeneratingWeekly(false);
    }
  };

  // Wrap mutations so a failed request surfaces a message and never leaves the
  // optimistic state silently out of sync with the server.
  const runAction = async (action: () => Promise<void>, fallback: string) => {
    setActionError(null);
    try {
      await action();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : fallback);
    }
  };

  const handleToggleTask = (task: MemoryTask) =>
    runAction(async () => {
      const nextStatus = task.status === "completed" ? "open" : "completed";
      const updated = await patchTaskStatus(task.task_id, nextStatus);
      setTasks((current) => current.map((t) => (t.task_id === updated.task_id ? updated : t)));
    }, "Couldn't update that task.");

  const handleResolveQuestion = (question: MemoryQuestion) =>
    runAction(async () => {
      const updated = await patchQuestionStatus(question.question_id, "answered");
      setQuestions((current) => current.map((q) => (q.question_id === updated.question_id ? updated : q)));
    }, "Couldn't resolve that question.");

  const handleDismissQuestion = (question: MemoryQuestion) =>
    runAction(async () => {
      const updated = await patchQuestionStatus(question.question_id, "archived");
      setQuestions((current) => current.filter((q) => q.question_id !== updated.question_id));
    }, "Couldn't dismiss that question.");

  const handleResolveRisk = (risk: MemoryRisk) =>
    runAction(async () => {
      const updated = await patchRiskStatus(risk.risk_id, "resolved");
      setRisks((current) => current.filter((r) => r.risk_id !== updated.risk_id));
    }, "Couldn't resolve that risk.");

  return (
    <div className="mx-auto max-w-6xl">
      <header className="mb-8 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">Dashboard</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Your memory, organized. Here's everything NorthStar has pulled together for you.
          </p>
        </div>
        <Button onClick={() => setQuickAddOpen(true)}>
          <Plus size={16} weight="bold" />
          Add note
        </Button>
      </header>

      {loadError ? (
        <p className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {loadError}
        </p>
      ) : null}

      {actionError ? (
        <p role="alert" className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {actionError}
        </p>
      ) : null}

      {/* What matters today */}
      <TodaySummaryCard
        daily={dailySummary}
        weekly={weeklySummary}
        generatingDaily={generatingDaily}
        generatingWeekly={generatingWeekly}
        onGenerateDaily={handleGenerateDaily}
        onGenerateWeekly={handleGenerateWeekly}
      />

      <div className="mt-5">
        <CommitmentsPanel />
      </div>

      {/* What to remember — the core loop leads the dashboard per the product pivot */}
      <div className="mt-5">
        <RecallSpotlight />
      </div>

      {/* What to do */}
      <div className="mt-5">
        <WhatToDoPanel
          tasks={tasks}
          questions={questions}
          risks={risks}
          onToggleTask={handleToggleTask}
          onResolveQuestion={handleResolveQuestion}
          onDismissQuestion={handleDismissQuestion}
          onResolveRisk={handleResolveRisk}
        />
      </div>

      {/* Supporting, lower-priority context */}
      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ActivityHeatmap key={heatmapKey} />
        </div>
        <Panel title="Concepts">
          <ConceptCloud concepts={concepts} />
        </Panel>
      </div>

      <div className="mt-5">
        <Panel title="Recent memory">
          <RecentMemoryFeed notes={recentNotes} />
        </Panel>
      </div>

      <Modal open={quickAddOpen} onClose={() => setQuickAddOpen(false)} title="Quick note">
        <QuickAddNote
          onCreated={() => {
            void loadAll();
            setHeatmapKey((key) => key + 1);
          }}
        />
      </Modal>
    </div>
  );
}
