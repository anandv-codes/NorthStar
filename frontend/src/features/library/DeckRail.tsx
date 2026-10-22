import { Link, useSearchParams } from "react-router-dom";
import { Archive, Cards, Plus } from "@phosphor-icons/react";
import clsx from "clsx";
import type { RecallDeck } from "../../shared/api/httpClient";
import { deckColorStyle } from "../recall/deckColors";

interface DeckRailProps {
  decks: RecallDeck[];
  selectedDeckId?: string;
  allTotal: number;
  allDue: number;
  onNewDeck: () => void;
}

export function DeckRail({ decks, selectedDeckId, allTotal, allDue, onNewDeck }: DeckRailProps) {
  const [searchParams] = useSearchParams();
  const active = decks.filter((deck) => !deck.archived_at);
  const archived = decks.filter((deck) => Boolean(deck.archived_at));

  const href = (deckId?: string) => {
    const next = new URLSearchParams(searchParams);
    const base = deckId ? `/app/library/recall/${deckId}` : "/app/library/recall";
    const query = next.toString();
    return query ? `${base}?${query}` : base;
  };

  const itemClass = (selected: boolean) =>
    clsx(
      "flex min-w-[190px] shrink-0 items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950 lg:min-w-0 lg:shrink lg:w-full",
      selected
        ? "border-neutral-950 bg-neutral-950 text-white"
        : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300 hover:bg-neutral-50",
    );

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-neutral-400">Decks</h2>
        <button
          type="button"
          onClick={onNewDeck}
          className="inline-flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-neutral-600 hover:bg-neutral-100 hover:text-neutral-950"
        >
          <Plus size={13} weight="bold" />
          New
        </button>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible">
        <Link to={href()} className={itemClass(!selectedDeckId)} aria-current={!selectedDeckId ? "page" : undefined}>
          <span
            className={clsx(
              "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
              selectedDeckId ? "bg-white/10" : "bg-neutral-100 text-neutral-600",
            )}
          >
            <Cards size={15} weight="bold" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold">All cards</span>
            <span className={clsx("block text-[11px]", selectedDeckId ? "text-neutral-500" : "text-white/65")}>
              {allDue} due · {allTotal} active
            </span>
          </span>
        </Link>

        {active.map((deck) => {
          const style = deckColorStyle(deck.color);
          const selected = selectedDeckId === deck.deck_id;
          return (
            <Link
              key={deck.deck_id}
              to={href(deck.deck_id)}
              aria-current={selected ? "page" : undefined}
              className={itemClass(selected)}
            >
              <span className={clsx("h-2.5 w-2.5 shrink-0 rounded-full", style.dot)} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">{deck.name}</span>
                <span className={clsx("block text-[11px]", selected ? "text-white/65" : "text-neutral-400")}>
                  {deck.due_cards} due · {deck.total_cards} card{deck.total_cards === 1 ? "" : "s"}
                </span>
              </span>
              {deck.is_default ? (
                <span
                  className={clsx(
                    "shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                    selected ? "bg-white/15 text-white/80" : "bg-neutral-100 text-neutral-500",
                  )}
                >
                  Default
                </span>
              ) : null}
            </Link>
          );
        })}
      </div>

      {archived.length > 0 ? (
        <div className="mt-4">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-neutral-400">
            Archived
          </p>
          <div className="space-y-1.5">
            {archived.map((deck) => {
              const selected = selectedDeckId === deck.deck_id;
              return (
                <Link
                  key={deck.deck_id}
                  to={href(deck.deck_id)}
                  aria-current={selected ? "page" : undefined}
                  className={clsx(
                    "flex items-center gap-2 rounded-lg border px-2.5 py-2 text-xs transition-colors",
                    selected
                      ? "border-neutral-950 bg-white text-neutral-950"
                      : "border-transparent text-neutral-500 hover:border-neutral-200 hover:bg-white hover:text-neutral-950",
                  )}
                >
                  <Archive size={13} />
                  <span className="min-w-0 flex-1 truncate font-medium">{deck.name}</span>
                  <span className="text-[10px] text-neutral-400">{deck.suspended_cards}</span>
                </Link>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
