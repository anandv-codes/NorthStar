import { FunnelSimple, MagnifyingGlass, X } from "@phosphor-icons/react";

export type NoteRange = "all" | "7d" | "30d" | "90d";
export type NoteStatusFilter = "" | "ready" | "processing" | "failed";

interface NoteFiltersProps {
  query: string;
  recall: "" | "on" | "off";
  status: NoteStatusFilter;
  range: NoteRange;
  sort: "newest" | "oldest";
  total: number;
  loading: boolean;
  onQueryChange: (value: string) => void;
  onRecallChange: (value: "" | "on" | "off") => void;
  onStatusChange: (value: NoteStatusFilter) => void;
  onRangeChange: (value: NoteRange) => void;
  onSortChange: (value: "newest" | "oldest") => void;
  onClear: () => void;
}

const selectClass =
  "h-9 w-full cursor-pointer rounded-lg border border-neutral-200 bg-white px-2.5 text-xs font-medium text-neutral-700 focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-200";

export function NoteFilters({
  query,
  recall,
  status,
  range,
  sort,
  total,
  loading,
  onQueryChange,
  onRecallChange,
  onStatusChange,
  onRangeChange,
  onSortChange,
  onClear,
}: NoteFiltersProps) {
  const hasFilters = Boolean(query || recall || status || range !== "all" || sort !== "newest");

  return (
    <div className="space-y-3">
      <div>
        <label htmlFor="note-search" className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
          Search notes
        </label>
        <div className="relative mt-1">
          <MagnifyingGlass
            size={15}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400"
          />
          <input
            id="note-search"
            type="search"
            maxLength={100}
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search text or summaries"
            className="h-10 w-full rounded-xl border border-neutral-200 bg-white pl-9 pr-9 text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-200"
          />
          {query ? (
            <button
              type="button"
              onClick={() => onQueryChange("")}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 cursor-pointer items-center justify-center rounded-md text-neutral-400 hover:bg-neutral-100 hover:text-neutral-900"
            >
              <X size={14} />
            </button>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Recall</span>
          <select
            className={`${selectClass} mt-1`}
            value={recall}
            onChange={(event) => onRecallChange(event.target.value as "" | "on" | "off")}
          >
            <option value="">All notes</option>
            <option value="on">Recall on</option>
            <option value="off">Recall off</option>
          </select>
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Status</span>
          <select
            className={`${selectClass} mt-1`}
            value={status}
            onChange={(event) => onStatusChange(event.target.value as NoteStatusFilter)}
          >
            <option value="">Any status</option>
            <option value="ready">Ready</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
          </select>
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Date</span>
          <select
            className={`${selectClass} mt-1`}
            value={range}
            onChange={(event) => onRangeChange(event.target.value as NoteRange)}
          >
            <option value="all">Any time</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
          </select>
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Sort</span>
          <select
            className={`${selectClass} mt-1`}
            value={sort}
            onChange={(event) => onSortChange(event.target.value as "newest" | "oldest")}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </label>
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-neutral-100 pt-3">
        <p className="inline-flex items-center gap-1.5 text-xs text-neutral-500">
          <FunnelSimple size={13} />
          {loading ? "Loading…" : `${total} note${total === 1 ? "" : "s"}`}
        </p>
        {hasFilters ? (
          <button
            type="button"
            onClick={onClear}
            className="cursor-pointer rounded-md px-2 py-1 text-[11px] font-semibold text-neutral-500 hover:bg-neutral-100 hover:text-neutral-950"
          >
            Clear filters
          </button>
        ) : null}
      </div>
    </div>
  );
}
