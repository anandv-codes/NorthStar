import { useIsMobile } from "./useIsMobile";

export type NavRoute = "today" | "review" | "notes" | "ask" | "capture";

interface AppNavProps {
  active: NavRoute;
  onLogout: () => void;
  subtitle?: string;
}

const LINKS: { route: NavRoute; hash: string; label: string }[] = [
  { route: "today", hash: "#/today", label: "Today" },
  { route: "review", hash: "#/review", label: "Review" },
  { route: "notes", hash: "#/notes", label: "Notes" },
  { route: "ask", hash: "#/ask", label: "Ask" },
];

export function AppNav({ active, onLogout, subtitle }: AppNavProps) {
  const isMobile = useIsMobile();

  const linkStyle = (route: NavRoute) => ({
    padding: "6px 10px",
    borderRadius: 8,
    textDecoration: "none",
    color: route === active ? "#fff" : "#111",
    background: route === active ? "#111" : "transparent",
    whiteSpace: "nowrap" as const,
  });

  return (
    <header
      style={{
        background: "#fff",
        borderBottom: "1px solid #e5e0d8",
        padding: isMobile ? "12px 16px" : "16px 20px",
      }}
    >
      <div
        style={{
          maxWidth: 900,
          margin: "0 auto",
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          alignItems: isMobile ? "stretch" : "center",
          justifyContent: "space-between",
          gap: isMobile ? 8 : 16,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
          }}
        >
          <a
            href="#/today"
            style={{ fontWeight: 700, color: "#111", textDecoration: "none" }}
          >
            NorthStar
          </a>
          <button onClick={onLogout}>Log out</button>
        </div>

        <nav
          style={{
            display: "flex",
            gap: 4,
            alignItems: "center",
            overflowX: isMobile ? "auto" : "visible",
          }}
        >
          {LINKS.map((link) => (
            <a key={link.route} href={link.hash} style={linkStyle(link.route)}>
              {link.label}
            </a>
          ))}
          <a
            href="#/capture"
            style={{
              marginLeft: 8,
              padding: "6px 12px",
              borderRadius: 8,
              textDecoration: "none",
              color: "#fff",
              background: "#111",
              whiteSpace: "nowrap",
            }}
          >
            + Capture
          </a>
        </nav>
      </div>
      {subtitle ? (
        <div
          style={{
            maxWidth: 900,
            margin: "6px auto 0",
            fontSize: 12,
            color: "#666",
          }}
        >
          {subtitle}
        </div>
      ) : null}
    </header>
  );
}
