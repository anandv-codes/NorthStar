import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowClockwise,
  ArrowLeft,
  ArrowRight,
  Brain,
  Cards,
  CheckCircle,
  NotePencil,
  Spinner,
} from "@phosphor-icons/react";
import clsx from "clsx";
import {
  fetchRecallCards,
  fetchSuggestions,
  getNoteMemory,
  setNoteRecall,
  type NoteMemoryResponse,
} from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { formatLibraryDate, noteTitle } from "./libraryUtils";

interface NoteDetailPanelProps {
  noteId: string;
}

const RECALL_LABELS: Record<string, string> = {
  ready: "Recall ready",
  pending: "Generating recall questions",
  failed: "Recall generation failed",
  off: "Recall off",
};

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "failed" || status === "open"
      ? "bg-amber-50 text-amber-800"
      : status === "completed" || status === "answered" || status === "resolved"
        ? "bg-emerald-50 text-emerald-700"
        : "bg-neutral-100 text-neutral-600";
  return (
    <span className={clsx("rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize", tone)}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  if (count === 0) return null;
  return (
    <section>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-400">{title}</h3>
        <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold text-neutral-500">
          {count}
        </span>
      </div>
      {children}
    </section>
  );
}

function MemoryRow({ children }: { children: React.ReactNode }) {
  return (
    <li className="rounded-xl border border-neutral-200 bg-white px-3.5 py-2.5 text-sm leading-relaxed text-neutral-700">
      {children}
    </li>
  );
}

export function NoteDetailPanel({ noteId }: NoteDetailPanelProps) {
  const [searchParams] = useSearchParams();
  const notesHref = `/app/library/notes${searchParams.toString() ? `?${searchParams}` : ""}`;
  const [memory, setMemory] = useState<NoteMemoryResponse | null>(null);
  const [suggestionCount, setSuggestionCount] = useState(0);
  const [cardCount, setCardCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);
  const [recallError, setRecallError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const [snapshot, suggestions, cards] = await Promise.all([
        getNoteMemory(noteId),
        fetchSuggestions(1, noteId),
        fetchRecallCards({
          sourceNoteId: noteId,
          includeNotDue: true,
          status: "all",
          limit: 1,
        }),
      ]);
      if (id !== requestId.current) return;
      setMemory(snapshot);
      setSuggestionCount(suggestions.total);
      setCardCount(cards.total);
    } catch (err) {
      if (id !== requestId.current) return;
      setError(err instanceof Error ? err.message : "Couldn't load this note.");
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [noteId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleToggleRecall = async () => {
    if (!memory || toggling) return;
    setToggling(true);
    setRecallError(null);
    try {
      const result = await setNoteRecall(memory.note.note_id, !memory.note.recall_enabled);
      setMemory((current) =>
        current
          ? {
              ...current,
              note: {
                ...current.note,
                recall_enabled: result.enabled,
                recall_status: result.recall_status,
              },
            }
          : current,
      );
      setSuggestionCount(result.suggestions_total);
    } catch (err) {
      setRecallError(err instanceof Error ? err.message : "Couldn't update recall for this note.");
    } finally {
      setToggling(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3" aria-label="Loading note">
        <div className="h-8 w-2/3 animate-pulse rounded-lg bg-neutral-100" />
        <div className="h-40 animate-pulse rounded-2xl bg-neutral-100" />
        <div className="h-24 animate-pulse rounded-2xl bg-neutral-100" />
      </div>
    );
  }

  if (error || !memory) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-5">
        <p className="text-sm text-red-700">{error || "That note no longer exists."}</p>
        <Button className="mt-3" size="sm" variant="outline" onClick={() => void load()}>
          <ArrowClockwise size={14} />
          Try again
        </Button>
      </div>
    );
  }

  const note = memory.note;
  const recalled = Boolean(note.recall_enabled);

  return (
    <article className="min-w-0">
      <div className="mb-4 flex items-center justify-between gap-3 lg:hidden">
        <Link
          to={notesHref}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-neutral-500 hover:text-neutral-950"
        >
          <ArrowLeft size={14} />
          All notes
        </Link>
      </div>

      <header className="border-b border-neutral-200 pb-4">
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-neutral-400">
          <span>{formatLibraryDate(note.created_at)}</span>
          <span aria-hidden="true">·</span>
          <span className="capitalize">{note.status}</span>
          {recalled ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-50 px-2 py-0.5 font-semibold text-accent-700">
              <Brain size={11} weight="bold" />
              Recall
            </span>
          ) : null}
        </div>
        <h2 className="mt-2 font-display text-2xl font-semibold leading-tight tracking-tight text-neutral-950">
          {noteTitle(note.raw_text, note.enriched_summary)}
        </h2>
      </header>

      <div className="mt-5 rounded-2xl border border-neutral-200 bg-white p-5 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-neutral-950">
              <Brain size={16} weight="bold" className="text-neutral-500" />
              {RECALL_LABELS[note.recall_status ?? "off"] ?? "Recall off"}
            </p>
            <p className="mt-1.5 text-xs text-neutral-500">
              {suggestionCount > 0
                ? `${suggestionCount} question${suggestionCount === 1 ? "" : "s"} waiting to be verified.`
                : `${cardCount} card${cardCount === 1 ? "" : "s"} created from this note.`}
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={recalled}
            aria-label="Add this note to Recall"
            disabled={toggling}
            onClick={() => void handleToggleRecall()}
            className={clsx(
              "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
              recalled ? "bg-accent-600" : "bg-neutral-300",
            )}
          >
            <span
              className={clsx(
                "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                recalled ? "translate-x-6" : "translate-x-1",
              )}
            />
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2 border-t border-neutral-100 pt-4">
          {suggestionCount > 0 ? (
            <Link
              to={`/app/recall/verify?note=${encodeURIComponent(note.note_id)}`}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-neutral-950 px-3 text-xs font-semibold text-white hover:bg-neutral-800"
            >
              Verify questions
              <ArrowRight size={13} weight="bold" />
            </Link>
          ) : null}
          {cardCount > 0 ? (
            <Link
              to={`/app/library/recall?note=${encodeURIComponent(note.note_id)}`}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
            >
              <Cards size={13} weight="bold" />
              View {cardCount} card{cardCount === 1 ? "" : "s"}
            </Link>
          ) : null}
          {note.recall_enabled && note.recall_status === "pending" ? (
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
            >
              <ArrowClockwise size={13} />
              Refresh status
            </button>
          ) : null}
        </div>
        {recallError ? (
          <p role="alert" className="mt-2 text-xs text-red-600">
            {recallError}
          </p>
        ) : null}
      </div>

      <section className="mt-6">
        <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-400">Original note</h3>
        <div className="mt-2 whitespace-pre-wrap rounded-2xl border border-neutral-200 bg-white p-5 text-sm leading-relaxed text-neutral-700 shadow-card">
          {note.raw_text}
        </div>
      </section>

      {note.enriched_summary ? (
        <section className="mt-5">
          <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-400">Summary</h3>
          <p className="mt-2 rounded-2xl border border-neutral-200 bg-neutral-50 p-5 text-sm leading-relaxed text-neutral-700">
            {note.enriched_summary}
          </p>
        </section>
      ) : null}

      <section className="mt-6 space-y-5" aria-labelledby="note-memory-heading">
        <div className="flex items-center justify-between gap-2">
          <h3 id="note-memory-heading" className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-400">
            What NorthStar found
          </h3>
          <span className="inline-flex items-center gap-1 text-[11px] text-neutral-400">
            <CheckCircle size={12} />
            Read-only
          </span>
        </div>

        <Section title="Tasks" count={memory.tasks.length}>
          <ul className="space-y-1.5">
            {memory.tasks.map((task) => (
              <MemoryRow key={task.task_id}>
                <div className="flex items-start justify-between gap-3">
                  <span>{task.description}</span>
                  <StatusBadge status={task.status} />
                </div>
              </MemoryRow>
            ))}
          </ul>
        </Section>

        <Section title="Open questions" count={memory.questions.length}>
          <ul className="space-y-1.5">
            {memory.questions.map((question) => (
              <MemoryRow key={question.question_id}>
                <div className="flex items-start justify-between gap-3">
                  <span>{question.question}</span>
                  <StatusBadge status={question.status} />
                </div>
                {question.answer ? <p className="mt-1 text-xs text-neutral-500">{question.answer}</p> : null}
              </MemoryRow>
            ))}
          </ul>
        </Section>

        <Section title="Decisions" count={memory.decisions.length}>
          <ul className="space-y-1.5">
            {memory.decisions.map((decision) => (
              <MemoryRow key={decision.decision_id}>
                <p>{decision.decision}</p>
                {decision.rationale ? (
                  <p className="mt-1 text-xs text-neutral-500">{decision.rationale}</p>
                ) : null}
              </MemoryRow>
            ))}
          </ul>
        </Section>

        <Section title="Concepts" count={memory.concepts.length}>
          <ul className="space-y-1.5">
            {memory.concepts.map((concept) => (
              <MemoryRow key={concept.concept_id}>{concept.concept}</MemoryRow>
            ))}
          </ul>
        </Section>

        <Section title="Facts" count={memory.facts.length}>
          <ul className="space-y-1.5">
            {memory.facts.map((fact) => (
              <MemoryRow key={fact.fact_id}>{fact.content}</MemoryRow>
            ))}
          </ul>
        </Section>

        <Section title="Entities" count={memory.entities.length}>
          <div className="flex flex-wrap gap-1.5">
            {memory.entities.map((entity) => (
              <span
                key={entity.entity_id}
                className="rounded-full border border-neutral-200 bg-white px-2.5 py-1 text-xs font-medium text-neutral-600"
              >
                {entity.name}
                {entity.entity_type ? (
                  <span className="ml-1 text-neutral-400">{entity.entity_type}</span>
                ) : null}
              </span>
            ))}
          </div>
        </Section>

        {memory.tasks.length +
          memory.questions.length +
          memory.decisions.length +
          memory.concepts.length +
          memory.facts.length +
          memory.entities.length ===
        0 ? (
          <div className="rounded-2xl border border-dashed border-neutral-200 bg-white px-5 py-8 text-center">
            <NotePencil size={20} className="mx-auto text-neutral-400" />
            <p className="mt-2 text-sm font-medium text-neutral-700">No memory extracted yet</p>
            <p className="mt-1 text-xs text-neutral-500">
              {note.status === "processing"
                ? "NorthStar is still processing this note."
                : "There were no tasks, questions, decisions, or concepts to pull out."}
            </p>
          </div>
        ) : null}
      </section>

      <p className="mt-6 inline-flex items-center gap-1.5 text-[11px] text-neutral-400">
        {loading ? <Spinner size={12} className="animate-spin" /> : null}
        Updated from the latest extraction run.
      </p>
    </article>
  );
}
