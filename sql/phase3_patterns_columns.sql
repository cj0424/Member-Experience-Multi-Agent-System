-- Phase 3: extra fields on each pattern.
-- Adds columns only. Nothing is changed or deleted. Safe to run more than once.

alter table public.patterns add column if not exists topic               text;     -- evidence/rules.py TOPICS
alter table public.patterns add column if not exists priority            text;     -- Alta / Media / Baja
alter table public.patterns add column if not exists priority_score      integer;  -- 5-15
alter table public.patterns add column if not exists confidence          text;     -- Alta / Moderada
alter table public.patterns add column if not exists evidence_ids        text;     -- e.g. 'OBS-002, REV-005'
alter table public.patterns add column if not exists detected_period_end date;     -- last day of the week it was detected

create index if not exists patterns_topic_idx on public.patterns (topic);
