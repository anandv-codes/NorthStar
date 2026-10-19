import type { ReactNode } from "react";
import type { MemoryQuestion, MemoryRisk, MemoryTask } from "../../../shared/api/httpClient";
import { TaskBoard } from "./TaskBoard";
import { OpenQuestions } from "./OpenQuestions";
import { RiskWatch } from "./RiskWatch";

interface WhatToDoPanelProps {
  tasks: MemoryTask[];
  questions: MemoryQuestion[];
  risks: MemoryRisk[];
  onToggleTask: (task: MemoryTask) => void;
  onResolveQuestion: (question: MemoryQuestion) => void;
  onDismissQuestion: (question: MemoryQuestion) => void;
  onResolveRisk: (risk: MemoryRisk) => void;
}

function SubSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-neutral-400">{title}</h3>
      <div className="mt-2">{children}</div>
    </div>
  );
}

/** One card instead of three separate panels — keeps "what to do" scannable as a single unit. */
export function WhatToDoPanel({
  tasks,
  questions,
  risks,
  onToggleTask,
  onResolveQuestion,
  onDismissQuestion,
  onResolveRisk,
}: WhatToDoPanelProps) {
  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-card">
      <h2 className="text-sm font-semibold text-neutral-950">What to do</h2>
      <div className="mt-4 grid grid-cols-1 gap-6 divide-y divide-neutral-100 lg:grid-cols-3 lg:divide-y-0 lg:divide-x">
        <SubSection title="Tasks">
          <TaskBoard tasks={tasks} onToggle={onToggleTask} />
        </SubSection>
        <div className="pt-6 lg:pl-6 lg:pt-0">
          <SubSection title="Questions">
            <OpenQuestions questions={questions} onResolve={onResolveQuestion} onDismiss={onDismissQuestion} />
          </SubSection>
        </div>
        <div className="pt-6 lg:pl-6 lg:pt-0">
          <SubSection title="Risks">
            <RiskWatch risks={risks} onResolve={onResolveRisk} />
          </SubSection>
        </div>
      </div>
    </section>
  );
}
