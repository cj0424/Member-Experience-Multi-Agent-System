-- Phase 3: the weekly summaries written by scripts/weekly_run.py.
-- Adds one table. Safe to run more than once.

create table if not exists public.notifications (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  week_label  text,                 -- the week analysed, if any
  channel     text,                 -- whatsapp | none
  body        text,
  status      text check (status in ('sent', 'not_sent', 'error')),
  error       text
);
