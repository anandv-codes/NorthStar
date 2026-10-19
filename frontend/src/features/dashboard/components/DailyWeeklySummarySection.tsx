import { useState } from "react";
import { PeriodSummaryStatus } from "../../../shared/api/httpClient";

interface DailyWeeklySummarySectionProps {
  dailySummary: PeriodSummaryStatus | null;
  weeklySummary: PeriodSummaryStatus | null;
  onGenerateDaily: () => Promise<void>;
  onRegenerateDaily: () => Promise<void>;
  onGenerateWeekly: () => Promise<void>;
  onRegenerateWeekly: () => Promise<void>;
  busy: boolean;
}

const STAT_LABELS: Record<string, string> = {
  facts_recorded: "Facts",
  decisions_made: "Decisions",
  questions_opened: "Questions",
  questions_answered: "Questions answered",
  notes_count: "Notes",
  tasks_opened: "Tasks opened",
  tasks_completed: "Tasks completed",
  risks_opened: "Risks opened",
  risks_resolved: "Risks resolved",
};

function StatChips({ stats }: { stats: Record<string, number> }) {
  const entries = Object.entries(stats).filter(([, value]) => value > 0);
  if (entries.length === 0) {
    return null;
  }
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem" }}>
      {entries.map(([key, value]) => (
        <span
          key={key}
          style={{
            fontSize: "0.8em",
            backgroundColor: "#eef2ff",
            color: "#333",
            padding: "0.2rem 0.6rem",
            borderRadius: "999px",
          }}
        >
          {STAT_LABELS[key] ?? key}: {value}
        </span>
      ))}
    </div>
  );
}

export function DailyWeeklySummarySection({
  dailySummary,
  weeklySummary,
  onGenerateDaily,
  onRegenerateDaily,
  onGenerateWeekly,
  onRegenerateWeekly,
  busy,
}: DailyWeeklySummarySectionProps) {
  const [period, setPeriod] = useState<"daily" | "weekly">("daily");

  const active = period === "daily" ? dailySummary : weeklySummary;
  const onGenerate = period === "daily" ? onGenerateDaily : onGenerateWeekly;
  const onRegenerate = period === "daily" ? onRegenerateDaily : onRegenerateWeekly;

  return (
    <section>
      <h2>What to remember</h2>
      <p style={{ marginTop: 0, color: "#666", fontSize: "0.9em" }}>
        Daily and weekly reflection on what you captured and what still needs
        attention.
      </p>
      <div style={{ marginBottom: "0.75rem" }}>
        <button
          onClick={() => setPeriod("daily")}
          disabled={period === "daily"}
          style={{ marginRight: "0.5rem" }}
        >
          Daily
        </button>
        <button onClick={() => setPeriod("weekly")} disabled={period === "weekly"}>
          Weekly
        </button>
      </div>

      {!active ? (
        <p>Loading…</p>
      ) : active.status === "ready" && active.summary ? (
        <div
          style={{
            padding: "1rem",
            backgroundColor: "#fafafa",
            borderRadius: "4px",
            border: "1px solid #eee",
          }}
        >
          <div style={{ fontSize: "0.85em", color: "#666", marginBottom: "0.5rem" }}>
            {active.summary.period_start === active.summary.period_end
              ? active.summary.period_start
              : `${active.summary.period_start} to ${active.summary.period_end}`}
          </div>
          <p style={{ margin: 0, color: "#333" }}>{active.summary.narrative}</p>
          <StatChips stats={active.summary.stats} />
          <div style={{ marginTop: "0.75rem" }}>
            <button onClick={() => void onRegenerate()} disabled={busy}>
              Regenerate
            </button>
          </div>
        </div>
      ) : active.status === "not_generated" ? (
        <div>
          <p>
            {active.notes_count} note{active.notes_count === 1 ? "" : "s"} ready for
            reflection.
          </p>
          <button onClick={() => void onGenerate()} disabled={busy}>
            Generate {period} reflection
          </button>
        </div>
      ) : (
        <p title={`Needs at least ${active.min_notes_required} notes; currently ${active.notes_count}.`}>
          {Math.max(0, active.min_notes_required - active.notes_count)} more note
          {Math.max(0, active.min_notes_required - active.notes_count) === 1 ? "" : "s"}{" "}
          needed to unlock the {period} reflection ({active.notes_count}/
          {active.min_notes_required}).
        </p>
      )}
    </section>
  );
}
