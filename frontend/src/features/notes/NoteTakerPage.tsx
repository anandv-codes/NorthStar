import { useCallback, useRef, useState } from "react";
import { CheckCircle, Microphone, PaperPlaneTilt, Spinner } from "@phosphor-icons/react";
import { createNote, getNoteStatus, type NoteStatus } from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";

const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 20000;

export function NoteTakerPage() {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [note, setNote] = useState<NoteStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<NoteStatus[]>([]);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  const pollNote = useCallback(
    (noteId: string, startedAt: number) => {
      pollTimer.current = setTimeout(async () => {
        try {
          const status = await getNoteStatus(noteId);
          setNote(status);
          if (status.status === "enriched" || status.status === "failed" || Date.now() - startedAt > POLL_TIMEOUT_MS) {
            setHistory((current) => [status, ...current.filter((n) => n.note_id !== status.note_id)]);
            return;
          }
          pollNote(noteId, startedAt);
        } catch {
          // Stop silently; the user can still see the note as "processing".
        }
      }, POLL_INTERVAL_MS);
    },
    [],
  );

  const handleSubmit = async () => {
    const trimmed = text.trim();
    if (!trimmed || submitting) {
      return;
    }
    setSubmitting(true);
    setError(null);
    stopPolling();
    try {
      const created = await createNote({ text: trimmed });
      setText("");
      const status = await getNoteStatus(created.note_id);
      setNote(status);
      pollNote(created.note_id, Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save your note.");
    } finally {
      setSubmitting(false);
    }
  };

  const isProcessing = note && note.status !== "enriched" && note.status !== "failed";

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-8">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">Note Taker</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Write whatever's on your mind. NorthStar will pull out tasks, questions and concepts for you.
        </p>
      </header>

      <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-card">
        <div className="relative">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Had a call with the design team about the onboarding flow..."
            rows={6}
            className="w-full resize-none rounded-xl border border-neutral-200 p-4 pr-12 text-sm leading-relaxed text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-950 focus:outline-none focus:ring-2 focus:ring-neutral-950/10"
          />
          <button
            type="button"
            disabled
            title="Voice input coming soon"
            aria-label="Voice input (coming soon)"
            className="absolute right-3 top-3 inline-flex h-8 w-8 cursor-not-allowed items-center justify-center rounded-lg text-neutral-300"
          >
            <Microphone size={18} />
          </button>
        </div>
        <div className="mt-4 flex items-center justify-between">
          <p className="text-xs text-neutral-400">{text.trim().length} characters</p>
          <Button onClick={handleSubmit} disabled={submitting || !text.trim()}>
            {submitting ? <Spinner size={16} className="animate-spin" /> : <PaperPlaneTilt size={16} weight="bold" />}
            Save note
          </Button>
        </div>
      </div>

      {error ? (
        <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
      ) : null}

      {note ? (
        <div className="mt-6 rounded-2xl border border-neutral-200 bg-white p-5 shadow-card">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-neutral-950">Latest note</p>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                isProcessing
                  ? "bg-neutral-100 text-neutral-600"
                  : note.status === "failed"
                    ? "bg-red-50 text-red-700"
                    : "bg-accent-50 text-accent-700"
              }`}
            >
              {isProcessing ? (
                <Spinner size={12} className="animate-spin" />
              ) : note.status === "failed" ? null : (
                <CheckCircle size={12} weight="fill" />
              )}
              {isProcessing ? "Processing" : note.status === "failed" ? "Failed" : "Enriched"}
            </span>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-neutral-700">{note.raw_text}</p>
          {note.enriched_summary ? (
            <p className="mt-3 rounded-xl bg-neutral-50 p-3 text-sm leading-relaxed text-neutral-600">
              {note.enriched_summary}
            </p>
          ) : null}
        </div>
      ) : null}

      {history.length > 0 ? (
        <div className="mt-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.15em] text-neutral-400">
            Earlier today
          </p>
          <ul className="space-y-3">
            {history.slice(1).map((item) => (
              <li key={item.note_id} className="rounded-xl border border-neutral-100 p-4 text-sm text-neutral-600">
                {item.enriched_summary || item.raw_text}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
