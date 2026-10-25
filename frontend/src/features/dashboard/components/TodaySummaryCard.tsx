import { useState } from "react";
import clsx from "clsx";
import { ArrowsClockwise, Sparkle, Target } from "@phosphor-icons/react";
import { Button } from "../../../shared/ui/Button";
import type { PeriodSummaryStatus } from "../../../shared/api/httpClient";

interface TodaySummaryCardProps {
  daily: PeriodSummaryStatus | null;
  weekly: PeriodSummaryStatus | null;
  generatingDaily: boolean;
  generatingWeekly: boolean;
  onGenerateDaily: () => void;
  onGenerateWeekly: () => void;
}

const TABS = [
  { key: "daily", label: "Today" },
  { key: "weekly", label: "This week" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/** Replaces two separate daily/weekly cards with one tabbed card to cut dashboard clutter. */
export function TodaySummaryCard({
  daily,
  weekly,
  generatingDaily,
  generatingWeekly,
  onGenerateDaily,
  onGenerateWeekly,
}: TodaySummaryCardProps) {
  const [tab, setTab] = useState<TabKey>("daily");
  const status = tab === "daily" ? daily : weekly;
  const loading = tab === "daily" ? generatingDaily : generatingWeekly;
  const onGenerate = tab === "daily" ? onGenerateDaily : onGenerateWeekly;
  const hasSummary = status?.status === "ready" && status.summary;
  const focusValue = status?.summary?.stats?.long_term_focus;
  const focus = Array.isArray(focusValue)
    ? focusValue.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-card">
      <h2 className="sr-only">Summary</h2>
      <div className="flex items-center justify-between">
        <div role="tablist" aria-label="Summary period" className="inline-flex rounded-full bg-neutral-100 p-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={clsx(
                "rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors",
                tab === t.key ? "bg-neutral-950 text-white" : "text-neutral-500 hover:text-neutral-900",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        {hasSummary ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-accent-50 px-2.5 py-1 text-[11px] font-semibold text-accent-700">
            <Sparkle size={12} weight="fill" /> Ready
          </span>
        ) : null}
      </div>

      <div role="tabpanel" aria-label={TABS.find((t) => t.key === tab)?.label}>
        {hasSummary ? (
          <>
            <p className="mt-4 text-sm leading-relaxed text-neutral-600">{status?.summary?.narrative}</p>
            {focus.length > 0 ? (
              <div className="mt-4 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3">
                <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                  <Target size={13} weight="bold" />
                  Long-term focus
                </p>
                <ul className="mt-2 space-y-1.5">
                  {focus.map((goal, index) => (
                    <li key={`${goal}-${index}`} className="text-sm leading-snug text-neutral-800">
                      {goal}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : status?.status === "insufficient_data" ? (
          <p className="mt-4 text-sm text-neutral-500">
            Not enough notes yet ({status.notes_count}/{status.min_notes_required} needed). Keep capturing notes
            and check back soon.
          </p>
        ) : (
          <p className="mt-4 text-sm text-neutral-500">No summary generated for this period yet.</p>
        )}
      </div>

      <Button variant="outline" size="sm" className="mt-5" onClick={onGenerate} disabled={loading}>
        <ArrowsClockwise size={16} className={loading ? "animate-spin" : ""} />
        {hasSummary ? "Regenerate" : "Generate"}
      </Button>
    </div>
  );
}
