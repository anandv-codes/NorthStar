import { Link } from "react-router-dom";
import {
  Archive,
  ArrowClockwise,
  Cards,
  ClockCounterClockwise,
  PencilSimple,
  Sparkle,
  Stack,
} from "@phosphor-icons/react";
import clsx from "clsx";
import type { RecallDeck } from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { deckColorStyle } from "../recall/deckColors";

interface DeckStatsHeaderProps {
  deck: RecallDeck | null;
  total: number;
  due: number;
  newCards: number;
  suspended: number;
  onEdit: () => void;
  onArchive: () => void;
  onRestore: () => void;
  onRefresh: () => void;
  refreshing: boolean;
}

export function DeckStatsHeader({
  deck,
  total,
  due,
  newCards,
  suspended,
  onEdit,
  onArchive,
  onRestore,
  onRefresh,
  refreshing,
}: DeckStatsHeaderProps) {
  const style = deckColorStyle(deck?.color);
  const archived = Boolean(deck?.archived_at);
  const studyBase = deck ? `/app/recall/study/${deck.deck_id}` : "/app/recall/study/all";
  const stats = [
    { label: "Due now", value: due, icon: ClockCounterClockwise, tone: "text-amber-700" },
    { label: "Active", value: total, icon: Cards, tone: "text-neutral-700" },
    { label: "New", value: newCards, icon: Sparkle, tone: "text-sky-700" },
    { label: "Suspended", value: suspended, icon: Archive, tone: "text-neutral-500" },
  ];

  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-card sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span aria-hidden="true" className={clsx("h-3 w-3 rounded-full", style.dot)} />
            <h2 className="truncate font-display text-xl font-semibold tracking-tight text-neutral-950">
              {deck?.name ?? "All cards"}
            </h2>
            {deck?.is_default ? (
              <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-500">
                Default
              </span>
            ) : null}
            {archived ? (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                Archived
              </span>
            ) : null}
          </div>
          <p className="mt-1 max-w-xl text-sm text-neutral-500">
            {deck?.description || (deck ? "No description yet." : "Browse every active card across your decks.")}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {!archived ? (
            <>
              <Link
                to={`${studyBase}?mode=due`}
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-neutral-950 px-3 text-xs font-semibold text-white hover:bg-neutral-800"
              >
                <ClockCounterClockwise size={14} weight="bold" />
                Study due
              </Link>
              <Link
                to={`${studyBase}?mode=all`}
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
              >
                <Stack size={14} weight="bold" />
                Review all
              </Link>
            </>
          ) : null}
          {deck ? (
            <Button size="sm" variant="outline" onClick={onEdit}>
              <PencilSimple size={14} />
              Edit
            </Button>
          ) : null}
          {deck && !archived && !deck.is_default ? (
            <Button size="sm" variant="ghost" onClick={onArchive}>
              <Archive size={14} />
              Archive
            </Button>
          ) : null}
          {archived ? (
            <Button size="sm" variant="outline" onClick={onRestore}>
              Restore
            </Button>
          ) : null}
          <button
            type="button"
            onClick={onRefresh}
            aria-label="Refresh cards"
            title="Refresh cards"
            className="inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border border-neutral-200 bg-white text-neutral-500 hover:bg-neutral-100 hover:text-neutral-950"
          >
            <ArrowClockwise size={14} className={refreshing ? "animate-spin" : undefined} />
          </button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 border-t border-neutral-100 pt-4 sm:grid-cols-4">
        {stats.map(({ label, value, icon: Icon, tone }) => (
          <div key={label} className="rounded-xl bg-neutral-50 px-3 py-2.5">
            <p className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-neutral-400">
              <Icon size={11} weight="bold" className={tone} />
              {label}
            </p>
            <p className="mt-1 text-lg font-semibold leading-none text-neutral-950">{value}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
