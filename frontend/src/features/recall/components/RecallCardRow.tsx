import { useState } from "react";
import { Link } from "react-router-dom";
import { CaretDown, CaretUp, Clock, NotePencil, Repeat } from "@phosphor-icons/react";
import clsx from "clsx";
import type { RecallCard, RecallDeck } from "../../../shared/api/httpClient";
import { DeckPicker } from "./DeckPicker";
import { deckColorStyle, formatDueDate } from "../deckColors";
import { formatLibraryDate } from "../../library/libraryUtils";

interface RecallCardRowProps {
  card: RecallCard;
  decks: RecallDeck[];
  deck?: RecallDeck | null;
  selected: boolean;
  disabled?: boolean;
  onSelect: (selected: boolean) => void;
  onDeckChange: (deckId: string) => void;
  onCreateDeck: () => void;
}

const STATE_STYLES: Record<string, string> = {
  new: "bg-sky-50 text-sky-700",
  learning: "bg-amber-50 text-amber-800",
  review: "bg-emerald-50 text-emerald-700",
  relearning: "bg-rose-50 text-rose-700",
};

export function RecallCardRow({
  card,
  decks,
  deck,
  selected,
  disabled = false,
  onSelect,
  onDeckChange,
  onCreateDeck,
}: RecallCardRowProps) {
  const [expanded, setExpanded] = useState(false);
  const style = deckColorStyle(deck?.color);

  return (
    <li
      className={clsx(
        "rounded-2xl border bg-white p-4 shadow-card transition-colors",
        selected ? "border-neutral-950" : "border-neutral-200",
      )}
    >
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={(event) => onSelect(event.target.checked)}
          disabled={disabled}
          aria-label={`Select question: ${card.question}`}
          className="mt-1 h-4 w-4 shrink-0 rounded border-neutral-300 text-neutral-950 focus:ring-neutral-950 disabled:opacity-40"
        />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold leading-relaxed text-neutral-950">{card.question}</p>
              <p
                className={clsx(
                  "mt-1 text-xs leading-relaxed text-neutral-500",
                  expanded ? "" : "line-clamp-2",
                )}
              >
                {card.answer}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setExpanded((current) => !current)}
              aria-expanded={expanded}
              aria-label={expanded ? "Hide card details" : "Show card details"}
              className="inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg text-neutral-400 hover:bg-neutral-100 hover:text-neutral-950"
            >
              {expanded ? <CaretUp size={15} /> : <CaretDown size={15} />}
            </button>
          </div>

          <div className="mt-2.5 flex flex-wrap items-center gap-2 text-[11px]">
            {deck ? (
              <span
                className={clsx(
                  "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-semibold",
                  style.soft,
                  style.text,
                )}
              >
                <span aria-hidden="true" className={clsx("h-2 w-2 rounded-full", style.dot)} />
                {deck.name}
              </span>
            ) : null}
            <span className={clsx("rounded-full px-2 py-0.5 font-semibold capitalize", STATE_STYLES[card.state] ?? "bg-neutral-100 text-neutral-600")}>
              {card.state}
            </span>
            <span className="inline-flex items-center gap-1 text-neutral-500">
              <Clock size={11} />
              {formatDueDate(card.next_due)}
            </span>
            <span className="inline-flex items-center gap-1 text-neutral-400">
              <Repeat size={11} />
              {card.review_count} review{card.review_count === 1 ? "" : "s"}
            </span>
            {card.lapses > 0 ? <span className="text-rose-600">{card.lapses} lapse{card.lapses === 1 ? "" : "s"}</span> : null}
            {card.status === "suspended" ? (
              <span className="rounded-full bg-neutral-100 px-2 py-0.5 font-semibold text-neutral-500">Suspended</span>
            ) : null}
          </div>

          {expanded ? (
            <div className="mt-3 grid gap-3 rounded-xl bg-neutral-50 p-3 text-[11px] text-neutral-500 sm:grid-cols-2">
              <p>
                <span className="font-semibold text-neutral-700">Interval:</span> {card.interval} day
                {card.interval === 1 ? "" : "s"}
              </p>
              <p>
                <span className="font-semibold text-neutral-700">Ease:</span> {card.easiness.toFixed(2)}
              </p>
              <p>
                <span className="font-semibold text-neutral-700">Repetitions:</span> {card.repetitions}
              </p>
              <p>
                <span className="font-semibold text-neutral-700">Last reviewed:</span>{" "}
                {card.last_reviewed ? formatLibraryDate(card.last_reviewed) : "Never"}
              </p>
              {card.source_note_ids.length > 0 ? (
                <p className="sm:col-span-2">
                  <span className="font-semibold text-neutral-700">Source note:</span>{" "}
                  <Link
                    to={`/app/library/notes/${card.source_note_ids[0]}`}
                    className="inline-flex items-center gap-1 font-medium text-neutral-700 underline-offset-2 hover:text-neutral-950 hover:underline"
                  >
                    <NotePencil size={11} />
                    Open note
                  </Link>
                  {card.source_note_ids.length > 1 ? (
                    <span className="text-neutral-400"> +{card.source_note_ids.length - 1} more</span>
                  ) : null}
                </p>
              ) : null}
            </div>
          ) : null}

          {!disabled ? (
            <div className="mt-3">
              <DeckPicker
                decks={decks}
                value={card.deck_id ?? ""}
                onChange={onDeckChange}
                onCreate={onCreateDeck}
                label="Move to"
                compact
              />
            </div>
          ) : null}
        </div>
      </div>
    </li>
  );
}
