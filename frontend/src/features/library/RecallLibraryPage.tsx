import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowClockwise,
  Archive,
  Cards,
  CheckCircle,
  NotePencil,
  Spinner,
  X,
} from "@phosphor-icons/react";
import clsx from "clsx";
import {
  archiveRecallDeck,
  bulkUpdateRecallCards,
  fetchRecallCards,
  fetchRecallDecks,
  restoreRecallDeck,
  updateRecallCard,
  type RecallCard,
  type RecallDeck,
} from "../../shared/api/httpClient";
import { useDebouncedValue } from "../../shared/lib/useDebouncedValue";
import { Button } from "../../shared/ui/Button";
import { Modal } from "../../shared/ui/Modal";
import { DeckFormModal } from "../recall/components/DeckFormModal";
import { DeckPicker } from "../recall/components/DeckPicker";
import { RecallCardRow } from "../recall/components/RecallCardRow";
import {
  CardFilters,
  type CardDueFilter,
  type CardStateFilter,
  type CardStatusFilter,
} from "./CardFilters";
import { DeckRail } from "./DeckRail";
import { DeckStatsHeader } from "./DeckStatsHeader";

const PAGE_SIZE = 40;
const BULK_LIMIT = 200;
const CARD_STATES: CardStateFilter[] = ["", "new", "learning", "review", "relearning"];
const DUE_FILTERS: CardDueFilter[] = ["", "due", "not_due"];
const STATUS_FILTERS: CardStatusFilter[] = ["active", "suspended", "all"];
const SORTS = ["due", "newest", "reviews", "lapses"] as const;

function cardErrorMessage(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : "";
  if (message.includes("deck_archived")) {
    return "Restore that deck before reactivating its cards.";
  }
  if (message.includes("deck_not_found")) {
    return "That deck is no longer available.";
  }
  return message || fallback;
}

export function RecallLibraryPage() {
  const { deckId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const query = searchParams.get("q") ?? "";
  const stateParam = searchParams.get("state") as CardStateFilter | null;
  const state = stateParam && CARD_STATES.includes(stateParam) ? stateParam : "";
  const dueParam = searchParams.get("due") as CardDueFilter | null;
  const due = dueParam && DUE_FILTERS.includes(dueParam) ? dueParam : "";
  const sortParam = searchParams.get("sort");
  const sort = SORTS.includes(sortParam as (typeof SORTS)[number])
    ? (sortParam as (typeof SORTS)[number])
    : "due";
  const sourceNoteId = searchParams.get("note") ?? "";
  const statusFilterParam = searchParams.get("status") as CardStatusFilter | null;
  const statusFilter =
    statusFilterParam && STATUS_FILTERS.includes(statusFilterParam)
      ? statusFilterParam
      : sourceNoteId
        ? "all"
        : "active";

  const [decks, setDecks] = useState<RecallDeck[]>([]);
  const [decksReady, setDecksReady] = useState(false);
  const [cards, setCards] = useState<RecallCard[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchText, setSearchText] = useState(query);
  const debouncedSearch = useDebouncedValue(searchText, 300);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeckId, setBulkDeckId] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editingDeck, setEditingDeck] = useState<RecallDeck | null>(null);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const requestId = useRef(0);

  const selectedDeck = decks.find((deck) => deck.deck_id === deckId) ?? null;
  const archived = Boolean(selectedDeck?.archived_at);
  const deckMissing = Boolean(deckId) && decksReady && !selectedDeck;
  const activeDecks = decks.filter((deck) => !deck.archived_at);

  const setParam = useCallback(
    (key: string, value: string | null) => {
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
    setParam("q", debouncedSearch.trim() || null);
  }, [debouncedSearch, query, setParam]);

  const loadDecks = useCallback(async () => {
    try {
      const result = await fetchRecallDecks(true);
      setDecks(result.decks);
      setDecksReady(true);
      return result.decks;
    } catch (err) {
      setDecksReady(true);
      setError(err instanceof Error ? err.message : "Couldn't load your decks.");
      return [];
    }
  }, []);

  useEffect(() => {
    void loadDecks();
  }, [loadDecks]);

  useEffect(() => {
    if (!bulkDeckId && decks.length > 0) {
      const fallback = decks.find((deck) => !deck.archived_at && deck.is_default) ?? decks.find((deck) => !deck.archived_at);
      if (fallback) setBulkDeckId(fallback.deck_id);
    }
  }, [bulkDeckId, decks]);

  const loadCards = useCallback(
    async (offset: number, append: boolean, refresh = false) => {
      if (!decksReady) return;
      if (deckId && !selectedDeck) {
        setCards([]);
        setTotal(0);
        setLoading(false);
        return;
      }
      const id = ++requestId.current;
      if (refresh) setRefreshing(true);
      else if (append) setLoadingMore(true);
      else setLoading(true);
      setError(null);
      try {
        const result = await fetchRecallCards({
          deckId: deckId ?? null,
          includeNotDue: true,
          status: archived ? "suspended" : statusFilter,
          state: state || undefined,
          q: query || undefined,
          due: archived ? undefined : due || undefined,
          sourceNoteId: sourceNoteId || undefined,
          sort,
          limit: PAGE_SIZE,
          offset,
        });
        if (id !== requestId.current) return;
        setCards((current) => (append ? [...current, ...result.cards] : result.cards));
        setTotal(result.total);
        if (!append) setSelectedIds(new Set());
      } catch (err) {
        if (id !== requestId.current) return;
        setError(err instanceof Error ? err.message : "Couldn't load recall cards.");
      } finally {
        if (id === requestId.current) {
          setLoading(false);
          setLoadingMore(false);
          setRefreshing(false);
        }
      }
    },
    [archived, deckId, decksReady, due, query, selectedDeck, sort, sourceNoteId, state, statusFilter],
  );

  useEffect(() => {
    void loadCards(0, false);
  }, [loadCards]);

  const allStats = useMemo(() => {
    return activeDecks.reduce(
      (acc, deck) => ({
        total: acc.total + deck.total_cards,
        due: acc.due + deck.due_cards,
        newCards: acc.newCards + deck.new_cards,
        suspended: acc.suspended + deck.suspended_cards,
      }),
      { total: 0, due: 0, newCards: 0, suspended: 0 },
    );
  }, [activeDecks]);

  const stats = selectedDeck
    ? {
        total: selectedDeck.total_cards,
        due: selectedDeck.due_cards,
        newCards: selectedDeck.new_cards,
        suspended: selectedDeck.suspended_cards,
      }
    : allStats;

  const clearFilters = () => {
    setSearchText("");
    const next = new URLSearchParams(searchParams);
    ["q", "state", "due", "sort", "note"].forEach((key) => next.delete(key));
    setSearchParams(next, { replace: true });
  };

  const handleMoveCard = async (card: RecallCard, nextDeckId: string) => {
    if (!nextDeckId || nextDeckId === card.deck_id) return;
    setError(null);
    try {
      await updateRecallCard(card.card_id, { deck_id: nextDeckId });
      await loadCards(0, false, true);
      await loadDecks();
    } catch (err) {
      setError(cardErrorMessage(err, "Couldn't move that card."));
    }
  };

  const applyBulkUpdate = async (
    cardIds: string[],
    patch: { deck_id?: string; status?: "active" | "suspended" },
  ) => {
    for (let index = 0; index < cardIds.length; index += BULK_LIMIT) {
      await bulkUpdateRecallCards({
        ...patch,
        card_ids: cardIds.slice(index, index + BULK_LIMIT),
      });
    }
  };

  const handleBulkMove = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0 || !bulkDeckId) return;
    setBulkBusy(true);
    setError(null);
    try {
      await applyBulkUpdate(ids, { deck_id: bulkDeckId });
      setSelectedIds(new Set());
      await loadCards(0, false, true);
      await loadDecks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't move the selected cards.");
    } finally {
      setBulkBusy(false);
    }
  };

  const handleBulkStatus = async (nextStatus: "active" | "suspended") => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    setBulkBusy(true);
    setError(null);
    try {
      await applyBulkUpdate(ids, { status: nextStatus });
      setSelectedIds(new Set());
      await loadCards(0, false, true);
      await loadDecks();
    } catch (err) {
      setError(
        cardErrorMessage(
          err,
          `Couldn't ${nextStatus === "suspended" ? "suspend" : "restore"} the selected cards.`,
        ),
      );
    } finally {
      setBulkBusy(false);
    }
  };

  const handleSavedDeck = (deck: RecallDeck) => {
    setDecks((current) => {
      const exists = current.some((item) => item.deck_id === deck.deck_id);
      return exists
        ? current.map((item) => (item.deck_id === deck.deck_id ? { ...item, ...deck } : item))
        : [...current, deck];
    });
  };

  const handleArchive = async () => {
    if (!selectedDeck) return;
    setArchiving(true);
    setError(null);
    try {
      await archiveRecallDeck(selectedDeck.deck_id);
      setConfirmArchive(false);
      await loadDecks();
      await loadCards(0, false, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't archive this deck.");
    } finally {
      setArchiving(false);
    }
  };

  const handleRestore = async () => {
    if (!selectedDeck) return;
    setRestoring(true);
    setError(null);
    try {
      await restoreRecallDeck(selectedDeck.deck_id);
      await loadDecks();
      await loadCards(0, false, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't restore this deck.");
    } finally {
      setRestoring(false);
    }
  };

  const allSelected = cards.length > 0 && cards.every((card) => selectedIds.has(card.card_id));
  const activeDeckOptions = activeDecks;

  return (
    <div className="grid gap-6 lg:grid-cols-[250px_minmax(0,1fr)]">
      <aside className="min-w-0 self-start lg:sticky lg:top-6">
        <DeckRail
          decks={decks}
          selectedDeckId={selectedDeck?.deck_id}
          allTotal={allStats.total}
          allDue={allStats.due}
          onNewDeck={() => {
            setEditingDeck(null);
            setFormOpen(true);
          }}
        />
      </aside>

      <div className="min-w-0 space-y-4">
        <DeckStatsHeader
          deck={selectedDeck}
          total={stats.total}
          due={stats.due}
          newCards={stats.newCards}
          suspended={stats.suspended}
          onEdit={() => {
            if (!selectedDeck) return;
            setEditingDeck(selectedDeck);
            setFormOpen(true);
          }}
          onArchive={() => setConfirmArchive(true)}
          onRestore={() => void handleRestore()}
          onRefresh={() => void Promise.all([loadCards(0, false, true), loadDecks()])}
          refreshing={refreshing || restoring}
        />

        {sourceNoteId ? (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-accent-200 bg-accent-50 px-3.5 py-2.5 text-xs text-accent-800">
            <span className="inline-flex items-center gap-1.5 font-medium">
              <NotePencil size={14} />
              Showing cards created from one note.
            </span>
            <button
              type="button"
              onClick={() => setParam("note", null)}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-semibold hover:bg-accent-100"
            >
              <X size={12} />
              Clear
            </button>
          </div>
        ) : null}

        <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-card">
          <CardFilters
            query={searchText}
            state={state}
            due={due}
            status={archived ? "suspended" : statusFilter}
            sort={sort}
            total={total}
            loading={loading}
            disabled={deckMissing || archived}
            onQueryChange={setSearchText}
            onStateChange={(value) => setParam("state", value || null)}
            onDueChange={(value) => setParam("due", value || null)}
            onStatusChange={(value) => setParam("status", value)}
            onSortChange={(value) => setParam("sort", value === "due" ? null : value)}
            onClear={clearFilters}
          />
        </div>

        {error ? (
          <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </p>
        ) : null}

        {deckMissing ? (
          <div className="rounded-2xl border border-neutral-200 bg-white px-6 py-12 text-center shadow-card">
            <p className="font-display text-lg font-semibold text-neutral-950">Deck not found</p>
            <p className="mt-1.5 text-sm text-neutral-500">It may have been removed or belong to another account.</p>
            <Link
              to="/app/library/recall"
              className="mt-5 inline-flex h-9 items-center justify-center rounded-lg bg-neutral-950 px-3 text-xs font-semibold text-white hover:bg-neutral-800"
            >
              Browse all cards
            </Link>
          </div>
        ) : loading ? (
          <div className="space-y-2" aria-label="Loading recall cards">
            {[0, 1, 2].map((item) => (
              <div key={item} className="h-32 animate-pulse rounded-2xl bg-neutral-100" />
            ))}
          </div>
        ) : cards.length === 0 ? (
          <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-white px-6 py-14 text-center shadow-card">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100 text-neutral-500">
              <Cards size={20} weight="bold" />
            </span>
            <p className="mt-5 font-display text-lg font-semibold text-neutral-950">
              {archived ? "No suspended cards in this deck" : "No cards match these filters"}
            </p>
            <p className="mt-1.5 max-w-sm text-sm text-neutral-500">
              {archived
                ? "This archived deck has no cards left to restore."
                : sourceNoteId
                  ? "This note has no recall cards yet. Verify its questions to create some."
                  : "Try clearing the search and filters, or add questions from a note."}
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <button
                type="button"
                onClick={clearFilters}
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
              >
                <ArrowClockwise size={13} />
                Clear filters
              </button>
              <Link
                to="/app/notes"
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-neutral-950 px-3 text-xs font-semibold text-white hover:bg-neutral-800"
              >
                <NotePencil size={13} />
                Write a note
              </Link>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-3 px-1">
              <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-neutral-600">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(event) => {
                    setSelectedIds(
                      event.target.checked ? new Set(cards.map((card) => card.card_id)) : new Set(),
                    );
                  }}
                  className="h-4 w-4 rounded border-neutral-300 text-neutral-950 focus:ring-neutral-950"
                />
                Select all loaded
              </label>
              <p className="text-xs text-neutral-400">
                {cards.length} of {total} loaded
              </p>
            </div>

            <ul className="space-y-2">
              {cards.map((card) => (
                <RecallCardRow
                  key={card.card_id}
                  card={card}
                  decks={activeDeckOptions}
                  deck={decks.find((deck) => deck.deck_id === card.deck_id) ?? null}
                  selected={selectedIds.has(card.card_id)}
                  disabled={archived}
                  onSelect={(checked) => {
                    setSelectedIds((current) => {
                      const next = new Set(current);
                      if (checked) next.add(card.card_id);
                      else next.delete(card.card_id);
                      return next;
                    });
                  }}
                  onDeckChange={(nextDeckId) => void handleMoveCard(card, nextDeckId)}
                  onCreateDeck={() => {
                    setEditingDeck(null);
                    setFormOpen(true);
                  }}
                />
              ))}
            </ul>

            <div className="flex items-center justify-end">
              {cards.length < total ? (
                <button
                  type="button"
                  onClick={() => void loadCards(cards.length, true)}
                  disabled={loadingMore}
                  className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-100 disabled:cursor-wait disabled:opacity-60"
                >
                  {loadingMore ? <Spinner size={13} className="animate-spin" /> : null}
                  {loadingMore ? "Loading…" : "Load more"}
                </button>
              ) : null}
            </div>
          </>
        )}
      </div>

      {selectedIds.size > 0 && !archived ? (
        <div className="sticky bottom-4 z-20 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-neutral-200 bg-white p-3 shadow-soft lg:col-start-2">
          <p className="inline-flex items-center gap-1.5 text-xs font-semibold text-neutral-700">
            <CheckCircle size={14} weight="fill" className="text-accent-600" />
            {selectedIds.size} selected
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <DeckPicker
              decks={activeDeckOptions}
              value={bulkDeckId}
              onChange={setBulkDeckId}
              disabled={bulkBusy}
              compact
              label="Move to"
            />
            <Button size="sm" variant="outline" disabled={bulkBusy || !bulkDeckId} onClick={() => void handleBulkMove()}>
              Move
            </Button>
            {statusFilter !== "active" ? (
              <Button size="sm" variant="ghost" disabled={bulkBusy} onClick={() => void handleBulkStatus("active")}>
                <ArrowClockwise size={14} />
                Restore
              </Button>
            ) : null}
            {statusFilter !== "suspended" ? (
              <Button size="sm" variant="ghost" disabled={bulkBusy} onClick={() => void handleBulkStatus("suspended")}>
                <Archive size={14} />
                Suspend
              </Button>
            ) : null}
            <button
              type="button"
              onClick={() => setSelectedIds(new Set())}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-neutral-400 hover:bg-neutral-100 hover:text-neutral-950"
              aria-label="Clear selection"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      ) : null}

      <DeckFormModal
        open={formOpen}
        deck={editingDeck}
        onClose={() => setFormOpen(false)}
        onSaved={handleSavedDeck}
      />

      <Modal open={confirmArchive} onClose={() => setConfirmArchive(false)} title="Archive this deck?">
        <p className="text-sm leading-relaxed text-neutral-600">
          {selectedDeck?.name} and its {selectedDeck?.total_cards ?? 0} active card
          {selectedDeck?.total_cards === 1 ? "" : "s"} will be suspended. Review history is kept, and you can
          restore the deck later.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => setConfirmArchive(false)} disabled={archiving}>
            Cancel
          </Button>
          <Button size="sm" onClick={() => void handleArchive()} disabled={archiving}>
            {archiving ? <Spinner size={14} className="animate-spin" /> : <Archive size={14} />}
            Archive deck
          </Button>
        </div>
      </Modal>
    </div>
  );
}
