-- Phase 3: start the realistic run from week 1.
-- Run ONLY after checking that archive_phase2 has a copy of every table
-- (Step 1b earlier). This empties the working tables; archive_phase2 keeps
-- the Phase 2 data.

-- 1. Move the old Phase 1 archive tables out of "public", so the app can't see them
create schema if not exists archive_phase1;
alter table if exists public.patterns_archive_phase1        set schema archive_phase1;
alter table if exists public.pattern_history_archive_phase1 set schema archive_phase1;

-- 2. Empty the working tables and restart their id counters at 1
truncate table
  public.pattern_history,
  public.insights_runs,
  public.patterns,
  public.evidence_tags,
  public.evidence_items,
  public.source_runs
restart identity cascade;
