-- Phase 3: one row per Gemini call, written by agents/llm.py.
-- Time, token and cost tracking (Dashboard) and data for the eval set.
-- Adds one table. Safe to run more than once.

create table if not exists public.llm_calls (
  id             bigint generated always as identity primary key,
  created_at     timestamptz not null default now(),
  agent          text,              -- insights_tagging, insights_naming, action_planning, execution_kit, outcome_check, pala…
  model          text,
  duration_ms    integer,           -- total time, including retries
  input_tokens   integer,
  output_tokens  integer,
  cost_usd       numeric,           -- only if prices are set in .env
  attempts       integer,           -- 1 = first try; 2-3 = needed a retry
  status         text check (status in ('ok', 'error')),
  error          text
);

create index if not exists llm_calls_created_at_idx on public.llm_calls (created_at);
