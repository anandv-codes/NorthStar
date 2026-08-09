import { RecentMemoryResponse } from "../../../shared/api/httpClient";

interface RecentMemorySectionProps {
  recentMemory: RecentMemoryResponse | null;
}

export function RecentMemorySection({ recentMemory }: RecentMemorySectionProps) {
  return (
    <section>
      <h2>Recent notes</h2>
      {!recentMemory || recentMemory.notes.length === 0 ? (
        <p>No recent notes.</p>
      ) : (
        <ul>
          {recentMemory.notes.map((note) => (
            <li key={note.note_id}>
              {note.enriched_summary || note.raw_text} ({note.status})
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
