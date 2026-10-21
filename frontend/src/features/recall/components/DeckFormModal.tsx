import { useEffect, useState } from "react";
import { Spinner } from "@phosphor-icons/react";
import {
  createRecallDeck,
  updateRecallDeck,
  type RecallDeck,
  type RecallDeckColor,
} from "../../../shared/api/httpClient";
import { Button } from "../../../shared/ui/Button";
import { Modal } from "../../../shared/ui/Modal";
import { DECK_COLOR_OPTIONS, DECK_COLOR_STYLES } from "../deckColors";

interface DeckFormModalProps {
  open: boolean;
  deck?: RecallDeck | null;
  onClose: () => void;
  onSaved: (deck: RecallDeck) => void;
}

export function DeckFormModal({ open, deck, onClose, onSaved }: DeckFormModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState<RecallDeckColor>("neutral");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(deck?.name ?? "");
    setDescription(deck?.description ?? "");
    setColor(deck?.color ?? "neutral");
    setError(null);
    setSaving(false);
  }, [open, deck]);

  const handleSave = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Give your deck a name.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: trimmed,
        description: description.trim() || null,
        color,
      };
      const saved = deck
        ? await updateRecallDeck(deck.deck_id, payload)
        : await createRecallDeck(payload);
      onSaved(saved);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save this deck.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={deck ? "Edit deck" : "New deck"}>
      <div className="space-y-4">
        <div>
          <label htmlFor="deck-name" className="text-xs font-semibold text-neutral-600">
            Name
          </label>
          <input
            id="deck-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={60}
            placeholder="e.g. AWS, Algorithms, Design systems"
            className="mt-1 w-full rounded-xl border border-neutral-200 px-3 py-2.5 text-sm text-neutral-900 focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-200"
          />
        </div>

        <div>
          <label htmlFor="deck-description" className="text-xs font-semibold text-neutral-600">
            Description <span className="font-normal text-neutral-400">(optional)</span>
          </label>
          <textarea
            id="deck-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={2}
            maxLength={240}
            placeholder="What belongs in this deck?"
            className="mt-1 w-full resize-none rounded-xl border border-neutral-200 px-3 py-2.5 text-sm text-neutral-900 focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-200"
          />
        </div>

        <fieldset>
          <legend className="text-xs font-semibold text-neutral-600">Colour</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {DECK_COLOR_OPTIONS.map((option) => (
              <button
                key={option}
                type="button"
                aria-label={`Use ${option} colour`}
                aria-pressed={color === option}
                onClick={() => setColor(option)}
                className={`inline-flex h-9 w-9 items-center justify-center rounded-full border-2 transition-colors ${
                  color === option ? "border-neutral-950" : "border-transparent hover:border-neutral-300"
                }`}
              >
                <span className={`h-5 w-5 rounded-full ${DECK_COLOR_STYLES[option].dot}`} />
              </button>
            ))}
          </div>
        </fieldset>

        {error ? (
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button size="sm" onClick={() => void handleSave()} disabled={saving || !name.trim()}>
            {saving ? <Spinner size={14} className="animate-spin" /> : null}
            {deck ? "Save deck" : "Create deck"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
