import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Plus, Target } from "@phosphor-icons/react";
import type { UserCommitment } from "../../shared/api/httpClient";
import {
  createCommitment,
  deleteCommitment,
  fetchCommitments,
  updateCommitment,
} from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { Modal } from "../../shared/ui/Modal";
import { CommitmentCard } from "../commitments/CommitmentCard";
import { ContributionsModal } from "../commitments/ContributionsModal";

export function SettingsPage() {
  const [commitments, setCommitments] = useState<UserCommitment[]>([]);
  const [maxActive, setMaxActive] = useState(3);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [newText, setNewText] = useState("");
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<UserCommitment | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<UserCommitment | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchCommitments();
      setCommitments(data.commitments);
      setMaxActive(data.max_active);
      setSelected((current) => {
        if (!current) {
          return null;
        }
        return data.commitments.find((row) => row.commitment_id === current.commitment_id) ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load long-term goals.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const active = commitments.filter((row) => row.status === "active");
  const completed = commitments.filter((row) => row.status === "completed");
  const atLimit = active.length >= maxActive;

  const replace = (updated: UserCommitment) => {
    setCommitments((current) =>
      current.map((row) => (row.commitment_id === updated.commitment_id ? updated : row)),
    );
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    const text = newText.trim();
    if (!text || atLimit) {
      return;
    }
    setCreating(true);
    setActionError(null);
    try {
      const created = await createCommitment(text);
      setCommitments((current) => [created, ...current]);
      setNewText("");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Couldn't add that goal.");
    } finally {
      setCreating(false);
    }
  };

  const handleProgress = async (commitmentId: string, value: number) => {
    const updated = await updateCommitment(commitmentId, { progress: value });
    replace(updated);
  };

  const handleComplete = async (commitmentId: string) => {
    const updated = await updateCommitment(commitmentId, {
      progress: 100,
      status: "completed",
    });
    replace(updated);
  };

  const handleRename = async (commitmentId: string, text: string) => {
    const updated = await updateCommitment(commitmentId, { text });
    replace(updated);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) {
      return;
    }
    setDeleting(true);
    setActionError(null);
    try {
      await deleteCommitment(deleteTarget.commitment_id);
      setCommitments((current) =>
        current.filter((row) => row.commitment_id !== deleteTarget.commitment_id),
      );
      setDeleteTarget(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Couldn't delete that goal.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-8">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">
          Settings
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          Manage the long-term goals NorthStar keeps in view.
        </p>
      </header>

      {error ? (
        <p role="alert" className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      <section className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-accent-50 text-accent-700">
                <Target size={17} weight="bold" />
              </span>
              <h2 className="font-display text-base font-semibold text-neutral-950">
                Long-term goals
              </h2>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-neutral-500">
              Write 1–200 characters. You can keep up to {maxActive} active goals. Completed
              goals free a slot and stay read-only.
            </p>
          </div>
          <span className="rounded-full bg-neutral-100 px-2.5 py-1 text-[11px] font-semibold text-neutral-600">
            {active.length}/{maxActive} active
          </span>
        </div>

        <form onSubmit={(event) => void handleCreate(event)} className="mt-5">
          <label htmlFor="new-goal" className="text-xs font-semibold text-neutral-700">
            Add a long-term goal
          </label>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            <input
              id="new-goal"
              value={newText}
              onChange={(event) => setNewText(event.target.value)}
              maxLength={200}
              disabled={atLimit || creating}
              placeholder={
                atLimit
                  ? "Complete or delete a goal to add another"
                  : "e.g. Ship the NorthStar MVP"
              }
              className="h-11 flex-1 rounded-xl border border-neutral-300 px-3.5 text-sm text-neutral-950 placeholder:text-neutral-400 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-200 disabled:bg-neutral-50 disabled:text-neutral-400"
            />
            <Button type="submit" disabled={atLimit || creating || !newText.trim()}>
              <Plus size={16} weight="bold" />
              {creating ? "Adding…" : "Add goal"}
            </Button>
          </div>
          {atLimit ? (
            <p className="mt-2 text-xs text-amber-700">
              You have {maxActive} active goals. Complete or delete one to choose another.
            </p>
          ) : null}
        </form>

        {actionError ? (
          <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {actionError}
          </p>
        ) : null}

        {loading ? (
          <div className="mt-6 grid gap-3 sm:grid-cols-2" aria-hidden="true">
            <div className="h-52 animate-pulse rounded-xl bg-neutral-100" />
            <div className="h-52 animate-pulse rounded-xl bg-neutral-100" />
          </div>
        ) : (
          <>
            <div className="mt-6">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Active
              </h3>
              {active.length === 0 ? (
                <p className="mt-2 rounded-xl border border-dashed border-neutral-200 px-4 py-6 text-center text-sm text-neutral-500">
                  No active goals yet. Add one above whenever you are ready.
                </p>
              ) : (
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {active.map((commitment) => (
                    <CommitmentCard
                      key={commitment.commitment_id}
                      commitment={commitment}
                      editable
                      onProgress={(value) => handleProgress(commitment.commitment_id, value)}
                      onComplete={() => handleComplete(commitment.commitment_id)}
                      onRename={(text) => handleRename(commitment.commitment_id, text)}
                      onDelete={() => setDeleteTarget(commitment)}
                      onOpenContributions={() => setSelected(commitment)}
                    />
                  ))}
                </div>
              )}
            </div>

            <div className="mt-8">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Completed
              </h3>
              {completed.length === 0 ? (
                <p className="mt-2 text-sm text-neutral-500">Completed goals will appear here.</p>
              ) : (
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {completed.map((commitment) => (
                    <CommitmentCard
                      key={commitment.commitment_id}
                      commitment={commitment}
                      editable
                      onProgress={(value) => handleProgress(commitment.commitment_id, value)}
                      onComplete={() => handleComplete(commitment.commitment_id)}
                      onDelete={() => setDeleteTarget(commitment)}
                      onOpenContributions={() => setSelected(commitment)}
                    />
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </section>

      <ContributionsModal
        commitment={selected}
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        onChanged={() => {
          void load();
        }}
      />

      <Modal
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title="Delete this long-term goal?"
      >
        {deleteTarget ? (
          <>
            <p className="font-display text-base font-semibold leading-snug text-neutral-950">
              {deleteTarget.text}
            </p>
            <p className="mt-3 text-sm leading-relaxed text-neutral-600">
              This permanently deletes the goal and all of its note contributions. This cannot
              be undone.
            </p>
            {actionError ? (
              <p role="alert" className="mt-3 text-sm text-red-600">
                {actionError}
              </p>
            ) : null}
            <div className="mt-5 flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
              >
                Cancel
              </Button>
              <button
                type="button"
                onClick={() => void confirmDelete()}
                disabled={deleting}
                className="inline-flex h-11 items-center justify-center rounded-xl bg-red-700 px-5 text-sm font-medium text-white hover:bg-red-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:opacity-60"
              >
                {deleting ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </>
        ) : null}
      </Modal>
    </div>
  );
}
