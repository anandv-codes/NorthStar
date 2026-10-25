import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import clsx from "clsx";
import {
  CheckCircle,
  ClockCounterClockwise,
  PencilSimple,
  Trash,
} from "@phosphor-icons/react";
import type { UserCommitment } from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { Modal } from "../../shared/ui/Modal";

interface CommitmentCardProps {
  commitment: UserCommitment;
  onProgress: (value: number) => Promise<void>;
  onComplete: () => Promise<void>;
  onOpenContributions: () => void;
  editable?: boolean;
  onRename?: (text: string) => Promise<void>;
  onDelete?: () => void;
}

function formatDate(value?: string | null) {
  if (!value) {
    return "";
  }
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function CommitmentCard({
  commitment,
  onProgress,
  onComplete,
  onOpenContributions,
  editable = false,
  onRename,
  onDelete,
}: CommitmentCardProps) {
  const isCompleted = commitment.status === "completed";
  const [value, setValue] = useState(commitment.progress);
  const [saving, setSaving] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [completeOpen, setCompleteOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(commitment.text);
  const [renaming, setRenaming] = useState(false);
  const lastSaved = useRef(commitment.progress);
  const savingRef = useRef(false);
  const pendingRef = useRef<number | null>(null);

  useEffect(() => {
    lastSaved.current = commitment.progress;
    if (!savingRef.current && pendingRef.current === null) {
      setValue(commitment.progress);
    }
  }, [commitment.commitment_id, commitment.progress]);

  useEffect(() => {
    setDraft(commitment.text);
  }, [commitment.text]);

  const saveProgress = async (next: number) => {
    if (next === lastSaved.current && pendingRef.current === null) {
      return;
    }
    if (savingRef.current) {
      // Keep only the latest value while a request is in flight; this prevents
      // fast keyboard changes from being dropped when the user tabs away.
      pendingRef.current = next;
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      await onProgress(next);
      lastSaved.current = next;
    } catch (err) {
      setValue(lastSaved.current);
      pendingRef.current = null;
      setError(err instanceof Error ? err.message : "Couldn't save progress.");
    } finally {
      savingRef.current = false;
      setSaving(false);
      const queued = pendingRef.current;
      pendingRef.current = null;
      if (queued !== null && queued !== lastSaved.current) {
        void saveProgress(queued);
      }
    }
  };

  const requestComplete = () => {
    setError(null);
    setCompleteOpen(true);
  };

  const commitSlider = () => {
    if (value >= 100) {
      requestComplete();
      return;
    }
    void saveProgress(value);
  };

  const handleSliderChange = (event: ChangeEvent<HTMLInputElement>) => {
    setValue(Number(event.target.value));
    setError(null);
  };

  const cancelComplete = () => {
    setValue(lastSaved.current);
    setCompleteOpen(false);
  };

  const confirmComplete = async () => {
    setCompleting(true);
    setError(null);
    try {
      await onComplete();
      setValue(100);
      lastSaved.current = 100;
      setCompleteOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't complete this goal.");
    } finally {
      setCompleting(false);
    }
  };

  const startRename = () => {
    setDraft(commitment.text);
    setEditing(true);
    setError(null);
  };

  const saveRename = async () => {
    const next = draft.trim();
    if (!onRename || !next || next === commitment.text) {
      setEditing(false);
      return;
    }
    setRenaming(true);
    setError(null);
    try {
      await onRename(next);
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update this goal.");
    } finally {
      setRenaming(false);
    }
  };

  const contributionLabel =
    commitment.contribution_count === 1
      ? "1 note update"
      : `${commitment.contribution_count} note updates`;

  return (
    <article className="flex h-full flex-col rounded-xl border border-neutral-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {editing ? (
            <div>
              <label htmlFor={`goal-text-${commitment.commitment_id}`} className="sr-only">
                Long-term goal
              </label>
              <input
                id={`goal-text-${commitment.commitment_id}`}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                maxLength={200}
                className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm text-neutral-950 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-200"
              />
              <div className="mt-2 flex items-center gap-2">
                <Button size="sm" onClick={() => void saveRename()} disabled={renaming}>
                  Save
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setEditing(false)}
                  disabled={renaming}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <h3 className="font-display text-base font-semibold leading-snug text-neutral-950">
              {commitment.text}
            </h3>
          )}
        </div>
        <span
          className={clsx(
            "shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide",
            isCompleted
              ? "bg-emerald-50 text-emerald-700"
              : "bg-accent-50 text-accent-700",
          )}
        >
          {isCompleted ? "Completed" : "Active"}
        </span>
      </div>

      <div className="mt-5 flex items-end justify-between">
        <span className="font-display text-2xl font-semibold text-neutral-950">{value}%</span>
        {isCompleted ? (
          <span className="text-[11px] text-neutral-500">
            {commitment.completed_at
              ? `Completed ${formatDate(commitment.completed_at)}`
              : "Completed"}
          </span>
        ) : (
          <span className="text-[11px] text-neutral-500">
            {saving ? "Saving…" : "You control this"}
          </span>
        )}
      </div>

      {isCompleted ? (
        <div
          className="mt-2 h-2 overflow-hidden rounded-full bg-neutral-100"
          role="img"
          aria-label="Goal completed at 100 percent"
        >
          <div className="h-full rounded-full bg-emerald-500" style={{ width: "100%" }} />
        </div>
      ) : (
        <div className="mt-2">
          <label htmlFor={`goal-progress-${commitment.commitment_id}`} className="sr-only">
            Progress for {commitment.text}
          </label>
          <input
            id={`goal-progress-${commitment.commitment_id}`}
            type="range"
            min={0}
            max={100}
            step={1}
            value={value}
            onChange={handleSliderChange}
            onPointerUp={commitSlider}
            onKeyUp={commitSlider}
            onBlur={commitSlider}
            aria-valuetext={`${value}%`}
            className="h-2 w-full cursor-pointer appearance-none rounded-full bg-neutral-200 accent-accent-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600 focus-visible:ring-offset-2"
          />
          <div className="mt-1 flex justify-between text-[10px] text-neutral-400">
            <span>0%</span>
            <span>100%</span>
          </div>
        </div>
      )}

      {error ? (
        <p role="alert" className="mt-3 text-xs text-red-600">
          {error}
        </p>
      ) : null}

      <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-neutral-100 pt-4">
        <button
          type="button"
          onClick={onOpenContributions}
          className="inline-flex items-center gap-1.5 rounded-lg text-xs font-medium text-neutral-600 transition-colors hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600 focus-visible:ring-offset-2"
        >
          <ClockCounterClockwise size={15} />
          {contributionLabel}
        </button>

        {editable && !isCompleted ? (
          <div className="ml-auto flex items-center gap-1">
            <button
              type="button"
              onClick={startRename}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-neutral-500 hover:bg-neutral-100 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600"
              aria-label={`Edit ${commitment.text}`}
            >
              <PencilSimple size={15} />
            </button>
            <button
              type="button"
              onClick={requestComplete}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-neutral-500 hover:bg-emerald-50 hover:text-emerald-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600"
              aria-label={`Complete ${commitment.text}`}
            >
              <CheckCircle size={16} />
            </button>
            {onDelete ? (
              <button
                type="button"
                onClick={onDelete}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-neutral-500 hover:bg-red-50 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                aria-label={`Delete ${commitment.text}`}
              >
                <Trash size={15} />
              </button>
            ) : null}
          </div>
        ) : null}

        {editable && isCompleted && onDelete ? (
          <button
            type="button"
            onClick={onDelete}
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-neutral-500 hover:bg-red-50 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          >
            <Trash size={14} />
            Delete
          </button>
        ) : null}
      </div>

      <Modal
        open={completeOpen}
        onClose={cancelComplete}
        title="Complete this long-term goal?"
      >
        <p className="text-sm leading-relaxed text-neutral-600">
          “{commitment.text}” will move to Completed at 100%. Completed goals are read-only:
          you can still review their note updates, but you cannot change progress or edit them.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-neutral-500">
          You can delete the goal later if you no longer want it.
        </p>
        {error ? (
          <p role="alert" className="mt-3 text-sm text-red-600">
            {error}
          </p>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={cancelComplete} disabled={completing}>
            Not yet
          </Button>
          <Button onClick={() => void confirmComplete()} disabled={completing}>
            {completing ? "Completing…" : "Complete goal"}
          </Button>
        </div>
      </Modal>
    </article>
  );
}
