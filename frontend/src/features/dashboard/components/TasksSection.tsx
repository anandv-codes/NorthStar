import { useState } from "react";
import { MemoryTask } from "../../../shared/api/httpClient";

interface TasksSectionProps {
  tasks: MemoryTask[];
  onMarkDone: (taskId: string) => Promise<void>;
  activeTaskId: string | null;
}
export function TasksSection({
  tasks,
  onMarkDone,
  activeTaskId,
}: TasksSectionProps) {
  const [archiveDisplayState, setArchiveDisplayState] = useState(false);
  const visibleTasks = tasks.filter((task) =>
    archiveDisplayState ? task.status === "completed" : task.status === "open",
  );

  return (
    <section>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          width: "70%",
        }}
      >
        <h2>Tasks</h2>
        <button onClick={() => setArchiveDisplayState(!archiveDisplayState)}>
          {archiveDisplayState ? "Show Open Tasks" : "Show Completed Tasks"}
        </button>
      </div>
      {visibleTasks.length === 0 ? (
        <p>
          {archiveDisplayState
            ? "No completed tasks found."
            : "No open tasks found."}
        </p>
      ) : (
        <ul>
          {visibleTasks.map((task) => (
            <li key={task.task_id}>
              <span>
                {task.description} ({task.status}){" "}
              </span>
              <button
                onClick={() => onMarkDone(task.task_id)}
                disabled={
                  archiveDisplayState ||
                  task.status === "completed" ||
                  activeTaskId === task.task_id
                }
              >
                Mark done
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
