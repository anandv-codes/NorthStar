import { Check, Spinner, X } from "@phosphor-icons/react";
import type { RecallSuggestion } from "../../shared/api/httpClient";

interface SuggestionCardProps {
  suggestion: RecallSuggestion;
  processing: "accept" | "reject" | null;
  onAccept: () => void;
  onReject: () => void;
}

export function SuggestionCard({ suggestion, processing, onAccept, onReject }: SuggestionCardProps) {
  const busy = processing !== null;

  return (
    <div className="flex items-start justify-between gap-4 rounded-2xl border border-neutral-200 bg-white p-5 shadow-card">
      <div>
        <span className="rounded-full border border-neutral-200 px-2.5 py-1 text-[11px] font-semibold capitalize text-neutral-500">
          {suggestion.item_type}
        </span>
        <p className="mt-2.5 text-sm font-medium leading-relaxed text-neutral-900">{suggestion.question}</p>
        <p className="mt-1 text-xs text-neutral-400">Worth remembering? Add it to your recall deck.</p>
      </div>
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={onReject}
          title="Skip this suggestion"
          aria-label="Skip this suggestion"
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-200 text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-950 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {processing === "reject" ? <Spinner size={16} className="animate-spin" /> : <X size={16} />}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onAccept}
          title="Add to recall"
          aria-label="Add to recall"
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 transition-colors hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {processing === "accept" ? <Spinner size={16} className="animate-spin" /> : <Check size={16} weight="bold" />}
        </button>
      </div>
    </div>
  );
}
