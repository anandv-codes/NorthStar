import { CSSProperties, ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  style?: CSSProperties;
}

export function Card({ children, style }: CardProps) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #e5e0d8",
        borderRadius: 16,
        padding: 16,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

interface SectionTitleProps {
  children: ReactNode;
  hint?: string;
  action?: ReactNode;
}

export function SectionTitle({ children, hint, action }: SectionTitleProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        justifyContent: "space-between",
        gap: 12,
        marginBottom: 8,
      }}
    >
      <div>
        <span style={{ fontWeight: 700 }}>{children}</span>
        {hint ? (
          <span style={{ marginLeft: 8, fontSize: 12, color: "#666" }}>
            {hint}
          </span>
        ) : null}
      </div>
      {action}
    </div>
  );
}
