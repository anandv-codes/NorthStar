import clsx from "clsx";
import { ArrowsClockwise, Sparkle } from "@phosphor-icons/react";
import { Button } from "../../../shared/ui/Button";
import type { PeriodSummaryStatus } from "../../../shared/api/httpClient";

interface SummaryCardProps {
  title: string;
  status: PeriodSummaryStatus | null;
  loading: boolean;
  onGenerate: () => void;
}

export function SummaryCard({ title, status, loading, onGenerate }: SummaryCardProps) {
  const hasSummary = status?.status === "ready" && status.summary;

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-card">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-neutral-950">{title}</h2>
        {hasSummary ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-accent-50 px-2.5 py-1 text-[11px] font-semibold text-accent-700">
            <Sparkle size={12} weight="fill" /> Ready
          </span>
        ) : null}
      </div>

      {hasSummary ? (
        <p className="mt-4 text-sm leading-relaxed text-neutral-600">{status?.summary?.narrative}</p>
      ) : status?.status === "insufficient_data" ? (
        <p className="mt-4 text-sm text-neutral-500">
          Not enough notes yet ({status.notes_count}/{status.min_notes_required} needed). Keep capturing notes
          and check back soon.
        </p>
      ) : (
        <p className="mt-4 text-sm text-neutral-500">No summary generated for this period yet.</p>
      )}

      <Button
        variant="outline"
        size="sm"
        className={clsx("mt-5")}
        onClick={onGenerate}
        disabled={loading}
      >
        <ArrowsClockwise size={16} className={loading ? "animate-spin" : ""} />
        {hasSummary ? "Regenerate" : "Generate"}
      </Button>
    </div>
  );
}
