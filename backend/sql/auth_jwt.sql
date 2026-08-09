-- JWT auth schema (safe for existing users table)
-- Run in Supabase SQL editor.

create extension if not exists pgcrypto;

create table if not exists users (
  user_id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table users
  add column if not exists password_hash text,
  add column if not exists is_active boolean not null default true,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

-- Backfill existing rows if the column was added on a populated table.
update users
set password_hash = coalesce(password_hash, '')
where password_hash is null;

create unique index if not exists idx_users_email_unique
  on users (lower(email));

create table if not exists refresh_tokens (
  token_id uuid primary key default gen_random_uuid(),
  jti uuid not null unique,
  user_id uuid not null references users(user_id) on delete cascade,
  token_hash text not null,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  user_agent text,
  ip_address text
);

create index if not exists idx_refresh_tokens_user_id
  on refresh_tokens(user_id);

create index if not exists idx_refresh_tokens_expires_at
  on refresh_tokens(expires_at);
