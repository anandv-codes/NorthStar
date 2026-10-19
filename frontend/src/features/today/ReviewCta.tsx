import { Card } from "../../shared/ui/Card";

interface ReviewCtaProps {
  dueCount: number;
  suggestionCount: number;
}

export function ReviewCta({ dueCount, suggestionCount }: ReviewCtaProps) {
  if (dueCount === 0 && suggestionCount === 0) {
    return (
      <Card>
        <div style={{ fontSize: 18, fontWeight: 600 }}>You're caught up</div>
        <div style={{ color: "#666", marginTop: 6 }}>
          Nothing due right now. Capture a note to grow your memory.
        </div>
      </Card>
    );
  }

  return (
    <Card>
      {dueCount > 0 ? (
        <>
          <div style={{ fontSize: 18, fontWeight: 600 }}>
            {dueCount} card{dueCount === 1 ? "" : "s"} due
          </div>
          <div style={{ color: "#666", marginTop: 6, marginBottom: 12 }}>
            Review now to keep them fresh.
          </div>
          <a href="#/review">
            <button>Review {dueCount} due card{dueCount === 1 ? "" : "s"}</button>
          </a>
        </>
      ) : (
        <>
          <div style={{ fontSize: 18, fontWeight: 600 }}>
            {suggestionCount} question{suggestionCount === 1 ? "" : "s"} to consider
          </div>
          <div style={{ color: "#666", marginTop: 6, marginBottom: 12 }}>
            Accept the ones worth remembering; skip the rest.
          </div>
          <a href="#/review/suggested">
            <button>Review suggestions</button>
          </a>
        </>
      )}
    </Card>
  );
}
