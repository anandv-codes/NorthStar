import { useEffect, useMemo, useState } from "react";
import { ArrowClockwise, Check, Play, Timer, X } from "@phosphor-icons/react";
import clsx from "clsx";
import { Button } from "../../shared/ui/Button";
import { addTodayRecallSeconds } from "../../shared/lib/recallTime";

interface RecallCard {
  id: string;
  front: string;
  back: string;
  deck: string;
}

type Phase = "start" | "reviewing" | "finished";

const SAMPLE_CARDS: RecallCard[] = [
  {
    id: "1",
    front: "What was the agreed launch date for the Q3 release?",
    back: "October 14th — confirmed in the planning note from last Tuesday.",
    deck: "Product launch",
  },
  {
    id: "2",
    front: "Who owns the onboarding copy rewrite?",
    back: "Design team, with a first draft due by Friday.",
    deck: "Team tasks",
  },
  {
    id: "3",
    front: "What risk was flagged about the pricing page?",
    back: "The annual discount wasn't reflected correctly in the checkout flow.",
    deck: "Risks",
  },
  {
    id: "4",
    front: "What concept kept coming up this week?",
    back: "\"Grounded answers\" — tying chat responses back to source notes.",
    deck: "Concepts",
  },
];

function formatSessionTime(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/**
 * Recall has no backend yet — this screen is a fully-interactive, self-contained
 * preview so the review flow (and empty/finished states) can be evaluated end to end.
 */
export function RecallPage() {
  const [phase, setPhase] = useState<Phase>("start");
  const [queue, setQueue] = useState(SAMPLE_CARDS);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [sessionSeconds, setSessionSeconds] = useState(0);

  // Only ticks during the active review phase, and feeds the Dashboard's
  // "Recall today" card via localStorage (see shared/lib/recallTime.ts).
  useEffect(() => {
    if (phase !== "reviewing") {
      return;
    }
    const interval = setInterval(() => {
      setSessionSeconds((s) => s + 1);
      addTodayRecallSeconds(1);
    }, 1000);
    return () => clearInterval(interval);
  }, [phase]);

  const current = queue[index];
  const progress = useMemo(
    () => (queue.length === 0 ? 100 : Math.round((reviewedCount / (reviewedCount + queue.length - index)) * 100)),
    [reviewedCount, queue.length, index],
  );

  const handleStart = () => {
    setSessionSeconds(0);
    setPhase("reviewing");
  };

  const advance = () => {
    setRevealed(false);
    setReviewedCount((c) => c + 1);
    const nextIndex = index + 1;
    setIndex(nextIndex);
    if (nextIndex >= queue.length) {
      setPhase("finished");
    }
  };

  const handleRestart = () => {
    setQueue(SAMPLE_CARDS);
    setIndex(0);
    setRevealed(false);
    setReviewedCount(0);
    setSessionSeconds(0);
    setPhase("start");
  };

  return (
    <div className="mx-auto max-w-2xl">
      <header className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">Recall</h1>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
              <Timer size={14} weight="bold" />
              {formatSessionTime(sessionSeconds)}
            </span>
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
              Preview — not yet connected to your notes
            </span>
          </div>
        </div>
        <p className="mt-1 text-sm text-neutral-500">
          Spaced-repetition review of the ideas worth remembering, Anki-style.
        </p>
      </header>

      {phase === "start" ? (
        <div className="flex min-h-[320px] flex-col items-center justify-center rounded-2xl border border-neutral-200 bg-white p-8 text-center shadow-card">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-neutral-950 text-white">
            <Play size={20} weight="fill" />
          </span>
          <p className="mt-5 font-display text-xl font-semibold text-neutral-950">Ready to review?</p>
          <p className="mt-2 max-w-xs text-sm text-neutral-500">
            {queue.length} card{queue.length === 1 ? "" : "s"} queued up. The timer starts as soon as you begin.
          </p>
          <Button className="mt-6" onClick={handleStart}>
            <Play size={16} weight="bold" />
            Start session
          </Button>
        </div>
      ) : phase === "reviewing" ? (
        <>
          <div className="mb-4 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
            <div
              className="h-full rounded-full bg-neutral-950 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="flex min-h-[320px] flex-col rounded-2xl border border-neutral-200 bg-white p-8 shadow-card">
            <span className="self-start rounded-full border border-neutral-200 px-2.5 py-1 text-[11px] font-semibold text-neutral-500">
              {current.deck}
            </span>

            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <p className="font-display text-xl font-semibold leading-snug text-neutral-950 sm:text-2xl">
                {current.front}
              </p>
              {revealed ? (
                <p className="mt-6 max-w-md text-sm leading-relaxed text-neutral-600">{current.back}</p>
              ) : null}
            </div>

            {!revealed ? (
              <Button className="mx-auto mt-6" onClick={() => setRevealed(true)}>
                Show answer
              </Button>
            ) : (
              <div className="mx-auto mt-6 flex gap-3">
                <button
                  type="button"
                  onClick={advance}
                  className={clsx(
                    "inline-flex h-11 items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-5 text-sm font-medium text-amber-800 transition-colors hover:bg-amber-100",
                  )}
                >
                  <X size={16} weight="bold" />
                  Forgot — show again
                </button>
                <button
                  type="button"
                  onClick={advance}
                  className="inline-flex h-11 items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-5 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100"
                >
                  <Check size={16} weight="bold" />
                  Remembered
                </button>
              </div>
            )}
          </div>

          <p className="mt-4 text-center text-xs text-neutral-400">
            Card {index + 1} of {queue.length}
          </p>
        </>
      ) : (
        <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-white py-16 text-center shadow-card">
          <p className="font-display text-xl font-semibold text-neutral-950">You're all caught up</p>
          <p className="mt-2 max-w-xs text-sm text-neutral-500">
            You reviewed {reviewedCount} card{reviewedCount === 1 ? "" : "s"}. Once Recall is connected to your
            notes, new cards will appear here automatically.
          </p>
          <span className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-3 py-1.5 text-xs font-semibold text-neutral-600">
            <Timer size={14} weight="bold" />
            Session time: {formatSessionTime(sessionSeconds)}
          </span>
          <Button variant="outline" className="mt-6" onClick={handleRestart}>
            <ArrowClockwise size={16} />
            Restart preview deck
          </Button>
        </div>
      )}
    </div>
  );
}
