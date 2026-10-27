import { useCallback, useEffect, useRef, useState } from "react";

const ERROR_MESSAGES: Record<string, string> = {
  "not-allowed": "Microphone access was blocked. Allow it in your browser settings and try again.",
  "service-not-allowed": "Voice input is blocked by the browser on this device.",
  "audio-capture": "No microphone was found. Check that one is connected and available.",
  "no-speech": "Didn't catch that — try speaking again.",
  network: "Your browser's speech recognition service couldn't be reached. Check your connection or try Chrome or Edge.",
  "language-not-supported": "Voice input isn't available for this language.",
};

const BRAVE_NETWORK_ERROR =
  "Brave doesn't provide speech recognition, so voice input can't work here. Open NorthStar in Chrome or Edge, or type instead.";

function isBraveBrowser(): boolean {
  return (
    typeof navigator !== "undefined" &&
    Boolean((navigator as Navigator & { brave?: unknown }).brave)
  );
}

function speechErrorMessage(error: string): string {
  if (error === "network" && isBraveBrowser()) {
    return BRAVE_NETWORK_ERROR;
  }
  return ERROR_MESSAGES[error] ?? "Voice input hit a problem. Please try again.";
}

function getRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

export interface SpeechDictation {
  supported: boolean;
  starting: boolean;
  listening: boolean;
  interim: string;
  error: string | null;
  toggle: () => void;
  /** Flush the last phrase and stop (use when the user stops dictating). */
  stop: () => void;
  /** Discard any pending phrase and stop (use when submitting the note). */
  cancel: () => void;
}

interface UseSpeechDictationOptions {
  /** Receives each finalized phrase; append it to the note text. */
  onFinal: (chunk: string) => void;
}

/**
 * Browser speech-to-text for note dictation. Runs entirely client-side, so no
 * audio is sent to NorthStar; spoken text is placed in the note editor for the
 * user to review and edit before saving.
 */
export function useSpeechDictation({ onFinal }: UseSpeechDictationOptions): SpeechDictation {
  const [supported, setSupported] = useState(
    () => Boolean(getRecognitionConstructor()) && (typeof window === "undefined" || window.isSecureContext),
  );
  const [listening, setListening] = useState(false);
  const [starting, setStarting] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  useEffect(() => {
    return () => {
      const recognition = recognitionRef.current;
      recognitionRef.current = null;
      recognition?.abort();
    };
  }, []);

  const stop = useCallback(() => {
    // Flush the last phrase; `onend` flips `listening` once the browser has
    // delivered the final result, so the note can't be saved mid-transcript.
    recognitionRef.current?.stop();
  }, []);

  const cancel = useCallback(() => {
    const recognition = recognitionRef.current;
    recognitionRef.current = null;
    setStarting(false);
    setListening(false);
    setInterim("");
    recognition?.abort();
  }, []);

  const start = useCallback(() => {
    const Recognition = getRecognitionConstructor();
    if (!Recognition || !window.isSecureContext) {
      setSupported(false);
      setError("Voice input needs HTTPS (or localhost) and a supported browser.");
      return;
    }

    const previous = recognitionRef.current;
    recognitionRef.current = null;
    previous?.abort();
    setStarting(true);
    setError(null);

    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.lang = navigator.language || "en-US";

    // Ignore callbacks from a recognition session that was aborted/replaced.
    const isCurrent = () => recognitionRef.current === recognition;

    recognition.onstart = () => {
      if (!isCurrent()) {
        return;
      }
      setStarting(false);
      setListening(true);
      setError(null);
    };

    recognition.onresult = (event) => {
      if (!isCurrent()) {
        return;
      }
      let pending = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const phrase = result[0]?.transcript ?? "";
        if (result.isFinal) {
          const finalPhrase = phrase.trim();
          if (finalPhrase) {
            onFinalRef.current(finalPhrase);
          }
        } else {
          pending += phrase;
        }
      }
      setInterim(pending.trim());
    };

    recognition.onerror = (event) => {
      if (!isCurrent()) {
        return;
      }
      if (event.error === "aborted") {
        setStarting(false);
        return;
      }
      setStarting(false);
      setError(speechErrorMessage(event.error));
      setListening(false);
      setInterim("");
    };

    recognition.onend = () => {
      if (!isCurrent()) {
        return;
      }
      recognitionRef.current = null;
      setStarting(false);
      setListening(false);
      setInterim("");
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setStarting(false);
      setListening(false);
      setError("Voice input couldn't start. Please try again.");
    }
  }, []);

  const toggle = useCallback(() => {
    if (starting) {
      return;
    }
    if (listening) {
      stop();
    } else {
      start();
    }
  }, [starting, listening, start, stop]);

  return { supported, starting, listening, interim, error, toggle, stop, cancel };
}

/** Append a spoken phrase to existing note text without doubling separators. */
export function appendTranscript(current: string, chunk: string): string {
  const addition = chunk.trim();
  if (!addition) {
    return current;
  }
  if (!current) {
    return addition;
  }
  return /\s$/.test(current) ? `${current}${addition}` : `${current} ${addition}`;
}
