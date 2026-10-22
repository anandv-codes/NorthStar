import { Link } from "react-router-dom";
import { ArrowRight, Cards, PencilSimple } from "@phosphor-icons/react";
import type { RecallDeck } from "../../../shared/api/httpClient";
import { deckColorStyle } from "../deckColors";

interface DeckCardProps {
  deck: RecallDeck;
  onEdit: (deck: RecallDeck) => void;
}

export function DeckCard({ deck, onEdit }: DeckCardProps) {
  const style = deckColorStyle(deck.color);
  const studyHref =
    deck.due_cards > 0
      ? `/app/recall/study/${deck.deck_id}?mode=due`
      : `/app/recall/study/${deck.deck_id}?mode=all`;

  return (
    <div className="group relative flex flex-col overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-card transition-shadow hover:shadow-soft">
      <span aria-hidden="true" className={`h-1 w-full ${style.bar}`} />
      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <span aria-hidden="true" className={`h-2.5 w-2.5 shrink-0 rounded-full ${style.dot}`} />
            <h3 className="truncate font-display text-base font-semibold text-neutral-950">{deck.name}</h3>
            {deck.is_default ? (
              <span className="shrink-0 rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
                Default
              </span>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => onEdit(deck)}
            aria-label={`Edit ${deck.name} deck`}
            className="inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg text-neutral-400 opacity-100 transition-colors hover:bg-neutral-100 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950 lg:opacity-0 lg:group-hover:opacity-100 lg:focus:opacity-100"
          >
            <PencilSimple size={15} />
          </button>
        </div>

        <p className="mt-1.5 line-clamp-2 min-h-[2.25rem] text-xs leading-relaxed text-neutral-500">
          {deck.description || "No description yet."}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 font-semibold ${style.soft} ${style.text}`}>
            {deck.due_cards} due
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2.5 py-1 font-medium text-neutral-600">
            <Cards size={12} weight="bold" />
            {deck.total_cards} card{deck.total_cards === 1 ? "" : "s"}
          </span>
          {deck.new_cards > 0 ? (
            <span className="rounded-full bg-neutral-100 px-2.5 py-1 font-medium text-neutral-600">
              {deck.new_cards} new
            </span>
          ) : null}
        </div>

        <div className="mt-5 flex items-center gap-2">
          <Link
            to={studyHref}
            className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg bg-neutral-950 px-3 text-xs font-semibold text-white transition-colors hover:bg-neutral-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950 focus-visible:ring-offset-2"
          >
            {deck.due_cards > 0 ? `Study ${deck.due_cards} due` : "Review all"}
            <ArrowRight size={14} weight="bold" />
          </Link>
          <Link
            to={`/app/library/recall/${deck.deck_id}`}
            className="inline-flex h-9 items-center justify-center rounded-lg border border-neutral-200 px-3 text-xs font-semibold text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950 focus-visible:ring-offset-2"
          >
            Manage
          </Link>
        </div>
      </div>
    </div>
  );
}
