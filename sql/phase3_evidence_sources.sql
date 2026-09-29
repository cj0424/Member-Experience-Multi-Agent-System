-- Phase 3: multi-source evidence
-- Adds three new tables. Does not change or delete any existing table.
-- Safe to run more than once.

-- 1. Every piece of evidence Insights can use, from any source.
--    Club sources (survey, incident, staff) are stored in full.
--    Google reviews are stored as a reference only (id + date, body left empty),
--    because Google's terms don't allow storing review content.
create table if not exists public.evidence_items (
  id            text primary key,                -- ENC-001, INC-001, OBS-001, REV-001
  source        text not null
                check (source in ('survey', 'incident', 'staff', 'google')),
  event_date    date not null,                   -- the day it happened / was published
  period_start  date not null,                   -- Monday of the week it was read in
  author_role   text,                            -- Recepción, Entrenador, Mantenimiento
  area          text,                            -- Vestuarios, Pistas, Reservas... (incident log)
  body          text,                            -- full text; NULL for google
  created_at    timestamptz not null default now(),
  constraint google_body_not_stored check (source <> 'google' or body is null)
);

-- When Gemini tagged the entry (NULL = not tagged yet). Added separately so it
-- also works if you already ran an earlier version of this file.
alter table public.evidence_items add column if not exists tagged_at timestamptz;

create index if not exists evidence_items_event_date_idx
  on public.evidence_items (event_date);

-- 2. Topic tags per entry: our own analysis, one row per topic and direction.
create table if not exists public.evidence_tags (
  evidence_id  text not null references public.evidence_items (id) on delete cascade,
  topic        text not null,                    -- see evidence/rules.py TOPICS
  polarity     text not null check (polarity in ('queja', 'elogio')),
  safety       boolean not null default false,
  detail       text,                             -- e.g. 'pista 12'
  model        text,                             -- Gemini model used
  tagged_at    timestamptz not null default now(),
  primary key (evidence_id, topic, polarity)
);

-- 3. One row per source per run: what was read, what was new, and any error.
--    The latest successful Google run gives the "last run" date used to spot new reviews.
create table if not exists public.source_runs (
  id             bigint generated always as identity primary key,
  source         text not null
                 check (source in ('survey', 'incident', 'staff', 'google')),
  run_at         timestamptz not null default now(),
  period_start   date not null,
  period_end     date not null,
  items_read     integer not null default 0,
  items_new      integer not null default 0,
  status         text not null check (status in ('ok', 'empty', 'error')),
  error_message  text
);

create index if not exists source_runs_source_run_at_idx
  on public.source_runs (source, run_at desc);
