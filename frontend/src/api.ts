const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface CreateNotePayload {
  user_id: string;
  text: string;
}

export interface NoteStatus {
  note_id: string;
  user_id: string;
  status: string;
  created_at: string;
  raw_text: string;
  enriched_summary?: string;
  action_items?: string[];
  questions?: string[];
}

export async function createNote(payload: CreateNotePayload) {
  const response = await fetch(`${BASE_URL}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Failed to create note");
  }

  return response.json();
}

export async function getNoteStatus(user_id: string, note_id: string) {
  const response = await fetch(
    `${BASE_URL}/notes/${note_id}?user_id=${encodeURIComponent(user_id)}`,
  );
  if (!response.ok) {
    throw new Error("Failed to load note status");
  }
  return response.json() as Promise<NoteStatus>;
}
