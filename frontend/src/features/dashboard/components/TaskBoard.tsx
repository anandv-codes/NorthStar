import { CheckCircle, Circle } from "@phosphor-icons/react";
import type { MemoryTask } from "../../../shared/api/httpClient";

interface TaskBoardProps {
  tasks: MemoryTask[];
  onToggle: (task: MemoryTask) => void;
}

export function TaskBoard({ tasks, onToggle }: TaskBoardProps) {
  if (tasks.length === 0) {
    return <EmptyState label="No tasks yet. They'll show up here once NorthStar extracts them from your notes." />;
  }

  return (
    <ul className="divide-y divide-neutral-100">
      {tasks.map((task) => {
        const done = task.status === "done" || task.status === "completed";
        return (
          <li key={task.task_id} className="flex items-start gap-3 py-3">
            <button
              type="button"
              aria-pressed={done}
              aria-label={done ? "Mark task as open" : "Mark task as done"}
              onClick={() => onToggle(task)}
              className="mt-0.5 shrink-0 cursor-pointer text-neutral-300 transition-colors hover:text-neutral-950"
            >
              {done ? (
                <CheckCircle size={20} weight="fill" className="text-neutral-950" />
              ) : (
                <Circle size={20} />
              )}
            </button>
            <span className={`text-sm leading-relaxed ${done ? "text-neutral-400 line-through" : "text-neutral-700"}`}>
              {task.description}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function EmptyState({ label }: { label: string }) {
  return <p className="py-6 text-sm text-neutral-400">{label}</p>;
}
