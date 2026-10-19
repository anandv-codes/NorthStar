import { ReactNode } from "react";

export function Loading({ label = "Loading..." }: { label?: string }) {
  return <div style={{ color: "#666", padding: "8px 0" }}>{label}</div>;
}

interface EmptyStateProps {
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ message, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div style={{ color: "#777", padding: "8px 0" }}>
      <span>{message}</span>
      {actionLabel && onAction ? (
        <button onClick={onAction} style={{ marginLeft: 8 }}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

interface ErrorLineProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorLine({ message, onRetry }: ErrorLineProps) {
  return (
    <div style={{ color: "#b00020", padding: "8px 0" }}>
      <span>{message}</span>
      {onRetry ? (
        <button onClick={onRetry} style={{ marginLeft: 8 }}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function PageShell({ children }: { children: ReactNode }) {
  return (
    <div style={{ padding: 16, maxWidth: 900, margin: "0 auto" }}>{children}</div>
  );
}
