import type { RecentNote } from "../../../shared/api/httpClient";
import { EmptyState } from "./TaskBoard";

function formatRelativeTime(isoDate: string): string {
  const diffMs = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function RecentMemoryFeed({ notes }: { notes: RecentNote[] }) {
  if (notes.length === 0) {
    return <EmptyState label="Capture your first note to see it show up here." />;
  }

  return (
    <ul className="space-y-4">
      {notes.map((note) => (
        <li key={note.note_id} className="border-l-2 border-neutral-200 pl-4">
          <p className="text-xs font-medium text-neutral-400">{formatRelativeTime(note.created_at)}</p>
          <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-neutral-700">
            {note.enriched_summary || note.raw_text}
          </p>
        </li>
      ))}
    </ul>
  );
}
