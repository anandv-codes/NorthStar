import clsx from "clsx";
import { Microphone, MicrophoneSlash } from "@phosphor-icons/react";

interface MicButtonProps {
  listening: boolean;
  starting?: boolean;
  supported: boolean;
  onToggle: () => void;
  className?: string;
}

/**
 * Toggle for browser speech-to-text. Dictation writes into the note editor so
 * the user can review and edit the transcript before saving.
 */
export function MicButton({ listening, starting = false, supported, onToggle, className }: MicButtonProps) {
  const label = !supported
    ? "Voice input isn't supported in this browser"
    : starting
      ? "Starting voice input…"
      : listening
        ? "Stop voice input"
        : "Start voice input";

  return (
    <button
      type="button"
      disabled={!supported}
      aria-pressed={listening}
      aria-busy={starting || undefined}
      aria-label={label}
      title={label}
      onClick={onToggle}
      className={clsx(
        "inline-flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:text-neutral-300",
        starting && "cursor-wait opacity-70",
        listening
          ? "bg-red-50 text-red-600 hover:bg-red-100"
          : "text-neutral-500 hover:bg-neutral-100 hover:text-neutral-950",
        className,
      )}
    >
      {listening ? (
        <MicrophoneSlash size={18} weight="bold" aria-hidden="true" />
      ) : (
        <Microphone size={18} aria-hidden="true" />
      )}
    </button>
  );
}

interface MicStatusProps {
  listening: boolean;
  starting?: boolean;
  interim: string;
  error: string | null;
  supported: boolean;
}

/** Live caption/error for dictation. Final text lives in the editor itself. */
export function MicStatus({ listening, starting = false, interim, error, supported }: MicStatusProps) {
  if (error) {
    return (
      <p role="alert" className="mt-2 text-xs text-red-600">
        {error}
      </p>
    );
  }
  if (starting) {
    return (
      <p role="status" className="mt-2 text-xs text-neutral-500">
        Waiting for microphone permission…
      </p>
    );
  }
  if (listening) {
    return (
      <div className="mt-2 space-y-1">
        <p role="status" className="text-xs text-neutral-500">
          Listening… speak, then review the text before saving.
        </p>
        {/* Interim words are visual only: announcing every partial result is
            noisy for screen readers. Final phrases land in the textarea. */}
        {interim ? (
          <p aria-hidden="true" className="text-xs italic text-neutral-500">
            {interim}
          </p>
        ) : null}
      </div>
    );
  }
  if (!supported) {
    return (
      <p className="mt-2 text-xs text-neutral-500">
        Voice input isn't available here. You can type instead.
      </p>
    );
  }
  return null;
}
