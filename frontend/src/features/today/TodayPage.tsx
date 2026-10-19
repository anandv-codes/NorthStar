import { useCallback, useEffect, useState } from "react";
import {
  MemoryTask,
  PeriodSummaryStatus,
  RecentMemoryResponse,
  RecallSuggestion,
  fetchDailySummary,
  fetchDueCards,
  fetchRecentMemory,
  fetchSuggestions,
  fetchTasks,
  fetchWeeklySummary,
  generateDailySummary,
  generateWeeklySummary,
  patchTaskStatus,
} from "../../shared/api/httpClient";
import { TasksSection } from "../dashboard/components/TasksSection";
import { RecentMemorySection } from "../dashboard/components/RecentMemorySection";
import { DailyWeeklySummarySection } from "../dashboard/components/DailyWeeklySummarySection";
import { SuggestedQuestions } from "../review/SuggestedQuestions";
import { Loading, ErrorLine, PageShell } from "../../shared/ui/states";
import { Card, SectionTitle } from "../../shared/ui/Card";
import { ReviewCta } from "./ReviewCta";
import { QuickCapture } from "./QuickCapture";

export function TodayPage() {
  const [tasks, setTasks] = useState<MemoryTask[]>([]);
  const [recentMemory, setRecentMemory] = useState<RecentMemoryResponse | null>(null);
  const [dueCount, setDueCount] = useState(0);
  const [suggestions, setSuggestions] = useState<RecallSuggestion[]>([]);
  const [dailySummary, setDailySummary] = useState<PeriodSummaryStatus | null>(null);
  const [weeklySummary, setWeeklySummary] = useState<PeriodSummaryStatus | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [summaryBusy, setSummaryBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        taskData,
        recentData,
        due,
        suggested,
        daily,
        weekly,
      ] = await Promise.all([
        fetchTasks(),
        fetchRecentMemory(10),
        fetchDueCards(),
        fetchSuggestions(),
        fetchDailySummary(),
        fetchWeeklySummary(),
      ]);
      setTasks(taskData);
      setRecentMemory(recentData);
      setDueCount(due.total_due);
      setSuggestions(suggested.suggestions);
      setDailySummary(daily);
      setWeeklySummary(weekly);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Today.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleTaskDone = async (taskId: string) => {
    setActiveTaskId(taskId);
    try {
      await patchTaskStatus(taskId, "completed");
      await load();
    } finally {
      setActiveTaskId(null);
    }
  };

  const withSummaryBusy = async (action: () => Promise<unknown>) => {
    setSummaryBusy(true);
    try {
      await action();
      await load();
    } finally {
      setSummaryBusy(false);
    }
  };

  const openCount = tasks.filter((task) => task.status === "open").length;

  return (
    <PageShell>
      <div style={{ color: "#666", fontSize: 13, marginBottom: 12 }}>
        {dueCount} due · {suggestions.length} new to consider · {openCount} open task
        {openCount === 1 ? "" : "s"}
      </div>

      {loading ? <Loading label="Loading Today..." /> : null}
      {error ? <ErrorLine message={error} onRetry={() => void load()} /> : null}

      {!loading && !error ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <ReviewCta dueCount={dueCount} suggestionCount={suggestions.length} />

          {suggestions.length > 0 ? (
            <div>
              <SectionTitle hint="question only — accept to generate the answer">
                Suggested questions
              </SectionTitle>
              <SuggestedQuestions
                suggestions={suggestions.slice(0, 3)}
                onDecided={(candidateId) =>
                  setSuggestions((items) =>
                    items.filter((item) => item.candidate_id !== candidateId),
                  )
                }
              />
            </div>
          ) : null}

          <QuickCapture onCaptured={() => void load()} />

          {tasks.length === 0 && !recentMemory ? (
            <Card>
              <SectionTitle>Memory</SectionTitle>
              <div style={{ color: "#777" }}>
                No notes yet. Capture your first one above.
              </div>
            </Card>
          ) : (
            <>
              <TasksSection
                tasks={tasks}
                onMarkDone={handleTaskDone}
                activeTaskId={activeTaskId}
              />
              <RecentMemorySection recentMemory={recentMemory} />
            </>
          )}

          <DailyWeeklySummarySection
            dailySummary={dailySummary}
            weeklySummary={weeklySummary}
            onGenerateDaily={() => withSummaryBusy(() => generateDailySummary(false))}
            onRegenerateDaily={() => withSummaryBusy(() => generateDailySummary(true))}
            onGenerateWeekly={() => withSummaryBusy(() => generateWeeklySummary(false))}
            onRegenerateWeekly={() => withSummaryBusy(() => generateWeeklySummary(true))}
            busy={summaryBusy}
          />
        </div>
      ) : null}
    </PageShell>
  );
}
