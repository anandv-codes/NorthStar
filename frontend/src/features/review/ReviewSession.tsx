import { useCallback, useEffect, useRef, useState } from "react";
import { RecallCard, RecallGrade } from "../../shared/api/httpClient";
import { Card } from "../../shared/ui/Card";

interface ReviewSessionProps {
  card: RecallCard;
  reviewed: number;
  total: number;
  onGrade: (grade: RecallGrade, elapsedMs: number) => Promise<void>;
  onEnd: () => void;
}

const GRADES: { grade: RecallGrade; label: string; key: string }[] = [
  { grade: 1, label: "Again", key: "1" },
  { grade: 3, label: "Hard", key: "2" },
  { grade: 4, label: "Good", key: "3" },
  { grade: 5, label: "Easy", key: "4" },
];

export function ReviewSession({
  card,
  reviewed,
  total,
  onGrade,
  onEnd,
}: ReviewSessionProps) {
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const shownAt = useRef<number>(Date.now());

  useEffect(() => {
    setRevealed(false);
    setError(null);
    shownAt.current = Date.now();
  }, [card.card_id]);

  const submit = useCallback(
    async (grade: RecallGrade) => {
      if (busy) {
        return;
      }
      setBusy(true);
      setError(null);
      const elapsedMs = Date.now() - shownAt.current;
      try {
        await onGrade(grade, elapsedMs);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to submit review.");
      } finally {
        setBusy(false);
      }
    },
    [busy, onGrade],
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === " " || event.key === "Enter") {
        if (!revealed) {
          event.preventDefault();
          setRevealed(true);
        }
        return;
      }
      if (revealed) {
        const match = GRADES.find((g) => g.key === event.key);
        if (match) {
          event.preventDefault();
          void submit(match.grade);
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [revealed, submit]);

  return (
    <Card>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
        }}
      >
        <span style={{ color: "#666", fontSize: 13 }}>
          {reviewed} reviewed · {total - reviewed} left
        </span>
        <button onClick={onEnd}>End session</button>
      </div>

      <div
        style={{
          padding: "28px 12px",
          textAlign: "center",
          fontSize: 20,
          fontWeight: 600,
          whiteSpace: "pre-wrap",
        }}
      >
        {card.question}
      </div>

      {!revealed ? (
        <div style={{ textAlign: "center" }}>
          <button onClick={() => setRevealed(true)}>Show answer</button>
        </div>
      ) : (
        <div>
          <div
            style={{
              background: "#f0ebe3",
              borderRadius: 12,
              padding: 14,
              whiteSpace: "pre-wrap",
              marginBottom: 16,
            }}
          >
            {card.answer}
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap: 8,
            }}
          >
            {GRADES.map((item) => (
              <button
                key={item.grade}
                onClick={() => void submit(item.grade)}
                disabled={busy}
                title={`Keyboard: ${item.key}`}
              >
                {item.label} ({item.key})
              </button>
            ))}
          </div>
        </div>
      )}

      {error ? (
        <div style={{ color: "#b00020", marginTop: 12 }}>{error}</div>
      ) : null}
    </Card>
  );
}
