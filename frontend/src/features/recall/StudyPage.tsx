import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowClockwise,
  ArrowLeft,
  Check,
  Minus,
  Sparkle,
  Timer,
  X,
} from "@phosphor-icons/react";
import clsx from "clsx";
import {
  fetchDueCards,
  fetchRecallCards,
  fetchRecallDecks,
  reviewCard,
  type RecallCard,
  type RecallGrade,
} from "../../shared/api/httpClient";
import { addTodayRecallSeconds } from "../../shared/lib/recallTime";
import { Button } from "../../shared/ui/Button";

type Stage = "loading" | "start" | "reviewing" | "finished" | "empty" | "error";

const GRADE_OPTIONS: Array<{
  grade: RecallGrade;
  label: string;
  icon: typeof X;
  className: string;
}> = [
  { grade: 1, label: "Forgot", icon: X, className: "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100" },
  { grade: 3, label: "Tricky", icon: Minus, className: "border-orange-200 bg-orange-50 text-orange-800 hover:bg-orange-100" },
  { grade: 4, label: "Got it", icon: Check, className: "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100" },
  { grade: 5, label: "Easy", icon: Sparkle, className: "border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-100" },
];

function formatSessionTime(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function StudyPage() {
  const { deckId = "all" } = useParams();
  const [searchParams] = useSearchParams();
  const mode = searchParams.get("mode") === "all" ? "all" : "due";

  const [stage, setStage] = useState<Stage>("loading");
  const [deckName, setDeckName] = useState("All decks");
  const [cards, setCards] = useState<RecallCard[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [sessionSeconds, setSessionSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [requeueNotice, setRequeueNotice] = useState<string | null>(null);
  const cardShownAt = useRef<number>(Date.now());
  const requeuedCardIds = useRef<Set<string>>(new Set());

  const load = useCallback(async () => {
    setStage("loading");
    setError(null);
    try {
      const deckPromise = fetchRecallDecks();
      const cardsPromise =
        mode === "all"
          ? fetchRecallCards({
              deckId: deckId === "all" ? null : deckId,
              includeNotDue: true,
              limit: 200,
            })
          : fetchDueCards(200, deckId === "all" ? null : deckId);
      const [deckList, cardList] = await Promise.all([deckPromise, cardsPromise]);
      setDeckName(
        deckId === "all"
          ? "All decks"
          : deckList.decks.find((deck) => deck.deck_id === deckId)?.name ?? "Deck",
      );
      const loaded = "cards" in cardList ? cardList.cards : [];
      setCards(loaded);
      setIndex(0);
      setReviewedCount(0);
      setRevealed(false);
      setRequeueNotice(null);
      requeuedCardIds.current = new Set();
      setStage(loaded.length > 0 ? "start" : "empty");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load this review session.");
      setStage("error");
    }
  }, [deckId, mode]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (stage !== "reviewing") return;
    const interval = setInterval(() => {
      setSessionSeconds((seconds) => seconds + 1);
      addTodayRecallSeconds(1);
    }, 1000);
    return () => clearInterval(interval);
  }, [stage]);

  useEffect(() => {
    if (stage === "reviewing") {
      cardShownAt.current = Date.now();
    }
  }, [stage, index]);

  const current = cards[index];

  const handleGrade = async (grade: RecallGrade) => {
    if (!current) return;
    const elapsedMs = Date.now() - cardShownAt.current;
    try {
      await reviewCard(current.card_id, grade, elapsedMs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that review.");
      return;
    }
    setError(null);
    setRevealed(false);

    const willRequeue = grade === 1 && !requeuedCardIds.current.has(current.card_id);
    if (willRequeue) {
      requeuedCardIds.current.add(current.card_id);
      setCards((queue) => {
        const next = [...queue];
        next.splice(Math.min(index + 3, next.length), 0, current);
        return next;
      });
    }
    setRequeueNotice(
      willRequeue ? "Marked as forgotten — this card will come back later this session." : null,
    );

    setReviewedCount((count) => count + 1);
    const nextIndex = index + 1;
    setIndex(nextIndex);
    if (!willRequeue && nextIndex >= cards.length) {
      setStage("finished");
    }
  };

  const progress = cards.length === 0 ? 100 : Math.round((index / cards.length) * 100);
  const modeLabel = mode === "all" ? "Review all" : "Due review";

  return (
    <div className="mx-auto max-w-2xl">
      <header className="mb-6">
        <Link
          to={deckId === "all" ? "/app/recall" : `/app/recall/decks/${deckId}`}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-neutral-500 transition-colors hover:text-neutral-950"
        >
          <ArrowLeft size={14} />
          Back to recall
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">{deckName}</h1>
            <p className="mt-0.5 text-sm text-neutral-500">
              {modeLabel}
              {mode === "all" ? " · includes cards not due yet" : ""}
            </p>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
            <Timer size={14} weight="bold" />
            {formatSessionTime(sessionSeconds)}
          </span>
        </div>
      </header>

      {error ? (
        <p role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      {stage === "loading" ? (
        <div className="flex min-h-[320px] items-center justify-center rounded-2xl border border-neutral-200 bg-white shadow-card">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-950" />
        </div>
      ) : stage === "error" ? (
        <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-white py-16 shadow-card">
          <Button variant="outline" onClick={() => void load()}>
            <ArrowClockwise size={16} />
            Try again
          </Button>
        </div>
      ) : stage === "empty" ? (
        <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-white py-16 text-center shadow-card">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100 text-neutral-500">
            <Sparkle size={20} weight="bold" />
          </span>
          <p className="mt-5 font-display text-xl font-semibold text-neutral-950">
            {mode === "due" ? "Nothing due right now" : "No cards in this deck"}
          </p>
          <p className="mt-2 max-w-sm text-sm text-neutral-500">
            {mode === "due"
              ? "Try reviewing all cards, or come back when the next batch is due."
              : "Add a note with recall on to start filling this deck."}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            {mode === "due" ? (
              <Link
                to={`/app/recall/study/${deckId}?mode=all`}
                className="inline-flex h-10 items-center justify-center rounded-xl bg-neutral-950 px-4 text-sm font-semibold text-white hover:bg-neutral-800"
              >
                Review all cards
              </Link>
            ) : null}
            <Link
              to="/app/notes"
              className="inline-flex h-10 items-center justify-center rounded-xl border border-neutral-200 px-4 text-sm font-semibold text-neutral-700 hover:bg-neutral-100"
            >
              Write a note
            </Link>
          </div>
        </div>
      ) : stage === "start" ? (
        <div className="flex min-h-[320px] flex-col items-center justify-center rounded-2xl border border-neutral-200 bg-white p-8 text-center shadow-card">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-neutral-950 text-white">
            <Timer size={20} weight="bold" />
          </span>
          <p className="mt-5 font-display text-xl font-semibold text-neutral-950">Ready to review?</p>
          <p className="mt-2 max-w-sm text-sm text-neutral-500">
            {cards.length} card{cards.length === 1 ? "" : "s"} ready. The timer starts as soon as you begin.
          </p>
          {mode === "all" ? (
            <p className="mt-2 max-w-sm rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
              This includes cards that are not due yet. Grades still update scheduling.
            </p>
          ) : null}
          <Button className="mt-6" onClick={() => setStage("reviewing")}>
            Start session
          </Button>
        </div>
      ) : stage === "reviewing" && current ? (
        <>
          <div className="mb-4 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
            <div
              className="h-full rounded-full bg-neutral-950 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="flex min-h-[320px] flex-col rounded-2xl border border-neutral-200 bg-white p-8 shadow-card">
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <p className="font-display text-xl font-semibold leading-snug text-neutral-950 sm:text-2xl">
                {current.question}
              </p>
              {revealed ? (
                <p className="mt-6 max-w-md text-sm leading-relaxed text-neutral-600">{current.answer}</p>
              ) : null}
            </div>

            {!revealed ? (
              <Button className="mx-auto mt-6" onClick={() => setRevealed(true)}>
                Show answer
              </Button>
            ) : (
              <div className="mx-auto mt-6 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                {GRADE_OPTIONS.map(({ grade, label, icon: Icon, className }) => (
                  <button
                    key={grade}
                    type="button"
                    onClick={() => void handleGrade(grade)}
                    className={clsx(
                      "inline-flex h-11 cursor-pointer items-center justify-center gap-1.5 rounded-xl border px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950 focus-visible:ring-offset-2",
                      className,
                    )}
                  >
                    <Icon size={15} weight="bold" />
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>

          <p className="mt-4 text-center text-xs text-neutral-400">
            Card {index + 1} of {cards.length}
          </p>
          {requeueNotice ? (
            <p role="status" className="mt-1.5 text-center text-xs font-medium text-amber-700">
              {requeueNotice}
            </p>
          ) : null}
        </>
      ) : (
        <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-white py-16 text-center shadow-card">
          <p className="font-display text-xl font-semibold text-neutral-950">You're all caught up</p>
          <p className="mt-2 max-w-xs text-sm text-neutral-500">
            You logged {reviewedCount} review{reviewedCount === 1 ? "" : "s"}.
          </p>
          <span className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-3 py-1.5 text-xs font-semibold text-neutral-600">
            <Timer size={14} weight="bold" />
            Session time: {formatSessionTime(sessionSeconds)}
          </span>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <Button variant="outline" onClick={() => void load()}>
              <ArrowClockwise size={16} />
              Check for more
            </Button>
            <Link
              to="/app/recall"
              className="inline-flex h-11 items-center justify-center rounded-xl border border-neutral-200 px-5 text-sm font-medium text-neutral-700 hover:bg-neutral-100"
            >
              Back to decks
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
