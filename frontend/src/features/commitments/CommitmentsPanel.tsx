import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Plus, Target } from "@phosphor-icons/react";
import type { UserCommitment } from "../../shared/api/httpClient";
import {
  fetchCommitments,
  updateCommitment,
} from "../../shared/api/httpClient";
import { CommitmentCard } from "./CommitmentCard";
import { ContributionsModal } from "./ContributionsModal";

export function CommitmentsPanel() {
  const [commitments, setCommitments] = useState<UserCommitment[]>([]);
  const [maxActive, setMaxActive] = useState(3);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<UserCommitment | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchCommitments("active");
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
    // Notes process asynchronously, so refresh counts when the user comes back.
    window.addEventListener("focus", load);
    return () => window.removeEventListener("focus", load);
  }, [load]);

  const handleProgress = async (commitmentId: string, value: number) => {
    const updated = await updateCommitment(commitmentId, { progress: value });
    setCommitments((current) =>
      current.map((row) => (row.commitment_id === updated.commitment_id ? updated : row)),
    );
  };

  const handleComplete = async (commitmentId: string) => {
    await updateCommitment(commitmentId, { progress: 100, status: "completed" });
    setCommitments((current) =>
      current.filter((row) => row.commitment_id !== commitmentId),
    );
  };

  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-accent-50 text-accent-700">
              <Target size={17} weight="bold" />
            </span>
            <h2 className="font-display text-base font-semibold text-neutral-950">
              Long-term focus
            </h2>
            <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[11px] font-semibold text-neutral-600">
              {commitments.length}/{maxActive}
            </span>
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            Goals you choose. Notes add evidence; progress stays in your hands.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {commitments.length < maxActive ? (
            <Link
              to="/app/settings"
              className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-accent-700 hover:bg-accent-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600"
            >
              <Plus size={13} weight="bold" />
              Add goal
            </Link>
          ) : null}
          <Link
            to="/app/settings"
            className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-neutral-500 hover:bg-neutral-100 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600"
          >
            Manage
            <ArrowRight size={13} />
          </Link>
        </div>
      </div>

      {error ? (
        <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      {loading ? (
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-hidden="true">
          {[0, 1, 2].map((key) => (
            <div key={key} className="h-44 animate-pulse rounded-xl bg-neutral-100" />
          ))}
        </div>
      ) : commitments.length === 0 ? (
        <div className="mt-5 rounded-xl border border-dashed border-neutral-200 px-5 py-8 text-center">
          <p className="text-sm font-medium text-neutral-900">Choose up to 3 goals worth returning to.</p>
          <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-neutral-500">
            Long-term focus is user-authored. NorthStar only adds a one-line update when a
            note explicitly shows progress.
          </p>
          <Link
            to="/app/settings"
            className="mt-4 inline-flex h-9 items-center justify-center rounded-lg bg-neutral-950 px-4 text-xs font-semibold text-white hover:bg-neutral-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950 focus-visible:ring-offset-2"
          >
            Set your first goal
          </Link>
        </div>
      ) : (
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {commitments.map((commitment) => (
            <CommitmentCard
              key={commitment.commitment_id}
              commitment={commitment}
              onProgress={(value) => handleProgress(commitment.commitment_id, value)}
              onComplete={() => handleComplete(commitment.commitment_id)}
              onOpenContributions={() => setSelected(commitment)}
            />
          ))}
        </div>
      )}

      <ContributionsModal
        commitment={selected}
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        onChanged={() => {
          void load();
        }}
      />
    </section>
  );
}
