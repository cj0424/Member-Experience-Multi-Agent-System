-- Phase 3: detected patterns wait here for their recommendation.
-- "Ejecutar análisis" saves each new pattern as 'pending'; the owner generates
-- and reviews its recommendation one at a time ("Generar recomendación →").
-- Because they're stored here, nothing is lost if the app restarts.
-- Adds one table. Does not change or delete anything. Safe to run more than once.

create table if not exists public.pending_recommendations (
  id               bigint generated always as identity primary key,
  kind             text not null check (kind in ('nuevo', 'reaparece')),
  pattern_id       bigint,                 -- the existing pattern, for 'reaparece'
  name             text not null,
  description      text not null,          -- the Insights pattern block (evidence, priority…)
  topic            text,                   -- evidence/rules.py topic, used to avoid duplicates
  meta             jsonb,                  -- priority, confidence, evidence_ids, detected_period_end
  previous_action  text,                   -- for 'reaparece'
  rejected_ideas   text,                   -- for 'reaparece'
  insights_run_id  bigint,
  status           text not null default 'pending'
                   check (status in ('pending', 'approved', 'discarded')),
  created_at       timestamptz not null default now(),
  decided_at       timestamptz
);

create index if not exists pending_recommendations_status_idx
  on public.pending_recommendations (status);
