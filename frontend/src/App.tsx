import { useEffect, useState } from "react";
import { createNote, getNoteStatus, NoteStatus } from "./api";

function App() {
  const [text, setText] = useState("");
  const [noteId, setNoteId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [note, setNote] = useState<NoteStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const userId = "user-123";

  useEffect(() => {
    if (!noteId) {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const result = await getNoteStatus(userId, noteId);
        setNote(result);
        setStatus(result.status);
        if (result.status !== "processing") {
          window.clearInterval(interval);
        }
      } catch (err) {
        setError("Failed to fetch note status.");
        window.clearInterval(interval);
      }
    }, 1500);

    return () => window.clearInterval(interval);
  }, [noteId]);

  const handleSubmit = async () => {
    if (!text.trim()) {
      return;
    }

    setError(null);
    setNote(null);
    setStatus("processing");

    try {
      const result = await createNote({ user_id: userId, text });
      setNoteId(result.note_id);
    } catch (err) {
      setError("Failed to submit note.");
      setStatus(null);
    }
  };

  return (
    <div
      style={{
        padding: 24,
        maxWidth: 720,
        margin: "0 auto",
        fontFamily: "Inter, sans-serif",
      }}
    >
      <h1>NorthStar Phase 1</h1>

      <textarea
        rows={8}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type your note here"
        style={{
          width: "100%",
          fontSize: 16,
          padding: 12,
          borderRadius: 8,
          border: "1px solid #ccc",
        }}
      />

      <button
        onClick={handleSubmit}
        disabled={!text.trim() || status === "processing"}
        style={{
          marginTop: 12,
          padding: "10px 18px",
          fontSize: 16,
          cursor: "pointer",
        }}
      >
        Submit note
      </button>

      {status && (
        <div style={{ marginTop: 20 }}>
          <strong>Status:</strong> {status}
        </div>
      )}

      {error && <div style={{ color: "red", marginTop: 12 }}>{error}</div>}

      {note && (
        <section style={{ marginTop: 24 }}>
          <h2>Enriched note</h2>
          <p>
            <strong>Summary:</strong> {note.enriched_summary}
          </p>
          <p>
            <strong>Action items:</strong>
          </p>
          <ul>
            {note.action_items?.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p>
            <strong>Questions:</strong>
          </p>
          <ul>
            {note.questions?.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default App;
