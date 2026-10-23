#!/usr/bin/env bash
# Apply NorthStar's idempotent SQL migrations in order.
#
#   export SUPABASE_DB_URL='postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres'
#   ./backend/scripts/apply_migrations.sh
#
# Use Supabase's direct/session connection string (port 5432), not the
# transaction pooler (port 6543), so DDL statements are supported.
set -euo pipefail

: "${SUPABASE_DB_URL:?Set SUPABASE_DB_URL to the Supabase Postgres connection string}"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql not found. Install the PostgreSQL client, or run the files in the Supabase SQL editor." >&2
  exit 1
fi

SQL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../sql" && pwd)"

FILES=(
  auth_jwt.sql
  chat_conversations.sql
  phase3_work_memory.sql
  phase4_recall.sql
  phase4_recall_scheduler.sql
  phase4_recall_decks.sql
  phase4_recall_accept.sql
  phase4_pgvector.sql
)

for file in "${FILES[@]}"; do
  echo "==> applying ${file}"
  psql "${SUPABASE_DB_URL}" -v ON_ERROR_STOP=1 -f "${SQL_DIR}/${file}"
done

echo "All migrations applied."
