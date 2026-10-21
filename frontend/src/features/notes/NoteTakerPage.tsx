import { useCallback, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Brain, CheckCircle, PaperPlaneTilt, Spinner } from "@phosphor-icons/react";
import { createNote, getNoteStatus, setNoteRecall, type NoteStatus } from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { MicButton, MicStatus } from "../../shared/ui/MicButton";
import { appendTranscript, useSpeechDictation } from "../../shared/lib/useSpeechDictation";

const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 60000;

const TERMINAL_NOTE_STATUSES = new Set(["completed", "enriched", "failed"]);
const isTerminalStatus = (status: string) => TERMINAL_NOTE_STATUSES.has(status);

const RECALL_STATUS_LABELS: Record<string, string> = {
  ready: "Recall on",
  pending: "Generating cards…",
  failed: "Generation failed",
  off: "Recall off",
};

export function NoteTakerPage() {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [recallEnabled, setRecallEnabled] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [note, setNote] = useState<NoteStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [togglingRecall, setTogglingRecall] = useState(false);
  const [recallError, setRecallError] = useState<string | null>(null);
  const [history, setHistory] = useState<NoteStatus[]>([]);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dictation = useSpeechDictation({
    onFinal: (chunk) => setText((current) => appendTranscript(current, chunk)),
  });

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
          if (isTerminalStatus(status.status) || Date.now() - startedAt > POLL_TIMEOUT_MS) {
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
    if (!trimmed || submitting || dictation.listening) {
      return;
    }
    dictation.cancel();
    setSubmitting(true);
    setError(null);
    stopPolling();
    try {
      const created = await createNote({ text: trimmed, recall_enabled: recallEnabled });
      setText("");
      if (recallEnabled) {
        setRecallEnabled(false);
        navigate(`/app/recall/verify?note=${encodeURIComponent(created.note_id)}`);
        return;
      }
      const status = await getNoteStatus(created.note_id);
      setNote(status);
      pollNote(created.note_id, Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save your note.");
    } finally {
      setSubmitting(false);
    }
  };

  const isProcessing = Boolean(note) && !isTerminalStatus(note?.status ?? "");

  const handleToggleRecall = async () => {
    if (!note || togglingRecall) {
      return;
    }
    setTogglingRecall(true);
    setRecallError(null);
    try {
      const result = await setNoteRecall(note.note_id, !note.recall_enabled);
      setNote((current) =>
        current ? { ...current, recall_enabled: result.enabled, recall_status: result.recall_status } : current,
      );
    } catch (err) {
      setRecallError(err instanceof Error ? err.message : "Couldn't update recall for this note.");
    } finally {
      setTogglingRecall(false);
    }
  };

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
            className="w-full resize-none rounded-xl border border-neutral-200 p-4 pr-14 text-sm leading-relaxed text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-950 focus:outline-none focus:ring-2 focus:ring-neutral-950/10"
          />
          <MicButton
            listening={dictation.listening}
            starting={dictation.starting}
            supported={dictation.supported}
            onToggle={dictation.toggle}
            className="absolute right-2 top-2 bg-white"
          />
        </div>
        <MicStatus
          listening={dictation.listening}
          starting={dictation.starting}
          interim={dictation.interim}
          error={dictation.error}
          supported={dictation.supported}
        />
        <div className="mt-4 flex items-center justify-between">
          <p className="text-xs text-neutral-400">{text.trim().length} characters</p>
          <div className="flex items-center gap-3">
            <label className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-neutral-500">
              <input
                type="checkbox"
                checked={recallEnabled}
                onChange={(e) => setRecallEnabled(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-neutral-300 text-neutral-950 focus:ring-neutral-950/20"
              />
              <Brain size={14} />
              Add to Recall
            </label>
            <Button
              onClick={handleSubmit}
              disabled={submitting || dictation.listening || !text.trim()}
              title={dictation.listening ? "Stop listening to save your note" : undefined}
            >
              {submitting ? <Spinner size={16} className="animate-spin" /> : <PaperPlaneTilt size={16} weight="bold" />}
              Save note
            </Button>
          </div>
        </div>
      </div>

      {error ? (
        <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
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
              {isProcessing ? "Processing" : note.status === "failed" ? "Failed" : "Processed"}
            </span>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-neutral-700">{note.raw_text}</p>
          {note.enriched_summary ? (
            <p className="mt-3 rounded-xl bg-neutral-50 p-3 text-sm leading-relaxed text-neutral-600">
              {note.enriched_summary}
            </p>
          ) : null}

          <div className="mt-4 flex items-center justify-between border-t border-neutral-100 pt-4">
            <div className="flex items-center gap-2">
              <Brain size={16} className="text-neutral-500" weight="bold" />
              <span className="text-sm font-medium text-neutral-700">
                {RECALL_STATUS_LABELS[note.recall_status ?? "off"] ?? "Recall off"}
              </span>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={Boolean(note.recall_enabled)}
              aria-label="Add this note to Recall"
              disabled={togglingRecall}
              onClick={() => void handleToggleRecall()}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
                note.recall_enabled ? "bg-accent-600" : "bg-neutral-300"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  note.recall_enabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>
          {recallError ? (
            <p role="alert" className="mt-2 text-xs text-red-600">
              {recallError}
            </p>
          ) : null}
          {note.recall_enabled && note.recall_status === "ready" ? (
            <Link
              to={`/app/recall/verify?note=${encodeURIComponent(note.note_id)}`}
              className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-accent-600 hover:text-accent-700"
            >
              Verify the questions from this note
              <PaperPlaneTilt size={13} weight="bold" />
            </Link>
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
