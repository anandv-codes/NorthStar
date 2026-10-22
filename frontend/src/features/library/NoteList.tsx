import { Link, useSearchParams } from "react-router-dom";
import { ArrowClockwise, Brain, CheckCircle, NotePencil, Spinner } from "@phosphor-icons/react";
import clsx from "clsx";
import type { NoteStatus } from "../../shared/api/httpClient";
import { excerpt, formatLibraryDate, noteTitle } from "./libraryUtils";

interface NoteListProps {
  notes: NoteStatus[];
  selectedNoteId?: string;
  total: number;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  hasMore: boolean;
  onLoadMore: () => void;
  onRetry: () => void;
}

const RECALL_LABELS: Record<string, string> = {
  ready: "Recall ready",
  pending: "Generating recall",
  failed: "Recall failed",
  off: "Recall off",
};

function groupLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Earlier";
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  if (day === today) return "Today";
  if (day === today - 86_400_000) return "Yesterday";
  return "Earlier";
}

export function NoteList({
  notes,
  selectedNoteId,
  total,
  loading,
  loadingMore,
  error,
  hasMore,
  onLoadMore,
  onRetry,
}: NoteListProps) {
  const [searchParams] = useSearchParams();
  const query = searchParams.toString();
  const noteHref = (noteId: string) =>
    `/app/library/notes/${noteId}${query ? `?${query}` : ""}`;

  if (loading) {
    return (
      <div className="space-y-2" aria-label="Loading notes">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="h-28 animate-pulse rounded-xl bg-neutral-100" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
        <p className="text-sm text-red-700">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100"
        >
          <ArrowClockwise size={13} />
          Try again
        </button>
      </div>
    );
  }

  if (notes.length === 0) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white px-5 py-10 text-center shadow-card">
        <span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-neutral-100 text-neutral-500">
          <NotePencil size={19} weight="bold" />
        </span>
        <p className="mt-4 font-display text-base font-semibold text-neutral-950">No notes match these filters</p>
        <p className="mx-auto mt-1.5 max-w-xs text-sm text-neutral-500">
          Try a shorter search, a wider date range, or clear the filters.
        </p>
      </div>
    );
  }

  let lastGroup = "";

  return (
    <div>
      <ul className="space-y-2">
        {notes.map((note) => {
          const group = groupLabel(note.created_at);
          const showGroup = group !== lastGroup;
          lastGroup = group;
          const recallOn = Boolean(note.recall_enabled);
          const processing = note.status === "processing";
          const failed = note.status === "failed";

          return (
            <li key={note.note_id}>
              {showGroup ? (
                <p className="mb-1.5 mt-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-neutral-400 first:mt-0">
                  {group}
                </p>
              ) : null}
              <Link
                to={noteHref(note.note_id)}
                aria-current={selectedNoteId === note.note_id ? "page" : undefined}
                className={clsx(
                  "block rounded-xl border p-3.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950",
                  selectedNoteId === note.note_id
                    ? "border-neutral-950 bg-white shadow-card"
                    : "border-neutral-200 bg-white hover:border-neutral-300 hover:bg-neutral-50",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="line-clamp-2 text-sm font-semibold leading-snug text-neutral-950">
                    {noteTitle(note.raw_text, note.enriched_summary)}
                  </p>
                  {processing ? (
                    <Spinner size={14} className="mt-0.5 shrink-0 animate-spin text-neutral-400" />
                  ) : failed ? (
                    <span className="shrink-0 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-700">
                      Failed
                    </span>
                  ) : (
                    <CheckCircle size={14} weight="fill" className="mt-0.5 shrink-0 text-emerald-500" />
                  )}
                </div>
                <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-neutral-500">
                  {excerpt(note.enriched_summary || note.raw_text)}
                </p>
                <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-neutral-400">
                  <span>{formatLibraryDate(note.created_at)}</span>
                  {recallOn ? (
                    <>
                      <span aria-hidden="true">·</span>
                      <span
                        className={clsx(
                          "inline-flex items-center gap-1 font-medium",
                          note.recall_status === "failed" ? "text-red-600" : "text-accent-700",
                        )}
                      >
                        <Brain size={11} weight="bold" />
                        {RECALL_LABELS[note.recall_status ?? "off"] ?? "Recall on"}
                      </span>
                    </>
                  ) : null}
                </div>
              </Link>
            </li>
          );
        })}
      </ul>

      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-xs text-neutral-400">
          {notes.length} of {total} loaded
        </p>
        {hasMore ? (
          <button
            type="button"
            onClick={onLoadMore}
            disabled={loadingMore}
            className="inline-flex h-9 cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-100 disabled:cursor-wait disabled:opacity-60"
          >
            {loadingMore ? <Spinner size={13} className="animate-spin" /> : null}
            {loadingMore ? "Loading…" : "Load more"}
          </button>
        ) : null}
      </div>
    </div>
  );
}
