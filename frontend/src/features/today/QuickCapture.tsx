import { useState } from "react";
import { createNote } from "../../shared/api/httpClient";
import { Card, SectionTitle } from "../../shared/ui/Card";
import { ErrorLine } from "../../shared/ui/states";

interface QuickCaptureProps {
  onCaptured?: () => void;
}

export function QuickCapture({ onCaptured }: QuickCaptureProps) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    const content = text.trim();
    if (!content || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await createNote({ text: content });
      setText("");
      setStatus(result.status || "processing");
      onCaptured?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save note.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <SectionTitle hint="Capture → Understand → Remember → Act">
        Quick capture
      </SectionTitle>
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="What happened? Write it down..."
        rows={3}
        style={{
          width: "100%",
          resize: "vertical",
          padding: 12,
          borderRadius: 12,
          border: "1px solid #cfc7bc",
          fontFamily: "inherit",
          boxSizing: "border-box",
        }}
        disabled={busy}
      />
      <div
        style={{
          marginTop: 8,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <button onClick={() => void handleSave()} disabled={busy || !text.trim()}>
          {busy ? "Saving..." : "Save note"}
        </button>
        {status ? (
          <span style={{ fontSize: 13, color: "#666" }}>Processing...</span>
        ) : null}
      </div>
      {error ? <ErrorLine message={error} /> : null}
    </Card>
  );
}
