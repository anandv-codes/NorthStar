import { useCallback, useEffect, useState } from "react";
import {
  RecallCard,
  RecallGrade,
  RecallSuggestion,
  fetchDueCards,
  fetchSuggestions,
  reviewCard,
} from "../../shared/api/httpClient";
import { Card } from "../../shared/ui/Card";
import { Loading, ErrorLine, PageShell } from "../../shared/ui/states";
import { ReviewSession } from "./ReviewSession";
import { SuggestedQuestions } from "./SuggestedQuestions";

type Tab = "due" | "suggested";

interface ReviewPageProps {
  initialTab: Tab;
}

export function ReviewPage({ initialTab }: ReviewPageProps) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [dueQueue, setDueQueue] = useState<RecallCard[]>([]);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [suggestions, setSuggestions] = useState<RecallSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionStarted, setSessionStarted] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [due, suggested] = await Promise.all([
        fetchDueCards(),
        fetchSuggestions(),
      ]);
      setDueQueue(due.cards);
      setSuggestions(suggested.suggestions);
      setReviewedCount(0);
      setSessionStarted(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review queue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const switchTab = (next: Tab) => {
    setTab(next);
    window.location.hash = next === "suggested" ? "#/review/suggested" : "#/review";
  };

  const handleGrade = async (grade: RecallGrade, elapsedMs: number) => {
    const current = dueQueue[0];
    if (!current) {
      return;
    }
    await reviewCard(current.card_id, grade, elapsedMs);
    setDueQueue((queue) => queue.slice(1));
    setReviewedCount((count) => count + 1);
  };

  const handleSuggestionDecided = (candidateId: string) => {
    setSuggestions((items) => items.filter((item) => item.candidate_id !== candidateId));
  };

  const dueCount = dueQueue.length;

  return (
    <PageShell>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button
          onClick={() => switchTab("due")}
          disabled={tab === "due"}
        >
          Due cards ({dueCount})
        </button>
        <button
          onClick={() => switchTab("suggested")}
          disabled={tab === "suggested"}
        >
          Suggested ({suggestions.length})
        </button>
      </div>

      {loading ? <Loading label="Loading review queue..." /> : null}
      {error ? <ErrorLine message={error} onRetry={() => void load()} /> : null}

      {!loading && !error && tab === "due" ? (
        dueQueue.length === 0 ? (
          reviewedCount > 0 ? (
            <Card>
              <div style={{ fontSize: 18, fontWeight: 600 }}>
                Session complete
              </div>
              <div style={{ color: "#666", marginTop: 6 }}>
                {reviewedCount} card{reviewedCount === 1 ? "" : "s"} reviewed.
              </div>
              <div style={{ marginTop: 12 }}>
                <a href="#/today">Back to Today</a>
              </div>
            </Card>
          ) : (
            <Card>
              <div style={{ color: "#777" }}>
                You're caught up. Nothing due right now.
              </div>
            </Card>
          )
        ) : !sessionStarted ? (
          <Card>
            <div style={{ fontSize: 18, fontWeight: 600 }}>
              {dueQueue.length} due card{dueQueue.length === 1 ? "" : "s"}
            </div>
            <div style={{ color: "#666", marginTop: 6 }}>
              One question at a time. Reveal the answer, then grade your recall.
            </div>
            <div style={{ marginTop: 12 }}>
              <button onClick={() => setSessionStarted(true)}>
                Start reviewing
              </button>
            </div>
          </Card>
        ) : (
          <ReviewSession
            card={dueQueue[0]}
            reviewed={reviewedCount}
            total={reviewedCount + dueQueue.length}
            onGrade={handleGrade}
            onEnd={() => setSessionStarted(false)}
          />
        )
      ) : null}

      {!loading && !error && tab === "suggested" ? (
        <SuggestedQuestions
          suggestions={suggestions}
          onDecided={handleSuggestionDecided}
        />
      ) : null}
    </PageShell>
  );
}
