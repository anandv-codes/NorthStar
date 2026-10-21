import type { RecallDeckColor } from "../../shared/api/httpClient";

interface DeckColorStyle {
  dot: string;
  bar: string;
  soft: string;
  text: string;
}

export const DECK_COLOR_STYLES: Record<RecallDeckColor, DeckColorStyle> = {
  neutral: {
    dot: "bg-neutral-400",
    bar: "bg-neutral-300",
    soft: "bg-neutral-100",
    text: "text-neutral-600",
  },
  amber: {
    dot: "bg-amber-400",
    bar: "bg-amber-300",
    soft: "bg-amber-50",
    text: "text-amber-700",
  },
  emerald: {
    dot: "bg-emerald-400",
    bar: "bg-emerald-300",
    soft: "bg-emerald-50",
    text: "text-emerald-700",
  },
  sky: {
    dot: "bg-sky-400",
    bar: "bg-sky-300",
    soft: "bg-sky-50",
    text: "text-sky-700",
  },
  violet: {
    dot: "bg-violet-400",
    bar: "bg-violet-300",
    soft: "bg-violet-50",
    text: "text-violet-700",
  },
  rose: {
    dot: "bg-rose-400",
    bar: "bg-rose-300",
    soft: "bg-rose-50",
    text: "text-rose-700",
  },
};

export const DECK_COLOR_OPTIONS = Object.keys(DECK_COLOR_STYLES) as RecallDeckColor[];

export function deckColorStyle(color: RecallDeckColor | undefined) {
  return DECK_COLOR_STYLES[color ?? "neutral"] ?? DECK_COLOR_STYLES.neutral;
}

export function formatDueDate(value?: string | null): string {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not scheduled";
  const now = new Date();
  const dayMs = 24 * 60 * 60 * 1000;
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfDue = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const days = Math.round((startOfDue - startOfToday) / dayMs);
  if (days <= 0) return "Due now";
  if (days === 1) return "Due tomorrow";
  if (days < 7) return `Due in ${days} days`;
  return `Due ${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}
