"""One-off backfill: chunk + embed existing notes into pgvector.

Run after applying ``backend/sql/phase4_pgvector.sql`` and deploying the code
that writes chunks for new notes:

    python -m backend.scripts.backfill_pgvector                 # all users
    python -m backend.scripts.backfill_pgvector --user-id USER  # one user
    python -m backend.scripts.backfill_pgvector --dry-run       # count only

Idempotent: re-running re-indexes each note's chunks (delete-then-insert).
"""
from __future__ import annotations

import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_pgvector")

PAGE_SIZE = 100


def _fetch_notes(user_id: str | None, batch_size: int = PAGE_SIZE):
    from backend.app.infrastructure.db.supabase_client import supabase

    offset = 0
    while True:
        query = supabase.table("notes").select("note_id,user_id,raw_text")
        if user_id:
            query = query.eq("user_id", user_id)
        response = query.order("created_at", desc=False).range(offset, offset + batch_size - 1).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return
        yield from rows
        offset += batch_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", default=None, help="Limit to a single user_id.")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N notes.")
    parser.add_argument("--dry-run", action="store_true", help="Only count notes that would be indexed.")
    args = parser.parse_args()

    from backend.app.infrastructure.vector.vectorstore import index_note

    indexed = 0
    chunks = 0
    for note in _fetch_notes(args.user_id):
        if args.limit is not None and indexed >= args.limit:
            break
        note_id = note.get("note_id")
        text = note.get("raw_text") or ""
        if not note_id or not text.strip():
            continue
        if args.dry_run:
            logger.info("would index note %s", note_id)
        else:
            written = index_note(
                user_id=note["user_id"],
                note_id=note_id,
                text=text,
            )
            chunks += written
            logger.info("indexed note %s (%d chunks)", note_id, written)
        indexed += 1

    logger.info("done: %d note(s), %d chunk(s) indexed", indexed, chunks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
