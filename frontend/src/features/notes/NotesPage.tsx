import { useCallback, useEffect, useState } from "react";
import { RecentNote, fetchRecentMemory } from "../../shared/api/httpClient";
import { Card } from "../../shared/ui/Card";
import { Loading, ErrorLine, PageShell } from "../../shared/ui/states";

const STATUS_COLORS: Record<string, string> = {
  ready: "#1a7f37",
  pending: "#9a6700",
  failed: "#b00020",
  off: "#666",
};

export function NotesPage() {
  const [notes, setNotes] = useState<RecentNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRecentMemory(50);
      setNotes(data.notes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PageShell>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Notes</h2>
        <a href="#/capture">
          <button>+ Capture</button>
        </a>
      </div>

      {loading ? <Loading label="Loading notes..." /> : null}
      {error ? <ErrorLine message={error} onRetry={() => void load()} /> : null}

      {!loading && !error && notes.length === 0 ? (
        <Card>
          <div style={{ color: "#777" }}>
            No notes yet. <a href="#/capture">Capture one</a>.
          </div>
        </Card>
      ) : null}

      {!loading && !error ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {notes.map((note) => (
            <Card key={note.note_id}>
              <a
                href={`#/notes/${note.note_id}`}
                style={{ color: "#111", fontWeight: 600, textDecoration: "none" }}
              >
                {note.enriched_summary || note.raw_text.slice(0, 80)}
              </a>
              <div
                style={{
                  fontSize: 12,
                  color: "#666",
                  marginTop: 6,
                  display: "flex",
                  gap: 12,
                }}
              >
                <span>{new Date(note.created_at).toLocaleString()}</span>
                <span>{note.status}</span>
                {note.recall_status ? (
                  <span style={{ color: STATUS_COLORS[note.recall_status] ?? "#666" }}>
                    recall: {note.recall_status}
                  </span>
                ) : null}
              </div>
            </Card>
          ))}
        </div>
      ) : null}
    </PageShell>
  );
}
