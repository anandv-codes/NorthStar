import { RecentMemoryResponse } from "../../../shared/api/httpClient";

interface RecentMemorySectionProps {
  recentMemory: RecentMemoryResponse | null;
}

function SourceTrail({ noteIds }: { noteIds?: string[] }) {
  if (!noteIds || noteIds.length === 0) {
    return null;
  }

  const displayCount = Math.min(noteIds.length, 3);
  const displayedIds = noteIds.slice(0, displayCount);
  const hiddenCount = noteIds.length - displayCount;

  return (
    <div
      style={{
        fontSize: "0.85em",
        color: "#666",
        marginTop: "0.5rem",
        fontStyle: "italic",
      }}
      title={`Sourced from: ${noteIds.join(", ")}`}
    >
      Sourced from:{" "}
      {displayedIds.map((id, idx) => (
        <span key={id}>
          <code
            style={{
              backgroundColor: "#f0f0f0",
              padding: "0 0.25rem",
              borderRadius: "2px",
            }}
          >
            {id.slice(0, 8)}...
          </code>
          {idx < displayedIds.length - 1 ? ", " : ""}
        </span>
      ))}
      {hiddenCount > 0 && `, +${hiddenCount} more`}
    </div>
  );
}

export function RecentMemorySection({ recentMemory }: RecentMemorySectionProps) {
  return (
    <section>
      <h2>Recent notes</h2>
      {!recentMemory || recentMemory.notes.length === 0 ? (
        <p>No recent notes.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {recentMemory.notes.map((note) => (
            <li
              key={note.note_id}
              style={{
                marginBottom: "1.5rem",
                padding: "1rem",
                backgroundColor: "#fafafa",
                borderRadius: "4px",
                border: "1px solid #eee",
              }}
            >
              <div style={{ marginBottom: "0.5rem" }}>
                <strong>Raw capture:</strong>
                <p style={{ margin: "0.25rem 0 0.5rem 0", color: "#333" }}>
                  {note.raw_text}
                </p>
              </div>

              {note.enriched_summary && (
                <div style={{ marginBottom: "0.5rem" }}>
                  <strong>Enriched understanding:</strong>
                  <p style={{ margin: "0.25rem 0 0.5rem 0", color: "#555" }}>
                    {note.enriched_summary}
                  </p>
                </div>
              )}

              <SourceTrail noteIds={note.context_note_ids} />

              <div style={{ fontSize: "0.8em", color: "#999", marginTop: "0.5rem" }}>
                Status: {note.status}
              </div>
            </li>
          ))}
        </ul>
      )}

      <h2>Recent decisions</h2>
      {!recentMemory || recentMemory.decisions.length === 0 ? (
        <p>No recent decisions.</p>
      ) : (
        <ul>
          {recentMemory.decisions.map((decision) => (
            <li key={decision.decision_id}>
              {decision.decision}
              {decision.rationale ? ` - ${decision.rationale}` : ""}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
