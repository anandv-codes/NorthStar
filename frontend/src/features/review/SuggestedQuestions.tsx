import { useState } from "react";
import {
  RecallCard,
  RecallSuggestion,
  acceptSuggestion,
  rejectSuggestion,
} from "../../shared/api/httpClient";
import { Card } from "../../shared/ui/Card";
import { EmptyState, ErrorLine } from "../../shared/ui/states";

interface SuggestedQuestionsProps {
  suggestions: RecallSuggestion[];
  onDecided: (candidateId: string) => void;
}

export function SuggestedQuestions({
  suggestions,
  onDecided,
}: SuggestedQuestionsProps) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const [acceptedCard, setAcceptedCard] = useState<RecallCard | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const current = suggestions[0];

  const handleAccept = async () => {
    if (!current || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await acceptSuggestion(current.candidate_id);
      setAcceptedCard(result.card ?? null);
      setFeedback(
        result.card ? "Answer ready and added to your review queue." : "Added.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept suggestion.");
    } finally {
      setBusy(false);
    }
  };

  const handleSkip = async () => {
    if (!current || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await rejectSuggestion(current.candidate_id);
      onDecided(current.candidate_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to skip suggestion.");
    } finally {
      setBusy(false);
    }
  };

  const handleNext = () => {
    if (!current) {
      return;
    }
    onDecided(current.candidate_id);
    setAcceptedCard(null);
    setFeedback(null);
  };

  if (!current) {
    return (
      <Card>
        <EmptyState message="No suggested questions. Capture a note with recall enabled, or turn recall on for an existing note." />
      </Card>
    );
  }

  return (
    <Card>
      <div style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>
        {current.item_type}
        {current.source_note_id ? (
          <>
            {" · "}
            <a href={`#/notes/${current.source_note_id}`}>from note</a>
          </>
        ) : null}
      </div>
      <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
        {current.question}
      </div>

      {acceptedCard ? (
        <div>
          <div
            style={{
              background: "#f0ebe3",
              borderRadius: 12,
              padding: 14,
              whiteSpace: "pre-wrap",
            }}
          >
            {acceptedCard.answer}
          </div>
          {feedback ? (
            <div style={{ color: "#666", fontSize: 13, marginTop: 8 }}>
              {feedback}
            </div>
          ) : null}
          <div style={{ marginTop: 12 }}>
            <button onClick={handleNext}>Next suggestion</button>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => void handleAccept()} disabled={busy}>
            {busy ? "Generating answer..." : "Accept"}
          </button>
          <button onClick={() => void handleSkip()} disabled={busy}>
            Skip
          </button>
        </div>
      )}

      {error ? <ErrorLine message={error} /> : null}
    </Card>
  );
}
