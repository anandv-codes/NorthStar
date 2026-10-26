import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowClockwise,
  ArrowLeft,
  CheckCircle,
  NotePencil,
  Spinner,
  Stack,
  X,
} from "@phosphor-icons/react";
import {
  acceptSuggestion,
  acceptSuggestions,
  assignCandidateDecks,
  fetchRecallDecks,
  fetchSuggestions,
  getNoteStatus,
  rejectSuggestion,
  rejectSuggestions,
  restoreSuggestions,
  revealSuggestionAnswer,
  updateSuggestion,
  type NoteStatus,
  type RecallDeck,
  type RecallSuggestion,
} from "../../shared/api/httpClient";
import { Button } from "../../shared/ui/Button";
import { DeckPicker } from "./components/DeckPicker";
import { DeckFormModal } from "./components/DeckFormModal";
import { SuggestionCard } from "./SuggestionCard";

const POLL_INTERVAL_MS = 1500;
const NOTE_POLL_TIMEOUT_MS = 120_000;
const TERMINAL_NOTE_STATUSES = new Set(["completed", "enriched", "failed"]);

function isNoteSettled(status: NoteStatus): boolean {
  return TERMINAL_NOTE_STATUSES.has(status.status) && status.recall_status !== "pending";
}

export function RecallVerifyPage() {
  const [searchParams] = useSearchParams();
  const noteId = searchParams.get("note");

  const [decks, setDecks] = useState<RecallDeck[]>([]);
  const [preferredDeckId, setPreferredDeckId] = useState("");
  const [suggestions, setSuggestions] = useState<RecallSuggestion[]>([]);
  const [note, setNote] = useState<NoteStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notePollExpired, setNotePollExpired] = useState(false);
  const [notePollNonce, setNotePollNonce] = useState(0);
  const [processingSuggestionId, setProcessingSuggestionId] = useState<string | null>(null);
  const [processingAction, setProcessingAction] = useState<"accept" | "reject" | "save" | null>(null);
  const [deckSavingId, setDeckSavingId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeckId, setBulkDeckId] = useState("");
  const [bulkAssigning, setBulkAssigning] = useState(false);
  const [bulkAccepting, setBulkAccepting] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [selectionWarning, setSelectionWarning] = useState<string | null>(null);
  const [undoNotice, setUndoNotice] = useState<{
    candidateIds: string[];
    message: string;
  } | null>(null);
  const [undoBusy, setUndoBusy] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadSuggestions = useCallback(async () => {
    const list = await fetchSuggestions(200, noteId);
    setSuggestions(list.suggestions);
    const liveIds = new Set(list.suggestions.map((item) => item.candidate_id));
    setSelectedIds((current) => new Set(Array.from(current).filter((id) => liveIds.has(id))));
    return list.suggestions;
  }, [noteId]);

  const refreshNote = useCallback(async () => {
    if (!noteId) return null;
    try {
      const status = await getNoteStatus(noteId);
      setNote(status);
      return status;
    } catch {
      return null;
    }
  }, [noteId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [deckList, suggestionList] = await Promise.all([
        fetchRecallDecks(),
        fetchSuggestions(200, noteId),
      ]);
      setDecks(deckList.decks);
      const defaultDeckId =
        deckList.decks.find((deck) => deck.is_default)?.deck_id ?? deckList.decks[0]?.deck_id ?? "";
      setPreferredDeckId((current) => current || defaultDeckId);
      setBulkDeckId((current) => current || defaultDeckId);
      setSuggestions(suggestionList.suggestions);
      if (noteId) {
        setNote(await getNoteStatus(noteId));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load your questions.");
    } finally {
      setLoading(false);
    }
  }, [noteId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!noteId) return;
    let cancelled = false;
    const deadline = Date.now() + NOTE_POLL_TIMEOUT_MS;

    const poll = async () => {
      try {
        const status = await getNoteStatus(noteId);
        if (cancelled) return;
        setNote(status);
        setNotePollExpired(false);
        await loadSuggestions();
        if (cancelled) return;

        // Keep polling until the note itself is final. Suggestions can appear
        // while the worker is still writing them, so a non-empty list is not a
        // signal to stop: doing that freezes `note` at "pending" and leaves the
        // page showing the generation spinner after every suggestion is filed.
        if (isNoteSettled(status)) return;

        if (Date.now() >= deadline) {
          setNotePollExpired(true);
          return;
        }
        pollTimer.current = setTimeout(() => void poll(), POLL_INTERVAL_MS);
      } catch {
        if (cancelled) return;
        // Keep trying transient failures until the deadline instead of
        // leaving the page stuck on a stale "pending" snapshot.
        if (Date.now() >= deadline) {
          setNotePollExpired(true);
          return;
        }
        pollTimer.current = setTimeout(() => void poll(), POLL_INTERVAL_MS);
      }
    };

    setNotePollExpired(false);
    void poll();
    return () => {
      cancelled = true;
      if (pollTimer.current) {
        clearTimeout(pollTimer.current);
        pollTimer.current = null;
      }
    };
  }, [noteId, loadSuggestions, notePollNonce]);

  useEffect(() => {
    if (!undoNotice) return;
    const timer = setTimeout(() => setUndoNotice(null), 10_000);
    return () => clearTimeout(timer);
  }, [undoNotice]);

  const fallbackDeckId = preferredDeckId || decks.find((deck) => deck.is_default)?.deck_id || "";

  const removeSuggestions = (candidateIds: Set<string>) => {
    if (candidateIds.size === 0) return;
    setSuggestions((current) =>
      current.filter((item) => !candidateIds.has(item.candidate_id)),
    );
    setSelectedIds((current) => {
      const next = new Set(current);
      candidateIds.forEach((candidateId) => next.delete(candidateId));
      return next;
    });
  };

  const removeSuggestion = (candidateId: string) => {
    removeSuggestions(new Set([candidateId]));
  };

  const handleAccept = async (suggestion: RecallSuggestion) => {
    setProcessingSuggestionId(suggestion.candidate_id);
    setProcessingAction("accept");
    try {
      await acceptSuggestion(suggestion.candidate_id);
      removeSuggestion(suggestion.candidate_id);
      void refreshNote();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add that question to a deck.");
    } finally {
      setProcessingSuggestionId(null);
      setProcessingAction(null);
    }
  };

  const handleReject = async (suggestion: RecallSuggestion) => {
    setProcessingSuggestionId(suggestion.candidate_id);
    setProcessingAction("reject");
    try {
      await rejectSuggestion(suggestion.candidate_id);
      removeSuggestion(suggestion.candidate_id);
      setUndoNotice({
        candidateIds: [suggestion.candidate_id],
        message: "Card skipped.",
      });
      void refreshNote();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't skip that question.");
    } finally {
      setProcessingSuggestionId(null);
      setProcessingAction(null);
    }
  };

  const handleSave = async (suggestion: RecallSuggestion, question: string, answer: string) => {
    setProcessingSuggestionId(suggestion.candidate_id);
    setProcessingAction("save");
    try {
      const updated = await updateSuggestion(suggestion.candidate_id, { question, answer });
      setSuggestions((current) =>
        current.map((item) => (item.candidate_id === suggestion.candidate_id ? updated : item)),
      );
    } finally {
      setProcessingSuggestionId(null);
      setProcessingAction(null);
    }
  };

  const handleRevealAnswer = async (suggestion: RecallSuggestion): Promise<string | null> => {
    const updated = await revealSuggestionAnswer(suggestion.candidate_id);
    if (!updated) return suggestion.answer ?? null;
    setSuggestions((current) =>
      current.map((item) =>
        item.candidate_id === suggestion.candidate_id ? { ...item, ...updated } : item,
      ),
    );
    return updated.answer ?? null;
  };

  const handleDeckChange = async (suggestion: RecallSuggestion, deckId: string) => {
    if (!deckId) return;
    setDeckSavingId(suggestion.candidate_id);
    setError(null);
    try {
      const updated = await updateSuggestion(suggestion.candidate_id, { deck_id: deckId });
      setSuggestions((current) =>
        current.map((item) => (item.candidate_id === suggestion.candidate_id ? updated : item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't move that question to a deck.");
    } finally {
      setDeckSavingId(null);
    }
  };

  const handleSelect = (candidateId: string, selected: boolean) => {
    setSelectionWarning(null);
    setSelectedIds((current) => {
      const next = new Set(current);
      if (selected) next.add(candidateId);
      else next.delete(candidateId);
      return next;
    });
  };

  const allSelected =
    suggestions.length > 0 && suggestions.every((item) => selectedIds.has(item.candidate_id));

  const handleSelectAll = (selected: boolean) => {
    setSelectionWarning(null);
    setSelectedIds(selected ? new Set(suggestions.map((item) => item.candidate_id)) : new Set());
  };

  const handleBulkAssign = async () => {
    const candidateIds = Array.from(selectedIds);
    if (candidateIds.length === 0 || !bulkDeckId) return;
    setBulkAssigning(true);
    setError(null);
    try {
      const result = await assignCandidateDecks(candidateIds, bulkDeckId);
      const byId = new Map(result.suggestions.map((item) => [item.candidate_id, item]));
      setSuggestions((current) => current.map((item) => byId.get(item.candidate_id) ?? item));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't assign those questions.");
    } finally {
      setBulkAssigning(false);
    }
  };

  const handleBulkAccept = async () => {
    const candidateIds = Array.from(selectedIds);
    if (candidateIds.length === 0) {
      setSelectionWarning("No recall card selected. Select at least one card before adding.");
      return;
    }
    setSelectionWarning(null);
    setBulkAccepting(true);
    setError(null);
    try {
      const result = await acceptSuggestions(candidateIds, null);
      const acceptedIds = new Set(
        result.results.filter((item) => item.status === "carded").map((item) => item.candidate_id),
      );
      removeSuggestions(acceptedIds);
      if (acceptedIds.size > 0) {
        void refreshNote();
      }
      if (result.failed > 0) {
        const firstError = result.results.find((item) => item.error)?.error;
        setError(
          `${result.failed} question${result.failed === 1 ? "" : "s"} couldn't be added${
            firstError ? `: ${firstError}` : "."
          }`,
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add the selected questions.");
    } finally {
      setBulkAccepting(false);
    }
  };

  const handleFinishReview = async () => {
    const candidateIds = Array.from(selectedIds);
    const hasSelection = candidateIds.length > 0;
    const unselectedIds = suggestions
      .filter((item) => !selectedIds.has(item.candidate_id))
      .map((item) => item.candidate_id);

    if (hasSelection) {
      setSelectionWarning(null);
    } else {
      setSelectionWarning("No recall card selected. Discarding all remaining cards.");
    }

    setFinishing(true);
    setError(null);
    try {
      if (hasSelection) {
        const acceptResult = await acceptSuggestions(candidateIds, null);
        const acceptedIds = new Set(
          acceptResult.results
            .filter((item) => item.status === "carded")
            .map((item) => item.candidate_id),
        );
        removeSuggestions(acceptedIds);
        if (acceptedIds.size > 0) {
          void refreshNote();
        }

        if (acceptResult.failed > 0) {
          const firstError = acceptResult.results.find((item) => item.error)?.error;
          setError(
            `${acceptResult.failed} selected question${
              acceptResult.failed === 1 ? "" : "s"
            } couldn't be added${firstError ? `: ${firstError}` : "."} Nothing was discarded, so you can retry.`,
          );
          return;
        }
      }

      if (unselectedIds.length === 0) return;

      const rejectResult = await rejectSuggestions(unselectedIds);
      const rejectedIds = new Set(
        rejectResult.results
          .filter((item) => item.status === "rejected")
          .map((item) => item.candidate_id),
      );
      removeSuggestions(rejectedIds);

      if (rejectedIds.size > 0) {
        setUndoNotice({
          candidateIds: Array.from(rejectedIds),
          message: `${rejectedIds.size} card${rejectedIds.size === 1 ? "" : "s"} discarded.`,
        });
      }

      if (rejectResult.failed > 0) {
        const firstError = rejectResult.results.find((item) => item.error)?.error;
        setError(
          `${rejectResult.failed} unselected card${
            rejectResult.failed === 1 ? "" : "s"
          } couldn't be discarded${firstError ? `: ${firstError}` : "."}`,
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't finish the review.");
    } finally {
      setFinishing(false);
    }
  };

  const handleUndo = async () => {
    if (!undoNotice || undoBusy) return;
    setUndoBusy(true);
    setError(null);
    try {
      const result = await restoreSuggestions(undoNotice.candidateIds);
      const failedIds = result.results
        .filter((item) => item.status === "failed")
        .map((item) => item.candidate_id);

      if (result.restored > 0) {
        setSelectionWarning(null);
        await loadSuggestions();
        void refreshNote();
      }

      if (failedIds.length > 0) {
        const firstError = result.results.find((item) => item.error)?.error;
        setUndoNotice({
          candidateIds: failedIds,
          message: `${failedIds.length} card${
            failedIds.length === 1 ? "" : "s"
          } couldn't be restored.`,
        });
        setError(
          `Some cards couldn't be restored${firstError ? `: ${firstError}` : "."}`,
        );
      } else {
        setUndoNotice(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't restore those cards.");
    } finally {
      setUndoBusy(false);
    }
  };

  const handleDeckCreated = async (deck: RecallDeck) => {
    setDecks((current) => [...current, deck]);
    setPreferredDeckId(deck.deck_id);
    setBulkDeckId(deck.deck_id);
    const candidateIds = Array.from(selectedIds);
    if (candidateIds.length === 0) return;
    setBulkAssigning(true);
    try {
      const result = await assignCandidateDecks(candidateIds, deck.deck_id);
      const byId = new Map(result.suggestions.map((item) => [item.candidate_id, item]));
      setSuggestions((current) => current.map((item) => byId.get(item.candidate_id) ?? item));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deck created, but assigning questions failed.");
    } finally {
      setBulkAssigning(false);
    }
  };

  const handleRetryNote = () => {
    setNotePollExpired(false);
    setNotePollNonce((value) => value + 1);
  };

  const noteProcessing =
    Boolean(noteId) && !notePollExpired && (!note || !isNoteSettled(note));
  const noteFailed = note?.status === "failed" || note?.recall_status === "failed";

  return (
    <div className="mx-auto max-w-2xl">
      <header className="mb-6">
        <Link
          to="/app/recall"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-neutral-500 transition-colors hover:text-neutral-950"
        >
          <ArrowLeft size={14} />
          Back to recall
        </Link>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">
              Verify questions
            </h1>
            <p className="mt-0.5 max-w-lg text-sm text-neutral-500">
              Tick the cards worth keeping, choose their decks, then finish to discard the rest.
            </p>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
            <Stack size={14} weight="bold" />
            {suggestions.length} to verify
          </span>
        </div>
      </header>

      {error ? (
        <p role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      {loading ? (
        <div className="flex min-h-[280px] items-center justify-center rounded-2xl border border-neutral-200 bg-white shadow-card">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-950" />
        </div>
      ) : noteProcessing && suggestions.length === 0 ? (
        <div className="flex min-h-[280px] flex-col items-center justify-center rounded-2xl border border-neutral-200 bg-white p-8 text-center shadow-card">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-neutral-950 text-white">
            <Spinner size={20} className="animate-spin" />
          </span>
          <p className="mt-5 font-display text-xl font-semibold text-neutral-950">
            Turning your note into questions
          </p>
          <p className="mt-2 max-w-sm text-sm text-neutral-500">
            This usually takes a few seconds. You can leave this page — the questions will be waiting in
            Recall.
          </p>
          <div className="mt-5 h-1.5 w-48 overflow-hidden rounded-full bg-neutral-100">
            <div className="h-full w-1/2 animate-pulse rounded-full bg-neutral-950" />
          </div>
        </div>
      ) : suggestions.length === 0 ? (
        <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-white py-14 text-center shadow-card">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-neutral-100 text-neutral-500">
            <CheckCircle size={20} weight="bold" />
          </span>
          <p className="mt-5 font-display text-xl font-semibold text-neutral-950">
            {noteFailed
              ? "Question generation failed"
              : notePollExpired
                ? "Still generating questions"
                : "Nothing left to verify"}
          </p>
          <p className="mt-2 max-w-sm text-sm text-neutral-500">
            {noteFailed
              ? "Your note was saved, but recall questions couldn't be generated. Try toggling recall again from the note."
              : notePollExpired
                ? "Your note is still being processed. Questions will appear in Recall when they're ready."
                : "All caught up. New questions from recall-enabled notes will appear here."}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            {notePollExpired ? (
              <button
                type="button"
                onClick={handleRetryNote}
                className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl border border-neutral-200 px-4 text-sm font-semibold text-neutral-700 hover:bg-neutral-100"
              >
                <ArrowClockwise size={14} />
                Check again
              </button>
            ) : null}
            <Link
              to="/app/recall"
              className="inline-flex h-10 items-center justify-center rounded-xl border border-neutral-200 px-4 text-sm font-semibold text-neutral-700 hover:bg-neutral-100"
            >
              Back to decks
            </Link>
            <Link
              to="/app/notes"
              className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-neutral-950 px-4 text-sm font-semibold text-white hover:bg-neutral-800"
            >
              <NotePencil size={15} />
              Write a note
            </Link>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="space-y-3 rounded-2xl border border-neutral-200 bg-white p-4 shadow-card">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-neutral-700">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={(event) => handleSelectAll(event.target.checked)}
                    className="h-4 w-4 rounded border-neutral-300 text-neutral-950 focus:ring-neutral-950"
                  />
                  Select all
                </label>
                <p className="mt-1 max-w-md text-xs leading-relaxed text-neutral-500">
                  Tick the cards you want to keep. You can finish without reviewing every card.
                </p>
              </div>
              <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold text-neutral-600">
                {selectedIds.size} selected
              </span>
            </div>

            {selectionWarning ? (
              <p
                role="alert"
                className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800"
              >
                {selectionWarning}
              </p>
            ) : null}

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-neutral-100 pt-3">
              <DeckPicker
                decks={decks}
                value={bulkDeckId}
                onChange={setBulkDeckId}
                onCreate={() => setFormOpen(true)}
                disabled={bulkAssigning}
                label="Move selected to"
              />
              <Button
                size="sm"
                variant="outline"
                disabled={selectedIds.size === 0 || !bulkDeckId || bulkAssigning}
                onClick={() => void handleBulkAssign()}
              >
                {bulkAssigning ? "Assigning…" : "Assign deck"}
              </Button>
            </div>

            <div className="flex flex-col gap-3 border-t border-neutral-100 pt-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs leading-relaxed text-neutral-500">
                {selectedIds.size === 0
                  ? "No recall card selected. Finishing will discard all remaining cards."
                  : `Keeps ${selectedIds.size} selected and discards ${
                      suggestions.length - selectedIds.size
                    } unselected.`}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={selectedIds.size === 0 || bulkAccepting || finishing}
                  onClick={() => void handleBulkAccept()}
                >
                  {bulkAccepting ? "Adding…" : `Add selected (${selectedIds.size})`}
                </Button>
                <Button
                  size="sm"
                  disabled={bulkAccepting || bulkAssigning || finishing}
                  onClick={() => void handleFinishReview()}
                >
                  {finishing ? "Finishing…" : "Finish review"}
                </Button>
              </div>
            </div>
          </div>

          {suggestions.map((suggestion) => (
            <SuggestionCard
              key={suggestion.candidate_id}
              suggestion={suggestion}
              decks={decks}
              deckValue={suggestion.deck_id ?? fallbackDeckId}
              deckSaving={deckSavingId === suggestion.candidate_id}
              selected={selectedIds.has(suggestion.candidate_id)}
              processing={
                processingSuggestionId === suggestion.candidate_id ? processingAction : null
              }
              onSelect={(selected) => handleSelect(suggestion.candidate_id, selected)}
              onAccept={() => void handleAccept(suggestion)}
              onReject={() => void handleReject(suggestion)}
              onSave={(question, answer) => handleSave(suggestion, question, answer)}
              onDeckChange={(deckId) => void handleDeckChange(suggestion, deckId)}
              onCreateDeck={() => setFormOpen(true)}
              onRevealAnswer={() => handleRevealAnswer(suggestion)}
            />
          ))}

          <button
            type="button"
            onClick={() => void loadSuggestions()}
            className="inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium text-neutral-500 transition-colors hover:text-neutral-950"
          >
            <ArrowClockwise size={14} />
            Refresh questions
          </button>
        </div>
      )}

      {undoNotice ? (
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="fixed inset-x-4 bottom-4 z-50 mx-auto flex max-w-lg items-center justify-between gap-4 rounded-xl bg-neutral-950 px-4 py-3 text-sm text-white shadow-soft"
        >
          <span className="min-w-0">{undoNotice.message}</span>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => void handleUndo()}
              disabled={undoBusy}
              className="inline-flex h-8 items-center justify-center rounded-lg px-2 text-sm font-semibold text-white underline-offset-2 hover:underline disabled:cursor-wait disabled:opacity-60"
            >
              {undoBusy ? "Restoring…" : "Undo"}
            </button>
            <button
              type="button"
              onClick={() => setUndoNotice(null)}
              aria-label="Dismiss undo message"
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-neutral-400 hover:bg-white/10 hover:text-white"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      ) : null}

      <DeckFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={(deck) => void handleDeckCreated(deck)}
      />
    </div>
  );
}
