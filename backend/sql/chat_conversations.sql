-- Chat interface storage for threaded conversations.
-- Run in the Supabase SQL editor.

create table if not exists chat_threads (
  thread_id uuid primary key,
  user_id text not null,
  title text,
  summary text,
  summary_updated_at timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists chat_messages (
  message_id uuid primary key,
  thread_id uuid not null references chat_threads(thread_id) on delete cascade,
  user_id text not null,
  role text not null,
  content text not null,
  intent text,
  metadata jsonb,
  created_at timestamptz not null,
  constraint chat_messages_role_check check (role in ('user', 'assistant', 'system'))
);

create index if not exists idx_chat_threads_user_updated_at
  on chat_threads(user_id, updated_at desc);

create index if not exists idx_chat_messages_thread_created_at
  on chat_messages(thread_id, created_at asc);

create index if not exists idx_chat_messages_user_created_at
  on chat_messages(user_id, created_at desc);

-- Tool actions the assistant has proposed (create/complete a task, etc.) and
-- is waiting on explicit user confirmation for before touching work-memory data.
create table if not exists pending_chat_actions (
  pending_action_id uuid primary key,
  user_id text not null,
  thread_id uuid not null references chat_threads(thread_id) on delete cascade,
  tool_name text not null,
  tool_args jsonb not null default '{}'::jsonb,
  description text not null,
  confirmed_message text not null,
  status text not null default 'pending',
  created_at timestamptz not null,
  resolved_at timestamptz,
  expires_at timestamptz not null,
  constraint pending_chat_actions_status_check
    check (status in ('pending', 'confirmed', 'cancelled', 'expired'))
);

create index if not exists idx_pending_chat_actions_thread_status
  on pending_chat_actions(thread_id, status);

