import { useEffect, useId, useState } from "react";
import { Check, PencilSimple, Spinner, X } from "@phosphor-icons/react";
import type { RecallSuggestion } from "../../shared/api/httpClient";

interface SuggestionCardProps {
  suggestion: RecallSuggestion;
  selected: boolean;
  processing: "accept" | "reject" | "save" | null;
  onSelect: (selected: boolean) => void;
  onAccept: () => void;
  onReject: () => void;
  onSave: (question: string, answer: string) => Promise<void>;
}

function validateQuestionField(value: string): string | null {
  const question = value.trim();
  if (!question) return "Add a question.";
  if (!question.endsWith("?")) return "Questions must end with a question mark.";
  return null;
}

function validateAnswerField(value: string): string | null {
  return value.trim() ? null : "Add an answer before saving.";
}

export function SuggestionCard({
  suggestion,
  selected,
  processing,
  onSelect,
  onAccept,
  onReject,
  onSave,
}: SuggestionCardProps) {
  const [showAnswer, setShowAnswer] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draftQuestion, setDraftQuestion] = useState(suggestion.question);
  const [draftAnswer, setDraftAnswer] = useState(suggestion.answer ?? "");
  const [questionError, setQuestionError] = useState<string | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const questionErrorId = useId();
  const answerErrorId = useId();
  const busy = processing !== null;

  useEffect(() => {
    setDraftQuestion(suggestion.question);
    setDraftAnswer(suggestion.answer ?? "");
  }, [suggestion.question, suggestion.answer]);

  const startEditing = () => {
    setDraftQuestion(suggestion.question);
    setDraftAnswer(suggestion.answer ?? "");
    setQuestionError(null);
    setAnswerError(null);
    setShowAnswer(true);
    setEditing(true);
  };

  const cancelEditing = () => {
    setDraftQuestion(suggestion.question);
    setDraftAnswer(suggestion.answer ?? "");
    setQuestionError(null);
    setAnswerError(null);
    setEditing(false);
  };

  const save = async () => {
    const nextQuestionError = validateQuestionField(draftQuestion);
    const nextAnswerError = validateAnswerField(draftAnswer);
    setQuestionError(nextQuestionError);
    setAnswerError(nextAnswerError);
    if (nextQuestionError || nextAnswerError) return;

    try {
      await onSave(draftQuestion.trim(), draftAnswer.trim());
      setEditing(false);
    } catch (err) {
      setAnswerError(err instanceof Error ? err.message : "Couldn't save this suggestion.");
    }
  };

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-card">
      <div className="flex items-start gap-3">
        <label className="mt-1 inline-flex shrink-0 cursor-pointer items-center">
          <input
            type="checkbox"
            checked={selected}
            disabled={busy}
            onChange={(event) => onSelect(event.target.checked)}
            aria-label={`Select suggestion: ${suggestion.question}`}
            className="h-4 w-4 rounded border-neutral-300 text-neutral-950 focus:ring-neutral-950"
          />
        </label>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-neutral-200 px-2.5 py-1 text-[11px] font-semibold capitalize text-neutral-500">
              {suggestion.item_type}
            </span>
            {!editing ? (
              <button
                type="button"
                disabled={busy}
                onClick={startEditing}
                className="inline-flex items-center gap-1 text-xs font-medium text-neutral-500 transition-colors hover:text-neutral-950 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <PencilSimple size={13} />
                Edit
              </button>
            ) : null}
          </div>

          {editing ? (
            <div className="mt-3 space-y-3">
              <div>
                <label
                  htmlFor={`${questionErrorId}-input`}
                  className="text-xs font-semibold text-neutral-600"
                >
                  Question
                </label>
                <textarea
                  id={`${questionErrorId}-input`}
                  value={draftQuestion}
                  rows={2}
                  aria-invalid={Boolean(questionError)}
                  aria-describedby={questionError ? questionErrorId : undefined}
                  onBlur={() => setQuestionError(validateQuestionField(draftQuestion))}
                  onChange={(event) => setDraftQuestion(event.target.value)}
                  className="mt-1 w-full resize-none rounded-xl border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-200"
                />
                {questionError ? (
                  <p id={questionErrorId} role="alert" className="mt-1 text-xs text-red-600">
                    {questionError}
                  </p>
                ) : null}
              </div>

              <div>
                <label
                  htmlFor={`${answerErrorId}-input`}
                  className="text-xs font-semibold text-neutral-600"
                >
                  Answer
                </label>
                <textarea
                  id={`${answerErrorId}-input`}
                  value={draftAnswer}
                  rows={3}
                  aria-invalid={Boolean(answerError)}
                  aria-describedby={answerError ? answerErrorId : undefined}
                  onBlur={() => setAnswerError(validateAnswerField(draftAnswer))}
                  onChange={(event) => setDraftAnswer(event.target.value)}
                  className="mt-1 w-full resize-none rounded-xl border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-200"
                />
                {answerError ? (
                  <p id={answerErrorId} role="alert" className="mt-1 text-xs text-red-600">
                    {answerError}
                  </p>
                ) : null}
              </div>
            </div>
          ) : (
            <>
              <p className="mt-2.5 text-sm font-medium leading-relaxed text-neutral-900">
                {suggestion.question}
              </p>
              {showAnswer ? (
                <p className="mt-2 rounded-xl bg-neutral-50 px-3 py-2 text-sm leading-relaxed text-neutral-600">
                  {suggestion.answer || "No answer yet. Edit this suggestion to add one."}
                </p>
              ) : null}
              <div className="mt-2 flex items-center gap-3">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setShowAnswer((current) => !current)}
                  className="text-xs font-semibold text-neutral-500 transition-colors hover:text-neutral-950 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-expanded={showAnswer}
                >
                  {showAnswer ? "Hide answer" : "Show answer"}
                </button>
                <span className="text-xs text-neutral-400">Worth remembering?</span>
              </div>
            </>
          )}
        </div>

        <div className="flex shrink-0 gap-2">
          {editing ? (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={cancelEditing}
                className="inline-flex h-9 items-center justify-center rounded-lg border border-neutral-200 px-3 text-xs font-semibold text-neutral-600 transition-colors hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void save()}
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-neutral-950 bg-neutral-950 px-3 text-xs font-semibold text-white transition-colors hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {processing === "save" ? <Spinner size={14} className="animate-spin" /> : null}
                Save
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={onReject}
                title="Skip this suggestion"
                aria-label="Skip this suggestion"
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-200 text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-950 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {processing === "reject" ? <Spinner size={16} className="animate-spin" /> : <X size={16} />}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={onAccept}
                title="Add to recall"
                aria-label="Add to recall"
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 transition-colors hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {processing === "accept" ? <Spinner size={16} className="animate-spin" /> : <Check size={16} weight="bold" />}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
