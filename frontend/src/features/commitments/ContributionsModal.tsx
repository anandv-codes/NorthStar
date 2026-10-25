import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowSquareOut, PencilSimple, Trash } from "@phosphor-icons/react";
import type {
  CommitmentContribution,
  UserCommitment,
} from "../../shared/api/httpClient";
import {
  deleteCommitmentContribution,
  fetchCommitmentContributions,
  updateCommitmentContribution,
} from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { Modal } from "../../shared/ui/Modal";

interface ContributionsModalProps {
  commitment: UserCommitment | null;
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
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

export function ContributionsModal({
  commitment,
  open,
  onClose,
  onChanged,
}: ContributionsModalProps) {
  const [items, setItems] = useState<CommitmentContribution[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const readOnly = commitment?.status === "completed";

  useEffect(() => {
    if (!open || !commitment) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setEditingId(null);
    setConfirmDeleteId(null);
    fetchCommitmentContributions(commitment.commitment_id)
      .then((rows) => {
        if (!cancelled) {
          setItems(rows);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Couldn't load note updates.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, commitment?.commitment_id]);

  const startEdit = (item: CommitmentContribution) => {
    setEditingId(item.contribution_id);
    setDraft(item.comment);
    setConfirmDeleteId(null);
    setError(null);
  };

  const saveEdit = async (item: CommitmentContribution) => {
    const next = draft.trim();
    if (!next || next === item.comment) {
      setEditingId(null);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await updateCommitmentContribution(item.contribution_id, next);
      setItems((current) =>
        current.map((row) =>
          row.contribution_id === updated.contribution_id
            ? {
                ...row,
                ...updated,
                // The PATCH response is the bare contribution row; keep the
                // source-note provenance already loaded for this item.
                source_note_created_at: row.source_note_created_at,
                source_note_excerpt: row.source_note_excerpt,
              }
            : row,
        ),
      );
      setEditingId(null);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update that note.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item: CommitmentContribution) => {
    setSaving(true);
    setError(null);
    try {
      await deleteCommitmentContribution(item.contribution_id);
      setItems((current) =>
        current.filter((row) => row.contribution_id !== item.contribution_id),
      );
      setConfirmDeleteId(null);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't remove that note.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open && Boolean(commitment)}
      onClose={onClose}
      title="Long-term focus history"
    >
      {commitment ? (
        <>
          <div className="rounded-xl bg-neutral-50 px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">
              {readOnly ? "Completed goal" : "Active goal"}
            </p>
            <p className="mt-1 font-display text-base font-semibold leading-snug text-neutral-950">
              {commitment.text}
            </p>
            <p className="mt-1 text-xs text-neutral-500">{commitment.progress}% progress</p>
          </div>

          <p className="mt-4 text-xs leading-relaxed text-neutral-500">
            Notes can add one update per goal per note. Updates are optional evidence, not
            progress: you stay in control of the slider.
          </p>

          {readOnly ? (
            <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
              Completed goals are read-only. This history stays available until you delete
              the goal.
            </p>
          ) : null}

          {error ? (
            <p role="alert" className="mt-3 text-sm text-red-600">
              {error}
            </p>
          ) : null}

          {loading ? (
            <p className="mt-5 text-sm text-neutral-500">Loading note updates…</p>
          ) : items.length === 0 ? (
            <p className="mt-5 rounded-xl border border-dashed border-neutral-200 px-4 py-6 text-center text-sm text-neutral-500">
              No note updates yet. Capture a note that explicitly shows progress toward this
              goal.
            </p>
          ) : (
            <ol className="mt-5 space-y-3">
              {items.map((item) => (
                <li key={item.contribution_id} className="rounded-xl border border-neutral-200 p-3">
                  {editingId === item.contribution_id ? (
                    <div>
                      <label htmlFor={`contribution-${item.contribution_id}`} className="sr-only">
                        Update text
                      </label>
                      <textarea
                        id={`contribution-${item.contribution_id}`}
                        value={draft}
                        onChange={(event) => setDraft(event.target.value)}
                        maxLength={240}
                        rows={2}
                        className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm text-neutral-950 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-200"
                      />
                      <div className="mt-2 flex items-center justify-end gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setEditingId(null)}
                          disabled={saving}
                        >
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => void saveEdit(item)}
                          disabled={saving}
                        >
                          Save
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className="text-sm leading-relaxed text-neutral-800">{item.comment}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-neutral-500">
                        <Link
                          to={`/app/library/notes/${item.note_id}`}
                          onClick={onClose}
                          className="inline-flex items-center gap-1 font-medium text-accent-700 hover:text-accent-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600"
                        >
                          Source note
                          <ArrowSquareOut size={12} />
                        </Link>
                        <span>{formatDate(item.source_note_created_at ?? item.created_at)}</span>
                        {item.edited_at ? (
                          <span className="rounded-full bg-neutral-100 px-2 py-0.5">Edited</span>
                        ) : null}
                      </div>
                      {item.source_note_excerpt ? (
                        <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-neutral-400">
                          “{item.source_note_excerpt}”
                        </p>
                      ) : null}

                      {confirmDeleteId === item.contribution_id ? (
                        <div className="mt-3 flex items-center justify-between gap-2 rounded-lg bg-red-50 px-3 py-2">
                          <p className="text-xs text-red-800">Remove this note update?</p>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => setConfirmDeleteId(null)}
                              disabled={saving}
                              className="rounded px-2 py-1 text-xs font-medium text-red-800 hover:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                            >
                              Cancel
                            </button>
                            <button
                              type="button"
                              onClick={() => void remove(item)}
                              disabled={saving}
                              className="rounded bg-red-700 px-2 py-1 text-xs font-semibold text-white hover:bg-red-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      ) : null}

                      {!readOnly && confirmDeleteId !== item.contribution_id ? (
                        <div className="mt-2 flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => startEdit(item)}
                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-neutral-500 hover:bg-neutral-100 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600"
                            aria-label="Edit note update"
                          >
                            <PencilSimple size={14} />
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteId(item.contribution_id)}
                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-neutral-500 hover:bg-red-50 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                            aria-label="Remove note update"
                          >
                            <Trash size={14} />
                          </button>
                        </div>
                      ) : null}
                    </>
                  )}
                </li>
              ))}
            </ol>
          )}
        </>
      ) : null}
    </Modal>
  );
}
