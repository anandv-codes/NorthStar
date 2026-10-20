import { useState } from "react";
import { CheckCircle, Microphone, PaperPlaneTilt, Spinner } from "@phosphor-icons/react";
import { createNote } from "../../../shared/api/httpClient";
import { Button } from "../../../shared/ui/Button";

interface QuickAddNoteProps {
  onCreated?: () => void;
}

export function QuickAddNote({ onCreated }: QuickAddNoteProps) {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    const trimmed = text.trim();
    if (!trimmed || submitting) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await createNote({ text: trimmed });
      setText("");
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

      <div className="mt-4 flex justify-end">
        <Button onClick={handleSubmit} disabled={submitting || !text.trim()}>
          {submitting ? <Spinner size={16} className="animate-spin" /> : <PaperPlaneTilt size={16} weight="bold" />}
          Save note
        </Button>
      </div>
    </div>
  );
}
