import { Check, X } from "@phosphor-icons/react";
import type { MemoryQuestion } from "../../../shared/api/httpClient";
import { EmptyState } from "./TaskBoard";

interface OpenQuestionsProps {
  questions: MemoryQuestion[];
  onResolve: (question: MemoryQuestion) => void;
  onDismiss: (question: MemoryQuestion) => void;
}

export function OpenQuestions({ questions, onResolve, onDismiss }: OpenQuestionsProps) {
  if (questions.length === 0) {
    return <EmptyState label="No open questions right now." />;
  }

  return (
    <ul className="divide-y divide-neutral-100">
      {questions.map((question) => (
        <li key={question.question_id} className="flex items-start justify-between gap-3 py-3">
          <div>
            <p className="text-sm leading-relaxed text-neutral-700">{question.question}</p>
            {question.answer ? (
              <p className="mt-1 text-xs text-neutral-400">Answer: {question.answer}</p>
            ) : null}
          </div>
          <div className="flex shrink-0 gap-1">
            <button
              type="button"
              aria-label="Resolve question"
              onClick={() => onResolve(question)}
              className="inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-950"
            >
              <Check size={15} />
            </button>
            <button
              type="button"
              aria-label="Dismiss question"
              onClick={() => onDismiss(question)}
              className="inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-950"
            >
              <X size={15} />
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
