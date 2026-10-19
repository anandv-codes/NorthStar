import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowClockwise, Minus, NotePencil, Sparkle, Timer, X, Check } from "@phosphor-icons/react";
import clsx from "clsx";
import {
  RecallCard,
  RecallGrade,
  RecallSuggestion,
  acceptSuggestion,
  fetchDueCards,
  fetchSuggestions,
  rejectSuggestion,
  reviewCard,
} from "../../shared/api/httpClient";
import { addTodayRecallSeconds } from "../../shared/lib/recallTime";
import { Button } from "../../shared/ui/Button";
import { SuggestionCard } from "./SuggestionCard";

type Stage = "loading" | "suggestions" | "start" | "reviewing" | "finished" | "empty" | "error";

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

export function RecallPage() {
  const [stage, setStage] = useState<Stage>("loading");
  const [suggestions, setSuggestions] = useState<RecallSuggestion[]>([]);
  const [processingSuggestionId, setProcessingSuggestionId] = useState<string | null>(null);
  const [processingAction, setProcessingAction] = useState<"accept" | "reject" | null>(null);
  const [dueCards, setDueCards] = useState<RecallCard[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [sessionSeconds, setSessionSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const cardShownAt = useRef<number>(Date.now());

  const load = useCallback(async () => {
    setStage("loading");
    setError(null);
    try {
      const [suggestionList, due] = await Promise.all([fetchSuggestions(), fetchDueCards()]);
      setSuggestions(suggestionList.suggestions);
      setDueCards(due.cards);
      setIndex(0);
      setReviewedCount(0);
      if (suggestionList.suggestions.length > 0) {
        setStage("suggestions");
      } else if (due.cards.length > 0) {
        setStage("start");
      } else {
        setStage("empty");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load your recall deck.");
      setStage("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Only ticks during the active review phase, and feeds the Dashboard's
  // "Recall today" card via localStorage (see shared/lib/recallTime.ts).
  useEffect(() => {
    if (stage !== "reviewing") {
      return;
    }
    const interval = setInterval(() => {
      setSessionSeconds((s) => s + 1);
      addTodayRecallSeconds(1);
    }, 1000);
    return () => clearInterval(interval);
  }, [stage]);

  useEffect(() => {
    if (stage === "reviewing") {
      cardShownAt.current = Date.now();
    }
  }, [stage, index]);

  const handleAcceptSuggestion = async (suggestion: RecallSuggestion) => {
    setProcessingSuggestionId(suggestion.candidate_id);
    setProcessingAction("accept");
    try {
      const result = await acceptSuggestion(suggestion.candidate_id);
      setSuggestions((current) => current.filter((s) => s.candidate_id !== suggestion.candidate_id));
      if (result.card) {
        setDueCards((current) => [...current, result.card as RecallCard]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add that to your recall deck.");
    } finally {
      setProcessingSuggestionId(null);
      setProcessingAction(null);
    }
  };

  const handleRejectSuggestion = async (suggestion: RecallSuggestion) => {
    setProcessingSuggestionId(suggestion.candidate_id);
    setProcessingAction("reject");
    try {
      await rejectSuggestion(suggestion.candidate_id);
      setSuggestions((current) => current.filter((s) => s.candidate_id !== suggestion.candidate_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't skip that suggestion.");
    } finally {
      setProcessingSuggestionId(null);
      setProcessingAction(null);
    }
  };

  // Once every suggestion has been triaged, move on to reviewing due cards (if any).
  useEffect(() => {
    if (stage === "suggestions" && suggestions.length === 0) {
      setStage(dueCards.length > 0 ? "start" : "empty");
    }
  }, [stage, suggestions.length, dueCards.length]);

  const handleStart = () => {
    setSessionSeconds(0);
    setStage("reviewing");
  };

  const current = dueCards[index];

  const handleGrade = async (grade: RecallGrade) => {
    if (!current) {
      return;
    }
    const elapsedMs = Date.now() - cardShownAt.current;
    try {
      await reviewCard(current.card_id, grade, elapsedMs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that review.");
    }
    setRevealed(false);
    setReviewedCount((c) => c + 1);
    const nextIndex = index + 1;
    setIndex(nextIndex);
    if (nextIndex >= dueCards.length) {
      setStage("finished");
    }
  };

  const progress = dueCards.length === 0 ? 100 : Math.round((index / dueCards.length) * 100);

  return (
    <div className="mx-auto max-w-2xl">
      <header className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">Recall</h1>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
            <Timer size={14} weight="bold" />
            {formatSessionTime(sessionSeconds)}
          </span>
        </div>
        <p className="mt-1 text-sm text-neutral-500">
          Spaced-repetition review of the ideas worth remembering, Anki-style.
        </p>
      </header>

      {error ? (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      ) : null}

      {stage === "loading" ? (
        <div className="flex min-h-[320px] items-center justify-center rounded-2xl border border-neutral-200 bg-white shadow-card">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-950" />
        </div>
      ) : stage === "error" ? (
        <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-white py-16 text-center shadow-card">
          <Button variant="outline" onClick={() => void load()}>
            <ArrowClockwise size={16} />
            Try again
          </Button>
        </div>
      ) : stage === "suggestions" ? (
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-neutral-400">
            New from your notes — {suggestions.length} to review
          </p>
          {suggestions.map((suggestion) => (
            <SuggestionCard
              key={suggestion.candidate_id}
              suggestion={suggestion}
              processing={processingSuggestionId === suggestion.candidate_id ? processingAction : null}
              onAccept={() => void handleAcceptSuggestion(suggestion)}
              onReject={() => void handleRejectSuggestion(suggestion)}
            />
          ))}
        </div>
      ) : stage === "empty" ? (
        <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-white py-16 text-center shadow-card">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100 text-neutral-500">
            <Sparkle size={20} weight="bold" />
          </span>
          <p className="mt-5 font-display text-xl font-semibold text-neutral-950">Nothing due right now</p>
          <p className="mt-2 max-w-xs text-sm text-neutral-500">
            Turn on recall for a note to generate review cards, then check back here.
          </p>
          <Button className="mt-6" onClick={() => void load()} variant="outline">
            <ArrowClockwise size={16} />
            Check again
          </Button>
          <Link to="/app/notes" className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent-600 hover:text-accent-700">
            <NotePencil size={16} />
            Go write a note
          </Link>
        </div>
      ) : stage === "start" ? (
        <div className="flex min-h-[320px] flex-col items-center justify-center rounded-2xl border border-neutral-200 bg-white p-8 text-center shadow-card">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-neutral-950 text-white">
            <Timer size={20} weight="bold" />
          </span>
          <p className="mt-5 font-display text-xl font-semibold text-neutral-950">Ready to review?</p>
          <p className="mt-2 max-w-xs text-sm text-neutral-500">
            {dueCards.length} card{dueCards.length === 1 ? "" : "s"} due. The timer starts as soon as you begin.
          </p>
          <Button className="mt-6" onClick={handleStart}>
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
                      "inline-flex h-11 items-center justify-center gap-1.5 rounded-xl border px-3 text-sm font-medium transition-colors",
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
            Card {index + 1} of {dueCards.length}
          </p>
        </>
      ) : (
        <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-white py-16 text-center shadow-card">
          <p className="font-display text-xl font-semibold text-neutral-950">You're all caught up</p>
          <p className="mt-2 max-w-xs text-sm text-neutral-500">
            You reviewed {reviewedCount} card{reviewedCount === 1 ? "" : "s"}. New cards will show up here as they
            become due.
          </p>
          <span className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-3 py-1.5 text-xs font-semibold text-neutral-600">
            <Timer size={14} weight="bold" />
            Session time: {formatSessionTime(sessionSeconds)}
          </span>
          <Button variant="outline" className="mt-6" onClick={() => void load()}>
            <ArrowClockwise size={16} />
            Check for more
          </Button>
        </div>
      )}
    </div>
  );
}
