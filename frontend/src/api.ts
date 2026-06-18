const BASE_URL = "http://localhost:8000";

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
  insights?: string[];
}

export async function createNote(payload: CreateNotePayload) {
  console.debug("[API] Submitting note for user:", payload.user_id);
  const response = await fetch(`${BASE_URL}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Failed to create note");
  }

  const result = response.json();
  console.debug("[API] Note created:", result);
  return result;
}

export async function getNoteStatus(user_id: string, note_id: string) {
  console.debug("[API] Polling note status:", note_id);
  const response = await fetch(
    `${BASE_URL}/notes/${note_id}?user_id=${encodeURIComponent(user_id)}`,
  );
  if (!response.ok) {
    throw new Error("Failed to load note status");
  }
  return response.json() as Promise<NoteStatus>;
}
