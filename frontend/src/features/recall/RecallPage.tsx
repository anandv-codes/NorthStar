import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowClockwise,
  ArrowRight,
  Cards,
  CheckCircle,
  ClockCounterClockwise,
  NotePencil,
  Plus,
  Sparkle,
} from "@phosphor-icons/react";
import {
  fetchRecallDecks,
  fetchSuggestions,
  type RecallDeck,
} from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { DeckCard } from "./components/DeckCard";
import { DeckFormModal } from "./components/DeckFormModal";

export function RecallPage() {
  const navigate = useNavigate();
  const [decks, setDecks] = useState<RecallDeck[]>([]);
  const [suggestionCount, setSuggestionCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingDeck, setEditingDeck] = useState<RecallDeck | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [deckList, suggestions] = await Promise.all([fetchRecallDecks(true), fetchSuggestions(1)]);
      setDecks(deckList.decks);
      setSuggestionCount(suggestions.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load your recall decks.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSavedDeck = (deck: RecallDeck) => {
    setDecks((current) => {
      const exists = current.some((item) => item.deck_id === deck.deck_id);
      return exists
        ? current.map((item) => (item.deck_id === deck.deck_id ? { ...item, ...deck } : item))
        : [...current, deck];
    });
  };

  const activeDecks = decks.filter((deck) => !deck.archived_at);
  const archivedDecks = decks.filter((deck) => Boolean(deck.archived_at));
  const totalDue = activeDecks.reduce((sum, deck) => sum + deck.due_cards, 0);
  const totalCards = activeDecks.reduce((sum, deck) => sum + deck.total_cards, 0);
  const hasCards = totalCards > 0;

  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">Recall</h1>
            <p className="mt-1 max-w-xl text-sm text-neutral-500">
              Review by category, or let NorthStar decide what is due today.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {suggestionCount > 0 ? (
              <Button variant="outline" onClick={() => navigate("/app/recall/verify")}>
                <CheckCircle size={16} weight="bold" />
                Verify {suggestionCount} new
              </Button>
            ) : null}
            <Button onClick={() => navigate(totalDue > 0 ? "/app/recall/study/all?mode=due" : "/app/recall/study/all?mode=all")}>
              <ClockCounterClockwise size={16} weight="bold" />
              {totalDue > 0 ? `Review ${totalDue} due` : "Review all cards"}
            </Button>
          </div>
        </div>
      </header>

      {error ? (
        <p role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      <div className="mb-6 grid grid-cols-3 overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-card">
        {[
          { label: "Due today", value: totalDue, icon: ClockCounterClockwise },
          { label: "Cards", value: totalCards, icon: Cards },
          { label: "New questions", value: suggestionCount, icon: Sparkle },
        ].map(({ label, value, icon: Icon }, index) => (
          <div
            key={label}
            className={`flex items-center gap-3 px-4 py-4 sm:px-5 ${index > 0 ? "border-l border-neutral-100" : ""}`}
          >
            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-neutral-100 text-neutral-600">
              <Icon size={16} weight="bold" />
            </span>
            <div className="min-w-0">
              <p className="text-lg font-semibold leading-none text-neutral-950">{loading ? "—" : value}</p>
              <p className="mt-1 truncate text-[11px] font-medium text-neutral-500">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="flex min-h-[240px] items-center justify-center rounded-2xl border border-neutral-200 bg-white shadow-card">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-950" />
        </div>
      ) : (
        <>
          <section aria-labelledby="decks-heading">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 id="decks-heading" className="text-xs font-semibold uppercase tracking-[0.15em] text-neutral-400">
                Your decks
              </h2>
              <button
                type="button"
                onClick={() => {
                  setEditingDeck(null);
                  setFormOpen(true);
                }}
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-semibold text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950"
              >
                <Plus size={14} weight="bold" />
                New deck
              </button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {activeDecks.map((deck) => (
                <DeckCard
                  key={deck.deck_id}
                  deck={deck}
                  onEdit={(item) => {
                    setEditingDeck(item);
                    setFormOpen(true);
                  }}
                />
              ))}
            </div>

            {archivedDecks.length > 0 ? (
              <div className="mt-6">
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.15em] text-neutral-400">
                  Archived
                </h3>
                <ul className="space-y-2">
                  {archivedDecks.map((deck) => (
                    <li
                      key={deck.deck_id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-neutral-200 bg-white px-4 py-3"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-neutral-700">{deck.name}</p>
                        <p className="text-xs text-neutral-400">
                          {deck.total_cards} active · {deck.suspended_cards} suspended
                        </p>
                      </div>
                      <Link
                        to={`/app/recall/decks/${deck.deck_id}`}
                        className="inline-flex h-8 items-center justify-center rounded-lg border border-neutral-200 px-3 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
                      >
                        Manage
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>

          {!hasCards ? (
            <div className="mt-6 flex flex-col items-center rounded-2xl border border-neutral-200 bg-white py-12 text-center shadow-card">
              <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100 text-neutral-500">
                <Sparkle size={20} weight="bold" />
              </span>
              <p className="mt-5 font-display text-lg font-semibold text-neutral-950">No cards yet</p>
              <p className="mt-1.5 max-w-sm text-sm text-neutral-500">
                Add a note with recall turned on, verify its questions, and file them into a deck.
              </p>
              <Link
                to="/app/notes"
                className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-accent-600 hover:text-accent-700"
              >
                <NotePencil size={16} />
                Write a note
              </Link>
            </div>
          ) : null}

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-neutral-200 bg-white px-5 py-4 shadow-card">
            <div>
              <p className="text-sm font-semibold text-neutral-950">Review everything</p>
              <p className="mt-0.5 text-xs text-neutral-500">
                Includes cards that are not due yet. Grades still update scheduling.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                to="/app/recall/study/all?mode=due"
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-neutral-200 px-3 text-xs font-semibold text-neutral-700 transition-colors hover:bg-neutral-100"
              >
                Due only
                <ArrowRight size={13} weight="bold" />
              </Link>
              <Link
                to="/app/recall/study/all?mode=all"
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-neutral-950 px-3 text-xs font-semibold text-white transition-colors hover:bg-neutral-800"
              >
                All cards
                <ArrowRight size={13} weight="bold" />
              </Link>
            </div>
          </div>
        </>
      )}

      <DeckFormModal
        open={formOpen}
        deck={editingDeck}
        onClose={() => setFormOpen(false)}
        onSaved={handleSavedDeck}
      />

      <button
        type="button"
        onClick={() => void load()}
        className="mt-6 inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium text-neutral-500 transition-colors hover:text-neutral-950"
      >
        <ArrowClockwise size={14} />
        Refresh
      </button>
    </div>
  );
}
