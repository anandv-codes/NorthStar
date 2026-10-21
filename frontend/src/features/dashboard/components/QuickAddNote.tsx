import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Brain, CheckCircle, PaperPlaneTilt, Spinner } from "@phosphor-icons/react";
import { createNote } from "../../../shared/api/httpClient";
import { Button } from "../../../shared/ui/Button";
import { MicButton, MicStatus } from "../../../shared/ui/MicButton";
import { appendTranscript, useSpeechDictation } from "../../../shared/lib/useSpeechDictation";

interface QuickAddNoteProps {
  onCreated?: () => void;
}

export function QuickAddNote({ onCreated }: QuickAddNoteProps) {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [recallEnabled, setRecallEnabled] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dictation = useSpeechDictation({
    onFinal: (chunk) => setText((current) => appendTranscript(current, chunk)),
  });

  const handleSubmit = async () => {
    const trimmed = text.trim();
    if (!trimmed || submitting || dictation.listening) {
      return;
    }
    dictation.cancel();
    setSubmitting(true);
    setError(null);
    try {
      const created = await createNote({ text: trimmed, recall_enabled: recallEnabled });
      setText("");
      if (recallEnabled) {
        setRecallEnabled(false);
        navigate(`/app/recall/verify?note=${encodeURIComponent(created.note_id)}`);
        return;
      }
      setSuccess(true);
      onCreated?.();
      setTimeout(() => setSuccess(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save your note.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="relative">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="What's on your mind?"
          rows={5}
          autoFocus
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

      {error ? (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      ) : null}
      {success ? (
        <p role="status" className="mt-2 flex items-center gap-1.5 text-sm text-accent-700">
          <CheckCircle size={16} weight="fill" /> Note saved
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <label className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-neutral-500">
          <input
            type="checkbox"
            checked={recallEnabled}
            onChange={(event) => setRecallEnabled(event.target.checked)}
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
  );
}
