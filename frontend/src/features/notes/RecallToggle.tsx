import { useState } from "react";
import { setNoteRecall } from "../../shared/api/httpClient";
import { ErrorLine } from "../../shared/ui/states";

interface RecallToggleProps {
  noteId: string;
  enabled: boolean;
  recallStatus: string;
  onChanged?: (enabled: boolean, recallStatus: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  ready: "#1a7f37",
  pending: "#9a6700",
  failed: "#b00020",
  off: "#666",
};

export function RecallToggle({
  noteId,
  enabled,
  recallStatus,
  onChanged,
}: RecallToggleProps) {
  const [isOn, setIsOn] = useState(enabled);
  const [status, setStatus] = useState(recallStatus);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = async () => {
    if (busy) {
      return;
    }
    const next = !isOn;
    setBusy(true);
    setError(null);
    try {
      const result = await setNoteRecall(noteId, next);
      setIsOn(result.enabled);
      setStatus(result.recall_status);
      onChanged?.(result.enabled, result.recall_status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update recall.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <button onClick={() => void toggle()} disabled={busy} aria-pressed={isOn}>
        {busy ? "Working..." : isOn ? "Turn recall off" : "Turn recall on"}
      </button>
      <span
        style={{
          marginLeft: 8,
          fontSize: 12,
          color: STATUS_COLORS[status] ?? "#666",
        }}
      >
        recall: {status}
      </span>
      {error ? <ErrorLine message={error} /> : null}
    </div>
  );
}
