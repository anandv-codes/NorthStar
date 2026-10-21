import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowClockwise,
  ArrowLeft,
  ArrowRight,
  Cards,
  ClockCounterClockwise,
  PencilSimple,
  Spinner,
  Trash,
} from "@phosphor-icons/react";
import {
  archiveRecallDeck,
  fetchRecallCards,
  fetchRecallDecks,
  moveRecallCard,
  restoreRecallDeck,
  type RecallCard,
  type RecallDeck,
} from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { Modal } from "../../shared/ui/Modal";
import { DeckFormModal } from "./components/DeckFormModal";
import { DeckPicker } from "./components/DeckPicker";
import { deckColorStyle, formatDueDate } from "./deckColors";

export function DeckDetailPage() {
  const { deckId = "" } = useParams();
  const [decks, setDecks] = useState<RecallDeck[]>([]);
  const [deck, setDeck] = useState<RecallDeck | null>(null);
  const [cards, setCards] = useState<RecallCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [movingCardId, setMovingCardId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const deckList = await fetchRecallDecks(true);
      setDecks(deckList.decks);
      const found = deckList.decks.find((item) => item.deck_id === deckId) ?? null;
      setDeck(found);
      if (!found) {
        setError("That deck no longer exists.");
        setCards([]);
        return;
      }
      const cardList = await fetchRecallCards({
        deckId,
        includeNotDue: true,
        status: found.archived_at ? "suspended" : "active",
        limit: 500,
      });
      setCards(cardList.cards);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load this deck.");
    } finally {
      setLoading(false);
    }
  }, [deckId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleMove = async (card: RecallCard, nextDeckId: string) => {
    if (!nextDeckId || nextDeckId === card.deck_id) return;
    setMovingCardId(card.card_id);
    setError(null);
    try {
      await moveRecallCard(card.card_id, nextDeckId);
      setCards((current) => current.filter((item) => item.card_id !== card.card_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't move that card.");
    } finally {
      setMovingCardId(null);
    }
  };

  const handleArchive = async () => {
    if (!deck) return;
    setArchiving(true);
    setError(null);
    try {
      await archiveRecallDeck(deck.deck_id);
      setConfirmArchive(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't archive this deck.");
    } finally {
      setArchiving(false);
    }
  };

  const handleRestore = async () => {
    if (!deck) return;
    setError(null);
    try {
      await restoreRecallDeck(deck.deck_id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't restore this deck.");
    }
  };

  const style = deckColorStyle(deck?.color);
  const archived = Boolean(deck?.archived_at);

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-6">
        <Link
          to="/app/recall"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-neutral-500 transition-colors hover:text-neutral-950"
        >
          <ArrowLeft size={14} />
          Back to recall
        </Link>

        {loading ? (
          <div className="mt-6 flex min-h-[120px] items-center justify-center rounded-2xl border border-neutral-200 bg-white shadow-card">
            <span className="h-7 w-7 animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-950" />
          </div>
        ) : deck ? (
          <>
            <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span aria-hidden="true" className={`h-3 w-3 rounded-full ${style.dot}`} />
                  <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">
                    {deck.name}
                  </h1>
                  {deck.is_default ? (
                    <span className="rounded-full bg-neutral-100 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
                      Default
                    </span>
                  ) : null}
                  {archived ? (
                    <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                      Archived
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 max-w-xl text-sm text-neutral-500">
                  {deck.description || "No description yet."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setFormOpen(true)}
                className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-neutral-200 px-3 text-xs font-semibold text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-950"
              >
                <PencilSimple size={14} />
                Edit
              </button>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
              <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 font-semibold ${style.soft} ${style.text}`}>
                {deck.due_cards} due
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2.5 py-1 font-medium text-neutral-600">
                <Cards size={12} weight="bold" />
                {deck.total_cards} active card{deck.total_cards === 1 ? "" : "s"}
              </span>
              {deck.suspended_cards > 0 ? (
                <span className="rounded-full bg-neutral-100 px-2.5 py-1 font-medium text-neutral-600">
                  {deck.suspended_cards} suspended
                </span>
              ) : null}
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {archived ? (
                <Button variant="outline" onClick={() => void handleRestore()}>
                  Restore deck
                </Button>
              ) : (
                <>
                  <Link
                    to={`/app/recall/study/${deck.deck_id}?mode=due`}
                    className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-neutral-950 px-4 text-sm font-semibold text-white transition-colors hover:bg-neutral-800"
                  >
                    <ClockCounterClockwise size={15} weight="bold" />
                    Study {deck.due_cards} due
                  </Link>
                  <Link
                    to={`/app/recall/study/${deck.deck_id}?mode=all`}
                    className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl border border-neutral-200 px-4 text-sm font-semibold text-neutral-700 transition-colors hover:bg-neutral-100"
                  >
                    Review all cards
                    <ArrowRight size={14} weight="bold" />
                  </Link>
                  {!deck.is_default ? (
                    <Button variant="ghost" onClick={() => setConfirmArchive(true)}>
                      <Trash size={15} />
                      Archive
                    </Button>
                  ) : null}
                </>
              )}
            </div>
          </>
        ) : null}
      </header>

      {error ? (
        <p role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      {archived ? (
        <p className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          This deck is archived and its cards are suspended. Restore it to study or move cards again.
        </p>
      ) : null}

      {!loading && deck ? (
        <section aria-labelledby="deck-cards-heading">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 id="deck-cards-heading" className="text-xs font-semibold uppercase tracking-[0.15em] text-neutral-400">
              Cards
            </h2>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium text-neutral-500 transition-colors hover:text-neutral-950"
            >
              <ArrowClockwise size={14} />
              Refresh
            </button>
          </div>

          {cards.length === 0 ? (
            <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-white py-12 text-center shadow-card">
              <p className="font-display text-lg font-semibold text-neutral-950">No cards in this deck</p>
              <p className="mt-1.5 max-w-sm text-sm text-neutral-500">
                Verify questions from a note and assign them here, or move cards from another deck.
              </p>
              <Link
                to="/app/recall/verify"
                className="mt-5 inline-flex h-9 items-center justify-center rounded-lg bg-neutral-950 px-3 text-xs font-semibold text-white hover:bg-neutral-800"
              >
                Verify questions
              </Link>
            </div>
          ) : (
            <ul className="space-y-2">
              {cards.map((card) => (
                <li
                  key={card.card_id}
                  className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-card"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium leading-relaxed text-neutral-950">{card.question}</p>
                      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-neutral-500">{card.answer}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-neutral-500">
                        <span className="rounded-full bg-neutral-100 px-2 py-0.5 font-medium capitalize">
                          {card.state}
                        </span>
                        <span>{formatDueDate(card.next_due)}</span>
                        <span>·</span>
                        <span>{card.review_count} reviews</span>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <DeckPicker
                        decks={decks.filter((item) => !item.archived_at)}
                        value={card.deck_id ?? ""}
                        onChange={(nextDeckId) => void handleMove(card, nextDeckId)}
                        disabled={archived || movingCardId === card.card_id}
                        label="Move"
                        compact
                      />
                      {movingCardId === card.card_id ? (
                        <Spinner size={15} className="animate-spin text-neutral-400" />
                      ) : null}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      <DeckFormModal
        open={formOpen}
        deck={deck}
        onClose={() => setFormOpen(false)}
        onSaved={(saved) => {
          setDeck(saved);
          setDecks((current) =>
            current.map((item) => (item.deck_id === saved.deck_id ? { ...item, ...saved } : item)),
          );
        }}
      />

      <Modal open={confirmArchive} onClose={() => setConfirmArchive(false)} title="Archive this deck?">
        <p className="text-sm leading-relaxed text-neutral-600">
          {deck?.name} and its {deck?.total_cards ?? 0} card{deck?.total_cards === 1 ? "" : "s"} will be
          suspended. Review history is kept, and you can restore the deck later.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => setConfirmArchive(false)} disabled={archiving}>
            Cancel
          </Button>
          <Button size="sm" onClick={() => void handleArchive()} disabled={archiving}>
            {archiving ? <Spinner size={14} className="animate-spin" /> : <Trash size={14} />}
            Archive deck
          </Button>
        </div>
      </Modal>
    </div>
  );
}
