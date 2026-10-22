import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { NotePencil, Sparkle } from "@phosphor-icons/react";
import clsx from "clsx";
import { fetchNotes, type NoteStatus } from "../../shared/api/httpClient";
import { useDebouncedValue } from "../../shared/lib/useDebouncedValue";
import { NoteDetailPanel } from "./NoteDetailPanel";
import { NoteFilters, type NoteRange, type NoteStatusFilter } from "./NoteFilters";
import { NoteList } from "./NoteList";

const PAGE_SIZE = 20;
const RANGES: NoteRange[] = ["all", "7d", "30d", "90d"];
const STATUSES: NoteStatusFilter[] = ["", "ready", "processing", "failed"];

export function NotesLibraryPage() {
  const { noteId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const query = searchParams.get("q") ?? "";
  const recallParam = searchParams.get("recall");
  const recall = recallParam === "on" || recallParam === "off" ? recallParam : "";
  const statusParam = searchParams.get("status") as NoteStatusFilter | null;
  const status = statusParam && STATUSES.includes(statusParam) ? statusParam : "";
  const rangeParam = searchParams.get("range") as NoteRange | null;
  const range = rangeParam && RANGES.includes(rangeParam) ? rangeParam : "all";
  const sort = searchParams.get("sort") === "oldest" ? "oldest" : "newest";

  const [searchText, setSearchText] = useState(query);
  const debouncedSearch = useDebouncedValue(searchText, 300);
  const [notes, setNotes] = useState<NoteStatus[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const setParam = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(searchParams);
      if (value) next.set(key, value);
      else next.delete(key);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  useEffect(() => {
    setSearchText(query);
  }, [query]);

  useEffect(() => {
    if (debouncedSearch === query) return;
    setParam("q", debouncedSearch.trim());
  }, [debouncedSearch, query, setParam]);

  const createdAfter = useMemo(() => {
    if (range === "all") return undefined;
    const days = range === "7d" ? 7 : range === "30d" ? 30 : 90;
    const date = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
    return date.toISOString();
  }, [range]);

  const loadNotes = useCallback(
    async (offset: number, append: boolean) => {
      const id = ++requestId.current;
      if (append) setLoadingMore(true);
      else setLoading(true);
      setError(null);
      try {
        const result = await fetchNotes({
          q: query || undefined,
          recall: recall || undefined,
          status: status || undefined,
          createdAfter,
          sort,
          limit: PAGE_SIZE,
          offset,
        });
        if (id !== requestId.current) return;
        setNotes((current) => (append ? [...current, ...result.notes] : result.notes));
        setTotal(result.total);
      } catch (err) {
        if (id !== requestId.current) return;
        setError(err instanceof Error ? err.message : "Couldn't load your notes.");
      } finally {
        if (id === requestId.current) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [query, recall, status, createdAfter, sort],
  );

  useEffect(() => {
    void loadNotes(0, false);
  }, [loadNotes]);

  const clearFilters = () => {
    setSearchText("");
    setSearchParams({}, { replace: true });
  };

  const hasMore = notes.length < total;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(300px,360px)_minmax(0,1fr)]">
      <section className={clsx("min-w-0", noteId ? "hidden lg:block" : "block")}>
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-lg font-semibold text-neutral-950">All notes</h2>
            <p className="text-xs text-neutral-500">Search, filter, and reopen any note.</p>
          </div>
          <Link
            to="/app/notes"
            className="inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-neutral-950 px-3 text-xs font-semibold text-white hover:bg-neutral-800"
          >
            <NotePencil size={14} weight="bold" />
            New note
          </Link>
        </div>

        <div className="lg:sticky lg:top-6">
          <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-card">
            <NoteFilters
              query={searchText}
              recall={recall}
              status={status}
              range={range}
              sort={sort}
              total={total}
              loading={loading}
              onQueryChange={setSearchText}
              onRecallChange={(value) => setParam("recall", value)}
              onStatusChange={(value) => setParam("status", value)}
              onRangeChange={(value) => setParam("range", value)}
              onSortChange={(value) => setParam("sort", value)}
              onClear={clearFilters}
            />
          </div>

          <div className="mt-4 lg:max-h-[calc(100vh-22rem)] lg:overflow-y-auto lg:pr-1">
            <NoteList
              notes={notes}
              selectedNoteId={noteId}
              total={total}
              loading={loading}
              loadingMore={loadingMore}
              error={error}
              hasMore={hasMore}
              onLoadMore={() => void loadNotes(notes.length, true)}
              onRetry={() => void loadNotes(0, false)}
            />
          </div>
        </div>
      </section>

      <section className={clsx("min-w-0", noteId ? "block" : "hidden lg:block")}>
        {noteId ? (
          <NoteDetailPanel noteId={noteId} />
        ) : (
          <div className="flex min-h-[420px] flex-col items-center justify-center rounded-2xl border border-dashed border-neutral-200 bg-white px-6 text-center">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100 text-neutral-500">
              <Sparkle size={20} weight="bold" />
            </span>
            <p className="mt-5 font-display text-lg font-semibold text-neutral-950">Choose a note to revisit</p>
            <p className="mt-1.5 max-w-sm text-sm text-neutral-500">
              Open a note from the list to read the original text and everything NorthStar extracted from it.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
