import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Sparkle } from "@phosphor-icons/react";
import { fetchTasks, type MemoryTask } from "../../shared/api/httpClient";
import { LogoMark } from "../../shared/ui/Logo";

const SUGGESTED_PROMPT = "What are the key risks I should follow up on this week?";

const QUICK_ACTIONS = [
  "Summarize what I logged today",
  "What's still open from this week?",
  "Any risks I should know about?",
];

interface ChatEmptyStateProps {
  onUseSuggestion: (text: string) => void;
}

export function ChatEmptyState({ onUseSuggestion }: ChatEmptyStateProps) {
  const [openTasks, setOpenTasks] = useState<MemoryTask[]>([]);

  useEffect(() => {
    fetchTasks("open")
      .then(setOpenTasks)
      .catch(() => setOpenTasks([]));
  }, []);

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-10 text-center">
      <span className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-neutral-950 text-white">
        <LogoMark size={24} className="text-white" />
      </span>
      <h2 className="mt-5 font-display text-2xl font-semibold text-neutral-950">Hi, there 👋</h2>
      <p className="mt-1.5 text-sm text-neutral-500">Ask about your notes, and NorthStar will handle the rest.</p>

      <div className="mt-8 grid w-full max-w-2xl grid-cols-1 gap-3 text-left sm:grid-cols-3">
        <div className="rounded-2xl bg-neutral-950 p-4 text-white">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/15">
              <LogoMark size={14} className="text-white" />
            </span>
            <span className="rounded-full bg-white/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
              Assistant
            </span>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-neutral-300">
            Grounded in your notes, summaries and tasks — ask anything you've captured.
          </p>
        </div>

        <div className="rounded-2xl border border-neutral-200 p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-neutral-950">Open tasks</p>
            <Link
              to="/app/dashboard"
              className="inline-flex items-center gap-0.5 text-[11px] font-medium text-accent-600 hover:text-accent-700"
            >
              View all <ArrowUpRight size={12} />
            </Link>
          </div>
          <ul className="mt-2.5 space-y-1.5">
            {openTasks.length === 0 ? (
              <li className="text-xs text-neutral-400">Nothing open right now.</li>
            ) : (
              openTasks.slice(0, 3).map((task) => (
                <li key={task.task_id} className="truncate text-xs text-neutral-600">
                  {task.description}
                </li>
              ))
            )}
          </ul>
        </div>

        <button
          type="button"
          onClick={() => onUseSuggestion(SUGGESTED_PROMPT)}
          className="rounded-2xl border border-neutral-200 p-4 text-left transition-colors hover:border-neutral-950"
        >
          <div className="flex items-center gap-1.5 text-neutral-400">
            <Sparkle size={14} weight="fill" />
            <span className="text-[11px] font-semibold uppercase tracking-wide">Suggested prompt</span>
          </div>
          <p className="mt-2.5 text-xs leading-relaxed text-neutral-700">{SUGGESTED_PROMPT}</p>
        </button>
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action}
            type="button"
            onClick={() => onUseSuggestion(action)}
            className="rounded-full border border-neutral-200 px-3.5 py-1.5 text-xs font-medium text-neutral-600 transition-colors hover:border-neutral-950 hover:text-neutral-950"
          >
            {action}
          </button>
        ))}
      </div>
    </div>
  );
}
