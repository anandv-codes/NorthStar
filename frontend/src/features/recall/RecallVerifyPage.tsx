import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowClockwise,
  ArrowLeft,
  CheckCircle,
  NotePencil,
  Spinner,
  Stack,
} from "@phosphor-icons/react";
import {
  acceptSuggestion,
  acceptSuggestions,
  assignCandidateDecks,
  fetchRecallDecks,
  fetchSuggestions,
  getNoteStatus,
  rejectSuggestion,
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
const TERMINAL_NOTE_STATUSES = new Set(["completed", "enriched", "failed"]);

export function RecallVerifyPage() {
  const [searchParams] = useSearchParams();
  const noteId = searchParams.get("note");

  const [decks, setDecks] = useState<RecallDeck[]>([]);
  const [preferredDeckId, setPreferredDeckId] = useState("");
  const [suggestions, setSuggestions] = useState<RecallSuggestion[]>([]);
  const [note, setNote] = useState<NoteStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingSuggestionId, setProcessingSuggestionId] = useState<string | null>(null);
  const [processingAction, setProcessingAction] = useState<"accept" | "reject" | "save" | null>(null);
  const [deckSavingId, setDeckSavingId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeckId, setBulkDeckId] = useState("");
  const [bulkAssigning, setBulkAssigning] = useState(false);
  const [bulkAccepting, setBulkAccepting] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadSuggestions = useCallback(async () => {
    const list = await fetchSuggestions(200, noteId);
    setSuggestions(list.suggestions);
    const liveIds = new Set(list.suggestions.map((item) => item.candidate_id));
    setSelectedIds((current) => new Set(Array.from(current).filter((id) => liveIds.has(id))));
    return list.suggestions;
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

    const poll = async () => {
      try {
        const status = await getNoteStatus(noteId);
        if (cancelled) return;
        setNote(status);
        const generated = await loadSuggestions();
        if (cancelled) return;
        const done =
          TERMINAL_NOTE_STATUSES.has(status.status) &&
          status.recall_status !== "pending";
        if (!done && generated.length === 0) {
          pollTimer.current = setTimeout(() => void poll(), POLL_INTERVAL_MS);
        }
      } catch {
        // The note page also surfaces failures; stop polling quietly.
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (pollTimer.current) {
        clearTimeout(pollTimer.current);
        pollTimer.current = null;
      }
    };
  }, [noteId, loadSuggestions]);

  const fallbackDeckId = preferredDeckId || decks.find((deck) => deck.is_default)?.deck_id || "";

  const removeSuggestion = (candidateId: string) => {
    setSuggestions((current) => current.filter((item) => item.candidate_id !== candidateId));
    setSelectedIds((current) => {
      const next = new Set(current);
      next.delete(candidateId);
      return next;
    });
  };

  const handleAccept = async (suggestion: RecallSuggestion) => {
    setProcessingSuggestionId(suggestion.candidate_id);
    setProcessingAction("accept");
    try {
      await acceptSuggestion(suggestion.candidate_id);
      removeSuggestion(suggestion.candidate_id);
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
    if (candidateIds.length === 0) return;
    setBulkAccepting(true);
    setError(null);
    try {
      const result = await acceptSuggestions(candidateIds, bulkDeckId || null);
      const acceptedIds = new Set(
        result.results.filter((item) => item.status === "carded").map((item) => item.candidate_id),
      );
      setSuggestions((current) => current.filter((item) => !acceptedIds.has(item.candidate_id)));
      setSelectedIds((current) => {
        const next = new Set(current);
        acceptedIds.forEach((candidateId) => next.delete(candidateId));
        return next;
      });
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

  const noteProcessing =
    Boolean(noteId) &&
    (!note || (!TERMINAL_NOTE_STATUSES.has(note.status) || note.recall_status === "pending"));
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
              Check each question, reveal its answer, and file it into the right deck.
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
            {noteFailed ? "Question generation failed" : "Nothing left to verify"}
          </p>
          <p className="mt-2 max-w-sm text-sm text-neutral-500">
            {noteFailed
              ? "Your note was saved, but recall questions couldn't be generated. Try toggling recall again from the note."
              : "All caught up. New questions from recall-enabled notes will appear here."}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
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
          <div className="space-y-3 rounded-2xl border border-neutral-200 bg-white p-3 shadow-card">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-neutral-600">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(event) => handleSelectAll(event.target.checked)}
                  className="h-4 w-4 rounded border-neutral-300 text-neutral-950 focus:ring-neutral-950"
                />
                Select all
              </label>
              <Button size="sm" disabled={selectedIds.size === 0 || bulkAccepting} onClick={() => void handleBulkAccept()}>
                {bulkAccepting ? "Adding…" : `Add selected (${selectedIds.size})`}
              </Button>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-neutral-100 pt-3">
              <DeckPicker
                decks={decks}
                value={bulkDeckId}
                onChange={setBulkDeckId}
                onCreate={() => setFormOpen(true)}
                disabled={bulkAssigning}
                label="File selected under"
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

      <DeckFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={(deck) => void handleDeckCreated(deck)}
      />
    </div>
  );
}
