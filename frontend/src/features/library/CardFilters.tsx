import { FunnelSimple, MagnifyingGlass, X } from "@phosphor-icons/react";

export type CardStateFilter = "" | "new" | "learning" | "review" | "relearning";
export type CardDueFilter = "" | "due" | "not_due";
export type CardStatusFilter = "active" | "suspended" | "all";

interface CardFiltersProps {
  query: string;
  state: CardStateFilter;
  due: CardDueFilter;
  status: CardStatusFilter;
  sort: "due" | "newest" | "reviews" | "lapses";
  total: number;
  loading: boolean;
  disabled?: boolean;
  onQueryChange: (value: string) => void;
  onStateChange: (value: CardStateFilter) => void;
  onDueChange: (value: CardDueFilter) => void;
  onStatusChange: (value: CardStatusFilter) => void;
  onSortChange: (value: "due" | "newest" | "reviews" | "lapses") => void;
  onClear: () => void;
}

const selectClass =
  "h-9 w-full cursor-pointer rounded-lg border border-neutral-200 bg-white px-2.5 text-xs font-medium text-neutral-700 focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-200 disabled:cursor-not-allowed disabled:opacity-50";

export function CardFilters({
  query,
  state,
  due,
  status,
  sort,
  total,
  loading,
  disabled = false,
  onQueryChange,
  onStateChange,
  onDueChange,
  onStatusChange,
  onSortChange,
  onClear,
}: CardFiltersProps) {
  const hasFilters = Boolean(query || state || due || status !== "active" || sort !== "due");
  return (
    <div className="space-y-3">
      <div>
        <label htmlFor="card-search" className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
          Search cards
        </label>
        <div className="relative mt-1">
          <MagnifyingGlass
            size={15}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400"
          />
          <input
            id="card-search"
            type="search"
            maxLength={100}
            value={query}
            disabled={disabled}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search questions or answers"
            className="h-10 w-full rounded-xl border border-neutral-200 bg-white pl-9 pr-9 text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-200 disabled:bg-neutral-50"
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

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2">
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Due</span>
          <select
            className={`${selectClass} mt-1`}
            value={due}
            disabled={disabled}
            onChange={(event) => onDueChange(event.target.value as CardDueFilter)}
          >
            <option value="">Any time</option>
            <option value="due">Due now</option>
            <option value="not_due">Not due</option>
          </select>
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">State</span>
          <select
            className={`${selectClass} mt-1`}
            value={state}
            disabled={disabled}
            onChange={(event) => onStateChange(event.target.value as CardStateFilter)}
          >
            <option value="">Any state</option>
            <option value="new">New</option>
            <option value="learning">Learning</option>
            <option value="review">Review</option>
            <option value="relearning">Relearning</option>
          </select>
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Availability</span>
          <select
            className={`${selectClass} mt-1`}
            value={status}
            disabled={disabled}
            onChange={(event) => onStatusChange(event.target.value as CardStatusFilter)}
          >
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
            <option value="all">All cards</option>
          </select>
        </label>
        <label className="block">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Sort</span>
          <select
            className={`${selectClass} mt-1`}
            value={sort}
            onChange={(event) => onSortChange(event.target.value as "due" | "newest" | "reviews" | "lapses")}
          >
            <option value="due">Soonest due</option>
            <option value="newest">Newest first</option>
            <option value="reviews">Most reviewed</option>
            <option value="lapses">Most lapses</option>
          </select>
        </label>
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-neutral-100 pt-3">
        <p className="inline-flex items-center gap-1.5 text-xs text-neutral-500">
          <FunnelSimple size={13} />
          {loading ? "Loading…" : `${total} card${total === 1 ? "" : "s"}`}
        </p>
        {hasFilters && !disabled ? (
          <button
            type="button"
            onClick={onClear}
            disabled={disabled}
            className="cursor-pointer rounded-md px-2 py-1 text-[11px] font-semibold text-neutral-500 hover:bg-neutral-100 hover:text-neutral-950 disabled:opacity-50"
          >
            Clear filters
          </button>
        ) : null}
      </div>
    </div>
  );
}
