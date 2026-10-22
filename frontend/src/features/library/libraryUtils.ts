const DAY_MS = 24 * 60 * 60 * 1000;

export function formatLibraryDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  if (day === today) {
    return `Today, ${date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
  }
  if (day === today - DAY_MS) {
    return `Yesterday, ${date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
  }
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function noteTitle(rawText: string, summary?: string | null): string {
  const firstLine = rawText.split(/\r?\n/).find((line) => line.trim());
  const candidate = (firstLine || summary || "Untitled note").trim();
  return candidate.length > 90 ? `${candidate.slice(0, 87)}…` : candidate;
}

export function excerpt(text: string, max = 150): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  return normalized.length > max ? `${normalized.slice(0, max - 1)}…` : normalized;
}
