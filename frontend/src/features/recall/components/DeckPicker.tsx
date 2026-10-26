import { useId } from "react";
import { Plus } from "@phosphor-icons/react";
import type { RecallDeck } from "../../../shared/api/httpClient";

interface DeckPickerProps {
  decks: RecallDeck[];
  value: string | null | undefined;
  onChange: (deckId: string) => void;
  onCreate?: () => void;
  disabled?: boolean;
  label?: string;
  compact?: boolean;
}

export function DeckPicker({
  decks,
  value,
  onChange,
  onCreate,
  disabled = false,
  label = "Deck",
  compact = false,
}: DeckPickerProps) {
  const id = useId();
  const activeDecks = decks.filter((deck) => !deck.archived_at);

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <label
        htmlFor={id}
        className={compact ? "text-[11px] font-semibold uppercase tracking-wide text-neutral-400" : "text-xs font-semibold text-neutral-700"}
      >
        {label}
      </label>
      <select
        id={id}
        value={value ?? ""}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className={
          compact
            ? "max-w-[11rem] cursor-pointer truncate rounded-lg border border-neutral-200 bg-white px-2 py-1 text-xs font-medium text-neutral-700 focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-200 disabled:cursor-not-allowed disabled:opacity-50"
            : "min-w-[12rem] flex-1 cursor-pointer rounded-xl border border-neutral-300 bg-white px-3 py-2.5 text-sm font-semibold text-neutral-800 shadow-sm focus:border-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-200 disabled:cursor-not-allowed disabled:opacity-50"
        }
      >
        {value == null ? <option value="">Choose a deck</option> : null}
        {activeDecks.map((deck) => (
          <option key={deck.deck_id} value={deck.deck_id}>
            {deck.name}
          </option>
        ))}
      </select>
      {onCreate ? (
        <button
          type="button"
          onClick={onCreate}
          disabled={disabled}
          className="inline-flex cursor-pointer items-center gap-1 rounded-lg px-1.5 py-1 text-xs font-medium text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-950 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus size={12} weight="bold" />
          New
        </button>
      ) : null}
    </div>
  );
}
