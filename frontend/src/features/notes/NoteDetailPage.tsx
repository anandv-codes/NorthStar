import { useCallback, useEffect, useState } from "react";
import { NoteMemoryResponse, getNoteMemory } from "../../shared/api/httpClient";
import { Card, SectionTitle } from "../../shared/ui/Card";
import { Loading, ErrorLine, PageShell } from "../../shared/ui/states";
import { RecallToggle } from "./RecallToggle";

interface NoteDetailPageProps {
  noteId: string;
}

export function NoteDetailPage({ noteId }: NoteDetailPageProps) {
  const [memory, setMemory] = useState<NoteMemoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recallEnabled, setRecallEnabled] = useState(false);
  const [recallStatus, setRecallStatus] = useState("off");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getNoteMemory(noteId);
      setMemory(data);
      setRecallEnabled(
        data.note.recall_enabled ?? data.note.recall_status !== "off",
      );
      setRecallStatus(data.note.recall_status ?? "off");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load note.");
    } finally {
      setLoading(false);
    }
  }, [noteId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <PageShell>
        <Loading label="Loading note..." />
      </PageShell>
    );
  }

  if (error || !memory) {
    return (
      <PageShell>
        <ErrorLine message={error ?? "Note not found."} onRetry={() => void load()} />
      </PageShell>
    );
  }

  const { note } = memory;

  return (
    <PageShell>
      <p>
        <a href="#/notes">Back to notes</a>
      </p>

      <Card>
        <SectionTitle hint={new Date(note.created_at).toLocaleString()}>
          Note
        </SectionTitle>
        <div style={{ whiteSpace: "pre-wrap", marginBottom: 12 }}>
          {note.raw_text}
        </div>
        <RecallToggle
          noteId={note.note_id}
          enabled={recallEnabled}
          recallStatus={recallStatus}
          onChanged={(enabled, status) => {
            setRecallEnabled(enabled);
            setRecallStatus(status);
          }}
        />
      </Card>

      {note.enriched_summary ? (
        <Card style={{ marginTop: 12 }}>
          <SectionTitle>Summary</SectionTitle>
          <div style={{ whiteSpace: "pre-wrap" }}>{note.enriched_summary}</div>
        </Card>
      ) : null}

      <MemoryList title="Tasks" items={memory.tasks.map((t) => t.description)} />
      <MemoryList title="Questions" items={memory.questions.map((q) => q.question)} />
      <MemoryList title="Facts" items={memory.facts.map((f) => f.content)} />
      <MemoryList title="Decisions" items={memory.decisions.map((d) => d.decision)} />
      <MemoryList title="Risks" items={memory.risks.map((r) => r.risk)} />
      <MemoryList title="Entities" items={memory.entities.map((e) => e.name)} />
    </PageShell>
  );
}

function MemoryList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <Card style={{ marginTop: 12 }}>
      <SectionTitle>{title}</SectionTitle>
      <ul style={{ margin: 0, paddingLeft: 20 }}>
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </ul>
    </Card>
  );
}
