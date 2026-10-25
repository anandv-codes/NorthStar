import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Plus, Target, X } from "@phosphor-icons/react";
import { createCommitment } from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { Logo } from "../../shared/ui/Logo";

const MAX_GOALS = 3;

export function CommitmentOnboardingPage() {
  const navigate = useNavigate();
  const [goals, setGoals] = useState<string[]>([""]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nonEmpty = goals.map((goal) => goal.trim()).filter(Boolean);
  const canSave = nonEmpty.length > 0;

  const updateGoal = (index: number, value: string) => {
    setGoals((current) => current.map((goal, i) => (i === index ? value : goal)));
    setError(null);
  };

  const addGoal = () => {
    if (goals.length < MAX_GOALS) {
      setGoals((current) => [...current, ""]);
    }
  };

  const removeGoal = (index: number) => {
    setGoals((current) => current.filter((_, i) => i !== index));
  };

  const save = async () => {
    if (!canSave || saving) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      for (const goal of nonEmpty) {
        await createCommitment(goal);
      }
      navigate("/app/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save your goals.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50 px-4 py-10 sm:px-6 lg:flex lg:items-center lg:justify-center">
      <div className="mx-auto w-full max-w-2xl">
        <div className="flex items-center justify-between">
          <Logo />
          <Link
            to="/app/dashboard"
            className="rounded-lg px-3 py-2 text-sm font-medium text-neutral-500 hover:bg-neutral-100 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600"
          >
            Skip for now
          </Link>
        </div>

        <div className="mt-8 rounded-2xl border border-neutral-200 bg-white p-6 shadow-soft sm:p-8">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-accent-50 text-accent-700">
            <Target size={22} weight="bold" />
          </span>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-accent-700">
            Optional setup
          </p>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-neutral-950">
            What are you working toward?
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-neutral-600">
            Pick up to 3 long-term goals. NorthStar keeps them in view, and notes can add a
            one-line update when they explicitly show progress.
          </p>

          <div className="mt-5 rounded-xl border border-accent-100 bg-accent-50/60 px-4 py-3">
            <p className="text-xs leading-relaxed text-accent-900">
              Progress always stays manual. A note can add evidence, but it never moves your
              slider or completes a goal for you.
            </p>
          </div>

          <div className="mt-6 space-y-3">
            {goals.map((goal, index) => (
              <div key={index}>
                <div className="flex items-center justify-between">
                  <label
                    htmlFor={`onboarding-goal-${index}`}
                    className="text-xs font-semibold text-neutral-700"
                  >
                    Goal {index + 1}
                  </label>
                  {goals.length > 1 ? (
                    <button
                      type="button"
                      onClick={() => removeGoal(index)}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-neutral-400 hover:bg-neutral-100 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600"
                      aria-label={`Remove goal ${index + 1}`}
                    >
                      <X size={14} />
                    </button>
                  ) : null}
                </div>
                <input
                  id={`onboarding-goal-${index}`}
                  value={goal}
                  onChange={(event) => updateGoal(index, event.target.value)}
                  maxLength={200}
                  disabled={saving}
                  placeholder={
                    index === 0
                      ? "e.g. Ship the NorthStar MVP"
                      : "e.g. Build a consistent writing habit"
                  }
                  className="mt-1.5 h-11 w-full rounded-xl border border-neutral-300 px-3.5 text-sm text-neutral-950 placeholder:text-neutral-400 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-200"
                />
              </div>
            ))}
          </div>

          {goals.length < MAX_GOALS ? (
            <button
              type="button"
              onClick={addGoal}
              disabled={saving}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-semibold text-accent-700 hover:bg-accent-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600"
            >
              <Plus size={14} weight="bold" />
              Add another goal
            </button>
          ) : null}

          {error ? (
            <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          ) : null}

          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
            <Link
              to="/app/dashboard"
              className="inline-flex h-11 items-center justify-center rounded-xl px-4 text-sm font-medium text-neutral-500 hover:bg-neutral-100 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-600"
            >
              Skip for now
            </Link>
            <Button onClick={() => void save()} disabled={!canSave || saving}>
              {saving ? "Saving…" : "Save goals"}
              <ArrowRight size={16} />
            </Button>
          </div>

          <p className="mt-4 text-center text-[11px] text-neutral-400">
            You can edit, complete, or delete these anytime in Settings.
          </p>
        </div>
      </div>
    </div>
  );
}
