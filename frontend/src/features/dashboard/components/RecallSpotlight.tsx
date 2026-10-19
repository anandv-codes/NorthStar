import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Sparkle, Timer } from "@phosphor-icons/react";
import { fetchDueCards, fetchSuggestions } from "../../../shared/api/httpClient";
import { getTodayRecallSeconds } from "../../../shared/lib/recallTime";
import { Button } from "../../../shared/ui/Button";

/**
 * Leads the dashboard per the product pivot: recall is the primary loop, not a side widget.
 */
export function RecallSpotlight() {
  const navigate = useNavigate();
  const [dueCount, setDueCount] = useState<number | null>(null);
  const [suggestionCount, setSuggestionCount] = useState<number | null>(null);
  const [todaySeconds, setTodaySeconds] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchDueCards(1), fetchSuggestions(1)])
      .then(([due, suggestions]) => {
        if (cancelled) return;
        setDueCount(due.total_due);
        setSuggestionCount(suggestions.total);
      })
      .catch(() => {
        if (!cancelled) {
          setDueCount(0);
          setSuggestionCount(0);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const sync = () => setTodaySeconds(getTodayRecallSeconds());
    sync();
    window.addEventListener("focus", sync);
    const interval = setInterval(sync, 5000);
    return () => {
      window.removeEventListener("focus", sync);
      clearInterval(interval);
    };
  }, []);

  const loading = dueCount === null || suggestionCount === null;
  const hasWork = (dueCount ?? 0) > 0 || (suggestionCount ?? 0) > 0;
  const todayMinutes = Math.round(todaySeconds / 60);

  return (
    <section
      aria-labelledby="recall-spotlight-heading"
      className="rounded-2xl bg-neutral-950 p-6 text-white shadow-soft sm:p-7"
    >
      <div className="flex flex-col items-start justify-between gap-5 sm:flex-row sm:items-center">
        <div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-neutral-300">
            <Timer size={12} weight="bold" />
            Today's recall
          </span>
          <h2 id="recall-spotlight-heading" className="mt-3 font-display text-xl font-semibold sm:text-2xl">
            {loading
              ? "Checking what's due\u2026"
              : hasWork
                ? `${dueCount} card${dueCount === 1 ? "" : "s"} due, ${suggestionCount} new to review`
                : "You're all caught up"}
          </h2>
          <p className="mt-1.5 max-w-md text-sm leading-relaxed text-neutral-400">
            {hasWork
              ? "A few minutes of active recall now beats re-reading your notes later."
              : "Turn on recall from any note to start building your review deck."}
          </p>
          {todayMinutes > 0 ? (
            <p className="mt-2 text-xs font-medium text-neutral-500">
              Already reviewed for {todayMinutes} min today
            </p>
          ) : null}
        </div>

        <Button
          variant="secondary"
          onClick={() => navigate("/app/recall")}
          disabled={loading}
          className="w-full sm:w-auto"
        >
          {hasWork ? "Start review" : "Go to Recall"}
          {hasWork ? <ArrowRight size={16} weight="bold" /> : <Sparkle size={16} weight="bold" />}
        </Button>
      </div>
    </section>
  );
}
